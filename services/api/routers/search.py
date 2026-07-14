"""Search route: GET /search — Redis-cached product search across platforms."""

from fastapi import APIRouter, Query

from schemas.compare import DEFAULT_LAT, DEFAULT_LON, DEFAULT_PINCODE
from schemas.search import PlatformResults, SearchResponse
from services import qc_client
from services.redis_client import get_cache, search_cache_key, set_cache

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(min_length=1, description="Product to search for"),
    platforms: str = Query("blinkit,zepto,swiggy", description="Comma-separated"),
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
