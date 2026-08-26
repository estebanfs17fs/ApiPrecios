import logging
from typing import List, Set

from precios_uy.models import Producto
from precios_uy.scrapers.base import ScraperBase

logger = logging.getLogger(__name__)


class TiendaInglesaScraper(ScraperBase):
    supermercado = "Tienda Inglesa"
    BASE = "https://www.tiendainglesa.com.uy"

    def _extraer_productos(self, soup) -> List[Producto]:
        result = []
        items = soup.select("div.card-product-container")
        for item in items:
            try:
                nombre_el = item.select_one("span.card-product-name, .card-product-name")
                precio_el = item.select_one(
                    "div.card-product-price div.card-product-price-containner span, "
                    "div.card-product-price span, .card-product-price span"
                )
                link_el = (
                    item.select_one("div.card-product-name-and-price a")
                    or item.select_one("div.card-product-container-img a")
                    or item.select_one("a")
                )
                img_el = item.select_one("img.card-product-img, img")

                nombre = nombre_el.get_text(strip=True) if nombre_el else None
                precio_text = precio_el.get_text(strip=True) if precio_el else None

                if not nombre or not precio_text:
                    continue

                precio = self._parse_precio(precio_text)
                prod_url = (
                    self.BASE + link_el["href"]
                    if link_el and link_el.get("href")
                    else None
                )
                prod_img = (
                    img_el.get("data-src") or img_el.get("src")
                    if img_el
                    else None
                )

                producto = Producto(
                    supermercado=self.supermercado,
                    nombre=nombre,
                    precio=precio,
                    url_producto=prod_url,
                    url_imagen=prod_img,
                )
                result.append(producto)
            except Exception:
                continue
        return result

    def _scrape_categoria_paginada(self, name: str, cat_id: int, max_pages: int = 5) -> List[Producto]:
        result = []
        for page in range(1, max_pages + 1):
            url = f"{self.BASE}/supermercado/{name}/{cat_id}?0,{cat_id},*,0,0,0,0,0,0,0,{page}"
            try:
                soup = self._get_soup(url)
                items = self._extraer_productos(soup)
                if not items:
                    break
                result.extend(items)
            except Exception:
                break
        return result

    def _scrape_lista_api(self, name: str, list_id: int, max_pages: int = 5) -> List[Producto]:
        result = []
        for page in range(1, max_pages + 1):
            url = f"{self.BASE}/supermercado/listas/{name}/busqueda?{list_id},0,*%3A*%26,0,0,0,,,false,,,,{page}"
            try:
                soup = self._get_soup(url)
                items = self._extraer_productos(soup)
                if not items:
                    break
                result.extend(items)
            except Exception:
                break
        return result

    def scrapear(self, max_pages: int = 5) -> List[Producto]:
        productos = []
        vistas_urls: Set[str] = set()

        logger.info("Iniciando scraping por categorías y listas en %s", self.supermercado)

        # Categorías principales del supermercado Tienda Inglesa
        categorias = [
            ("almacen", 1),
            ("frescos", 2),
            ("bebidas", 3),
            ("limpieza", 4),
            ("perfumeria", 5),
            ("congelados", 6),
            ("rotiseria", 7),
            ("mascotas", 8),
            ("hogar", 9),
            ("bebes", 10),
        ]

        for cat_name, cat_id in categorias:
            prods = self._scrape_categoria_paginada(cat_name, cat_id, max_pages=max_pages)
            for p in prods:
                if p.url_producto and p.url_producto in vistas_urls:
                    continue
                if p.url_producto:
                    vistas_urls.add(p.url_producto)
                p.categoria = cat_name.capitalize()
                productos.append(p)

        # Listas promocionales destacadas
        listas = [
            ("ofertas", 3716),
            ("ciberlunes", 17298),
            ("los-rompe-del-finde", 12658),
            ("preciazos-de-la-tienda", 16329),
        ]

        for name, list_id in listas:
            prods = self._scrape_lista_api(name, list_id, max_pages=max_pages)
            for p in prods:
                if p.url_producto and p.url_producto in vistas_urls:
                    continue
                if p.url_producto:
                    vistas_urls.add(p.url_producto)
                productos.append(p)

        logger.info("%s: %d productos únicos extraídos", self.supermercado, len(productos))
        return productos
