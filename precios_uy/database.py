import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, case, func, inspect, literal, or_, text

from precios_uy import models
from precios_uy.models import HistorialPrecio, Producto, ProductoScrapeado, init_db
from precios_uy.normalizacion import (
    ean_valido,
    extraer_medida,
    nombre_normalizado,
    normalizar_texto,
    similitud,
    tokens,
)

logger = logging.getLogger(__name__)

# similitud mínima para considerar que dos nombres son el mismo producto
UMBRAL_SIMILITUD = 0.6
# si solo uno de los dos tiene medida, no se puede confirmar que sea la misma
# presentación y se pide más parecido en el nombre
UMBRAL_SIN_MEDIDA = 0.8


def _umbral(medida_a: Optional[str], medida_b: Optional[str]) -> float:
    return UMBRAL_SIN_MEDIDA if bool(medida_a) != bool(medida_b) else UMBRAL_SIMILITUD


def SessionLocal():
    # se resuelve en cada llamada para que los tests puedan reemplazar la sesión
    return models.SessionLocal()


def _identificador(p: ProductoScrapeado) -> str:
    if p.sku:
        return f"sku:{p.sku}"[:500]
    if p.url_producto:
        return p.url_producto[:500]
    return f"nombre:{nombre_normalizado(p.nombre)}|{extraer_medida(p.nombre) or ''}"[:500]


def guardar_productos(
    productos: Iterable[ProductoScrapeado], fecha: Optional[datetime] = None
) -> int:
    """
    Inserta o actualiza los productos. Solo agrega una fila al historial de precios
    cuando el producto es nuevo o su precio cambió, así la base no crece en cada scrapeo.
    """
    fecha = fecha or datetime.now()
    return _guardar([(p, fecha) for p in productos])


def _guardar(pares: List[Tuple[ProductoScrapeado, datetime]]) -> int:
    if not pares:
        return 0
    session = SessionLocal()
    try:
        por_super: Dict[str, Dict[str, Producto]] = {}
        procesados = 0
        for p, fecha in pares:
            if p.precio is None or p.precio <= 0 or not p.nombre:
                continue
            existentes = por_super.get(p.supermercado)
            if existentes is None:
                existentes = {
                    e.identificador: e
                    for e in session.query(Producto).filter(
                        Producto.supermercado == p.supermercado
                    )
                }
                por_super[p.supermercado] = existentes

            ident = _identificador(p)
            prod = existentes.get(ident)
            if prod is None:
                prod = Producto(supermercado=p.supermercado, identificador=ident, creado=fecha)
                session.add(prod)
                existentes[ident] = prod
                cambio = True
            else:
                cambio = prod.precio != p.precio or prod.precio_anterior != p.precio_anterior

            prod.nombre = p.nombre.strip()[:300]
            prod.nombre_normalizado = nombre_normalizado(p.nombre)[:300]
            prod.medida = extraer_medida(p.nombre)
            prod.ean = ean_valido(p.ean) or prod.ean
            prod.precio = p.precio
            prod.precio_anterior = p.precio_anterior
            prod.categoria = p.categoria or prod.categoria
            prod.marca = p.marca or prod.marca
            prod.url_producto = p.url_producto or prod.url_producto
            prod.url_imagen = p.url_imagen or prod.url_imagen
            prod.actualizado = fecha
            if cambio:
                prod.historial.append(
                    HistorialPrecio(precio=p.precio, precio_anterior=p.precio_anterior, fecha=fecha)
                )
            procesados += 1
        session.commit()
        return procesados
    finally:
        session.close()


def obtener_ultimos_precios(
    supermercado: Optional[str] = None,
    categoria: Optional[str] = None,
    limite: int = 50,
) -> List[Producto]:
    session = SessionLocal()
    try:
        q = session.query(Producto)
        if supermercado:
            q = q.filter(Producto.supermercado == supermercado)
        if categoria:
            q = q.filter(Producto.categoria == categoria)
        return q.order_by(Producto.supermercado, Producto.nombre).limit(limite).all()
    finally:
        session.close()


def _filtro_texto(termino: str):
    """Todas las palabras del término deben aparecer (sin importar tildes ni orden)."""
    palabras = tokens(termino)
    medida = extraer_medida(termino)
    condiciones = [Producto.nombre_normalizado.like(f"%{t}%") for t in palabras]
    if medida:
        condiciones.append(Producto.medida == medida)
    if not condiciones:
        condiciones.append(Producto.nombre.ilike(f"%{termino.strip()}%"))
    return and_(*condiciones)


def buscar_productos(
    termino: str,
    limite: int = 20,
    supermercados: Optional[List[str]] = None,
) -> List[Producto]:
    session = SessionLocal()
    try:
        q = session.query(Producto).filter(_filtro_texto(termino))
        if supermercados:
            q = q.filter(Producto.supermercado.in_(supermercados))
        return q.order_by(_relevancia(termino), Producto.precio).limit(limite).all()
    finally:
        session.close()


def _relevancia(termino: str):
    """0 si el nombre empieza con la primera palabra buscada ("arroz" -> "Arroz Saman"),
    1 si no ("Galletas de arroz"), para que lo buscado aparezca antes que lo que solo
    lo menciona."""
    palabras = termino.split()
    if not palabras:
        return literal(0)
    return case((Producto.nombre.ilike(f"{palabras[0]}%"), 0), else_=1)


def obtener_producto(producto_id: int) -> Optional[Producto]:
    session = SessionLocal()
    try:
        return session.get(Producto, producto_id)
    finally:
        session.close()


def obtener_historial(producto_id: int) -> List[HistorialPrecio]:
    session = SessionLocal()
    try:
        return (
            session.query(HistorialPrecio)
            .filter(HistorialPrecio.producto_id == producto_id)
            .order_by(HistorialPrecio.fecha)
            .all()
        )
    finally:
        session.close()


def obtener_supermercados() -> List[str]:
    session = SessionLocal()
    try:
        resultados = session.query(Producto.supermercado).distinct().all()
        return sorted(r[0] for r in resultados)
    finally:
        session.close()


def obtener_categorias(supermercado: Optional[str] = None) -> List[str]:
    session = SessionLocal()
    try:
        q = session.query(Producto.categoria).distinct()
        if supermercado:
            q = q.filter(Producto.supermercado == supermercado)
        resultados = q.all()
        return sorted(r[0] for r in resultados if r[0])
    finally:
        session.close()


def son_equivalentes(a: Producto, b: Producto) -> bool:
    if a.ean and b.ean:
        return a.ean == b.ean
    return similitud(
        a.nombre_normalizado or "", b.nombre_normalizado or "", a.medida, b.medida
    ) >= _umbral(a.medida, b.medida)


def agrupar_equivalentes(productos: List[Producto]) -> List[List[Producto]]:
    """
    Agrupa productos que parecen ser el mismo en distintos supermercados.

    Un producto entra a un grupo solo si es equivalente a todos sus miembros: si
    bastara con parecerse a uno, un nombre sin medida ("Arroz blanco") uniría el
    paquete de 500 g con el de 1 kg.
    """
    grupos: List[List[Producto]] = []
    # primero los que traen EAN y medida, que son los que mejor definen el grupo
    for p in sorted(productos, key=lambda x: (not x.ean, not x.medida)):
        mejor, mejor_score = None, 0.0
        for grupo in grupos:
            if not all(son_equivalentes(p, g) for g in grupo):
                continue
            score = sum(
                similitud(p.nombre_normalizado or "", g.nombre_normalizado or "")
                for g in grupo
            ) / len(grupo)
            if score > mejor_score:
                mejor, mejor_score = grupo, score
        if mejor is None:
            grupos.append([p])
        else:
            mejor.append(p)
    # se devuelven en el orden en que llegaron (por relevancia de la búsqueda)
    orden = {id(p): i for i, p in enumerate(productos)}
    return sorted(grupos, key=lambda g: min(orden[id(p)] for p in g))


def comparar_productos(termino: str, limite: int = 300) -> List[dict]:
    """
    Busca un término y agrupa los resultados equivalentes entre supermercados.
    Cada grupo trae las ofertas ordenadas por precio.
    """
    productos = buscar_productos(termino, limite=limite)
    grupos = []
    for grupo in agrupar_equivalentes(productos):
        # si un supermercado aparece dos veces en un grupo, se queda la más barata
        mejores: Dict[str, Producto] = {}
        for p in sorted(grupo, key=lambda x: x.precio):
            mejores.setdefault(p.supermercado, p)
        ofertas = sorted(mejores.values(), key=lambda x: x.precio)
        principal = ofertas[0]
        # para mostrar, mejor un nombre que no esté todo en mayúsculas
        nombre = next((p.nombre for p in ofertas if not p.nombre.isupper()), principal.nombre)
        grupos.append(
            {
                "nombre": nombre,
                "medida": principal.medida,
                "ean": next((p.ean for p in ofertas if p.ean), None),
                "url_imagen": next((p.url_imagen for p in ofertas if p.url_imagen), None),
                "precio_min": principal.precio,
                "precio_max": ofertas[-1].precio,
                "supermercado_mas_barato": principal.supermercado,
                "ofertas": [p.to_dict() for p in ofertas],
            }
        )
    primera = normalizar_texto(termino).split()[:1]

    def relevancia(g):
        empieza = bool(primera) and normalizar_texto(g["nombre"]).startswith(primera[0])
        return (0 if empieza else 1, -len(g["ofertas"]), g["precio_min"])

    grupos.sort(key=relevancia)
    return grupos


def _equivalente_en(session, ref: Producto, supermercado: str) -> Optional[Producto]:
    if ref.supermercado == supermercado:
        return ref
    q = session.query(Producto).filter(Producto.supermercado == supermercado)
    if ref.ean:
        por_ean = q.filter(Producto.ean == ref.ean).order_by(Producto.precio).first()
        if por_ean:
            return por_ean
    palabras = (ref.nombre_normalizado or "").split()
    if not palabras:
        return None
    candidatos = q.filter(
        or_(*[Producto.nombre_normalizado.like(f"%{t}%") for t in palabras])
    )
    if ref.medida:
        candidatos = candidatos.filter(
            or_(Producto.medida == ref.medida, Producto.medida.is_(None))
        )
    mejor, mejor_score = None, 0.0
    for c in candidatos.limit(1000):
        if ref.ean and c.ean and ref.ean != c.ean:
            continue
        score = similitud(ref.nombre_normalizado, c.nombre_normalizado or "", ref.medida, c.medida)
        if score < _umbral(ref.medida, c.medida):
            continue
        if score > mejor_score or (
            score == mejor_score and mejor is not None and c.precio < mejor.precio
        ):
            mejor, mejor_score = c, score
    return mejor


def opciones_producto(
    producto_id: int, supermercados: Optional[List[str]] = None
) -> Optional[List[dict]]:
    """
    El producto y su equivalente en cada supermercado, ordenados por precio.
    Devuelve None si el producto no existe.
    """
    session = SessionLocal()
    try:
        ref = session.get(Producto, producto_id)
        if ref is None:
            return None
        sups = [
            r[0]
            for r in session.query(Producto.supermercado).distinct()
            if not supermercados or r[0] in supermercados
        ]
        encontrados = [_equivalente_en(session, ref, s) for s in sups]
        return [p.to_dict() for p in sorted((p for p in encontrados if p), key=lambda p: p.precio)]
    finally:
        session.close()


def _mas_barato_por_texto(session, texto: str, supermercado: str) -> Optional[Producto]:
    return (
        session.query(Producto)
        .filter(Producto.supermercado == supermercado, _filtro_texto(texto))
        .order_by(Producto.precio)
        .first()
    )


def _mismo_producto_por_texto(session, texto: str, sups: List[str]) -> Dict[str, Producto]:
    """
    Entre lo que coincide con el texto, elige un mismo producto para comparar en
    todos los supermercados, así "leche 1 l" no compara la entera en uno con la
    descremada en otro. Se busca entre los que están en casi todos (a lo sumo uno
    menos que el que más cobertura tiene) el más barato en promedio: si solo se
    mirara la cobertura, "arroz 1 kg" terminaría eligiendo un risotto importado.
    """
    candidatos = (
        session.query(Producto)
        .filter(Producto.supermercado.in_(sups), _filtro_texto(texto))
        .order_by(_relevancia(texto), Producto.precio)
        .limit(300)
        .all()
    )
    opciones: List[Dict[str, Producto]] = []
    for grupo in agrupar_equivalentes(candidatos):
        por_super: Dict[str, Producto] = {}
        for p in sorted(grupo, key=lambda x: x.precio):
            por_super.setdefault(p.supermercado, p)
        opciones.append(por_super)
    if not opciones:
        return {}
    cobertura = max(len(o) for o in opciones)
    minima = max(1, cobertura - 1) if cobertura > 2 else cobertura
    return min(
        (o for o in opciones if len(o) >= minima),
        key=lambda o: (sum(p.precio for p in o.values()) / len(o), -len(o)),
    )


def comparar_lista(items: List[dict], supermercados: Optional[List[str]] = None) -> dict:
    """
    Compara una lista de compras entre supermercados.

    Cada item es {"producto_id": int, "cantidad": float} (busca ese producto o su
    equivalente en cada supermercado) o {"texto": str, "cantidad": float}
    (toma el producto que coincide con el texto y está en más supermercados; donde
    no está, el más barato que coincida, marcado como "aproximado").
    """
    session = SessionLocal()
    try:
        disponibles = [
            r[0] for r in session.query(Producto.supermercado).distinct().order_by(
                Producto.supermercado
            )
        ]
        sups = [s for s in disponibles if not supermercados or s in supermercados]

        descripciones = []
        refs: List[Optional[Producto]] = []
        for item in items:
            ref = session.get(Producto, item["producto_id"]) if item.get("producto_id") else None
            refs.append(ref)
            descripciones.append(ref.nombre if ref else (item.get("texto") or "?"))

        mismos = [
            _mismo_producto_por_texto(session, item["texto"], sups)
            if refs[i] is None and item.get("texto")
            else {}
            for i, item in enumerate(items)
        ]

        # matriz[supermercado][indice] -> Producto encontrado
        matriz: Dict[str, Dict[int, Producto]] = {s: {} for s in sups}
        # (supermercado, indice) donde no estaba el mismo producto y se tomó otro parecido
        aproximados = set()
        for s in sups:
            for i, item in enumerate(items):
                ref = refs[i]
                if ref is not None:
                    encontrado = _equivalente_en(session, ref, s)
                elif s in mismos[i]:
                    encontrado = mismos[i][s]
                elif item.get("texto"):
                    encontrado = _mas_barato_por_texto(session, item["texto"], s)
                    if encontrado is not None:
                        aproximados.add((s, i))
                else:
                    encontrado = None
                if encontrado is not None:
                    matriz[s][i] = encontrado

        def detalle(i: int, p: Producto) -> dict:
            cantidad = items[i].get("cantidad", 1) or 1
            return {
                "indice": i,
                "cantidad": cantidad,
                "producto": p.to_dict(),
                "subtotal": round(p.precio * cantidad, 2),
                "aproximado": (p.supermercado, i) in aproximados,
            }

        resumen = []
        for s in sups:
            filas = [detalle(i, p) for i, p in sorted(matriz[s].items())]
            resumen.append(
                {
                    "supermercado": s,
                    "total": round(sum(f["subtotal"] for f in filas), 2),
                    "encontrados": len(filas),
                    "faltantes": [i for i in range(len(items)) if i not in matriz[s]],
                    "detalle": filas,
                }
            )
        resumen.sort(key=lambda r: (len(r["faltantes"]), r["total"]))

        completos = [r for r in resumen if not r["faltantes"]]
        recomendado = completos[0]["supermercado"] if completos else None

        optima, faltantes_optima = [], []
        for i in range(len(items)):
            opciones = [matriz[s][i] for s in sups if i in matriz[s]]
            # un "aproximado" es otro producto: solo cuenta si no hay del mismo
            exactos = [p for p in opciones if (p.supermercado, i) not in aproximados]
            opciones = exactos or opciones
            if opciones:
                optima.append(detalle(i, min(opciones, key=lambda p: p.precio)))
            else:
                faltantes_optima.append(i)

        # la combinación óptima como una lista de compras por supermercado
        por_super: Dict[str, List[dict]] = {}
        for fila in optima:
            por_super.setdefault(fila["producto"]["supermercado"], []).append(fila)
        listas_por_super = sorted(
            (
                {
                    "supermercado": s,
                    "total": round(sum(f["subtotal"] for f in filas), 2),
                    "detalle": filas,
                }
                for s, filas in por_super.items()
            ),
            key=lambda x: (-len(x["detalle"]), -x["total"]),
        )

        return {
            "items": [
                {"indice": i, "descripcion": descripciones[i], "cantidad": it.get("cantidad", 1)}
                for i, it in enumerate(items)
            ],
            "supermercados": resumen,
            "recomendado": recomendado,
            "combinacion_optima": {
                "total": round(sum(f["subtotal"] for f in optima), 2),
                "detalle": optima,
                "faltantes": faltantes_optima,
                "por_supermercado": listas_por_super,
            },
        }
    finally:
        session.close()


def migrar_v1() -> int:
    """Pasa los datos de la tabla vieja `productos_v1` al esquema nuevo."""
    engine = models.engine
    if "productos_v1" not in inspect(engine).get_table_names():
        return 0
    with engine.connect() as conn:
        filas = conn.execute(
            text(
                "SELECT supermercado, nombre, precio, precio_anterior, categoria, marca, "
                "url_producto, url_imagen, fecha_scraping FROM productos_v1 "
                "ORDER BY fecha_scraping"
            )
        ).fetchall()
    pares = []
    for fila in filas:
        fecha = fila[8]
        if isinstance(fecha, str):
            fecha = datetime.fromisoformat(fecha)
        pares.append((ProductoScrapeado(*fila[:8]), fecha or datetime.now()))
    total = _guardar(pares)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE productos_v1"))
    logger.info("Migradas %d filas del esquema anterior", total)
    return total


def renormalizar() -> int:
    """
    Recalcula el nombre normalizado y la medida de todos los productos guardados,
    para aplicar cambios en las reglas de normalización sin volver a scrapear.
    Devuelve cuántos cambiaron.
    """
    session = SessionLocal()
    try:
        cambiados = 0
        for prod in session.query(Producto):
            nombre = nombre_normalizado(prod.nombre)[:300]
            medida = extraer_medida(prod.nombre)
            if (nombre, medida) != (prod.nombre_normalizado, prod.medida):
                prod.nombre_normalizado, prod.medida = nombre, medida
                cambiados += 1
        session.commit()
        return cambiados
    finally:
        session.close()


def contar_productos() -> int:
    session = SessionLocal()
    try:
        return session.query(func.count(Producto.id)).scalar() or 0
    finally:
        session.close()


def init():
    if init_db():
        migrar_v1()
