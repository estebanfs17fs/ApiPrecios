from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from precios_uy.config import settings

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


@dataclass
class ProductoScrapeado:
    """Lo que devuelve un scraper. `database.guardar_productos` lo convierte en filas."""

    supermercado: str
    nombre: str
    precio: float
    precio_anterior: Optional[float] = None
    categoria: Optional[str] = None
    marca: Optional[str] = None
    url_producto: Optional[str] = None
    url_imagen: Optional[str] = None
    ean: Optional[str] = None
    sku: Optional[str] = None


class Producto(Base):
    """Un producto de un supermercado, con su precio más reciente."""

    __tablename__ = "productos"
    __table_args__ = (UniqueConstraint("supermercado", "identificador"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    supermercado = Column(String(50), nullable=False, index=True)
    # sku, url o nombre: lo que identifica al producto dentro de su supermercado
    identificador = Column(String(500), nullable=False)
    nombre = Column(String(300), nullable=False)
    nombre_normalizado = Column(String(300), nullable=True, index=True)
    medida = Column(String(30), nullable=True, index=True)
    ean = Column(String(14), nullable=True, index=True)
    precio = Column(Float, nullable=False)
    precio_anterior = Column(Float, nullable=True)
    categoria = Column(String(100), nullable=True)
    marca = Column(String(100), nullable=True)
    url_producto = Column(String(500), nullable=True)
    url_imagen = Column(String(500), nullable=True)
    creado = Column(DateTime, default=datetime.now)
    actualizado = Column(DateTime, default=datetime.now, index=True)

    historial = relationship(
        "HistorialPrecio",
        back_populates="producto",
        cascade="all, delete-orphan",
        order_by="HistorialPrecio.fecha",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "supermercado": self.supermercado,
            "nombre": self.nombre,
            "precio": self.precio,
            "precio_anterior": self.precio_anterior,
            "categoria": self.categoria,
            "marca": self.marca,
            "ean": self.ean,
            "medida": self.medida,
            "url_producto": self.url_producto,
            "url_imagen": self.url_imagen,
            "fecha_scraping": self.actualizado.isoformat() if self.actualizado else None,
        }


class HistorialPrecio(Base):
    """Un precio observado. Solo se agrega una fila cuando el precio cambia."""

    __tablename__ = "precios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False, index=True)
    precio = Column(Float, nullable=False)
    precio_anterior = Column(Float, nullable=True)
    fecha = Column(DateTime, default=datetime.now, index=True)

    producto = relationship("Producto", back_populates="historial")

    def to_dict(self):
        return {
            "precio": self.precio,
            "precio_anterior": self.precio_anterior,
            "fecha": self.fecha.isoformat() if self.fecha else None,
        }


def _renombrar_tabla_vieja():
    """
    La versión anterior guardaba una fila por producto y por scrapeo en `productos`.
    Si se encuentra ese esquema, se renombra a `productos_v1` para migrarlo.
    """
    insp = inspect(engine)
    if "productos" not in insp.get_table_names():
        return False
    columnas = {c["name"] for c in insp.get_columns("productos")}
    if "identificador" in columnas:
        return False
    indices = [i["name"] for i in insp.get_indexes("productos") if i.get("name")]
    with engine.begin() as conn:
        # los índices viejos chocarían por nombre con los de la tabla nueva
        for nombre in indices:
            conn.execute(text(f'DROP INDEX IF EXISTS "{nombre}"'))
        conn.execute(text("ALTER TABLE productos RENAME TO productos_v1"))
    return True


def init_db() -> bool:
    """Crea las tablas. Devuelve True si hay datos del esquema viejo para migrar."""
    vieja = _renombrar_tabla_vieja()
    Base.metadata.create_all(engine)
    return vieja
