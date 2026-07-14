"""QuickCommerce API client.

Wraps the external /v1/groupsearch endpoint and normalizes its messy,
platform-keyed response into our clean `Product` schema. Callers (routers) only
ever deal with `Product` / `PlatformResults`, never the raw API shape.

If settings.use_mock_qc is true, returns canned data instead of spending
credits — the normalization path is identical either way.
"""

import httpx

from config import settings
from schemas.search import PlatformResults, Product
from services import mock_qc


class QuickCommerceError(Exception):
    """Raised when the upstream API call fails (network, auth, or no credits)."""


def _normalize_product(raw: dict, platform: str) -> Product:
    """Map one raw API product dict → our Product schema (fake_discount auto-set)."""
    images = raw.get("images") or []
    image_url = images[0] if images else None
    return Product(
        platform=platform,
        item_id=str(raw["id"]) if raw.get("id") is not None else None,
        name=raw.get("name", "Unknown"),
        brand=raw.get("brand"),
        mrp=float(raw.get("mrp", 0) or 0),
        offer_price=float(raw.get("offer_price", raw.get("mrp", 0)) or 0),
        quantity=raw.get("quantity"),
        rating=raw.get("rating"),
        rating_count=raw.get("rating_count"),
        available=bool(raw.get("available", True)),
        image_url=image_url,
        deeplink=raw.get("deeplink"),
    )


def _normalize_results(results: dict[str, list[dict]]) -> list[PlatformResults]:
    """Map {platform: [raw, ...]} → [PlatformResults, ...]."""
    return [
        PlatformResults(
            platform=platform,
            products=[_normalize_product(raw, platform) for raw in raw_list],
        )
        for platform, raw_list in results.items()
    ]


async def groupsearch(
    query: str,
    platforms: list[str],
    lat: float,
    lon: float,
    pincode: str | None = None,
) -> list[PlatformResults]:
    """Search `query` across `platforms`. Returns normalized per-platform results."""
    if settings.use_mock_qc:
        raw_results = mock_qc.mock_groupsearch(query, platforms)
        return _normalize_results(raw_results)

    params = {
        "q": query,
        "lat": lat,
        "lon": lon,
        "platforms": ",".join(platforms),
    }
    if pincode:
        params["pincode"] = pincode

    headers = {"X-API-Key": settings.quickcommerce_api_key}
    url = f"{settings.quickcommerce_base_url}/v1/groupsearch"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise QuickCommerceError(str(exc)) from exc

    payload = resp.json()
    results = payload.get("data", {}).get("results", {})
    return _normalize_results(results)


async def get_credits() -> dict:
    """Fetch remaining credits (free call). Useful for a status endpoint."""
    headers = {"X-API-Key": settings.quickcommerce_api_key}
    url = f"{settings.quickcommerce_base_url}/v1/credits"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise QuickCommerceError(str(exc)) from exc
    return resp.json()
