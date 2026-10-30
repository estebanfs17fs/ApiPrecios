from precios_uy.normalizacion import (
    ean_valido,
    extraer_medida,
    nombre_normalizado,
    similitud,
)


def test_medidas_equivalentes():
    assert extraer_medida("Arroz 1 Kg") == "1000g"
    assert extraer_medida("Arroz 1000grs") == "1000g"
    assert extraer_medida("Coca Cola 1,5L") == "1500ml"
    assert extraer_medida("Aceite 900 cc") == "900ml"
    assert extraer_medida("Huevos") is None


def test_nombre_normalizado_ignora_tildes_mayusculas_y_orden():
    assert nombre_normalizado("Azúcar BELLA UNIÓN 1 kg") == nombre_normalizado(
        "bella union azucar 1kg"
    )


def test_similitud():
    a = nombre_normalizado("Arroz Saman Blanco 1kg")
    b = nombre_normalizado("ARROZ SAMAN BLANCO 1 KG")
    assert similitud(a, b, "1000g", "1000g") == 1.0
    assert similitud(a, b, "1000g", "5000g") == 0.0


def test_ean():
    assert ean_valido("7730123000017") == "7730123000017"
    assert ean_valido("abc") is None
    assert ean_valido(None) is None
