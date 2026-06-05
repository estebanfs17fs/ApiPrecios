from abc import ABC, abstractmethod
from typing import List

import cloudscraper
from bs4 import BeautifulSoup

from precios_uy.config import settings
from precios_uy.models import Producto


class ScraperBase(ABC):
    supermercado: str

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

    @abstractmethod
    def scrapear(self) -> List[Producto]:
        ...

    def _parse_precio(self, texto: str) -> float:
        texto = (
            texto.replace("$", "")
            .replace("UYU", "")
            .replace("U$S", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        return float(texto)
