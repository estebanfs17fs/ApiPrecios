import logging
import threading
from datetime import datetime
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from precios_uy.cache import mark_scrape
from precios_uy.config import settings
from precios_uy.database import guardar_productos
from precios_uy.scrapers import get_all_scrapers, get_scraper

logger = logging.getLogger(__name__)

_lock = threading.Lock()
estado_scraping = {
    "en_curso": False,
    "inicio": None,
    "fin": None,
    "resultados": {},
}


def ejecutar_scraping(supermercados: Optional[List[str]] = None) -> dict:
    """
    Scrapea todos los supermercados (o solo los indicados por clave, p. ej. 'disco')
    y guarda los resultados. Si ya hay un scrapeo en curso, no hace nada.
    """
    if not _lock.acquire(blocking=False):
        logger.info("Ya hay un scrapeo en curso, se omite")
        return estado_scraping["resultados"]
    try:
        estado_scraping.update(en_curso=True, inicio=datetime.now(), fin=None, resultados={})
        if supermercados:
            scrapers = [s for s in (get_scraper(n) for n in supermercados) if s]
        else:
            scrapers = get_all_scrapers()

        logger.info("Iniciando scraping de %d supermercados...", len(scrapers))
        total = 0
        for scraper in scrapers:
            try:
                # se guarda a medida que avanza (por categoría) para no perder
                # todo si el proceso se corta
                scraper.guardar_parcial = guardar_productos
                productos = scraper.scrapear()
                if scraper.guardados_parciales:
                    cantidad = scraper.guardados_parciales
                else:
                    cantidad = guardar_productos(productos)
                total += cantidad
                estado_scraping["resultados"][scraper.supermercado] = f"{cantidad} productos"
                logger.info("%s: %d productos guardados", scraper.supermercado, cantidad)
            except Exception as e:
                logger.exception("Error scraping %s", scraper.supermercado)
                estado_scraping["resultados"][scraper.supermercado] = f"error: {e}"
        logger.info("Scraping completado. Total: %d productos", total)
        mark_scrape()
        return estado_scraping["resultados"]
    finally:
        estado_scraping.update(en_curso=False, fin=datetime.now())
        _lock.release()


scheduler = BackgroundScheduler()
scheduler.add_job(
    ejecutar_scraping,
    "interval",
    hours=settings.scrap_interval_hours,
    id="scraping_periodico",
    next_run_time=datetime.now(),
)
