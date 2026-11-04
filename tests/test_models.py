from precios_uy.database import guardar_productos
from precios_uy.models import Base, HistorialPrecio, Producto, ProductoScrapeado


class TestProductoScrapeado:
    def test_campos_opcionales(self):
        p = ProductoScrapeado(supermercado="Test", nombre="Producto básico", precio=50.0)
        assert p.precio_anterior is None
        assert p.categoria is None
        assert p.ean is None


class TestProducto:
    def test_tablas_creadas(self):
        assert "productos" in Base.metadata.tables
        assert "precios" in Base.metadata.tables

    def test_to_dict(self, session):
        guardar_productos(
            [
                ProductoScrapeado(
                    supermercado="Disco",
                    nombre="Leche Conaprole 1 L",
                    precio=80.0,
                    precio_anterior=90.0,
                    categoria="Lácteos",
                    ean="7730105001234",
                )
            ]
        )
        d = session.query(Producto).one().to_dict()
        assert d["supermercado"] == "Disco"
        assert d["precio"] == 80.0
        assert d["precio_anterior"] == 90.0
        assert d["categoria"] == "Lácteos"
        assert d["ean"] == "7730105001234"
        assert d["medida"] == "1000ml"
        assert d["fecha_scraping"] is not None

    def test_historial(self, session):
        guardar_productos([ProductoScrapeado(supermercado="Disco", nombre="Yerba", precio=250.0)])
        p = session.query(Producto).one()
        assert [h.precio for h in p.historial] == [250.0]
        assert session.query(HistorialPrecio).count() == 1
