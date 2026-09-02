import logging

from precios_uy.scrapers.vtex_base import VtexScraperBase

logger = logging.getLogger(__name__)


class ElDoradoScraper(VtexScraperBase):
    supermercado = "El Dorado"
    base_url = "https://www.eldorado.com.uy"
