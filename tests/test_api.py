import pytest


class TestListarProductos:
    def test_devuelve_lista_vacia_sin_datos(self, client):
        resp = client.get("/api/productos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["productos"] == []

    def test_devuelve_productos(self, client, productos_db):
        resp = client.get("/api/productos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == len(productos_db)

    def test_filtro_por_supermercado(self, client, productos_db):
        resp = client.get("/api/productos?supermercado=Disco")
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["supermercado"] == "Disco" for p in data["productos"])

    def test_filtro_por_categoria(self, client, productos_db):
        resp = client.get("/api/productos?categoria=Lácteos")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["productos"]) == 1
        assert data["productos"][0]["nombre"] == "Leche 1L"

    def test_limite(self, client, productos_db):
        resp = client.get("/api/productos?limite=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_limite_invalido(self, client):
        resp = client.get("/api/productos?limite=999999")
        assert resp.status_code == 422


class TestBuscarProductos:
    def test_buscar_por_termino(self, client, productos_db):
        resp = client.get("/api/productos/buscar?q=Arroz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all("Arroz" in p["nombre"] for p in data["productos"])

    def test_buscar_sin_resultados(self, client, productos_db):
        resp = client.get("/api/productos/buscar?q=xyznoexiste")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_buscar_sin_query(self, client):
        resp = client.get("/api/productos/buscar")
        assert resp.status_code == 422


class TestListarSupermercados:
    def test_sin_datos(self, client):
        resp = client.get("/api/supermercados")
        assert resp.status_code == 200
        assert resp.json()["supermercados"] == []

    def test_con_datos(self, client, productos_db):
        resp = client.get("/api/supermercados")
        assert resp.status_code == 200
        assert sorted(resp.json()["supermercados"]) == sorted(
            ["Disco", "Tienda Inglesa"]
        )


class TestListarCategorias:
    def test_sin_datos(self, client):
        resp = client.get("/api/categorias")
        assert resp.status_code == 200
        assert resp.json()["categorias"] == []

    def test_con_datos(self, client, productos_db):
        resp = client.get("/api/categorias")
        data = resp.json()
        assert sorted(data["categorias"]) == sorted(
            ["Almacén", "Lácteos", "Panadería"]
        )

    def test_filtro_por_supermercado(self, client, productos_db):
        resp = client.get("/api/categorias?supermercado=Disco")
        data = resp.json()
        assert sorted(data["categorias"]) == sorted(["Almacén", "Lácteos"])


class TestScrapear:
    def test_endpoint_existe(self, client):
        resp = client.post("/api/scrapear")
        assert resp.status_code == 200
        data = resp.json()
        assert "resultados" in data
