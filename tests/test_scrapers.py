from precios_uy.scrapers import get_all_scrapers, get_scraper
from precios_uy.scrapers.base import ScraperBase
from precios_uy.scrapers.devoto import DevotoScraper
from precios_uy.scrapers.disco import DiscoScraper
from precios_uy.scrapers.el_dorado import ElDoradoScraper
from precios_uy.scrapers.frog import FrogScraper
from precios_uy.scrapers.kinko import KinkoScraper
from precios_uy.scrapers.macromercado import MacromercadoScraper
from precios_uy.scrapers.tata import TataScraper
from precios_uy.scrapers.tienda_inglesa import TiendaInglesaScraper


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
        assert len(scrapers) == 8

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

    def test_get_scraper_el_dorado(self):
        s = get_scraper("el_dorado")
        assert isinstance(s, ElDoradoScraper)

    def test_get_scraper_frog(self):
        s = get_scraper("frog")
        assert isinstance(s, FrogScraper)

    def test_get_scraper_kinko(self):
        s = get_scraper("kinko")
        assert isinstance(s, KinkoScraper)

    def test_get_scraper_devuelve_none_si_no_existe(self):
        assert get_scraper("inexistente") is None

    def test_scraper_tiene_nombre_correcto(self):
        casos = [
            (TataScraper, "Ta-Ta"),
            (DiscoScraper, "Disco"),
            (DevotoScraper, "Devoto"),
            (TiendaInglesaScraper, "Tienda Inglesa"),
            (MacromercadoScraper, "Macromercado"),
            (ElDoradoScraper, "El Dorado"),
            (FrogScraper, "Frog"),
            (KinkoScraper, "Kinko"),
        ]
        for cls, nombre in casos:
            assert cls().supermercado == nombre


class TestMacromercadoScraper:
    def test_devuelve_lista_vacia(self):
        scraper = MacromercadoScraper()
        assert scraper.scrapear() == []


class TestKinkoScraper:
    def test_devuelve_lista_vacia(self):
        assert KinkoScraper().scrapear() == []


_FROG_HOME = """
<ul class="mega-menu">
  <li class="has-sublist mega-menu-categories root-category-items">
    <a class="with-subcategories" href="/almacen-2">ALMACEN</a>
    <ul class="sublist"><li><a href="/aceites" title="ACEITES">ACEITES</a></li></ul>
  </li>
  <li class="root-category-items"><a href="/bebida">BEBIDA</a></li>
  <li class="root-category-items"><a href="/almacen-2">ALMACEN</a></li>
</ul>
"""


def _frog_pagina(productos, siguiente):
    items = "".join(
        f"""
        <div class="product-item" data-productid="{pid}">
          <div class="picture"><a href="/{slug}">
            <img src="data:image/gif;base64,R0l" data-lazyloadsrc="https://i.aw.uy/frog/{pid}.jpeg">
          </a></div>
          <div class="details">
            <h2 class="product-title"><a href="/{slug}">{nombre}</a></h2>
            <div class="prices">
              {f'<span class="price old-price">$ {anterior}</span>' if anterior else ''}
              <span class="price actual-price">$ {precio}</span>
            </div>
          </div>
        </div>"""
        for pid, slug, nombre, precio, anterior in productos
    )
    pager = '<div class="pager"><ul><li class="next-page"><a>Siguiente</a></li></ul></div>'
    return f'<div class="product-grid">{items}</div>{pager if siguiente else ""}'


class TestFrogScraper:
    def test_recorre_categorias_raiz_y_paginas(self, monkeypatch):
        from bs4 import BeautifulSoup

        paginas = {
            "https://frog.uy/": _FROG_HOME,
            "https://frog.uy/almacen-2?pagenumber=1": _frog_pagina(
                [(1, "arroz-saman-1kg", "Arroz Saman 1 Kg", "60", None)], siguiente=True
            ),
            "https://frog.uy/almacen-2?pagenumber=2": _frog_pagina(
                [(2, "aceite-optimo-900ml", "Aceite Optimo 900 Ml", "1.234,50", "1.300")],
                siguiente=False,
            ),
            # el mismo producto en dos categorías se cuenta una vez
            "https://frog.uy/bebida?pagenumber=1": _frog_pagina(
                [(1, "arroz-saman-1kg", "Arroz Saman 1 Kg", "60", None),
                 (3, "agua-salus-2l", "Agua Salus 2 L", "75", None)],
                siguiente=False,
            ),
        }
        pedidas = []

        def get_soup(url):
            pedidas.append(url)
            return BeautifulSoup(paginas[url], "lxml")

        monkeypatch.setattr("precios_uy.scrapers.frog.time.sleep", lambda s: None)
        scraper = FrogScraper()
        monkeypatch.setattr(scraper, "_get_soup", get_soup)
        lotes = []
        scraper.guardar_parcial = lambda lote: lotes.append(lote) or len(lote)

        productos = scraper.scrapear()

        assert [p.nombre for p in productos] == [
            "Arroz Saman 1 Kg", "Aceite Optimo 900 Ml", "Agua Salus 2 L",
        ]
        aceite = productos[1]
        assert aceite.precio == 1234.5
        assert aceite.precio_anterior == 1300.0
        assert aceite.categoria == "Almacen"
        assert aceite.sku == "2"
        assert aceite.url_producto == "https://frog.uy/aceite-optimo-900ml"
        assert aceite.url_imagen == "https://i.aw.uy/frog/2.jpeg"
        # ALMACEN aparece dos veces en el menú, pero se recorre una sola vez
        assert pedidas.count("https://frog.uy/almacen-2?pagenumber=1") == 1
        assert [len(lote) for lote in lotes] == [2, 1]

    def test_espera_y_reintenta_ante_405(self, monkeypatch):
        from bs4 import BeautifulSoup

        esperas = []
        monkeypatch.setattr("precios_uy.scrapers.frog.time.sleep", esperas.append)

        class Cortado(Exception):
            response = type("R", (), {"status_code": 405})()

        respuestas = [Cortado(), BeautifulSoup("<p>ok</p>", "lxml")]

        def get_soup(url):
            r = respuestas.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        scraper = FrogScraper()
        monkeypatch.setattr(scraper, "_get_soup", get_soup)
        assert scraper._get_pagina("https://frog.uy/x").p.text == "ok"
        assert FrogScraper.ESPERAS_LIMITE[0] in esperas


class TestVtexCanalVenta:
    def test_tata_usa_canal_4(self):
        url = TataScraper()._url_busqueda("fq=C:/1/", 0, 49)
        assert "fq=C:/1/&sc=4&_from=0&_to=49" in url

    def test_sin_canal(self):
        url = ElDoradoScraper()._url_busqueda("", 0, 0)
        assert "sc=" not in url
        assert url.endswith("search?_from=0&_to=0")


class TestGuardadoParcial:
    def test_entrega_lotes(self):
        from precios_uy.models import ProductoScrapeado

        s = MacromercadoScraper()
        lotes = []
        s.guardar_parcial = lambda lote: lotes.append(lote) or len(lote)
        s._entregar_parcial([ProductoScrapeado(supermercado="X", nombre="a", precio=1.0)])
        s._entregar_parcial([])
        assert len(lotes) == 1
        assert s.guardados_parciales == 1


class TestVtexReintentos:
    def test_reintenta_ante_500(self, monkeypatch):
        monkeypatch.setattr("precios_uy.scrapers.vtex_base.time.sleep", lambda s: None)

        class Resp:
            def __init__(self, status):
                self.status_code = status
                self.headers = {"resources": "0-0/1"}

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(self.status_code)

            def json(self):
                return [{"ok": True}]

        respuestas = [Resp(500), Resp(500), Resp(200)]
        s = TataScraper()
        monkeypatch.setattr(s._scraper, "get", lambda *a, **k: respuestas.pop(0))
        data, _ = s._get_json("http://x")
        assert data == [{"ok": True}]
        assert respuestas == []


class TestJerarquiaCategorias:
    def test_hija_por_id_o_por_path(self):
        es_hija = DiscoScraper._es_hija
        assert es_hija("canasta-familiar/1010", "almacen/10")
        assert es_hija("arroz/101013", "canasta-familiar/1010")
        assert es_hija("almacen/arroz", "almacen")
        assert not es_hija("bebidas/11", "almacen/10")
        assert not es_hija("almacen/10", "almacen/10")
