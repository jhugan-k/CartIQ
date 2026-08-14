"""Search route: GET /search — Redis-cached product search across platforms."""

from fastapi import APIRouter, Query, Request

from rate_limit import limiter
from schemas.compare import DEFAULT_LAT, DEFAULT_LON, DEFAULT_PINCODE
from schemas.search import PlatformResults, SearchResponse
from services import qc_client
from services.redis_client import get_cache, search_cache_key, set_cache

router = APIRouter(tags=["search"])


# search a product across platforms, serving from cache when possible so we
# don't spend a vendor API credit on a repeat query.
#
# This is the shared implementation: a PLAIN async function taking plain args,
# so the agent tools and the MCP server can call it directly. Keep it free of
# Request/Depends — the HTTP concerns (validation, rate limiting) belong to the
# thin route wrapper below, and the non-HTTP callers have no Request to give.
async def search_products(
    q: str,
    platforms: str = "blinkit,zepto,swiggy",
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    pincode: str = DEFAULT_PINCODE,
) -> SearchResponse:
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    key = search_cache_key(q, lat, lon, pincode)

    # 1) Cache hit → return without touching the paid API.
    cached = await get_cache(key)
    if cached is not None:
        return SearchResponse(**cached)

    # 2) Cache miss → call QC (or mock), normalize, cache, return.
    results: list[PlatformResults] = await qc_client.groupsearch(
        q, platform_list, lat, lon, pincode
    )
    response = SearchResponse(query=q, platforms=results)
    await set_cache(key, response.model_dump())
    return response


# Public (no auth) → keyed per IP. Caps vendor-API amplification on cache misses.
@router.get("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search(
    request: Request,
    q: str = Query(min_length=1, description="Product to search for"),
    platforms: str = Query("blinkit,zepto,swiggy", description="Comma-separated"),
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    pincode: str = DEFAULT_PINCODE,
) -> SearchResponse:
    return await search_products(q, platforms, lat, lon, pincode)
