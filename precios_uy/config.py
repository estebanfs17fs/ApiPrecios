import logging
import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///precios_uy.db"
    scrap_interval_hours: int = 6
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    request_timeout: int = 30
    log_level: str = "INFO"
    log_file: str = ""
    cache_ttl_hours: int = 6

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def setup_logging():
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handlers = [logging.StreamHandler(sys.stdout)]

    if settings.log_file:
        from logging.handlers import RotatingFileHandler
        handlers.append(RotatingFileHandler(
            settings.log_file, maxBytes=5*1024*1024, backupCount=3
        ))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


settings = Settings()
