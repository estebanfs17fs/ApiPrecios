
from precios_uy.database import (
    buscar_productos,
    guardar_productos,
    obtener_categorias,
    obtener_supermercados,
    obtener_ultimos_precios,
)
from precios_uy.models import Producto


class TestGuardarProductos:
    def test_guardar_vacio(self):
        assert guardar_productos([]) == 0

    def test_guardar_un_producto(self, session):
        p = Producto(supermercado="Disco", nombre="Test", precio=10.0)
        cantidad = guardar_productos([p])
        assert cantidad == 1
        assert session.query(Producto).count() == 1

    def test_guardar_varios(self, session):
        items = [
            Producto(supermercado="A", nombre="P1", precio=10.0),
            Producto(supermercado="B", nombre="P2", precio=20.0),
        ]
        assert guardar_productos(items) == 2
        assert session.query(Producto).count() == 2


class TestObtenerUltimosPrecios:
    def test_sin_productos(self):
        assert obtener_ultimos_precios() == []

    def test_devuelve_todos_sin_filtro(self, productos_db):
        resultados = obtener_ultimos_precios()
        assert len(resultados) == len(productos_db)

    def test_filtro_por_supermercado(self, productos_db):
        resultados = obtener_ultimos_precios(supermercado="Disco")
        assert len(resultados) == 2
        assert all(p.supermercado == "Disco" for p in resultados)

    def test_filtro_por_categoria(self, productos_db):
        resultados = obtener_ultimos_precios(categoria="Almacén")
        assert len(resultados) == 2
        assert all(p.categoria == "Almacén" for p in resultados)

    def test_filtro_combinado(self, productos_db):
        resultados = obtener_ultimos_precios(
            supermercado="Disco", categoria="Almacén"
        )
        assert len(resultados) == 1
        assert resultados[0].nombre == "Arroz 1kg"

    def test_limite(self, productos_db):
        resultados = obtener_ultimos_precios(limite=1)
        assert len(resultados) == 1

    def test_devuelve_ultimo_precio_por_producto(self, session):
        p1 = Producto(
            supermercado="Disco",
            nombre="Leche",
            precio=80.0,
        )
        p2 = Producto(
            supermercado="Disco",
            nombre="Leche",
            precio=90.0,
        )
        session.add_all([p1, p2])
        session.commit()

        resultados = obtener_ultimos_precios()
        leches = [r for r in resultados if r.nombre == "Leche"]
        assert len(leches) == 1
        assert leches[0].precio == 90.0


class TestBuscarProductos:
    def test_sin_resultados(self):
        assert buscar_productos("xyznoexiste") == []

    def test_encuentra_por_nombre(self, productos_db):
        resultados = buscar_productos("Arroz")
        assert len(resultados) == 2

    def test_case_insensitive(self, productos_db):
        resultados = buscar_productos("arroz")
        assert len(resultados) == 2

    def test_limite(self, productos_db):
        resultados = buscar_productos("a", limite=1)
        assert len(resultados) <= 1


class TestObtenerSupermercados:
    def test_sin_datos(self):
        assert obtener_supermercados() == []

    def test_devuelve_lista(self, productos_db):
        sups = obtener_supermercados()
        assert sorted(sups) == sorted(["Disco", "Tienda Inglesa"])

    def test_sin_duplicados(self, productos_db):
        sups = obtener_supermercados()
        assert len(sups) == len(set(sups))


class TestObtenerCategorias:
    def test_sin_datos(self):
        assert obtener_categorias() == []

    def test_devuelve_lista(self, productos_db):
        cats = obtener_categorias()
        assert sorted(cats) == sorted(["Almacén", "Lácteos", "Panadería"])

    def test_filtro_por_supermercado(self, productos_db):
        cats = obtener_categorias(supermercado="Disco")
        assert sorted(cats) == sorted(["Almacén", "Lácteos"])
