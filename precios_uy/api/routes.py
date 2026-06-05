import logging
from typing import Optional

from fastapi import APIRouter, Query

from precios_uy.cache import is_cache_fresh, mark_scrape
from precios_uy.database import (
    buscar_productos,
    comparar_productos,
    guardar_productos,
    obtener_categorias,
    obtener_supermercados,
    obtener_ultimos_precios,
)
from precios_uy.scrapers import get_all_scrapers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/productos")
def listar_productos(
    supermercado: Optional[str] = Query(None, description="Filtrar por supermercado"),
    categoria: Optional[str] = Query(None, description="Filtrar por categoría"),
    limite: int = Query(50, ge=1, le=500),
):
    productos = obtener_ultimos_precios(supermercado, categoria, limite)
    return {
        "total": len(productos),
        "productos": [p.to_dict() for p in productos],
    }


@router.get("/productos/buscar")
def buscar(
    q: str = Query(..., min_length=1, description="Término de búsqueda"),
    limite: int = Query(20, ge=1, le=200),
):
    productos = buscar_productos(q, limite)
    return {
        "total": len(productos),
        "productos": [p.to_dict() for p in productos],
    }


@router.get("/productos/comparar")
def comparar(
    q: str = Query(..., min_length=1, description="Nombre del producto a comparar"),
):
    resultados = comparar_productos(q)
    return {
        "producto": q,
        "resultados": resultados,
        "total": len(resultados),
    }


@router.get("/supermercados")
def listar_supermercados():
    return {"supermercados": obtener_supermercados()}


@router.get("/categorias")
def listar_categorias(
    supermercado: Optional[str] = Query(None, description="Filtrar por supermercado"),
):
    return {"categorias": obtener_categorias(supermercado)}


@router.post("/scrapear")
def disparar_scraping():
    if is_cache_fresh():
        logger.info("Cache vigente, omitiendo scraping")
        return {"mensaje": "Los datos aún están frescos. Usá cache_ttl_hours para forzar."}

    resultados = {}
    for scraper in get_all_scrapers():
        try:
            productos = scraper.scrapear()
            cantidad = guardar_productos(productos)
            resultados[scraper.supermercado] = f"{cantidad} productos"
        except Exception as e:
            logger.exception("Error scraping %s", scraper.supermercado)
            resultados[scraper.supermercado] = f"error: {e}"
    mark_scrape()
    return {"resultados": resultados}
