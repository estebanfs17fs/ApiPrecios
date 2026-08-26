from precios_uy.scrapers.devoto import DevotoScraper
from precios_uy.scrapers.disco import DiscoScraper
from precios_uy.scrapers.el_dorado import ElDoradoScraper
from precios_uy.scrapers.frog import FrogScraper
from precios_uy.scrapers.kinko import KinkoScraper
from precios_uy.scrapers.macromercado import MacromercadoScraper
from precios_uy.scrapers.tata import TataScraper
from precios_uy.scrapers.tienda_inglesa import TiendaInglesaScraper

SCRAPERS = {
    "tata": TataScraper,
    "disco": DiscoScraper,
    "devoto": DevotoScraper,
    "tienda_inglesa": TiendaInglesaScraper,
    "macromercado": MacromercadoScraper,
    "el_dorado": ElDoradoScraper,
    "frog": FrogScraper,
    "kinko": KinkoScraper,
}


def get_scraper(nombre: str):
    cls = SCRAPERS.get(nombre.lower())
    if cls:
        return cls()
    return None


def get_all_scrapers():
    return [cls() for cls in SCRAPERS.values()]
