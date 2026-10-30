"""
Scraping con navegador (Playwright) para sitios que cargan los productos a medida
que se hace scroll (infinite scroll) y que completan precios/imágenes recién cuando
el producto entra en pantalla (lazy loading). Lo usan Disco y Devoto.

Por qué se perdían productos antes:
- Se esperaba un tiempo fijo (1,2 s) y con 3 scrolls sin cambios se daba la
  categoría por terminada, aunque el sitio todavía estuviera cargando.
- Se hacía scroll de a 2500 px: los productos que quedaban "salteados" nunca
  entraban en pantalla y no llegaban a mostrar su precio, así que se descartaban.
- El HTML se leía una sola vez al final: si el sitio quita del DOM los productos
  que ya quedaron arriba (listas virtualizadas), esos se perdían.
- Había un tope de 30 scrolls por categoría.

Cómo se resuelve ahora:
- Se baja de a una pantalla, leyendo el DOM en cada paso, así cada producto
  entra en pantalla y carga su precio. Lo leído se acumula: no se pierde nada
  aunque el sitio después lo saque del DOM.
- Después de cada scroll se espera a que aparezcan productos nuevos o crezca la
  página (con un tiempo máximo), en vez de un tiempo fijo.
- Se hace clic en botones "Ver más"/"Cargar más" si existen.
- Al final se recorre la página de arriba a abajo, de a una pantalla, para que
  todos los productos muestren su precio e imagen.
- Además se escuchan las respuestas JSON que el sitio pide al hacer scroll: si
  traen productos (por ejemplo de la API de VTEX) se aprovechan directamente.
- Se descubren las categorías desde el menú del sitio, además de la lista fija.
"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from precios_uy.config import settings
from precios_uy.models import ProductoScrapeado
from precios_uy.normalizacion import extraer_medida, nombre_normalizado
from precios_uy.scrapers.base import ScraperBase
from precios_uy.scrapers.vtex_base import parsear_producto_vtex

logger = logging.getLogger(__name__)

# Devuelve solo los productos que no se leyeron antes (se marcan en el DOM), así
# el costo no crece con la cantidad de productos ya cargados en la página.
# `sin_precio` cuenta los que todavía esperan que el lazy loading muestre el precio.
_JS_EXTRAER = """
(sel) => {
  const imgUrl = (img) => {
    if (!img) return null;
    const cands = [
      img.getAttribute('data-src'), img.getAttribute('data-original'),
      img.getAttribute('data-lazy'), img.getAttribute('data-lazy-src'),
      (img.getAttribute('data-srcset') || img.getAttribute('srcset') || '')
        .split(',')[0].trim().split(' ')[0],
      img.getAttribute('src'),
    ];
    return cands.find(u => u && !u.startsWith('data:')) || null;
  };
  const texto = (el) => el ? (el.textContent || '').replace(/\\s+/g, ' ').trim() : null;
  const nuevos = [];
  let sinPrecio = 0;
  for (const item of document.querySelectorAll(sel.item)) {
    const nombre = item.querySelector(sel.nombre);
    const link = item.querySelector(sel.link);
    const href = link ? link.getAttribute('href') : null;
    const precio = texto(item.querySelector(sel.precio));
    // firma: si el sitio recicla el nodo con otro producto, cambia y se vuelve a leer
    const firma = (href || '') + '|' + texto(nombre) + '|' + (precio || '');
    if (item.dataset.puFirma === firma) continue;
    item.dataset.puFirma = firma;
    if (!precio) sinPrecio++;
    nuevos.push({
      nombre: texto(nombre) || (link && link.getAttribute('title')) || null,
      precio: precio,
      precio_anterior: texto(item.querySelector(sel.precio_anterior)),
      href: href,
      img: imgUrl(item.querySelector('img')),
    });
  }
  return {nuevos, sinPrecio};
}
"""

_JS_ESTADO = """
(selItem) => {
  const items = document.querySelectorAll(selItem);
  return {n: items.length, h: document.documentElement.scrollHeight,
          ultimo: items.length ? (items[items.length - 1].innerText || '') : ''};
}
"""

_JS_BAJAR_UNA_PANTALLA = """
() => {
  window.scrollBy(0, Math.round(window.innerHeight * 0.85));
  return window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
}
"""

_JS_HAY_NOVEDAD = """
([selItem, n, h, ultimo]) => {
  const items = document.querySelectorAll(selItem);
  const u = items.length ? (items[items.length - 1].innerText || '') : '';
  return items.length > n || document.documentElement.scrollHeight > h || u !== ultimo;
}
"""

_RE_TOTAL = re.compile(r"(\d[\d.]*)\s+(?:productos|resultados|artículos)", re.I)
_RE_CARGAR_MAS = re.compile(r"(ver|cargar|mostrar)\s+(más|mas)\b|load\s+more", re.I)


class BrowserScraperBase(ScraperBase):
    """
    Clase base para scrapers que requieren renderizado JavaScript en navegador
    (Playwright), con soporte para infinite scroll y lazy loading.
    """

    supermercado: str = "Browser Store"
    BASE_URL: str = ""
    RUTA_CATEGORIA = "/products/category/"

    SELECTOR_ITEM = ".product-item, div.product-card"
    SELECTOR_NOMBRE = ".desc-top h3 a, h3 a, .nombre, .title, .product-name"
    SELECTOR_PRECIO = ".product-prices .price .val, .val, .price"
    SELECTOR_PRECIO_ANTERIOR = ".product-prices .price-old .val, .price-old, .old-price, del"
    SELECTOR_LINK = ".desc-top h3 a, h3 a, a[href]"

    def __init__(self):
        super().__init__()
        self.categorias = [
            "almacen/10",
            "bebidas/11",
            "perfumeria-y-limpieza/12",
            "frescos/14",
            "mascotas/15",
            "tv-y-audio/20",
            "celulares-y-telefonia/21",
            "electrodomesticos/22",
            "tecnologia/23",
            "muebles/30",
            "hogar/31",
            "decoracion/32",
            "textil-hogar/33",
            "ferreteria-y-automovil/40",
            "deporte-y-tiempo-libre/41",
            "papeleria/42",
            "juguetes/43",
            "puericultura/50",
            "otras-categorias/91",
        ]

    # ------------------------------------------------------------------ utilidades

    @property
    def _selectores(self) -> dict:
        return {
            "item": self.SELECTOR_ITEM,
            "nombre": self.SELECTOR_NOMBRE,
            "precio": self.SELECTOR_PRECIO,
            "precio_anterior": self.SELECTOR_PRECIO_ANTERIOR,
            "link": self.SELECTOR_LINK,
        }

    def _url_absoluta(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        return urljoin(self.BASE_URL + "/", url)

    @staticmethod
    def _clave(p: ProductoScrapeado) -> str:
        """Clave para no repetir productos: la ruta de la URL o, si no hay, el nombre."""
        if p.url_producto:
            return urlparse(p.url_producto).path.rstrip("/").lower()
        return f"{nombre_normalizado(p.nombre)}|{extraer_medida(p.nombre) or ''}"

    def _agregar(self, destino: Dict[str, ProductoScrapeado], p: ProductoScrapeado):
        clave = self._clave(p)
        previo = destino.get(clave)
        if previo is None:
            destino[clave] = p
            return
        # completar datos que antes no estaban (precio o imagen cargados tarde)
        previo.url_imagen = previo.url_imagen or p.url_imagen
        previo.ean = previo.ean or p.ean
        previo.marca = previo.marca or p.marca
        previo.precio_anterior = previo.precio_anterior or p.precio_anterior

    def _desde_dom(self, crudo: dict, categoria: Optional[str]) -> Optional[ProductoScrapeado]:
        nombre = (crudo.get("nombre") or "").strip()
        if not nombre or not crudo.get("precio"):
            return None
        try:
            precio = self._parse_precio(crudo["precio"])
        except ValueError:
            return None
        if precio <= 0:
            return None
        precio_anterior = None
        if crudo.get("precio_anterior"):
            try:
                pa = self._parse_precio(crudo["precio_anterior"])
                precio_anterior = pa if pa > precio else None
            except ValueError:
                pass
        return ProductoScrapeado(
            supermercado=self.supermercado,
            nombre=nombre,
            precio=precio,
            precio_anterior=precio_anterior,
            categoria=categoria,
            url_producto=self._url_absoluta(crudo.get("href")),
            url_imagen=self._url_absoluta(crudo.get("img")),
        )

    def _desde_json(self, data, categoria: Optional[str], destino: Dict, profundidad: int = 0):
        """Busca productos dentro de una respuesta JSON del sitio (VTEX u otros)."""
        if profundidad > 8:
            return
        if isinstance(data, list):
            for x in data:
                self._desde_json(x, categoria, destino, profundidad + 1)
            return
        if not isinstance(data, dict):
            return
        if "productName" in data and "items" in data:
            p = parsear_producto_vtex(data, self.supermercado)
            if p:
                p.url_producto = self._url_absoluta(p.url_producto)
                p.categoria = p.categoria or categoria
                self._agregar(destino, p)
            return
        for v in data.values():
            if isinstance(v, (dict, list)):
                self._desde_json(v, categoria, destino, profundidad + 1)

    @staticmethod
    def _nombre_categoria(cat_path: str) -> str:
        return cat_path.strip("/").split("/")[0].replace("-", " ").capitalize()

    # ------------------------------------------------------------------ navegador

    async def _recolectar_dom(self, page, destino: Dict, categoria: str) -> int:
        """Agrega los productos nuevos del DOM. Devuelve cuántos quedan sin precio."""
        try:
            r = await page.evaluate(_JS_EXTRAER, self._selectores)
        except Exception as e:
            logger.debug("%s: error leyendo DOM: %s", self.supermercado, e)
            return 0
        for crudo in r["nuevos"]:
            p = self._desde_dom(crudo, categoria)
            if p:
                self._agregar(destino, p)
        return r["sinPrecio"]

    async def _click_cargar_mas(self, page) -> bool:
        try:
            boton = page.get_by_role("button", name=_RE_CARGAR_MAS).first
            if await boton.count() and await boton.is_visible():
                await boton.click(timeout=3000)
                return True
            link = page.get_by_role("link", name=_RE_CARGAR_MAS).first
            if await link.count() and await link.is_visible():
                await link.click(timeout=3000)
                return True
        except Exception:
            pass
        return False

    async def _bajar_hasta_el_final(self, page, destino: Dict, categoria: str) -> int:
        """
        Baja de a una pantalla (sin saltear productos) leyendo el DOM en cada paso,
        para que cada producto entre en pantalla y cargue su precio e imagen.
        """
        sin_precio = 0
        for _ in range(500):
            await page.wait_for_timeout(settings.scroll_paso_ms)
            sin_precio += await self._recolectar_dom(page, destino, categoria)
            if await page.evaluate(_JS_BAJAR_UNA_PANTALLA):
                await page.wait_for_timeout(settings.scroll_paso_ms)
                sin_precio += await self._recolectar_dom(page, destino, categoria)
                break
        return sin_precio

    async def _barrido_final(self, page, destino: Dict, categoria: str) -> None:
        """Recorre la página desde arriba para completar precios cargados tarde."""
        await page.evaluate("window.scrollTo(0, 0)")
        await self._bajar_hasta_el_final(page, destino, categoria)

    async def _total_informado(self, page) -> Optional[int]:
        """Muchos sitios muestran 'N productos': sirve para avisar si faltan."""
        try:
            m = _RE_TOTAL.search(await page.inner_text("body"))
            return int(m.group(1).replace(".", "")) if m else None
        except Exception:
            return None

    async def _subcategorias(self, page, cat_path: str) -> List[str]:
        """Links a subcategorías de la categoría actual (rutas más largas que la suya)."""
        try:
            hrefs = await page.eval_on_selector_all(
                f'a[href*="{self.RUTA_CATEGORIA}"]', "els => els.map(e => e.getAttribute('href'))"
            )
        except Exception:
            return []
        base = cat_path.strip("/") + "/"
        subs = []
        for h in hrefs:
            ruta = urlparse(h).path.split(self.RUTA_CATEGORIA, 1)[-1].strip("/")
            if ruta.startswith(base) and ruta not in subs:
                subs.append(ruta)
        return subs

    async def _scrapear_url(
        self, context, cat_path: str, categoria: str
    ) -> Tuple[List[ProductoScrapeado], Optional[int], List[str]]:
        """Devuelve (productos, total que informa el sitio, subcategorías encontradas)."""
        url = f"{self.BASE_URL}{self.RUTA_CATEGORIA}{cat_path}"
        dom: Dict[str, ProductoScrapeado] = {}
        red: Dict[str, ProductoScrapeado] = {}
        pendientes = set()

        async def leer_respuesta(resp):
            try:
                if "json" not in (resp.headers.get("content-type") or ""):
                    return
                self._desde_json(await resp.json(), categoria, red)
            except Exception:
                pass

        page = await context.new_page()
        page.on("response", lambda r: pendientes.add(asyncio.ensure_future(leer_respuesta(r))))
        logger.info("%s: abriendo %s", self.supermercado, url)
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            try:
                await page.wait_for_selector(self.SELECTOR_ITEM, timeout=15000)
            except Exception:
                logger.debug("%s: sin productos en el DOM inicial de %s", self.supermercado, url)

            inicio = time.monotonic()
            sin_novedad = 0
            sin_precio = 0
            for paso in range(1, settings.scroll_max_pasos + 1):
                antes = len(dom) + len(red)
                sin_precio += await self._bajar_hasta_el_final(page, dom, categoria)
                estado = await page.evaluate(_JS_ESTADO, self.SELECTOR_ITEM)
                await self._click_cargar_mas(page)
                try:
                    await page.wait_for_function(
                        _JS_HAY_NOVEDAD,
                        arg=[self.SELECTOR_ITEM, estado["n"], estado["h"], estado["ultimo"]],
                        timeout=settings.scroll_espera_ms,
                    )
                    # dar tiempo a que terminen de pintarse precios e imágenes
                    await page.wait_for_timeout(300)
                except Exception:
                    pass
                await self._recolectar_dom(page, dom, categoria)

                if len(dom) + len(red) == antes:
                    sin_novedad += 1
                    if sin_novedad >= settings.scroll_paciencia:
                        break
                else:
                    sin_novedad = 0
                if paso % 20 == 0:
                    logger.info(
                        "%s: %s, %d productos tras %d vueltas (%.0f s)",
                        self.supermercado, categoria, len(dom) + len(red), paso,
                        time.monotonic() - inicio,
                    )
            logger.info(
                "%s: %s, fin del scroll tras %d vueltas en %.0f s",
                self.supermercado, categoria, paso, time.monotonic() - inicio,
            )

            # solo hace falta volver a recorrer si quedaron productos sin precio
            if sin_precio:
                await self._barrido_final(page, dom, categoria)
            total = await self._total_informado(page)
            subcategorias = await self._subcategorias(page, cat_path)
        except Exception as e:
            logger.error("%s: error en %s: %s", self.supermercado, url, e)
            total, subcategorias = None, []
        finally:
            if pendientes:
                await asyncio.gather(*pendientes, return_exceptions=True)
            await page.close()

        resultado: Dict[str, ProductoScrapeado] = {}
        for p in list(red.values()) + list(dom.values()):
            self._agregar(resultado, p)

        if total and len(resultado) < total:
            logger.warning(
                "%s: %s informa %d productos y se obtuvieron %d",
                self.supermercado, url, total, len(resultado),
            )
        logger.info(
            "%s: %s -> %d productos (DOM %d, red %d)",
            self.supermercado, categoria, len(resultado), len(dom), len(red),
        )
        return list(resultado.values()), total, subcategorias

    async def _descubrir_categorias(self, context) -> List[str]:
        """Lee los links a categorías del menú del sitio."""
        page = await context.new_page()
        try:
            await page.goto(self.BASE_URL, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            hrefs = await page.eval_on_selector_all(
                f'a[href*="{self.RUTA_CATEGORIA}"]', "els => els.map(e => e.getAttribute('href'))"
            )
        except Exception as e:
            logger.debug("%s: no se pudieron descubrir categorías: %s", self.supermercado, e)
            hrefs = []
        finally:
            await page.close()
        rutas = []
        for h in hrefs:
            ruta = urlparse(h).path.split(self.RUTA_CATEGORIA, 1)[-1].strip("/")
            if ruta and ruta not in rutas:
                rutas.append(ruta)
        return rutas

    async def _lanzar_navegador(self, p):
        opciones = {
            "headless": settings.browser_headless,
            "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        }
        if settings.chromium_path:
            opciones["executable_path"] = settings.chromium_path
        return await p.chromium.launch(**opciones)

    async def _scrapear_async(
        self, categorias: Optional[List[str]] = None
    ) -> List[ProductoScrapeado]:
        from playwright.async_api import async_playwright

        todos: Dict[str, ProductoScrapeado] = {}
        async with async_playwright() as p:
            browser = await self._lanzar_navegador(p)
            context = await browser.new_context(
                user_agent=settings.user_agent,
                viewport={"width": 1280, "height": 900},
                locale="es-UY",
            )
            try:
                if categorias is None:
                    descubiertas = await self._descubrir_categorias(context)
                    # las descubiertas primero; las fijas por si el menú no carga
                    categorias = descubiertas + [
                        c for c in self.categorias if c not in descubiertas
                    ]
                pendientes = list(categorias)
                hechas = set()
                while pendientes:
                    cat = pendientes.pop(0)
                    if cat in hechas:
                        continue
                    hechas.add(cat)
                    prods, total, subcategorias = await self._scrapear_url(
                        context, cat, self._nombre_categoria(cat)
                    )
                    nuevos = []
                    for prod in prods:
                        if self._clave(prod) not in todos:
                            nuevos.append(prod)
                        self._agregar(todos, prod)
                    # guardar ya lo de esta categoría: si el proceso se corta, no se pierde
                    self._entregar_parcial(nuevos)
                    # si el sitio no deja llegar a todos con scroll, probar por subcategorías
                    if total and len(prods) < total * 0.95 and subcategorias:
                        logger.info(
                            "%s: %s incompleta (%d de %d), se recorren %d subcategorías",
                            self.supermercado, cat, len(prods), total, len(subcategorias),
                        )
                        pendientes[0:0] = [c for c in subcategorias if c not in hechas]
            finally:
                await browser.close()

        logger.info("%s: %d productos únicos", self.supermercado, len(todos))
        return list(todos.values())

    # ------------------------------------------------------------------ sin navegador

    def scrapear_fallback_http(self) -> List[ProductoScrapeado]:
        """Fallback a HTTP tradicional si Playwright no está disponible (solo ve la 1.ª carga)."""
        todos: Dict[str, ProductoScrapeado] = {}
        for cat in self.categorias:
            url = f"{self.BASE_URL}{self.RUTA_CATEGORIA}{cat}"
            try:
                soup = self._get_soup(url)
            except Exception as e:
                logger.debug("%s: Fallback HTTP error en %s: %s", self.supermercado, cat, e)
                continue
            for crudo in self._extraer_html(soup):
                p = self._desde_dom(crudo, self._nombre_categoria(cat))
                if p:
                    self._agregar(todos, p)
        return list(todos.values())

    def _extraer_html(self, soup: BeautifulSoup) -> List[dict]:
        crudos = []
        for item in soup.select(self.SELECTOR_ITEM):
            nombre = item.select_one(self.SELECTOR_NOMBRE)
            precio = item.select_one(self.SELECTOR_PRECIO)
            anterior = item.select_one(self.SELECTOR_PRECIO_ANTERIOR)
            link = item.select_one(self.SELECTOR_LINK)
            img = item.select_one("img")
            crudos.append(
                {
                    "nombre": nombre.get_text(strip=True) if nombre else None,
                    "precio": precio.get_text(strip=True) if precio else None,
                    "precio_anterior": anterior.get_text(strip=True) if anterior else None,
                    "href": link.get("href") if link else None,
                    "img": (img.get("data-src") or img.get("data-original") or img.get("src"))
                    if img
                    else None,
                }
            )
        return crudos

    def scrapear(self, categorias: Optional[List[str]] = None) -> List[ProductoScrapeado]:
        try:
            return asyncio.run(self._scrapear_async(categorias))
        except Exception as e:
            logger.warning(
                "%s: Fallo en Playwright (%s), ejecutando fallback HTTP...",
                self.supermercado,
                e,
            )
            return self.scrapear_fallback_http()
