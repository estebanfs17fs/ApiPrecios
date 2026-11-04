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


# si un precio es más del triple que el otro, casi seguro no es el mismo producto
# (un pack contra la unidad, o una presentación distinta que el nombre no aclara)
MAX_RELACION_PRECIOS = 3.0


def precios_compatibles(a: float, b: float) -> bool:
    if not a or not b:
        return True
    return max(a, b) / min(a, b) <= MAX_RELACION_PRECIOS


def son_equivalentes(a: Producto, b: Producto) -> bool:
    if a.ean and b.ean:
        return a.ean == b.ean
    return (
        precios_compatibles(a.precio, b.precio)
        and similitud(a.nombre_normalizado or "", b.nombre_normalizado or "", a.medida, b.medida)
        >= UMBRAL_SIMILITUD
    )


def agrupar_equivalentes(productos: List[Producto]) -> List[List[Producto]]:
    """Agrupa productos que parecen ser el mismo en distintos supermercados."""
    padre = list(range(len(productos)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for i in range(len(productos)):
        for j in range(i + 1, len(productos)):
            if productos[i].supermercado != productos[j].supermercado and son_equivalentes(
                productos[i], productos[j]
            ):
                padre[raiz(i)] = raiz(j)

    grupos: Dict[int, List[Producto]] = {}
    for i, p in enumerate(productos):
        grupos.setdefault(raiz(i), []).append(p)
    return list(grupos.values())


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
        if not precios_compatibles(ref.precio, c.precio):
            continue
        score = similitud(ref.nombre_normalizado, c.nombre_normalizado or "", ref.medida, c.medida)
        if score > mejor_score or (
            score == mejor_score and mejor is not None and c.precio < mejor.precio
        ):
            mejor, mejor_score = c, score
    return mejor if mejor_score >= UMBRAL_SIMILITUD else None


def _mas_barato_por_texto(session, texto: str, supermercado: str) -> Optional[Producto]:
    return (
        session.query(Producto)
        .filter(Producto.supermercado == supermercado, _filtro_texto(texto))
        .order_by(Producto.precio)
        .first()
    )


def comparar_lista(items: List[dict], supermercados: Optional[List[str]] = None) -> dict:
    """
    Compara una lista de compras entre supermercados.

    Cada item es {"producto_id": int, "cantidad": float} (busca ese producto o su
    equivalente en cada supermercado) o {"texto": str, "cantidad": float}
    (toma el más barato que coincida con el texto).
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

        # matriz[supermercado][indice] -> Producto encontrado
        matriz: Dict[str, Dict[int, Producto]] = {s: {} for s in sups}
        for s in sups:
            for i, item in enumerate(items):
                ref = refs[i]
                if ref is not None:
                    encontrado = _equivalente_en(session, ref, s)
                elif item.get("texto"):
                    encontrado = _mas_barato_por_texto(session, item["texto"], s)
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
            if opciones:
                optima.append(detalle(i, min(opciones, key=lambda p: p.precio)))
            else:
                faltantes_optima.append(i)

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
    """Recalcula nombre normalizado y medida de todos los productos (tras cambiar las reglas)."""
    session = SessionLocal()
    try:
        cambiados = 0
        for p in session.query(Producto).yield_per(2000):
            nn, medida = nombre_normalizado(p.nombre)[:300], extraer_medida(p.nombre)
            if p.nombre_normalizado != nn or p.medida != medida:
                p.nombre_normalizado, p.medida = nn, medida
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
