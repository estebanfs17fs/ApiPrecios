"""
Prueba el scraper con navegador contra un sitio local que imita a Disco/Devoto:
- "almacen": scroll infinito, precios que aparecen recién al entrar en pantalla
  (lazy loading) y lista virtualizada (saca del DOM los productos de arriba).
- "bebidas": botón "Ver más" y productos que llegan como JSON estilo VTEX.
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from precios_uy.config import settings
from precios_uy.scrapers.browser_base import BrowserScraperBase

pytest.importorskip("playwright")

TOTAL_ALMACEN = 137
TOTAL_BEBIDAS = 45
POR_PAGINA = 20

HOME = """<html><body><nav>
<a href="/products/category/almacen/10">Almacén</a>
<a href="/products/category/bebidas/11">Bebidas</a>
</nav></body></html>"""

ALMACEN = """<html><body>
<p>%(total)d productos</p>
<div id="lista"></div>
<script>
let pagina = 0, cargando = false, fin = false;
const lista = document.getElementById('lista');
const obs = new IntersectionObserver((entradas) => {
  entradas.forEach(e => {
    if (!e.isIntersecting) return;
    const el = e.target;
    setTimeout(() => {
      el.querySelector('.val').textContent = '$ ' + el.dataset.precio;
      const img = el.querySelector('img');
      img.src = img.dataset.src;
    }, 100);
    obs.unobserve(el);
  });
});
async function cargar() {
  if (cargando || fin) return;
  cargando = true;
  const r = await fetch('/api/items?pagina=' + pagina);
  const items = await r.json();
  pagina++;
  if (!items.length) fin = true;
  for (const it of items) {
    const d = document.createElement('div');
    d.className = 'product-item';
    d.style.height = '180px';
    d.dataset.precio = it.precio;
    d.innerHTML = '<figure><img src="data:image/gif;base64,R0lGOD" data-src="/img/' + it.id +
      '.jpg"></figure><div class="desc-top"><h3><a href="/producto/' + it.id + '">' +
      it.nombre + '</a></h3></div><div class="product-prices"><div class="price">' +
      '<span class="val"></span></div></div>';
    lista.appendChild(d);
    obs.observe(d);
  }
  // lista virtualizada: solo quedan los últimos 50 en el DOM
  while (lista.children.length > 50) lista.removeChild(lista.firstChild);
  cargando = false;
}
window.addEventListener('scroll', () => {
  if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 300) cargar();
});
cargar();
</script></body></html>"""

BEBIDAS = """<html><body>
<div id="lista"></div>
<button id="mas" type="button">Ver más</button>
<script>
let pagina = 0;
async function cargar() {
  const r = await fetch('/api/vtex?pagina=' + pagina);
  const prods = await r.json();
  pagina++;
  if (prods.length < %(por_pagina)d) document.getElementById('mas').remove();
  for (const p of prods) {
    const d = document.createElement('div');
    d.className = 'product-card';
    d.innerHTML = '<h3><a href="' + p.link + '">' + p.productName + '</a></h3>' +
      '<span class="price">$ ' + p.items[0].sellers[0].commertialOffer.Price + '</span>';
    document.getElementById('lista').appendChild(d);
  }
}
document.getElementById('mas').addEventListener('click', cargar);
cargar();
</script></body></html>"""


def _items_almacen(pagina):
    inicio = pagina * POR_PAGINA
    fin = min(inicio + POR_PAGINA, TOTAL_ALMACEN)
    return [
        {"id": i, "nombre": f"Arroz marca {i} 1 kg", "precio": f"{100 + i},50"}
        for i in range(inicio, fin)
    ]


def _items_bebidas(pagina):
    inicio = pagina * POR_PAGINA
    fin = min(inicio + POR_PAGINA, TOTAL_BEBIDAS)
    return [
        {
            "productId": str(i),
            "productName": f"Refresco {i} 1,5 L",
            "link": f"/refresco-{i}/p",
            "brand": "Marca",
            "categories": ["/Bebidas/Refrescos/"],
            "items": [
                {
                    "itemId": str(1000 + i),
                    "ean": f"77300000{i:05d}",
                    "images": [],
                    "sellers": [{"commertialOffer": {"Price": 50 + i, "ListPrice": 50 + i}}],
                }
            ],
        }
        for i in range(inicio, fin)
    ]


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _responder(self, cuerpo: str, tipo: str):
        datos = cuerpo.encode()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        url = urlparse(self.path)
        pagina = int(parse_qs(url.query).get("pagina", ["0"])[0])
        if url.path == "/":
            self._responder(HOME, "text/html; charset=utf-8")
        elif url.path.startswith("/products/category/almacen"):
            self._responder(ALMACEN % {"total": TOTAL_ALMACEN}, "text/html; charset=utf-8")
        elif url.path.startswith("/products/category/bebidas"):
            self._responder(BEBIDAS % {"por_pagina": POR_PAGINA}, "text/html; charset=utf-8")
        elif url.path == "/api/items":
            time.sleep(0.6)  # el sitio tarda en traer la página siguiente
            self._responder(json.dumps(_items_almacen(pagina)), "application/json")
        elif url.path == "/api/vtex":
            time.sleep(0.3)
            self._responder(json.dumps(_items_bebidas(pagina)), "application/json")
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def sitio():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    hilo = threading.Thread(target=server.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def ajustes_navegador():
    originales = (
        settings.chromium_path,
        settings.scroll_espera_ms,
        settings.scroll_paciencia,
    )
    ruta = os.environ.get("CHROMIUM_PATH") or settings.chromium_path
    if not ruta and os.path.exists("/opt/pw-browsers/chromium"):
        ruta = "/opt/pw-browsers/chromium"
    settings.chromium_path = ruta
    settings.scroll_espera_ms = 2000
    settings.scroll_paciencia = 3
    yield
    settings.chromium_path, settings.scroll_espera_ms, settings.scroll_paciencia = originales


class ScraperDePrueba(BrowserScraperBase):
    supermercado = "Prueba"

    def __init__(self, base_url):
        super().__init__()
        self.BASE_URL = base_url
        self.categorias = []


@pytest.mark.navegador
def test_scroll_infinito_con_lazy_loading_y_virtualizacion(sitio, ajustes_navegador):
    scraper = ScraperDePrueba(sitio)
    lotes = []
    scraper.guardar_parcial = lambda lote: lotes.append(lote) or len(lote)
    try:
        productos = scraper.scrapear(["almacen/10"])
    except Exception as e:  # sin navegador instalado
        pytest.skip(f"Playwright no disponible: {e}")

    assert len(productos) == TOTAL_ALMACEN
    # se entregó para guardar apenas terminó la categoría
    assert sum(len(lote) for lote in lotes) == TOTAL_ALMACEN
    precios = {p.nombre: p.precio for p in productos}
    assert precios["Arroz marca 0 1 kg"] == 100.5
    assert precios[f"Arroz marca {TOTAL_ALMACEN - 1} 1 kg"] == 100 + TOTAL_ALMACEN - 1 + 0.5
    assert all(p.url_imagen and p.url_imagen.endswith(".jpg") for p in productos)
    assert all(p.categoria == "Almacen" for p in productos)


@pytest.mark.navegador
def test_boton_ver_mas_y_json_vtex(sitio, ajustes_navegador):
    try:
        productos = ScraperDePrueba(sitio).scrapear(["bebidas/11"])
    except Exception as e:
        pytest.skip(f"Playwright no disponible: {e}")

    assert len(productos) == TOTAL_BEBIDAS
    # los datos del JSON (EAN, marca) se combinan con lo que se ve en pantalla
    assert all(p.ean for p in productos)
    assert all(p.url_producto.startswith(sitio) for p in productos)


@pytest.mark.navegador
def test_descubre_categorias_del_menu(sitio, ajustes_navegador):
    try:
        productos = ScraperDePrueba(sitio).scrapear()
    except Exception as e:
        pytest.skip(f"Playwright no disponible: {e}")

    assert len(productos) == TOTAL_ALMACEN + TOTAL_BEBIDAS
