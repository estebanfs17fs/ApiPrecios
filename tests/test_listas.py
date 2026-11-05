"""Listas guardadas: crear, ver, editar, borrar y volver a ejecutarlas con precios nuevos."""

import pytest

from precios_uy.database import guardar_productos
from precios_uy.models import ProductoScrapeado

YO = {"X-Usuario": "usuario-de-prueba-1"}
OTRO = {"X-Usuario": "usuario-de-prueba-2"}


@pytest.fixture
def catalogo():
    guardar_productos(
        [
            ProductoScrapeado("Disco", "Arroz Saman 1 kg", 120, sku="d1"),
            ProductoScrapeado("Ta-Ta", "Arroz Saman 1 Kg", 110, sku="t1"),
            ProductoScrapeado("Devoto", "ARROZ SAMAN 1KG", 125, sku="v1"),
            ProductoScrapeado("Disco", "Leche Conaprole Entera 1 L", 50, sku="d2"),
            ProductoScrapeado("Ta-Ta", "Leche Conaprole Entera 1 L", 55, sku="t2"),
            ProductoScrapeado("Devoto", "Leche Conaprole Entera 1 L", 52, sku="v2"),
        ]
    )


def _id(client, q, supermercado):
    productos = client.get(f"/api/productos/buscar?q={q}").json()["productos"]
    return next(p["id"] for p in productos if p["supermercado"] == supermercado)


def _nueva(client, catalogo_ids, headers=YO):
    arroz, leche = catalogo_ids
    return client.post(
        "/api/listas",
        headers=headers,
        json={
            "nombre": "Semana",
            "items": [
                {"producto_id": arroz, "nombre": "Arroz Saman 1 kg", "cantidad": 2},
                {"producto_id": leche, "nombre": "Leche entera", "cantidad": 3},
            ],
        },
    )


@pytest.fixture
def ids(client, catalogo):
    return _id(client, "arroz", "Disco"), _id(client, "leche", "Ta-Ta")


def test_opciones_de_un_producto_ordenadas_por_precio(client, ids):
    arroz, _ = ids
    r = client.get(f"/api/productos/{arroz}/opciones")
    assert r.status_code == 200
    opciones = r.json()["opciones"]
    assert [o["supermercado"] for o in opciones] == ["Ta-Ta", "Disco", "Devoto"]
    assert [o["precio"] for o in opciones] == [110, 120, 125]

    r = client.get(f"/api/productos/{arroz}/opciones?supermercado=Disco&supermercado=Devoto")
    assert [o["supermercado"] for o in r.json()["opciones"]] == ["Disco", "Devoto"]
    assert client.get("/api/productos/99999/opciones").status_code == 404


def test_crear_listar_y_ver(client, ids):
    r = _nueva(client, ids)
    assert r.status_code == 201
    creada = r.json()
    assert creada["nombre"] == "Semana"
    assert len(creada["items"]) == 2
    assert creada["ultima_ejecucion"] is None

    listas = client.get("/api/listas", headers=YO).json()["listas"]
    assert [lista["id"] for lista in listas] == [creada["id"]]
    detalle = client.get(f"/api/listas/{creada['id']}", headers=YO).json()
    assert detalle["ejecuciones"] == []


def test_cada_usuario_ve_solo_sus_listas(client, ids):
    lista_id = _nueva(client, ids).json()["id"]
    assert client.get("/api/listas", headers=OTRO).json()["listas"] == []
    assert client.get(f"/api/listas/{lista_id}", headers=OTRO).status_code == 404
    assert client.delete(f"/api/listas/{lista_id}", headers=OTRO).status_code == 404
    assert client.post(f"/api/listas/{lista_id}/ejecutar", headers=OTRO).status_code == 404


def test_requiere_usuario_valido(client, ids):
    assert client.get("/api/listas").status_code == 422
    assert client.get("/api/listas", headers={"X-Usuario": "corto"}).status_code == 422


def test_ejecutar_arma_una_lista_por_supermercado_y_guarda_historial(client, ids):
    lista_id = _nueva(client, ids).json()["id"]

    r = client.post(f"/api/listas/{lista_id}/ejecutar", headers=YO)
    assert r.status_code == 200
    res = r.json()
    optima = res["combinacion_optima"]
    # arroz en Ta-Ta (110 x 2) y leche en Disco (50 x 3)
    assert optima["total"] == 370
    por_super = {s["supermercado"]: s for s in optima["por_supermercado"]}
    assert set(por_super) == {"Ta-Ta", "Disco"}
    assert por_super["Ta-Ta"]["total"] == 220
    assert por_super["Disco"]["detalle"][0]["cantidad"] == 3
    # todo en un solo lugar: Ta-Ta 220 + 165 = 385, Disco 240 + 150 = 390
    assert res["recomendado"] == "Ta-Ta"
    assert res["ejecucion"]["total_recomendado"] == 385
    assert res["ejecucion"]["total_optimo"] == 370

    # bajan el arroz en Devoto y se vuelve a ejecutar la misma lista
    guardar_productos([ProductoScrapeado("Devoto", "ARROZ SAMAN 1KG", 100, sku="v1")])
    segunda = client.post(f"/api/listas/{lista_id}/ejecutar", headers=YO).json()
    assert segunda["combinacion_optima"]["total"] == 350
    assert {s["supermercado"] for s in segunda["combinacion_optima"]["por_supermercado"]} == {
        "Devoto",
        "Disco",
    }

    detalle = client.get(f"/api/listas/{lista_id}", headers=YO).json()
    assert [e["total_optimo"] for e in detalle["ejecuciones"]] == [350, 370]
    assert detalle["ultima_ejecucion"]["total_optimo"] == 350

    vieja = detalle["ejecuciones"][1]["id"]
    r = client.get(f"/api/listas/{lista_id}/ejecuciones/{vieja}", headers=YO)
    assert r.json()["combinacion_optima"]["total"] == 370


def test_editar_y_borrar(client, ids):
    lista_id = _nueva(client, ids).json()["id"]
    r = client.put(
        f"/api/listas/{lista_id}",
        headers=YO,
        json={
            "nombre": "Solo leche",
            "items": [{"texto": "leche entera", "nombre": "leche entera", "cantidad": 1}],
            "supermercados": ["Disco", "Ta-Ta"],
        },
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Solo leche"
    assert r.json()["supermercados"] == ["Disco", "Ta-Ta"]

    res = client.post(f"/api/listas/{lista_id}/ejecutar", headers=YO).json()
    assert {s["supermercado"] for s in res["supermercados"]} == {"Disco", "Ta-Ta"}

    assert client.delete(f"/api/listas/{lista_id}", headers=YO).status_code == 204
    assert client.get(f"/api/listas/{lista_id}", headers=YO).status_code == 404
