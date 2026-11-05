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


def test_packs_llevan_la_cantidad_de_envases():
    assert extraer_medida("Cerveza Pilsen 6 x 1 L") == "6x1000ml"
    assert extraer_medida("Pack x 6 Cerveza 473ml") == "6x473ml"
    assert extraer_medida("Yogur x6 de 120 g") == "6x120g"
    assert extraer_medida("Huevos x 12") == "12un"
    # "x 1 kg" no es un pack, y los metros no son ni medida ni pack
    assert extraer_medida("Arroz x 1 kg") == "1000g"
    assert extraer_medida("Papel higiénico 4 rollos x 30 m") is None


def test_kilo_abreviado():
    assert extraer_medida("Arroz Saman Don Ruggero Verde 1K") == "1000g"
