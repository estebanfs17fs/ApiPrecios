import os
import tempfile
from typing import Generator

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from precios_uy import database, models
from precios_uy.api.server import app
from precios_uy.database import init
from precios_uy.models import Base, Producto

_test_db_file = tempfile.mktemp(suffix=".db")
TEST_DATABASE_URL = f"sqlite:///{_test_db_file}"


@pytest.fixture(autouse=True)
def _test_database():
    original_url = models.settings.database_url
    original_timeout = models.settings.request_timeout
    models.settings.database_url = TEST_DATABASE_URL
    models.settings.request_timeout = 1

    engine = create_engine(TEST_DATABASE_URL, echo=False)
    test_session = sessionmaker(bind=engine)

    original_engine = models.engine
    original_session = models.SessionLocal
    original_db_session = database.SessionLocal
    models.engine = engine
    models.SessionLocal = test_session
    database.SessionLocal = test_session

    Base.metadata.create_all(engine)
    init()

    yield

    Base.metadata.drop_all(engine)
    engine.dispose()
    if os.path.exists(_test_db_file):
        os.remove(_test_db_file)

    models.engine = original_engine
    models.SessionLocal = original_session
    database.SessionLocal = original_db_session
    models.settings.database_url = original_url
    models.settings.request_timeout = original_timeout


@pytest.fixture
def session() -> Generator[Session, None, None]:
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def productos_db(session: Session):
    items = [
        Producto(
            supermercado="Disco",
            nombre="Arroz 1kg",
            precio=120.0,
            categoria="Almacén",
            url_producto="https://disco.com.uy/arroz",
            url_imagen="https://disco.com.uy/img/arroz.jpg",
        ),
        Producto(
            supermercado="Disco",
            nombre="Leche 1L",
            precio=80.0,
            categoria="Lácteos",
        ),
        Producto(
            supermercado="Tienda Inglesa",
            nombre="Arroz 1kg",
            precio=130.0,
            categoria="Almacén",
        ),
        Producto(
            supermercado="Tienda Inglesa",
            nombre="Pan 500g",
            precio=65.0,
            categoria="Panadería",
        ),
    ]
    for p in items:
        session.add(p)
    session.commit()
    return items
