from datetime import datetime, timedelta
from typing import Optional

from precios_uy.config import settings

_last_scrape: Optional[datetime] = None


def is_cache_fresh() -> bool:
    global _last_scrape
    if _last_scrape is None:
        return False
    ttl = timedelta(hours=settings.cache_ttl_hours)
    return datetime.now() - _last_scrape < ttl


def mark_scrape():
    global _last_scrape
    _last_scrape = datetime.now()


def invalidate_cache():
    global _last_scrape
    _last_scrape = None
