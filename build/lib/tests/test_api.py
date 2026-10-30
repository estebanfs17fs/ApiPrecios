

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
    def test_lanza_en_segundo_plano(self, client, monkeypatch):
        llamado = {}
        monkeypatch.setattr(
            "precios_uy.api.routes.ejecutar_scraping",
            lambda sups=None: llamado.setdefault("sups", sups),
        )
        monkeypatch.setattr("precios_uy.api.routes.is_cache_fresh", lambda: False)
        resp = client.post("/api/scrapear?supermercado=disco")
        assert resp.status_code == 202
        assert llamado["sups"] == ["disco"]

    def test_no_scrapea_si_datos_frescos(self, client, monkeypatch):
        monkeypatch.setattr("precios_uy.api.routes.is_cache_fresh", lambda: True)
        resp = client.post("/api/scrapear")
        assert "frescos" in resp.json()["mensaje"]

    def test_estado(self, client):
        resp = client.get("/api/scrapear")
        assert resp.status_code == 200
        assert resp.json()["en_curso"] is False


class TestCompararProductos:
    def test_agrupa_mismo_producto(self, client, productos_db):
        resp = client.get("/api/productos/comparar?q=arroz")
        data = resp.json()
        assert data["total"] == 1
        grupo = data["grupos"][0]
        assert [o["supermercado"] for o in grupo["ofertas"]] == ["Disco", "Tienda Inglesa"]
        assert grupo["precio_min"] == 120.0
        assert grupo["supermercado_mas_barato"] == "Disco"


class TestDetalleProducto:
    def test_detalle_con_historial(self, client, productos_db):
        pid = client.get("/api/productos/buscar?q=leche").json()["productos"][0]["id"]
        resp = client.get(f"/api/productos/{pid}")
        assert resp.status_code == 200
        assert resp.json()["historial"][0]["precio"] == 80.0

    def test_no_existe(self, client):
        assert client.get("/api/productos/9999").status_code == 404


class TestCompararLista:
    def test_compara_lista(self, client, productos_db):
        arroz = client.get("/api/productos/buscar?q=arroz").json()["productos"][0]
        resp = client.post(
            "/api/lista/comparar",
            json={
                "items": [
                    {"producto_id": arroz["id"], "cantidad": 2},
                    {"texto": "leche", "cantidad": 1},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["recomendado"] == "Disco"
        disco = next(s for s in data["supermercados"] if s["supermercado"] == "Disco")
        assert disco["total"] == 2 * 120 + 80
        ti = next(s for s in data["supermercados"] if s["supermercado"] == "Tienda Inglesa")
        assert ti["faltantes"] == [1]
        assert data["combinacion_optima"]["total"] == 320

    def test_item_vacio_es_invalido(self, client):
        resp = client.post("/api/lista/comparar", json={"items": [{"cantidad": 1}]})
        assert resp.status_code == 422


class TestFrontend:
    def test_sirve_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Lista de precios" in resp.text
