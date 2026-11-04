"""
Normalización de nombres de productos para poder reconocer el mismo producto
en distintos supermercados (cada uno escribe el nombre a su manera).

Estrategia:
1. Si ambos productos tienen código de barras (EAN), se comparan por EAN.
2. Si no, se compara la medida (1 kg == 1000 g == 1000 gr) y la similitud
   de las palabras del nombre (sin tildes, mayúsculas ni palabras vacías).
"""

import re
import unicodedata
from typing import Optional, Set

STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "con", "sin", "y", "en", "para", "x",
    "por", "a", "al", "un", "una", "pack", "paquete", "botella", "lata", "caja",
    "bolsa", "frasco", "sachet", "pote", "bandeja", "envase", "unidad", "unidades",
    "uds", "ud",
}

# unidad -> (unidad base, factor)
_UNIDADES = {
    "kg": ("g", 1000), "kgs": ("g", 1000), "kilo": ("g", 1000), "kilos": ("g", 1000),
    "g": ("g", 1), "gr": ("g", 1), "grs": ("g", 1), "gramos": ("g", 1),
    "l": ("ml", 1000), "lt": ("ml", 1000), "lts": ("ml", 1000), "litro": ("ml", 1000),
    "litros": ("ml", 1000),
    "ml": ("ml", 1), "cc": ("ml", 1), "cm3": ("ml", 1),
    "un": ("un", 1), "u": ("un", 1), "unid": ("un", 1), "unidades": ("un", 1),
    "uds": ("un", 1),
}

_RE_MEDIDA = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(sorted(_UNIDADES, key=len, reverse=True)) + r")\b"
)
_RE_EAN = re.compile(r"^\d{8,14}$")


def quitar_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(texto: str) -> str:
    texto = quitar_tildes(texto or "").lower()
    texto = re.sub(r"[^a-z0-9.,\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


_UNIDADES_PESO_VOLUMEN = [u for u, (base, _) in _UNIDADES.items() if base != "un"]
_U = "|".join(sorted(_UNIDADES_PESO_VOLUMEN, key=len, reverse=True))
_NUM = r"\d+(?:[.,]\d+)?"
# packs: "6 x 500 g", "500 g x 6", "pack x 6", "x6", "x 3 un"
_RE_PACKS = [
    re.compile(rf"\b(\d+)\s*x\s*{_NUM}\s*(?:{_U})\b"),
    re.compile(rf"{_NUM}\s*(?:{_U})\s*x\s*(\d+)\b"),
    re.compile(r"\b(?:pack|paquete|display|caja|bandeja)\s*(?:x|de)?\s*(\d+)\b"),
    re.compile(rf"\bx\s*(\d+)(?![.,]?\d*\s*(?:{_U})\b)"),
]


def extraer_cantidad(texto: str) -> int:
    """Cuántas unidades trae el pack: 'Pack x 6 Agua 500 ml' -> 6. 1 si no es pack."""
    t = normalizar_texto(texto)
    for patron in _RE_PACKS:
        m = patron.search(t)
        if m:
            n = int(m.group(1))
            if 2 <= n <= 100:
                return n
    return 1


def extraer_medida(texto: str) -> Optional[str]:
    """
    Devuelve la medida normalizada, p. ej. '1 Kg' -> '1000g', '1,5L' -> '1500ml'.
    Los packs llevan la cantidad adelante: 'Agua 500 ml pack x 6' -> '6x500ml',
    así no se confunden con la unidad suelta.
    """
    t = normalizar_texto(texto)
    medidas = list(_RE_MEDIDA.finditer(t))
    if not medidas:
        return None
    # preferir peso o volumen antes que "unidades"
    m = next((x for x in medidas if _UNIDADES[x.group(2)][0] != "un"), medidas[0])
    valor = float(m.group(1).replace(",", "."))
    base, factor = _UNIDADES[m.group(2)]
    total = valor * factor
    total_txt = str(int(total)) if total == int(total) else f"{total:g}"
    medida = f"{total_txt}{base}"
    cantidad = extraer_cantidad(texto)
    if base != "un" and cantidad > 1:
        medida = f"{cantidad}x{medida}"
    return medida


def tokens(texto: str) -> Set[str]:
    """Palabras significativas del nombre, sin la medida ni palabras vacías."""
    limpio = _RE_MEDIDA.sub(" ", normalizar_texto(texto))
    limpio = re.sub(r"[.,]", " ", limpio)
    return {t for t in limpio.split() if t not in STOPWORDS and len(t) > 1}


def nombre_normalizado(texto: str) -> str:
    return " ".join(sorted(tokens(texto)))


def ean_valido(ean: Optional[str]) -> Optional[str]:
    if not ean:
        return None
    ean = str(ean).strip()
    return ean if _RE_EAN.match(ean) else None


def similitud(
    nombre_a: str,
    nombre_b: str,
    medida_a: Optional[str] = None,
    medida_b: Optional[str] = None,
) -> float:
    """
    Similitud entre 0 y 1. Si las dos medidas son conocidas y distintas, son
    productos distintos (0). Las palabras se comparan con Jaccard.
    """
    if medida_a and medida_b and medida_a != medida_b:
        return 0.0
    ta, tb = set(nombre_a.split()), set(nombre_b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
