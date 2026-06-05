import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from precios_uy.cache import mark_scrape
from precios_uy.config import settings
from precios_uy.database import guardar_productos
from precios_uy.scrapers import get_all_scrapers

logger = logging.getLogger(__name__)


def ejecutar_scraping():
    logger.info("Iniciando scraping de todos los supermercados...")
    total = 0
    for scraper in get_all_scrapers():
        try:
            productos = scraper.scrapear()
            if productos:
                cantidad = guardar_productos(productos)
                total += cantidad
                logger.info(
                    "%s: %d productos guardados", scraper.supermercado, cantidad
                )
        except Exception as e:
            logger.error("Error scraping %s: %s", scraper.supermercado, e)
    logger.info("Scraping completado. Total: %d productos", total)
    mark_scrape()


scheduler = BackgroundScheduler()
scheduler.add_job(
    ejecutar_scraping,
    "interval",
    hours=settings.scrap_interval_hours,
    id="scraping_periodico",
    next_run_time=datetime.now(),
)
