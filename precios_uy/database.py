from datetime import datetime
from typing import List, Optional

from sqlalchemy import func

from precios_uy.models import Producto, SessionLocal, init_db


def guardar_productos(productos: List[Producto]) -> int:
    session = SessionLocal()
    try:
        session.add_all(productos)
        session.commit()
        return len(productos)
    finally:
        session.close()


def obtener_ultimos_precios(
    supermercado: Optional[str] = None,
    categoria: Optional[str] = None,
    limite: int = 50,
) -> List[Producto]:
    session = SessionLocal()
    try:
        subq = (
            session.query(
                Producto.supermercado,
                Producto.nombre,
                func.max(Producto.fecha_scraping).label("max_fecha"),
            )
            .group_by(Producto.supermercado, Producto.nombre)
            .subquery()
        )

        q = session.query(Producto).join(
            subq,
            (Producto.supermercado == subq.c.supermercado)
            & (Producto.nombre == subq.c.nombre)
            & (Producto.fecha_scraping == subq.c.max_fecha),
        )

        if supermercado:
            q = q.filter(Producto.supermercado == supermercado)
        if categoria:
            q = q.filter(Producto.categoria == categoria)

        return q.order_by(Producto.supermercado, Producto.nombre).limit(limite).all()
    finally:
        session.close()


def buscar_productos(termino: str, limite: int = 20) -> List[Producto]:
    session = SessionLocal()
    try:
        return (
            session.query(Producto)
            .filter(Producto.nombre.ilike(f"%{termino}%"))
            .order_by(Producto.fecha_scraping.desc())
            .limit(limite)
            .all()
        )
    finally:
        session.close()


def obtener_supermercados() -> List[str]:
    session = SessionLocal()
    try:
        resultados = session.query(Producto.supermercado).distinct().all()
        return [r[0] for r in resultados]
    finally:
        session.close()


def obtener_categorias(supermercado: Optional[str] = None) -> List[str]:
    session = SessionLocal()
    try:
        q = session.query(Producto.categoria).distinct()
        if supermercado:
            q = q.filter(Producto.supermercado == supermercado)
        resultados = q.all()
        return [r[0] for r in resultados if r[0]]
    finally:
        session.close()


def comparar_productos(termino: str) -> List[dict]:
    session = SessionLocal()
    try:
        productos = (
            session.query(Producto)
            .filter(Producto.nombre.ilike(f"%{termino}%"))
            .order_by(Producto.supermercado, Producto.precio)
            .all()
        )

        agrupados: dict[str, dict] = {}
        for p in productos:
            key = (p.supermercado, p.nombre)
            if key not in agrupados:
                agrupados[key] = {
                    "supermercado": p.supermercado,
                    "nombre": p.nombre,
                    "precio": p.precio,
                    "precio_anterior": p.precio_anterior,
                    "fecha": p.fecha_scraping.isoformat() if p.fecha_scraping else None,
                    "url_producto": p.url_producto,
                    "url_imagen": p.url_imagen,
                }

        return list(agrupados.values())
    finally:
        session.close()


def init():
    init_db()
