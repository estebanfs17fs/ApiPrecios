from typing import List

import cloudscraper
from bs4 import BeautifulSoup

from precios_uy.config import settings
from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase


class DiscoScraper(ScraperBase):
    supermercado = "Disco"

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

    def scrapear(self) -> List[Producto]:
        productos = []
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

        for cat in categorias:
            url = f"https://www.disco.com.uy/products/category/{cat}"
            try:
                soup = self._get_soup(url)
                items = soup.select("div.product-item")

                for item in items:
                    try:
                        nombre_el = item.select_one(".desc-top h3 a")
                        precio_el = item.select_one(".product-prices .price .val")
                        precio_anterior_el = item.select_one(".product-prices .before .val")
                        img_el = item.select_one("figure img")
                        link_el = item.select_one(".desc-top h3 a")

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
                                "https://www.disco.com.uy" + link_el["href"]
                                if link_el and link_el.get("href")
                                else None
                            ),
                            url_imagen=img_el.get("src") if img_el else None,
                        )
                        productos.append(producto)
                    except Exception:
                        continue
            except Exception:
                continue

        return productos

    def _parse_precio(self, texto: str) -> float:
        texto = texto.replace("$", "").replace("UYU", "").replace(".", "").replace(",", ".").strip()
        return float(texto)
