from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from precios_uy.api.routes import router
from precios_uy.config import settings, setup_logging
from precios_uy.database import init

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init()
    yield


app = FastAPI(
    title="Precios UY",
    description="API de precios de supermercados de Uruguay",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Frontend: buscar productos, armar la lista y comparar (http://localhost:8000/)
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def run():
    uvicorn.run(
        "precios_uy.api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
