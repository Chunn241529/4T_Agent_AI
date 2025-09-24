# app/utils/cache.py

from cachetools import TTLCache
from app.config import settings

cache = TTLCache(maxsize=settings.MAX_CACHE_SIZE, ttl=settings.CACHE_TTL_SECONDS)
