import logging

from precios_uy.scrapers.browser_base import BrowserScraperBase

logger = logging.getLogger(__name__)


class DevotoScraper(BrowserScraperBase):
    supermercado = "Devoto"
    BASE_URL = "https://www.devoto.com.uy"
