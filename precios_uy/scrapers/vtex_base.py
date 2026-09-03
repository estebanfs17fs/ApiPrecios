import logging
from typing import List, Optional, Set

from precios_uy.config import settings
from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class VtexScraperBase(ScraperBase):
    """
    Clase base optimizada para supermercados en VTEX.
    Recorre las categorías principales para obtener el catálogo completo de forma rápida.
    """
    supermercado: str = "VTEX Store"
    base_url: str = ""

    def __init__(self, base_url: Optional[str] = None, supermercado: Optional[str] = None):
        super().__init__()
        if base_url:
            self.base_url = base_url.rstrip("/")
        if supermercado:
            self.supermercado = supermercado

    def _get_json(self, url: str) -> tuple[list | dict, dict]:
        resp = self._scraper.get(
            url,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "application/json",
            },
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        return resp.json(), resp.headers

    def _obtener_ids_categorias(self) -> List[tuple[int, str]]:
        """Obtiene las categorías principales del árbol VTEX."""
        tree_url = f"{self.base_url}/api/catalog_system/pub/category/tree/2"
        cat_list = []
        try:
            tree_data, _ = self._get_json(tree_url)
            if isinstance(tree_data, list):
                for c in tree_data:
                    cid = c.get("id")
                    cname = c.get("name", "")
                    if cid:
                        cat_list.append((cid, cname))
        except Exception as e:
            logger.warning(
                "No se pudo obtener árbol de categorías VTEX para %s: %s",
                self.supermercado,
                e,
            )
        return cat_list

    def scrapear(self, max_offset_per_category: int = 500) -> List[Producto]:
        productos = []
        vistas_keys: Set[str] = set()
        page_size = 50

        logger.info(
            "Iniciando scraping VTEX rápido por categorías para %s (%s)",
            self.supermercado,
            self.base_url,
        )

        cats = self._obtener_ids_categorias()
        targets = [f"fq=C:{cid}" for cid, _ in cats] if cats else [""]

        for target in targets:
            api_endpoint = f"{self.base_url}/api/catalog_system/pub/products/search"
            param_prefix = f"{target}&" if target else ""

            try:
                init_url = f"{api_endpoint}?{param_prefix}_from=0&_to=0"
                _, headers = self._get_json(init_url)
                resources = headers.get("resources", "0-0/0")
                cat_total = int(resources.split("/")[-1])
            except Exception:
                cat_total = 200

            if cat_total <= 0:
                continue

            limite_offset = min(cat_total, max_offset_per_category, 2450)

            for offset in range(0, limite_offset, page_size):
                to_idx = min(offset + page_size - 1, cat_total - 1)
                url = f"{api_endpoint}?{param_prefix}_from={offset}&_to={to_idx}"

                try:
                    data, _ = self._get_json(url)
                    if not data or not isinstance(data, list):
                        break

                    for p in data:
                        try:
                            nombre = p.get("productName") or p.get("productTitle")
                            if not nombre:
                                continue

                            pid = str(p.get("productId") or p.get("link") or nombre)
                            if pid in vistas_keys:
                                continue
                            vistas_keys.add(pid)

                            items = p.get("items", [])
                            if not items:
                                continue

                            main_item = items[0]
                            sellers = main_item.get("sellers", [])
                            if not sellers:
                                continue

                            offer = sellers[0].get("commertialOffer", {})
                            precio = offer.get("Price")
                            if precio is None or float(precio) <= 0:
                                continue

                            precio_list = offer.get("ListPrice")
                            has_disc = (
                                precio_list and float(precio_list) > float(precio)
                            )
                            precio_anterior = float(precio_list) if has_disc else None

                            categories = p.get("categories", [])
                            cat_first = categories[0] if categories else ""
                            categoria = (
                                cat_first.strip("/").split("/")[-1]
                                if cat_first
                                else None
                            )
                            marca = p.get("brand")

                            images = main_item.get("images", [])
                            url_imagen = images[0].get("imageUrl") if images else None

                            producto = Producto(
                                supermercado=self.supermercado,
                                nombre=nombre.strip(),
                                precio=float(precio),
                                precio_anterior=precio_anterior,
                                categoria=categoria,
                                marca=marca,
                                url_producto=p.get("link"),
                                url_imagen=url_imagen,
                            )
                            productos.append(producto)
                        except Exception:
                            continue
                except Exception as page_err:
                    logger.debug("Error en página VTEX (%s): %s", url, page_err)
                    continue

        logger.info("%s: %d productos únicos extraídos en total", self.supermercado, len(productos))
        return productos
