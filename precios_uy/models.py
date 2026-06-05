from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from precios_uy.config import settings

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Producto(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supermercado = Column(String(50), nullable=False, index=True)
    nombre = Column(String(300), nullable=False)
    precio = Column(Float, nullable=False)
    precio_anterior = Column(Float, nullable=True)
    categoria = Column(String(100), nullable=True)
    marca = Column(String(100), nullable=True)
    url_producto = Column(String(500), nullable=True)
    url_imagen = Column(String(500), nullable=True)
    fecha_scraping = Column(DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "supermercado": self.supermercado,
            "nombre": self.nombre,
            "precio": self.precio,
            "precio_anterior": self.precio_anterior,
            "categoria": self.categoria,
            "marca": self.marca,
            "url_producto": self.url_producto,
            "url_imagen": self.url_imagen,
            "fecha_scraping": self.fecha_scraping.isoformat() if self.fecha_scraping else None,
        }


def init_db():
    Base.metadata.create_all(engine)
