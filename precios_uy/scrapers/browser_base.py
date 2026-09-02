import asyncio
import logging
import os
from typing import List, Set

from bs4 import BeautifulSoup

from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class BrowserScraperBase(ScraperBase):
    """
    Clase base para scrapers que requieren renderizado JavaScript en navegador (Playwright),
    soporte para Infinite Scroll y Lazy Loading de imágenes/precios (Disco, Devoto).
    """
    supermercado: str = "Browser Store"
    BASE_URL: str = ""

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

    async def _scrapear_categoria_playwright(
        self, page, cat_path: str, max_scroll_steps: int = 30
    ) -> List[Producto]:
        productos = []
        url = f"{self.BASE_URL}/products/category/{cat_path}"
        logger.info(
            "%s: Navegando con Playwright (infinite scroll + lazy load) a %s",
            self.supermercado,
            url,
        )

        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            try:
                await page.wait_for_selector(".product-item, div.product-card", timeout=10000)
            except Exception:
                logger.debug(
                    "%s: No se encontraron items en DOM inicial para %s",
                    self.supermercado,
                    url,
                )
                return productos

            last_count = 0
            stuck_count = 0

            # Bucle de Infinite Scroll
            for step in range(1, max_scroll_steps + 1):
                await page.evaluate("window.scrollBy(0, 2500);")
                await page.wait_for_timeout(1200)

                items_dom = await page.query_selector_all(".product-item, div.product-card")
                current_count = len(items_dom)

                if current_count == last_count:
                    stuck_count += 1
                    if stuck_count >= 3:
                        logger.debug(
                            "%s: Infinite scroll finalizado en paso %d (%d items)",
                            self.supermercado,
                            step,
                            current_count,
                        )
                        break
                else:
                    stuck_count = 0
                    last_count = current_count

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            items = soup.select(".product-item, div.product-card")

            cat_nombre = cat_path.split("/")[0].replace("-", " ").capitalize()

            for item in items:
                try:
                    nombre_el = item.select_one(".desc-top h3 a, h3 a, .nombre, .title")
                    precio_el = item.select_one(".product-prices .price .val, .val, .price")
                    img_el = item.select_one("figure img, img")
                    link_el = item.select_one(".desc-top h3 a, h3 a, a[href]")

                    nombre = nombre_el.get_text(strip=True) if nombre_el else None
                    precio_text = precio_el.get_text(strip=True) if precio_el else None

                    if not nombre or not precio_text:
                        continue

                    prod_url = None
                    if link_el and link_el.get("href"):
                        href = link_el["href"]
                        prod_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

                    precio = self._parse_precio(precio_text)

                    # Lazy loading: extraer la mejor imagen (data-src, data-original o src)
                    prod_img = None
                    if img_el:
                        prod_img = (
                            img_el.get("data-src")
                            or img_el.get("data-original")
                            or img_el.get("src")
                        )
                        if prod_img and not prod_img.startswith("http"):
                            prod_img = f"{self.BASE_URL}{prod_img}"

                    producto = Producto(
                        supermercado=self.supermercado,
                        nombre=nombre,
                        precio=precio,
                        categoria=cat_nombre,
                        url_producto=prod_url,
                        url_imagen=prod_img,
                    )
                    productos.append(producto)
                except Exception:
                    continue

        except Exception as e:
            logger.error("%s: Error Playwright en %s: %s", self.supermercado, url, e)

        return productos

    async def _scrapear_async(self, max_scroll_steps: int = 30) -> List[Producto]:
        from playwright.async_api import async_playwright

        todos_productos = []
        vistas_urls: Set[str] = set()

        exec_path = "/snap/bin/chromium" if os.path.exists("/snap/bin/chromium") else None

        async with async_playwright() as p:
            launch_args = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            }
            if exec_path:
                launch_args["executable_path"] = exec_path

            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()

            for cat in self.categorias:
                prods = await self._scrapear_categoria_playwright(
                    page, cat, max_scroll_steps=max_scroll_steps
                )
                for p_item in prods:
                    if p_item.url_producto and p_item.url_producto in vistas_urls:
                        continue
                    if p_item.url_producto:
                        vistas_urls.add(p_item.url_producto)
                    todos_productos.append(p_item)

            await browser.close()

        return todos_productos

    def scrapear_fallback_http(self) -> List[Producto]:
        """Fallback a HTTP tradicional si Playwright no está disponible."""
        productos = []
        vistas_urls: Set[str] = set()

        for cat in self.categorias:
            url = f"{self.BASE_URL}/products/category/{cat}"
            try:
                soup = self._get_soup(url)
                items = soup.select("div.product-item")

                for item in items:
                    try:
                        nombre_el = item.select_one(".desc-top h3 a, h3 a")
                        precio_el = item.select_one(".product-prices .price .val, .val")
                        img_el = item.select_one("figure img, img")
                        link_el = item.select_one(".desc-top h3 a, h3 a")

                        nombre = nombre_el.get_text(strip=True) if nombre_el else None
                        precio_text = precio_el.get_text(strip=True) if precio_el else None

                        if not nombre or not precio_text:
                            continue

                        prod_url = (
                            self.BASE_URL + link_el["href"]
                            if link_el and link_el.get("href")
                            else None
                        )

                        if prod_url and prod_url in vistas_urls:
                            continue
                        if prod_url:
                            vistas_urls.add(prod_url)

                        precio = self._parse_precio(precio_text)
                        cat_nombre = cat.split("/")[0].capitalize()

                        producto = Producto(
                            supermercado=self.supermercado,
                            nombre=nombre,
                            precio=precio,
                            categoria=cat_nombre,
                            url_producto=prod_url,
                            url_imagen=img_el.get("src") if img_el else None,
                        )
                        productos.append(producto)
                    except Exception:
                        continue
            except Exception as e:
                logger.debug("%s: Fallback HTTP error en %s: %s", self.supermercado, cat, e)
                continue

        return productos

    def scrapear(self, max_scroll_steps: int = 30) -> List[Producto]:
        try:
            return asyncio.run(self._scrapear_async(max_scroll_steps=max_scroll_steps))
        except Exception as e:
            logger.warning(
                "%s: Fallo en Playwright (%s), ejecutando fallback HTTP...",
                self.supermercado,
                e,
            )
            return self.scrapear_fallback_http()
