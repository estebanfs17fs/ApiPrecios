import logging

from typing import List

from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class MacromercadoScraper(ScraperBase):
    supermercado = "Macromercado"

    def scrapear(self) -> List[Producto]:
        logger.warning(
            "Macromercado no tiene tienda online pública. "
            "Solo cuenta con catálogo B2B sin precios."
        )
        return []
