import logging
from typing import List, Set

from precios_uy.config import settings
from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class DiscoScraper(ScraperBase):
    supermercado = "Disco"
    BASE_URL = "https://www.disco.com.uy"

    def scrapear(self, max_pages: int = 5) -> List[Producto]:
        productos = []
        vistas_urls: Set[str] = set()
        
        categorias = [
            "almacen/10",
            "bebidas/11",
            "perfumeria-y-limpieza/12",
            "frescos/13",
            "frescos/14",
            "mascotas/15",
            "electro/16",
            "tv-y-audio/17",
            "celulares/18",
            "tecnologia/19",
            "hogar/20",
            "ferreteria/21",
            "deporte/22",
            "juguetes/23",
            "bebe/24",
            "papeleria/25",
            "electrodomesticos/26",
            "muebles/27",
            "textil/28",
            "decoracion/29",
            "automotor/30",
        ]

        logger.info("Iniciando scraping por categorías y páginas en %s", self.supermercado)

        for cat in categorias:
            page = 1

            while page <= max_pages:
                url = f"{self.BASE_URL}/products/category/{cat}?page={page}"
                try:
                    soup = self._get_soup(url)
                    items = soup.select("div.product-item")

                    if not items:
                        break

                    nuevos_en_pagina = 0

                    for item in items:
                        try:
                            nombre_el = item.select_one(".desc-top h3 a, h3 a")
                            precio_el = item.select_one(".product-prices .price .val, .val")
                            img_el = item.select_one("figure img, img")
                            link_el = item.select_one(".desc-top h3 a, h3 a")

                            nombre = nombre_el.get_text(strip=True) if nombre_el else None
                            precio_text = precio_el.get_text(strip=True) if precio_el else None

                            if not nombre or not precio_text:
                                continue

                            prod_url = (
                                self.BASE_URL + link_el["href"]
                                if link_el and link_el.get("href")
                                else None
                            )

                            if prod_url and prod_url in vistas_urls:
                                continue
                            if prod_url:
                                vistas_urls.add(prod_url)

                            precio = self._parse_precio(precio_text)
                            cat_nombre = cat.split("/")[0].capitalize()

                            producto = Producto(
                                supermercado=self.supermercado,
                                nombre=nombre,
                                precio=precio,
                                categoria=cat_nombre,
                                url_producto=prod_url,
                                url_imagen=img_el.get("src") if img_el else None,
                            )
                            productos.append(producto)
                            nuevos_en_pagina += 1
                        except Exception:
                            continue

                    if nuevos_en_pagina == 0:
                        break

                    page += 1
                except Exception as e:
                    logger.debug("Error procesando %s página %d: %s", cat, page, e)
                    break

        logger.info("%s: %d productos únicos extraídos", self.supermercado, len(productos))
        return productos
