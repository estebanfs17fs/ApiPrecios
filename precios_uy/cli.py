import logging

import click

from precios_uy.cache import is_cache_fresh
from precios_uy.config import setup_logging
from precios_uy.database import (
    buscar_productos,
    comparar_productos,
    init,
    obtener_supermercados,
    obtener_ultimos_precios,
)
from precios_uy.scheduler import ejecutar_scraping, scheduler

logger = logging.getLogger(__name__)
setup_logging()


@click.group()
def cli():
    """Precios UY — Consulta precios de supermercados de Uruguay."""
    init()


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Scrapear aunque los datos estén frescos")
@click.option(
    "--supermercado", "-s", multiple=True, help="Solo este supermercado (p. ej. disco)"
)
def scrapear(force, supermercado):
    """Ejecuta scraping de todos los supermercados una vez."""
    if is_cache_fresh() and not force:
        click.echo("Datos aún frescos. Usá --force para rescrapear o ajustá CACHE_TTL_HOURS.")
        return
    resultados = ejecutar_scraping(list(supermercado) or None)
    for nombre, resultado in resultados.items():
        click.echo(f"{nombre:15s} {resultado}")


@cli.command()
@click.option("--supermercado", "-s", help="Filtrar por supermercado")
@click.option("--categoria", "-c", help="Filtrar por categoría")
@click.option("--limite", "-l", default=20, help="Cantidad máxima de resultados")
def listar(supermercado, categoria, limite):
    """Lista los últimos precios registrados."""
    productos = obtener_ultimos_precios(supermercado, categoria, limite)
    if not productos:
        click.echo("No hay productos registrados. Ejecutá 'scrapear' primero.")
        return

    for p in productos:
        click.echo(
            f"[{p.supermercado:15s}] ${p.precio:>8.2f} — {p.nombre[:60]}"
        )


@cli.command()
@click.argument("termino")
@click.option("--limite", "-l", default=20, help="Cantidad máxima de resultados")
def buscar(termino, limite):
    """Busca productos por nombre."""
    productos = buscar_productos(termino, limite)
    if not productos:
        click.echo(f"No se encontraron productos para '{termino}'.")
        return

    for p in productos:
        click.echo(
            f"[{p.supermercado:15s}] ${p.precio:>8.2f} — {p.nombre[:60]}"
        )


@cli.command()
@click.argument("termino")
def comparar(termino):
    """Muestra el mismo producto en los distintos supermercados."""
    grupos = comparar_productos(termino)
    if not grupos:
        click.echo(f"No se encontraron productos para '{termino}'.")
        return
    for g in grupos[:15]:
        click.echo(f"\n{g['nombre'][:70]}")
        for o in g["ofertas"]:
            click.echo(f"  [{o['supermercado']:15s}] ${o['precio']:>8.2f}  {o['nombre'][:50]}")


@cli.command()
def renormalizar():
    """Recalcula medidas y nombres normalizados (después de actualizar el programa)."""
    from precios_uy.database import renormalizar as _renormalizar

    click.echo(f"{_renormalizar()} productos actualizados")


@cli.command()
def supermercados():
    """Lista los supermercados disponibles en la BD."""
    sups = obtener_supermercados()
    if sups:
        for s in sups:
            click.echo(s)
    else:
        click.echo(
            "No hay datos. Ejecutá 'scrapear' para poblar la base de datos."
        )


@cli.command()
def schedule():
    """Inicia el scheduler para scraping automático cada N horas."""
    click.echo("Iniciando scheduler automático...")
    scheduler.start()
    try:
        import time

        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        click.echo("Deteniendo scheduler...")
        scheduler.shutdown()


def main():
    cli()
