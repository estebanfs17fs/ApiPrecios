import pytest

from precios_uy.scrapers import get_all_scrapers, get_scraper
from precios_uy.scrapers.base import ScraperBase
from precios_uy.scrapers.tata import TataScraper
from precios_uy.scrapers.disco import DiscoScraper
from precios_uy.scrapers.devoto import DevotoScraper
from precios_uy.scrapers.tienda_inglesa import TiendaInglesaScraper
from precios_uy.scrapers.macromercado import MacromercadoScraper


class TestParsePrecio:
    def setup_method(self):
        self.scraper = DiscoScraper()

    def test_precio_simple(self):
        assert self.scraper._parse_precio("$ 100") == 100.0

    def test_precio_con_centavos(self):
        assert self.scraper._parse_precio("$ 99,99") == 99.99

    def test_precio_con_miles(self):
        assert self.scraper._parse_precio("$ 1.234") == 1234.0

    def test_precio_con_miles_y_centavos(self):
        assert self.scraper._parse_precio("$ 1.234,56") == 1234.56

    def test_precio_con_espacios(self):
        assert self.scraper._parse_precio("  $  99,99  ") == 99.99

    def test_precio_con_uyu(self):
        assert self.scraper._parse_precio("UYU 100") == 100.0

    def test_precio_sin_simbolo(self):
        assert self.scraper._parse_precio("99,99") == 99.99

    def test_precio_entero_sin_decimales(self):
        assert self.scraper._parse_precio("$ 5000") == 5000.0


class TestScraperRegistry:
    def test_get_all_scrapers_returns_list(self):
        scrapers = get_all_scrapers()
        assert isinstance(scrapers, list)
        assert len(scrapers) == 5

    def test_get_all_scrapers_are_instances(self):
        for s in get_all_scrapers():
            assert isinstance(s, ScraperBase)

    def test_get_all_scrapers_have_nombre(self):
        for s in get_all_scrapers():
            assert s.supermercado

    def test_get_scraper_por_nombre(self):
        s = get_scraper("disco")
        assert isinstance(s, DiscoScraper)

    def test_get_scraper_case_insensitive(self):
        s = get_scraper("DISCO")
        assert isinstance(s, DiscoScraper)

    def test_get_scraper_devuelve_none_si_no_existe(self):
        assert get_scraper("inexistente") is None

    def test_scraper_tiene_nombre_correcto(self):
        casos = [
            (TataScraper, "Ta-Ta"),
            (DiscoScraper, "Disco"),
            (DevotoScraper, "Devoto"),
            (TiendaInglesaScraper, "Tienda Inglesa"),
            (MacromercadoScraper, "Macromercado"),
        ]
        for cls, nombre in casos:
            assert cls().supermercado == nombre


class TestMacromercadoScraper:
    def test_devuelve_lista_vacia(self):
        scraper = MacromercadoScraper()
        assert scraper.scrapear() == []
