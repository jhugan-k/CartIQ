"""Compare route: POST /cart/compare — price a cart on every platform.

For each cart item we search every platform, pick the cheapest AVAILABLE match
per platform, and sum per platform. The platform with the lowest total wins.
Per-item searches run concurrently (asyncio.gather) since they're independent.
"""

import asyncio

from fastapi import APIRouter

from schemas.compare import (
    CartCompareRequest,
    CartCompareResponse,
    PlatformLineItem,
    PlatformTotal,
)
from schemas.search import PlatformResults, Product
from services import qc_client
from services.redis_client import get_cache, search_cache_key, set_cache

router = APIRouter(tags=["compare"])


async def _search_item(query: str, req: CartCompareRequest) -> list[PlatformResults]:
    """Cached search for a single cart item (shares the /search cache)."""
    key = search_cache_key(query, req.lat, req.lon, req.pincode)
    cached = await get_cache(key)
    if cached is not None:
        return [PlatformResults(**p) for p in cached["platforms"]]
    results = await qc_client.groupsearch(
        query, req.platforms, req.lat, req.lon, req.pincode
    )
    await set_cache(key, {"query": query, "platforms": [r.model_dump() for r in results]})
    return results


def _cheapest_available(products: list[Product]) -> Product | None:
    available = [p for p in products if p.available]
    return min(available, key=lambda p: p.offer_price) if available else None


@router.post("/cart/compare", response_model=CartCompareResponse)
async def compare(req: CartCompareRequest) -> CartCompareResponse:
    # Fire all item searches concurrently.
    searches = await asyncio.gather(
        *(_search_item(item.query, req) for item in req.items)
    )

    # Build an empty priced cart per platform.
    totals: dict[str, PlatformTotal] = {
        p: PlatformTotal(platform=p) for p in req.platforms
    }

    for item, results in zip(req.items, searches):
        by_platform = {r.platform: r.products for r in results}
        for platform in req.platforms:
            pt = totals[platform]
            best = _cheapest_available(by_platform.get(platform, []))
            if best is None:
                pt.unavailable.append(item.query)
                pt.line_items.append(
                    PlatformLineItem(query=item.query, units=item.quantity, available=False)
                )
                continue
            line_total = round(best.offer_price * item.quantity, 2)
            pt.total = round(pt.total + line_total, 2)
            pt.line_items.append(
                PlatformLineItem(
                    query=item.query,
                    product_name=best.name,
                    offer_price=best.offer_price,
                    quantity_label=best.quantity,
                    units=item.quantity,
                    line_total=line_total,
                    available=True,
                )
            )

    # Winner = platform with a full cart (nothing unavailable) at lowest total.
    complete = [pt for pt in totals.values() if not pt.unavailable]
    pool = complete or list(totals.values())
    cheapest = min(pool, key=lambda pt: pt.total).platform if pool else None

    return CartCompareResponse(
        platform_totals=list(totals.values()),
        cheapest_platform=cheapest,
    )
