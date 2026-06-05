import logging

import click

from precios_uy.cache import is_cache_fresh, mark_scrape
from precios_uy.config import setup_logging
from precios_uy.database import (
    init,
    guardar_productos,
    obtener_ultimos_precios,
    buscar_productos,
    obtener_supermercados,
    comparar_productos,
)
from precios_uy.scrapers import get_all_scrapers, get_scraper
from precios_uy.scheduler import scheduler, ejecutar_scraping

logger = logging.getLogger(__name__)
setup_logging()


@click.group()
def cli():
    """Precios UY — Consulta precios de supermercados de Uruguay."""
    init()


@cli.command()
def scrapear():
    """Ejecuta scraping de todos los supermercados una vez."""
    if is_cache_fresh():
        click.echo("Datos aún frescos. Usá --force para rescrapear o ajustá CACHE_TTL_HOURS.")
        return
    ejecutar_scraping()


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
