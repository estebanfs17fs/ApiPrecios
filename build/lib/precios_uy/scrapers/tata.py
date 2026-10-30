import logging

from precios_uy.scrapers.vtex_base import VtexScraperBase

logger = logging.getLogger(__name__)


class TataScraper(VtexScraperBase):
    supermercado = "Ta-Ta"
    base_url = "https://tatauy.vtexcommercestable.com.br"
