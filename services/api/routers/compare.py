"""Compare route: POST /cart/compare — price a cart on every platform.

For each cart item we search every platform, pick the best-MATCHING available
product per platform, and sum per platform. The platform with the lowest total
wins. Per-item searches run concurrently (asyncio.gather) since they're
independent.

Matching matters: the real API returns 50-80 loosely-related products per query,
so taking the globally cheapest grabs irrelevant tiny items (a sachet, a random
SKU) and produces nonsense totals. We rank by query-token overlap first.
"""

import asyncio
import re

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


# search one cart item, reusing the same Redis cache the /search route writes to.
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


# filler words that shouldn't drive matching.
_STOP = {"pack", "of", "the", "a", "combo", "buy", "get", "with"}

# common Brand/name synonyms — the query token on the left also counts as a match for
# any of the tokens on the right (product names often use the formal brand).
_SYNONYMS = {
    "coke": {"coca", "cola"},
    "coca": {"coke"},
    "cola": {"coke"},
    "pepsi": {"pepsico"},
    "lays": {"lay"},
    "maggi": {"maggie"},
    "kurkure": {"kurkur"},
    "dairymilk": {"cadbury"},
    "sprite": {"limca"},
}


# widen the query's words with known synonyms so "coke" can match "coca-cola".
def _expand(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for t in tokens:
        out |= _SYNONYMS.get(t, set())
    return out
# quantity units — tokens that describe pack size.
_UNITS = {
    "ml", "l", "ltr", "litre", "liter", "g", "gm", "gms", "gram", "grams",
    "kg", "kgs", "kilo", "pc", "pcs", "piece", "pieces", "dozen", "no", "nos",
}


# break text into name words vs size words, splitting letters from digits so
# "750ml" and "750 ml" both become {'750','ml'} and therefore compare equal.
def _split_tokens(text: str) -> tuple[set[str], set[str]]:
    """Return (name_tokens, size_tokens). Splitting letter-runs from digit-runs
    makes "750ml" and "750 ml" tokenize identically → {'750','ml'}."""
    toks = set(re.findall(r"[a-z]+|\d+", text.lower()))
    size = {t for t in toks if t.isdigit() or t in _UNITS}
    name = toks - size - _STOP
    return name, size


# choose which product actually answers the query, scoring word overlap with
# size weighted highest, then breaking ties by price (never price alone).
def _best_match(query: str, products: list[Product]) -> Product | None:
    """Pick the available product that best matches the query.

    Scores products by query-token overlap, weighting SIZE/quantity tokens
    heavily so "milk 1L" doesn't match a 200ml pack and "24 eggs" doesn't match
    a 6-pack. Size is matched against the product's pack size (`quantity`) too,
    since that's where it usually lives. Ties break to the cheapest. Falls back
    to the API's top-ranked result when nothing matches.
    """
    available = [p for p in products if p.available]
    if not available:
        return None

    q_name, q_size = _split_tokens(query)
    if not q_name and not q_size:
        return min(available, key=lambda p: p.offer_price)
    q_name = _expand(q_name)  # let "coke" match "coca-cola", etc.

    def score(p: Product) -> int:
        p_name, p_size = _split_tokens(f"{p.name} {p.brand or ''} {p.quantity or ''}")
        return len(q_name & p_name) * 2 + len(q_size & p_size) * 3

    best = max(score(p) for p in available)
    if best == 0:
        return available[0]
    candidates = [p for p in available if score(p) == best]
    return min(candidates, key=lambda p: p.offer_price)


# price every cart item on every platform and report which platform wins.
# searches run concurrently, so total time ≈ the slowest single search.
@router.post("/cart/compare", response_model=CartCompareResponse)
async def compare(req: CartCompareRequest) -> CartCompareResponse:
    # fire all item searches concurrently.
    searches = await asyncio.gather(
        *(_search_item(item.query, req) for item in req.items)
    )

    # build an empty priced cart per platform.
    totals: dict[str, PlatformTotal] = {
        p: PlatformTotal(platform=p) for p in req.platforms
    }

    for item, results in zip(req.items, searches):
        by_platform = {r.platform: r.products for r in results}
        for platform in req.platforms:
            pt = totals[platform]
            products = by_platform.get(platform) or []
            best = _best_match(item.query, products)
            if best is None:
                # distinguish "the API gave us nothing for this platform" from
                # "the platform has it but it's out of stock" — very different!
                reason = "no_data" if not products else "out_of_stock"
                pt.unavailable.append(item.query)
                pt.line_items.append(
                    PlatformLineItem(
                        query=item.query,
                        units=item.quantity,
                        available=False,
                        status=reason,
                    )
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

    # winner = platform with a full cart (nothing unavailable) at lowest total.
    complete = [pt for pt in totals.values() if not pt.unavailable]
    pool = complete or list(totals.values())
    cheapest = min(pool, key=lambda pt: pt.total).platform if pool else None

    return CartCompareResponse(
        platform_totals=list(totals.values()),
        cheapest_platform=cheapest,
    )
