import logging
from typing import List, Optional

import cloudscraper

from precios_uy.config import settings
from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class VtexScraperBase(ScraperBase):
    """
    Clase base para supermercados que utilizan la plataforma VTEX.
    Consume la API REST pública de catálogo (/api/catalog_system/pub/products/search).
    Reutilizable para Ta-Ta, El Dorado, y otras tiendas VTEX.
    """
    supermercado: str = "VTEX Store"
    base_url: str = ""

    def __init__(self, base_url: Optional[str] = None, supermercado: Optional[str] = None):
        super().__init__()
        if base_url:
            self.base_url = base_url.rstrip("/")
        if supermercado:
            self.supermercado = supermercado

    def _get_json(self, url: str) -> tuple[list, dict]:
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

    def scrapear(self) -> List[Producto]:
        productos = []
        api_endpoint = f"{self.base_url}/api/catalog_system/pub/products/search"
        page_size = 50

        logger.info("Iniciando scraping VTEX para %s (%s)", self.supermercado, self.base_url)

        try:
            # Obtener el total de productos a través del header 'resources'
            initial_url = f"{api_endpoint}?_from=0&_to=0"
            _, headers = self._get_json(initial_url)
            resources = headers.get("resources", "0-0/0")
            
            try:
                total = int(resources.split("/")[-1])
            except (ValueError, IndexError):
                total = 500  # Valor por defecto si no viene la cabecera
            
            logger.info("%s: Se encontraron aproximadamente %d productos en catálogo", self.supermercado, total)
        except Exception as e:
            logger.error("Error al obtener total de catálogo en %s: %s", self.supermercado, e)
            return productos

        for offset in range(0, total, page_size):
            to_idx = min(offset + page_size - 1, total - 1)
            url = f"{api_endpoint}?_from={offset}&_to={to_idx}"

            try:
                data, _ = self._get_json(url)
                if not data or not isinstance(data, list):
                    break

                for p in data:
                    try:
                        nombre = p.get("productName") or p.get("productTitle")
                        if not nombre:
                            continue

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
                        precio_anterior = float(precio_list) if (precio_list and float(precio_list) > float(precio)) else None

                        # Extraer categoría y marca
                        categories = p.get("categories", [])
                        categoria = categories[0].strip("/").split("/")[-1] if categories else None
                        marca = p.get("brand")

                        # Imagen
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
                    except Exception as item_err:
                        logger.debug("Error procesando ítem VTEX en %s: %s", self.supermercado, item_err)
                        continue
            except Exception as page_err:
                logger.warning("Error consultando página offset=%d en %s: %s", offset, self.supermercado, page_err)
                continue

        logger.info("%s: %d productos extraídos exitosamente de VTEX API", self.supermercado, len(productos))
        return productos
