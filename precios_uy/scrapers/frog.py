import logging
from typing import List

from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class FrogScraper(ScraperBase):
    supermercado = "Frog"
    BASE_URL = "https://www.frog.com.uy"

    def scrapear(self) -> List[Producto]:
        productos = []
        logger.info("Iniciando scraping de %s (%s)", self.supermercado, self.BASE_URL)

        # Secciones y categorías navegables de Frog
        urls_secciones = [
            f"{self.BASE_URL}/Frog/",
            f"{self.BASE_URL}/",
        ]

        for url in urls_secciones:
            try:
                soup = self._get_soup(url)
                items = soup.select(".producto, .product-item, .card, div[class*='product']")

                for item in items:
                    try:
                        nombre_el = item.select_one(".nombre, .product-title, h3, h4, .title")
                        precio_el = item.select_one(".precio, .price, .product-price")
                        img_el = item.select_one("img")
                        link_el = item.select_one("a[href]")

                        nombre = nombre_el.get_text(strip=True) if nombre_el else None
                        precio_text = precio_el.get_text(strip=True) if precio_el else None

                        if not nombre or not precio_text:
                            continue

                        precio = self._parse_precio(precio_text)
                        url_prod = link_el["href"] if link_el else None
                        if url_prod and not url_prod.startswith("http"):
                            url_prod = self.BASE_URL + url_prod

                        url_img = img_el.get("src") if img_el else None
                        if url_img and not url_img.startswith("http"):
                            url_img = self.BASE_URL + url_img

                        producto = Producto(
                            supermercado=self.supermercado,
                            nombre=nombre,
                            precio=precio,
                            categoria="Conveniencia",
                            url_producto=url_prod,
                            url_imagen=url_img,
                        )
                        productos.append(producto)
                    except Exception as item_err:
                        logger.debug("Error procesando ítem Frog: %s", item_err)
                        continue
            except Exception as page_err:
                logger.warning("Error cargando página %s de Frog: %s", url, page_err)
                continue

        logger.info("%s: %d productos extraídos", self.supermercado, len(productos))
        return productos
