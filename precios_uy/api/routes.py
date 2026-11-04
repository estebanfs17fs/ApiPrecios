import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from precios_uy.cache import is_cache_fresh
from precios_uy.database import (
    buscar_productos,
    comparar_lista,
    comparar_productos,
    obtener_categorias,
    obtener_historial,
    obtener_producto,
    obtener_supermercados,
    obtener_ultimos_precios,
)
from precios_uy.scheduler import ejecutar_scraping, estado_scraping

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
    """Busca y agrupa el mismo producto en los distintos supermercados."""
    grupos = comparar_productos(q)
    return {
        "producto": q,
        "grupos": grupos,
        "total": len(grupos),
    }


@router.get("/productos/{producto_id}")
def detalle_producto(producto_id: int):
    producto = obtener_producto(producto_id)
    if producto is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return {
        **producto.to_dict(),
        "historial": [h.to_dict() for h in obtener_historial(producto_id)],
    }


class ItemLista(BaseModel):
    producto_id: Optional[int] = Field(None, description="Producto elegido de la búsqueda")
    texto: Optional[str] = Field(None, description="O un texto libre, p. ej. 'leche 1 l'")
    cantidad: float = Field(1, gt=0)

    @model_validator(mode="after")
    def _producto_o_texto(self):
        if not self.producto_id and not (self.texto and self.texto.strip()):
            raise ValueError("Cada item necesita producto_id o texto")
        return self


class Lista(BaseModel):
    items: List[ItemLista] = Field(..., min_length=1, max_length=200)
    supermercados: Optional[List[str]] = Field(
        None, description="Limitar la comparación a estos supermercados"
    )


@router.post("/lista/comparar")
def comparar_lista_compras(lista: Lista):
    """
    Calcula cuánto sale la lista en cada supermercado, cuál conviene y cuál es
    la combinación más barata comprando cada producto donde esté más barato.
    """
    return comparar_lista([i.model_dump() for i in lista.items], lista.supermercados)


@router.get("/supermercados")
def listar_supermercados():
    return {"supermercados": obtener_supermercados()}


@router.get("/categorias")
def listar_categorias(
    supermercado: Optional[str] = Query(None, description="Filtrar por supermercado"),
):
    return {"categorias": obtener_categorias(supermercado)}


@router.post("/scrapear", status_code=202)
def disparar_scraping(
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Scrapear aunque los datos estén frescos"),
    supermercado: Optional[List[str]] = Query(None, description="Solo estos (p. ej. disco)"),
):
    """Lanza el scraping en segundo plano. El progreso se ve en GET /api/scrapear."""
    if estado_scraping["en_curso"]:
        return {"mensaje": "Ya hay un scraping en curso", "estado": _estado()}
    if is_cache_fresh() and not force:
        return {"mensaje": "Los datos aún están frescos. Usá ?force=true para forzar."}
    background_tasks.add_task(ejecutar_scraping, supermercado)
    return {"mensaje": "Scraping iniciado", "estado": _estado()}


@router.get("/scrapear")
def estado():
    return _estado()


def _estado():
    return {
        "en_curso": estado_scraping["en_curso"],
        "inicio": estado_scraping["inicio"].isoformat() if estado_scraping["inicio"] else None,
        "fin": estado_scraping["fin"].isoformat() if estado_scraping["fin"] else None,
        "resultados": estado_scraping["resultados"],
    }
