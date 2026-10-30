import logging
import time
from typing import List, Optional, Set

import requests

from precios_uy.config import settings
from precios_uy.models import ProductoScrapeado
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


def parsear_producto_vtex(p: dict, supermercado: str) -> Optional[ProductoScrapeado]:
    """Convierte un producto de la API de búsqueda de VTEX. Devuelve None si no sirve."""
    try:
        nombre = p.get("productName") or p.get("productTitle")
        items = p.get("items") or []
        if not nombre or not items:
            return None
        main_item = items[0]
        sellers = main_item.get("sellers") or []
        if not sellers:
            return None
        offer = sellers[0].get("commertialOffer") or {}
        precio = offer.get("Price")
        if precio is None or float(precio) <= 0:
            return None

        precio_list = offer.get("ListPrice")
        has_disc = precio_list and float(precio_list) > float(precio)
        categories = p.get("categories") or []
        cat_first = categories[0] if categories else ""
        images = main_item.get("images") or []

        return ProductoScrapeado(
            supermercado=supermercado,
            nombre=nombre.strip(),
            precio=float(precio),
            precio_anterior=float(precio_list) if has_disc else None,
            categoria=cat_first.strip("/").split("/")[-1] if cat_first else None,
            marca=p.get("brand"),
            url_producto=p.get("link"),
            url_imagen=images[0].get("imageUrl") if images else None,
            ean=main_item.get("ean"),
            sku=main_item.get("itemId") or p.get("productId"),
        )
    except (TypeError, ValueError, AttributeError):
        return None


class VtexScraperBase(ScraperBase):
    """
    Clase base optimizada para supermercados en VTEX.
    Recorre las categorías principales para obtener el catálogo completo de forma rápida.
    """
    supermercado: str = "VTEX Store"
    base_url: str = ""
    # Canal de venta (`sc`). Algunas tiendas solo muestran el catálogo completo
    # en un canal en particular: sin él, Ta-Ta expone ~200 productos y con sc=4 ~31.000.
    canal_venta: Optional[int] = None

    def __init__(self, base_url: Optional[str] = None, supermercado: Optional[str] = None):
        super().__init__()
        if base_url:
            self.base_url = base_url.rstrip("/")
        if supermercado:
            self.supermercado = supermercado

    REINTENTOS = 3

    def _get_json(self, url: str) -> tuple[list | dict, dict]:
        # VTEX devuelve 500 de vez en cuando en páginas sueltas: se reintenta
        for intento in range(1, self.REINTENTOS + 1):
            try:
                resp = self._scraper.get(
                    url,
                    headers={
                        "User-Agent": settings.user_agent,
                        "Accept": "application/json",
                    },
                    timeout=settings.request_timeout,
                )
                if resp.status_code >= 500 and intento < self.REINTENTOS:
                    time.sleep(2 * intento)
                    continue
                resp.raise_for_status()
                return resp.json(), resp.headers
            except (requests.ConnectionError, requests.Timeout):
                if intento == self.REINTENTOS:
                    raise
                time.sleep(2 * intento)
        raise RuntimeError("sin respuesta")  # no se llega

    # VTEX no devuelve resultados más allá de _from=2500 en una misma búsqueda
    MAX_RESULTADOS_BUSQUEDA = 2500
    PAGE_SIZE = 50

    def _obtener_arbol_categorias(self) -> List[dict]:
        """Obtiene el árbol de categorías VTEX (3 niveles)."""
        tree_url = f"{self.base_url}/api/catalog_system/pub/category/tree/3"
        try:
            tree_data, _ = self._get_json(tree_url)
            if isinstance(tree_data, list):
                return tree_data
        except Exception as e:
            logger.warning(
                "No se pudo obtener árbol de categorías VTEX para %s: %s",
                self.supermercado,
                e,
            )
        return []

    def _url_busqueda(self, filtro: str, desde: int, hasta: int) -> str:
        params = [filtro] if filtro else []
        if self.canal_venta is not None:
            params.append(f"sc={self.canal_venta}")
        params.append(f"_from={desde}&_to={hasta}")
        return f"{self.base_url}/api/catalog_system/pub/products/search?{'&'.join(params)}"

    def _total_resultados(self, filtro: str) -> int:
        try:
            _, headers = self._get_json(self._url_busqueda(filtro, 0, 0))
            return int(headers.get("resources", "0-0/0").split("/")[-1])
        except Exception:
            return self.MAX_RESULTADOS_BUSQUEDA

    def _filtros_a_recorrer(self, categorias: List[dict], ruta: str = "") -> List[str]:
        """
        Devuelve los filtros `fq=C:/a/b/` a recorrer. Si una categoría tiene más
        productos de los que VTEX deja paginar, se baja a sus subcategorías para
        no perder productos.
        """
        filtros = []
        for c in categorias:
            cid = c.get("id")
            if not cid:
                continue
            filtro_ruta = f"{ruta}{cid}/"
            filtro = f"fq=C:/{filtro_ruta}"
            hijos = c.get("children") or []
            if hijos and self._total_resultados(filtro) > self.MAX_RESULTADOS_BUSQUEDA:
                filtros.extend(self._filtros_a_recorrer(hijos, filtro_ruta))
            else:
                filtros.append(filtro)
        return filtros

    def scrapear(self) -> List[ProductoScrapeado]:
        productos = []
        vistas_keys: Set[str] = set()
        page_size = self.PAGE_SIZE

        logger.info(
            "Iniciando scraping VTEX por categorías para %s (%s)",
            self.supermercado,
            self.base_url,
        )

        targets = self._filtros_a_recorrer(self._obtener_arbol_categorias()) or [""]

        for target in targets:
            inicio_lote = len(productos)
            cat_total = self._total_resultados(target)
            if cat_total <= 0:
                continue

            limite_offset = min(cat_total, self.MAX_RESULTADOS_BUSQUEDA)

            for offset in range(0, limite_offset, page_size):
                to_idx = min(offset + page_size - 1, limite_offset - 1)
                url = self._url_busqueda(target, offset, to_idx)

                try:
                    data, _ = self._get_json(url)
                    if not data or not isinstance(data, list):
                        break

                    for p in data:
                        pid = str(p.get("productId") or p.get("link") or p.get("productName"))
                        if pid in vistas_keys:
                            continue
                        producto = parsear_producto_vtex(p, self.supermercado)
                        if producto:
                            vistas_keys.add(pid)
                            productos.append(producto)
                except Exception as page_err:
                    logger.warning("%s: error en página VTEX (%s): %s",
                                   self.supermercado, url, page_err)
                    continue

            self._entregar_parcial(productos[inicio_lote:])

        logger.info("%s: %d productos únicos extraídos en total", self.supermercado, len(productos))
        return productos
