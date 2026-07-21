"""Alternatives route: GET /alternatives — find substitutes for an item.

When a branded item is unavailable, the user can ask for alternatives. We strip
the brand (or drop the first word) to make the query vaguer — "Amul Paneer" →
"Paneer" — and search that. On-demand only, so it costs a credit only when asked.
"""

from fastapi import APIRouter, Query

from schemas.compare import DEFAULT_LAT, DEFAULT_LON, DEFAULT_PINCODE
from schemas.search import PlatformResults, SearchResponse
from services import qc_client
from services.redis_client import get_cache, search_cache_key, set_cache

router = APIRouter(tags=["alternatives"])


# strip the brand off a product name to get a broader search term.
def _vaguer_query(product_name: str, brand: str | None) -> str:
    """Drop the brand from the name; fall back to dropping the first word."""
    name = product_name.strip()
    if brand and brand.lower() in name.lower():
        stripped = name.lower().replace(brand.lower(), "").strip()
        if stripped:
            return stripped
    parts = name.split()
    return " ".join(parts[1:]) if len(parts) > 1 else name


# find substitutes for an item by searching the brand-stripped term instead.
@router.get("/alternatives", response_model=SearchResponse)
async def alternatives(
    product_name: str = Query(min_length=1),
    brand: str | None = Query(None),
    platforms: str = Query("blinkit,zepto,swiggy"),
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    pincode: str = DEFAULT_PINCODE,
) -> SearchResponse:
    query = _vaguer_query(product_name, brand)
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]

    key = search_cache_key(query, lat, lon, pincode)
    cached = await get_cache(key)
    if cached is not None:
        return SearchResponse(**cached)

    results: list[PlatformResults] = await qc_client.groupsearch(
        query, platform_list, lat, lon, pincode
    )
    response = SearchResponse(query=query, platforms=results)
    await set_cache(key, response.model_dump())
    return response
