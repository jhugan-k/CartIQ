"""Async Redis client + search-cache helpers.

Redis is an in-memory key-value store. We use it to cache /search results so a
repeated search (same query + location) within the TTL is served from memory
instead of spending a QuickCommerce credit.

The client is a module-level singleton — one connection pool for the whole app,
created lazily on first use, rather than a new pool per request.
"""

import json

import redis.asyncio as redis

from config import settings

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the shared Redis client, creating it on first call."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def search_cache_key(query: str, lat: float, lon: float, pincode: str | None) -> str:
    """Stable cache key. Includes location so results from different places
    don't collide (prices are location-specific)."""
    return f"search:{query.lower().strip()}:{lat}:{lon}:{pincode or ''}"


async def get_cache(key: str):
    """Return the decoded JSON value for a key, or None on miss / any error."""
    try:
        raw = await get_redis().get(key)
    except redis.RedisError:
        return None  # cache is a best-effort optimization; never fail the request
    return json.loads(raw) if raw else None


async def set_cache(key: str, value, ttl: int | None = None) -> None:
    """Store a JSON-serializable value with a TTL (defaults to configured TTL)."""
    ttl = ttl if ttl is not None else settings.cache_ttl_seconds
    try:
        await get_redis().set(key, json.dumps(value), ex=ttl)
    except redis.RedisError:
        pass  # swallow — caching failures must not break the endpoint
