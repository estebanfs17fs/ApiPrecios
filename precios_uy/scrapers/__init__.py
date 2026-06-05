from precios_uy.scrapers.tata import TataScraper
from precios_uy.scrapers.disco import DiscoScraper
from precios_uy.scrapers.devoto import DevotoScraper
from precios_uy.scrapers.tienda_inglesa import TiendaInglesaScraper
from precios_uy.scrapers.macromercado import MacromercadoScraper

SCRAPERS = {
    "tata": TataScraper,
    "disco": DiscoScraper,
    "devoto": DevotoScraper,
    "tienda_inglesa": TiendaInglesaScraper,
    "macromercado": MacromercadoScraper,
}


def get_scraper(nombre: str):
    cls = SCRAPERS.get(nombre.lower())
    if cls:
        return cls()
    return None


def get_all_scrapers():
    return [cls() for cls in SCRAPERS.values()]
