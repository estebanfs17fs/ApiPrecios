import logging
from precios_uy.scrapers.browser_base import BrowserScraperBase

logger = logging.getLogger(__name__)


class DiscoScraper(BrowserScraperBase):
    supermercado = "Disco"
    BASE_URL = "https://www.disco.com.uy"
