import re
from abc import ABC, abstractmethod
from typing import List

import cloudscraper
from bs4 import BeautifulSoup

from precios_uy.config import settings
from precios_uy.models import ProductoScrapeado

_RE_IMPORTE = re.compile(r"\d+(?:\.\d{3})*(?:,\d+)?")


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
    def scrapear(self) -> List[ProductoScrapeado]:
        ...

    def _parse_precio(self, texto: str) -> float:
        """Toma el primer importe del texto en formato uruguayo: '$ 1.234,56' -> 1234.56."""
        m = _RE_IMPORTE.search(texto or "")
        if not m:
            raise ValueError(f"Precio no reconocido: {texto!r}")
        return float(m.group(0).replace(".", "").replace(",", "."))
