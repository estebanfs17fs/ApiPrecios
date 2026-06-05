import logging
from typing import List

import cloudscraper
from bs4 import BeautifulSoup

from precios_uy.config import settings
from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class TiendaInglesaScraper(ScraperBase):
    supermercado = "Tienda Inglesa"
    BASE = "https://www.tiendainglesa.com.uy"

    def __init__(self):
        self._scraper = cloudscraper.create_scraper()

    def _get_soup(self, url: str) -> BeautifulSoup:
        resp = self._scraper.get(
            url,
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")

    def _extraer_productos(self, soup) -> List[Producto]:
        result = []
        items = soup.select("div.card-product-container")
        for item in items:
            try:
                nombre_el = item.select_one("span.card-product-name")
                precio_el = item.select_one(
                    "div.card-product-price div.card-product-price-containner span"
                )
                link_el = (
                    item.select_one("div.card-product-name-and-price a")
                    or item.select_one("div.card-product-container-img a")
                )
                img_el = item.select_one("img.card-product-img")

                nombre = nombre_el.get_text(strip=True) if nombre_el else None
                precio_text = precio_el.get_text(strip=True) if precio_el else None

                if not nombre or not precio_text:
                    continue

                precio = self._parse_precio(precio_text)
                producto = Producto(
                    supermercado=self.supermercado,
                    nombre=nombre,
                    precio=precio,
                    url_producto=(
                        self.BASE + link_el["href"]
                        if link_el and link_el.get("href")
                        else None
                    ),
                    url_imagen=(
                        img_el.get("data-src") or img_el.get("src")
                        if img_el
                        else None
                    ),
                )
                result.append(producto)
            except Exception:
                continue
        return result

    def _scrape_lista_html(self, path: str) -> List[Producto]:
        try:
            soup = self._get_soup(self.BASE + path)
            return self._extraer_productos(soup)
        except Exception:
            return []

    def _scrape_lista_api(self, name: str, list_id: int, max_pages: int = 1) -> List[Producto]:
        result = []
        for page in range(1, max_pages + 1):
            url = (
                f"{self.BASE}/supermercado/listas/{name}/busqueda"
                f"?{list_id},0,*%3A*%26,0,0,0,,,false,,,,{page}"
            )
            try:
                soup = self._get_soup(url)
                items = self._extraer_productos(soup)
                if not items:
                    break
                result.extend(items)
            except Exception:
                break
        return result

    def scrapear(self) -> List[Producto]:
        productos = []

        # Lists with pagination (API-based)
        productos.extend(self._scrape_lista_api("ofertas", 3716, max_pages=9))
        productos.extend(self._scrape_lista_api("ciberlunes", 17298, max_pages=9))
        productos.extend(self._scrape_lista_api("los-rompe-del-finde", 12658, max_pages=2))
        productos.extend(self._scrape_lista_api("preciazos-de-la-tienda", 16329, max_pages=1))

        # Lists without pagination (HTML-based)
        productos.extend(self._scrape_lista_html("/listas/rompe-precios-limpieza/17354"))

        logger.info("%s: %d productos extraídos", self.supermercado, len(productos))
        return productos
