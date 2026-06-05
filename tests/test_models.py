from datetime import datetime

from precios_uy.models import Producto, Base, init_db
from precios_uy.database import init


class TestProducto:
    def test_create_with_all_fields(self):
        now = datetime.now()
        p = Producto(
            supermercado="Test",
            nombre="Producto de prueba",
            precio=99.99,
            precio_anterior=120.0,
            categoria="Almacén",
            marca="Marca X",
            url_producto="https://ejemplo.com/prod",
            url_imagen="https://ejemplo.com/img.jpg",
            fecha_scraping=now,
        )
        assert p.supermercado == "Test"
        assert p.nombre == "Producto de prueba"
        assert p.precio == 99.99
        assert p.precio_anterior == 120.0
        assert p.categoria == "Almacén"
        assert p.marca == "Marca X"
        assert p.url_producto == "https://ejemplo.com/prod"
        assert p.url_imagen == "https://ejemplo.com/img.jpg"
        assert p.fecha_scraping == now

    def test_create_with_required_fields_only(self):
        p = Producto(
            supermercado="Test",
            nombre="Producto básico",
            precio=50.0,
        )
        assert p.supermercado == "Test"
        assert p.nombre == "Producto básico"
        assert p.precio == 50.0
        assert p.precio_anterior is None
        assert p.categoria is None

    def test_to_dict(self, session):
        p = Producto(
            supermercado="Disco",
            nombre="Leche",
            precio=80.0,
            precio_anterior=90.0,
            categoria="Lácteos",
        )
        session.add(p)
        session.flush()
        d = p.to_dict()
        assert d["supermercado"] == "Disco"
        assert d["nombre"] == "Leche"
        assert d["precio"] == 80.0
        assert d["precio_anterior"] == 90.0
        assert d["categoria"] == "Lácteos"

    def test_to_dict_nullable_fields(self, session):
        p = Producto(supermercado="Test", nombre="Sin extras", precio=10.0)
        session.add(p)
        session.flush()
        d = p.to_dict()
        assert d["precio_anterior"] is None
        assert d["categoria"] is None
        assert d["marca"] is None
        assert d["url_producto"] is None
        assert d["url_imagen"] is None

    def test_default_fecha_scraping(self, session):
        p = Producto(supermercado="Test", nombre="Test", precio=10.0)
        session.add(p)
        session.flush()
        assert p.fecha_scraping is not None

    def test_init_db_creates_tables(self, session):
        assert Base.metadata.tables["productos"] is not None

    def test_save_and_retrieve(self, session):
        p = Producto(supermercado="Disco", nombre="Yerba", precio=250.0)
        session.add(p)
        session.commit()

        retrieved = session.query(Producto).filter_by(nombre="Yerba").first()
        assert retrieved is not None
        assert retrieved.precio == 250.0
        assert retrieved.supermercado == "Disco"
