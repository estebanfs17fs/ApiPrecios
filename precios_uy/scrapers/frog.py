import logging
import time
from typing import List, Optional, Set, Tuple

from precios_uy.models import ProductoScrapeado
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class FrogScraper(ScraperBase):
    """
    frog.uy es una tienda nopCommerce: las categorías raíz del menú incluyen los
    productos de sus subcategorías y paginan de a 40 con ?pagenumber=N.
    El sitio corta con 405 si se le piden muchas páginas seguidas, así que se
    hace una pausa entre páginas y, si corta igual, se espera y se reintenta.
    """

    supermercado = "Frog"
    BASE_URL = "https://frog.uy"
    MAX_PAGINAS = 150
    PAUSA = 1.5  # segundos entre páginas
    ESPERAS_LIMITE = (30, 60, 120)  # segundos a esperar cada vez que responde 405/429

    def _get_pagina(self, url: str):
        for espera in (*self.ESPERAS_LIMITE, None):
            time.sleep(self.PAUSA)
            try:
                return self._get_soup(url)
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status not in (405, 429) or espera is None:
                    raise
                logger.info("%s: límite de pedidos en %s, espero %d s",
                            self.supermercado, url, espera)
                time.sleep(espera)

    def _categorias_raiz(self) -> List[Tuple[str, str]]:
        soup = self._get_soup(self.BASE_URL + "/")
        categorias, vistas = [], set()
        for a in soup.select("li.root-category-items > a[href]"):
            href = a["href"]
            if href not in vistas:
                vistas.add(href)
                categorias.append((href, a.get_text(strip=True).title()))
        return categorias

    def _parsear_item(self, item, categoria: str) -> Optional[ProductoScrapeado]:
        link_el = item.select_one(".product-title a[href]")
        precio_el = item.select_one(".prices .actual-price")
        if not link_el or not precio_el:
            return None
        nombre = link_el.get_text(strip=True)
        if not nombre:
            return None
        anterior_el = item.select_one(".prices .old-price")
        img_el = item.select_one(".picture img")
        url_img = (img_el.get("data-lazyloadsrc") or img_el.get("src")) if img_el else None
        if url_img and url_img.startswith("data:"):
            url_img = None
        return ProductoScrapeado(
            supermercado=self.supermercado,
            nombre=nombre,
            precio=self._parse_precio(precio_el.get_text(strip=True)),
            precio_anterior=(
                self._parse_precio(anterior_el.get_text(strip=True)) if anterior_el else None
            ),
            categoria=categoria,
            url_producto=self.BASE_URL + link_el["href"],
            url_imagen=url_img,
            sku=item.get("data-productid"),
        )

    def _scrape_categoria(self, href: str, nombre: str, vistos: Set[str]) -> List[ProductoScrapeado]:
        result = []
        for pagina in range(1, self.MAX_PAGINAS + 1):
            url = f"{self.BASE_URL}{href}?pagenumber={pagina}"
            try:
                soup = self._get_pagina(url)
            except Exception as e:
                logger.warning("%s: error en %s: %s", self.supermercado, url, e)
                break
            items = soup.select("div.product-item")
            for item in items:
                try:
                    producto = self._parsear_item(item, nombre)
                except Exception as e:
                    logger.debug("%s: ítem descartado: %s", self.supermercado, e)
                    continue
                if producto and producto.url_producto not in vistos:
                    vistos.add(producto.url_producto)
                    result.append(producto)
            if not items or not soup.select_one(".pager li.next-page"):
                break
        return result

    def scrapear(self) -> List[ProductoScrapeado]:
        logger.info("Iniciando scraping de %s (%s)", self.supermercado, self.BASE_URL)
        productos: List[ProductoScrapeado] = []
        vistos: Set[str] = set()
        for href, nombre in self._categorias_raiz():
            nuevos = self._scrape_categoria(href, nombre, vistos)
            logger.info("%s: %s -> %d productos", self.supermercado, nombre, len(nuevos))
            productos.extend(nuevos)
            self._entregar_parcial(nuevos)
        logger.info("%s: %d productos extraídos", self.supermercado, len(productos))
        return productos
