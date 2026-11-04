import logging
from typing import List

from precios_uy.models import ProductoScrapeado
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class KinkoScraper(ScraperBase):
    supermercado = "Kinko"

    def scrapear(self) -> List[ProductoScrapeado]:
        logger.warning(
            "Kinko no tiene tienda online: kinko.com.uy es solo institucional "
            "(locales, franquicias, contacto) y no publica productos ni precios."
        )
        return []
