
from datetime import datetime

from sqlalchemy import text

from precios_uy import models
from precios_uy.database import (
    buscar_productos,
    comparar_lista,
    comparar_productos,
    guardar_productos,
    init,
    obtener_categorias,
    obtener_supermercados,
    obtener_ultimos_precios,
    renormalizar,
)
from precios_uy.models import HistorialPrecio, Producto
from precios_uy.models import ProductoScrapeado as PS


class TestGuardarProductos:
    def test_guardar_vacio(self):
        assert guardar_productos([]) == 0

    def test_guardar_un_producto(self, session):
        cantidad = guardar_productos([PS(supermercado="Disco", nombre="Test", precio=10.0)])
        assert cantidad == 1
        assert session.query(Producto).count() == 1

    def test_guardar_varios(self, session):
        items = [
            PS(supermercado="A", nombre="P1", precio=10.0),
            PS(supermercado="B", nombre="P2", precio=20.0),
        ]
        assert guardar_productos(items) == 2
        assert session.query(Producto).count() == 2

    def test_descarta_precios_invalidos(self, session):
        assert guardar_productos([PS(supermercado="A", nombre="P", precio=0)]) == 0

    def test_mismo_producto_no_se_duplica(self, session):
        guardar_productos([PS(supermercado="Disco", nombre="Leche", precio=80.0)])
        guardar_productos([PS(supermercado="Disco", nombre="Leche", precio=80.0)])
        assert session.query(Producto).count() == 1
        # sin cambio de precio no se agrega historial
        assert session.query(HistorialPrecio).count() == 1

    def test_historial_cuando_cambia_el_precio(self, session):
        guardar_productos([PS(supermercado="Disco", nombre="Leche", precio=80.0, sku="1")])
        guardar_productos([PS(supermercado="Disco", nombre="Leche", precio=90.0, sku="1")])
        p = session.query(Producto).one()
        assert p.precio == 90.0
        assert [h.precio for h in p.historial] == [80.0, 90.0]


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

    def test_devuelve_ultimo_precio_por_producto(self):
        guardar_productos([PS(supermercado="Disco", nombre="Leche", precio=80.0)])
        guardar_productos([PS(supermercado="Disco", nombre="Leche", precio=90.0)])

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


class TestBusquedaNormalizada:
    def test_sin_tildes_y_en_cualquier_orden(self):
        guardar_productos([PS(supermercado="Disco", nombre="Azúcar Bella Unión 1 Kg", precio=60.0)])
        assert len(buscar_productos("azucar union")) == 1
        assert len(buscar_productos("azucar 1000 g")) == 1
        assert buscar_productos("azucar 500 g") == []


class TestCompararProductos:
    def test_agrupa_por_ean_aunque_el_nombre_cambie(self):
        guardar_productos(
            [
                PS(supermercado="Ta-Ta", nombre="Arroz Saman Blanco 1kg", precio=70.0,
                   ean="7730123000017"),
                PS(supermercado="El Dorado", nombre="ARROZ SAMAN 1 KG", precio=65.0,
                   ean="7730123000017"),
                PS(supermercado="Disco", nombre="Arroz Saman Blanco 1 Kg", precio=72.0),
                PS(supermercado="Disco", nombre="Arroz Saman Blanco 5 Kg", precio=300.0),
            ]
        )
        grupos = comparar_productos("arroz saman")
        principal = grupos[0]
        assert [o["supermercado"] for o in principal["ofertas"]] == [
            "El Dorado", "Ta-Ta", "Disco",
        ]
        # el de 5 kg es otro producto
        assert any(g["medida"] == "5000g" for g in grupos[1:])

    def test_no_mezcla_productos_distintos(self):
        guardar_productos(
            [
                PS(supermercado="A", nombre="Leche Conaprole Entera 1 L", precio=40.0),
                PS(supermercado="B", nombre="Leche Conaprole Descremada 1 L", precio=42.0),
            ]
        )
        assert len(comparar_productos("leche")) == 2

    def test_un_nombre_sin_medida_no_une_presentaciones_distintas(self):
        guardar_productos(
            [
                PS(supermercado="A", nombre="Arroz Blanco Saman 500 g", precio=43.0),
                PS(supermercado="B", nombre="Arroz Blanco SAMAN 500 g", precio=45.0),
                PS(supermercado="C", nombre="Arroz blanco en bandeja", precio=55.0),
                PS(supermercado="D", nombre="Arroz Blanco Saman 1 kg", precio=60.0),
            ]
        )
        grupos = {
            g["medida"]: sorted(o["supermercado"] for o in g["ofertas"])
            for g in comparar_productos("arroz blanco")
        }
        assert grupos["500g"] == ["A", "B"]
        assert grupos["1000g"] == ["D"]

    def test_no_mezcla_pack_con_unidad(self):
        guardar_productos(
            [
                PS(supermercado="A", nombre="Cerveza Patricia 1 L", precio=120.0),
                PS(supermercado="B", nombre="Cerveza Patricia 6 x 1 L", precio=650.0),
            ]
        )
        assert len(comparar_productos("cerveza patricia")) == 2


class TestCompararLista:
    def test_encuentra_equivalente_en_otro_super(self, session):
        guardar_productos(
            [
                PS(supermercado="Disco", nombre="Yerba Canarias 1 Kg", precio=300.0),
                PS(supermercado="Ta-Ta", nombre="Yerba Mate CANARIAS 1kg", precio=280.0),
                PS(supermercado="Disco", nombre="Fideos Adria 500 g", precio=50.0),
            ]
        )
        yerba = session.query(Producto).filter_by(supermercado="Disco").first()
        r = comparar_lista(
            [{"producto_id": yerba.id, "cantidad": 1}, {"texto": "fideos", "cantidad": 3}]
        )
        tata = next(s for s in r["supermercados"] if s["supermercado"] == "Ta-Ta")
        assert tata["detalle"][0]["producto"]["precio"] == 280.0
        assert tata["faltantes"] == [1]
        assert r["recomendado"] == "Disco"
        assert r["combinacion_optima"]["total"] == 280.0 + 150.0

    def test_filtra_supermercados(self):
        guardar_productos(
            [
                PS(supermercado="A", nombre="Pan", precio=10.0),
                PS(supermercado="B", nombre="Pan", precio=5.0),
            ]
        )
        r = comparar_lista([{"texto": "pan", "cantidad": 1}], supermercados=["A"])
        assert [s["supermercado"] for s in r["supermercados"]] == ["A"]

    def test_texto_compara_el_mismo_producto_en_todos(self):
        guardar_productos(
            [
                PS(supermercado="A", nombre="Leche Conaprole Entera 1 L", precio=45.0),
                PS(supermercado="A", nombre="Leche Conaprole Descremada 1 L", precio=40.0),
                PS(supermercado="B", nombre="Leche CONAPROLE entera 1 L", precio=46.0),
                PS(supermercado="C", nombre="Leche Conaprole Entera 1Lt", precio=47.0),
                PS(supermercado="C", nombre="Leche Pili 1 L", precio=38.0),
            ]
        )
        r = comparar_lista([{"texto": "leche 1 l", "cantidad": 1}])
        elegidos = {
            s["supermercado"]: s["detalle"][0]["producto"]["nombre"] for s in r["supermercados"]
        }
        # la entera está en los tres: se compara esa, no la más barata de cada uno
        assert all("ntera" in n for n in elegidos.values())
        assert not any(d["aproximado"] for s in r["supermercados"] for d in s["detalle"])

    def test_texto_marca_aproximado_donde_no_esta_el_mismo(self):
        guardar_productos(
            [
                PS(supermercado="A", nombre="Yerba Canarias 1 Kg", precio=300.0),
                PS(supermercado="B", nombre="Yerba CANARIAS 1kg", precio=290.0),
                PS(supermercado="C", nombre="Yerba Sara 1 Kg", precio=250.0),
            ]
        )
        r = comparar_lista([{"texto": "yerba 1 kg", "cantidad": 1}])
        c = next(s for s in r["supermercados"] if s["supermercado"] == "C")
        assert c["detalle"][0]["aproximado"] is True
        a = next(s for s in r["supermercados"] if s["supermercado"] == "A")
        assert a["detalle"][0]["aproximado"] is False
        # la Sara es más barata, pero es otra yerba: la combinación usa la Canarias
        assert r["combinacion_optima"]["total"] == 290.0


class TestMigracionEsquemaViejo:
    def test_migra_tabla_vieja(self, session):
        engine = models.engine
        models.Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE productos (id INTEGER PRIMARY KEY, supermercado VARCHAR(50), "
                "nombre VARCHAR(300), precio FLOAT, precio_anterior FLOAT, categoria VARCHAR, "
                "marca VARCHAR, url_producto VARCHAR, url_imagen VARCHAR, fecha_scraping DATETIME)"
            ))
            conn.execute(text("CREATE INDEX ix_productos_supermercado ON productos (supermercado)"))
            for precio, fecha in [(80.0, datetime(2026, 1, 1)), (95.0, datetime(2026, 2, 1))]:
                conn.execute(
                    text(
                        "INSERT INTO productos (supermercado, nombre, precio, fecha_scraping) "
                        "VALUES ('Disco', 'Leche 1L', :p, :f)"
                    ),
                    {"p": precio, "f": fecha},
                )
        init()
        p = session.query(Producto).one()
        assert p.precio == 95.0
        assert [h.precio for h in p.historial] == [80.0, 95.0]


class TestRelevancia:
    def test_primero_lo_que_empieza_con_lo_buscado(self):
        guardar_productos(
            [
                PS(supermercado="Ta-Ta", nombre="Galletas de Arroz 150 g", precio=60.0),
                PS(supermercado="Ta-Ta", nombre="Condimento para Arroz 15 g", precio=50.0),
                PS(supermercado="Ta-Ta", nombre="Arroz Saman 1 kg", precio=70.0),
            ]
        )
        assert buscar_productos("arroz")[0].nombre == "Arroz Saman 1 kg"
        assert comparar_productos("arroz")[0]["nombre"] == "Arroz Saman 1 kg"


class TestRenormalizar:
    def test_recalcula_medida(self, session):
        guardar_productos([PS(supermercado="A", nombre="Cerveza Patricia 6 x 1 L", precio=650.0)])
        prod = session.query(Producto).one()
        prod.medida = "1000ml"  # como lo guardaba la versión anterior
        session.commit()
        assert renormalizar() == 1
        session.expire_all()
        assert session.query(Producto).one().medida == "6x1000ml"
        assert renormalizar() == 0
