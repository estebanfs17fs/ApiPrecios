"""
Listas de compras guardadas. Cada lista se puede volver a "ejecutar": se compara
con los precios del momento y se guarda el resultado, así se ve cómo cambia el
total y dónde conviene comprar cada cosa con el tiempo.

No hay cuentas: cada navegador se identifica con un id anónimo (`usuario`) y solo
ve sus listas.
"""

import json
from datetime import datetime
from typing import List, Optional

from precios_uy import models
from precios_uy.database import comparar_lista
from precios_uy.models import EjecucionLista, ListaGuardada


def _session():
    return models.SessionLocal()


def _a_dict(lista: ListaGuardada, con_ejecuciones: bool = False) -> dict:
    ultima = lista.ejecuciones[-1] if lista.ejecuciones else None
    datos = {
        "id": lista.id,
        "nombre": lista.nombre,
        "items": json.loads(lista.items),
        "supermercados": json.loads(lista.supermercados) if lista.supermercados else None,
        "creado": lista.creado.isoformat() if lista.creado else None,
        "actualizado": lista.actualizado.isoformat() if lista.actualizado else None,
        "ultima_ejecucion": ultima.resumen() if ultima else None,
    }
    if con_ejecuciones:
        datos["ejecuciones"] = [e.resumen() for e in reversed(lista.ejecuciones)]
    return datos


def _de_usuario(session, usuario: str, lista_id: int) -> Optional[ListaGuardada]:
    lista = session.get(ListaGuardada, lista_id)
    return lista if lista is not None and lista.usuario == usuario else None


def listar(usuario: str) -> List[dict]:
    session = _session()
    try:
        listas = (
            session.query(ListaGuardada)
            .filter(ListaGuardada.usuario == usuario)
            .order_by(ListaGuardada.actualizado.desc())
            .all()
        )
        return [_a_dict(lista) for lista in listas]
    finally:
        session.close()


def obtener(usuario: str, lista_id: int) -> Optional[dict]:
    session = _session()
    try:
        lista = _de_usuario(session, usuario, lista_id)
        return _a_dict(lista, con_ejecuciones=True) if lista else None
    finally:
        session.close()


def crear(usuario: str, nombre: str, items: List[dict], supermercados=None) -> dict:
    session = _session()
    try:
        lista = ListaGuardada(
            usuario=usuario,
            nombre=nombre,
            items=json.dumps(items, ensure_ascii=False),
            supermercados=json.dumps(supermercados) if supermercados else None,
        )
        session.add(lista)
        session.commit()
        return _a_dict(lista)
    finally:
        session.close()


def actualizar(
    usuario: str, lista_id: int, nombre: str, items: List[dict], supermercados=None
) -> Optional[dict]:
    session = _session()
    try:
        lista = _de_usuario(session, usuario, lista_id)
        if lista is None:
            return None
        lista.nombre = nombre
        lista.items = json.dumps(items, ensure_ascii=False)
        lista.supermercados = json.dumps(supermercados) if supermercados else None
        lista.actualizado = datetime.now()
        session.commit()
        return _a_dict(lista, con_ejecuciones=True)
    finally:
        session.close()


def borrar(usuario: str, lista_id: int) -> bool:
    session = _session()
    try:
        lista = _de_usuario(session, usuario, lista_id)
        if lista is None:
            return False
        session.delete(lista)
        session.commit()
        return True
    finally:
        session.close()


def ejecutar(usuario: str, lista_id: int) -> Optional[dict]:
    """Compara la lista con los precios actuales y guarda el resultado."""
    session = _session()
    try:
        lista = _de_usuario(session, usuario, lista_id)
        if lista is None:
            return None
        items = json.loads(lista.items)
        supermercados = json.loads(lista.supermercados) if lista.supermercados else None
        resultado = comparar_lista(items, supermercados)
        total_recomendado = next(
            (
                s["total"]
                for s in resultado["supermercados"]
                if s["supermercado"] == resultado["recomendado"]
            ),
            None,
        )
        ejecucion = EjecucionLista(
            lista_id=lista.id,
            total_optimo=resultado["combinacion_optima"]["total"],
            recomendado=resultado["recomendado"],
            total_recomendado=total_recomendado,
            resultado=json.dumps(resultado, ensure_ascii=False),
        )
        session.add(ejecucion)
        session.commit()
        return {**resultado, "ejecucion": ejecucion.resumen()}
    finally:
        session.close()


def obtener_ejecucion(usuario: str, lista_id: int, ejecucion_id: int) -> Optional[dict]:
    session = _session()
    try:
        lista = _de_usuario(session, usuario, lista_id)
        ejecucion = session.get(EjecucionLista, ejecucion_id)
        if lista is None or ejecucion is None or ejecucion.lista_id != lista.id:
            return None
        return {**json.loads(ejecucion.resultado), "ejecucion": ejecucion.resumen()}
    finally:
        session.close()
