from typing import List

import cloudscraper

from precios_uy.config import settings
from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase


class TataScraper(ScraperBase):
    supermercado = "Ta-Ta"

    def __init__(self):
        self._scraper = cloudscraper.create_scraper()

    def _get_json(self, url: str) -> list:
        resp = self._scraper.get(
            url,
            headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
            timeout=settings.request_timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def scrapear(self) -> List[Producto]:
        productos = []
        base = "https://tatauy.vtexassets.com/api/catalog_system/pub/products/search/"
        page_size = 50

        try:
            resp = self._scraper.get(
                f"{base}?_from=0&_to=0",
                headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
                timeout=settings.request_timeout,
            )
            resources = resp.headers.get("resources", "0-0/0")
            total = int(resources.split("/")[-1])
        except Exception:
            return productos

        for offset in range(0, total, page_size):
            try:
                url = f"{base}?_from={offset}&_to={min(offset + page_size - 1, total - 1)}"
                data = self._get_json(url)

                for p in data:
                    try:
                        nombre = p.get("productName")
                        if not nombre:
                            continue

                        items = p.get("items", [])
                        if not items:
                            continue

                        sellers = items[0].get("sellers", [])
                        if not sellers:
                            continue

                        offer = sellers[0].get("commertialOffer", {})
                        precio = offer.get("Price")
                        if precio is None:
                            continue

                        producto = Producto(
                            supermercado=self.supermercado,
                            nombre=nombre,
                            precio=float(precio),
                            url_producto=p.get("link"),
                            url_imagen=(
                                items[0]["images"][0]["imageUrl"]
                                if items[0].get("images")
                                else None
                            ),
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
