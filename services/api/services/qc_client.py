"""QuickCommerce API client.

Wraps the external /v1/groupsearch endpoint and normalizes its messy,
platform-keyed response into our clean `Product` schema. Callers (routers) only
ever deal with `Product` / `PlatformResults`, never the raw API shape.

If settings.use_mock_qc is true, returns canned data instead of spending
credits — the normalization path is identical either way.
"""

import logging

import httpx

from config import settings
from schemas.search import PlatformResults, Product
from services import mock_qc

logger = logging.getLogger("cartiq.qc")

# The QC API requires exact platform casing. We use lowercase everywhere
# internally, so translate on the way out and lowercase again on the way in.
_API_PLATFORM = {"blinkit": "BlinkIt", "zepto": "Zepto", "swiggy": "Swiggy"}


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
    """Map {platform: [raw, ...]} → [PlatformResults, ...].

    Platform keys are lowercased so the rest of the app (compare, frontend)
    always deals with our internal names regardless of the API's casing.
    """
    out = []
    for platform, raw_list in results.items():
        name = platform.lower()
        out.append(
            PlatformResults(
                platform=name,
                products=[_normalize_product(raw, name) for raw in (raw_list or [])],
            )
        )
    return out


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
        # Translate our lowercase names to the API's exact casing.
        "platforms": ",".join(_API_PLATFORM.get(p.lower(), p) for p in platforms),
    }
    if pincode:
        params["pincode"] = pincode

    headers = {"X-API-Key": settings.quickcommerce_api_key}
    url = f"{settings.quickcommerce_base_url}/v1/groupsearch"

    try:
        # Live QC searches take ~15s; give tail latency room.
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Surface the upstream status + body so failures are diagnosable.
        body = exc.response.text[:600]
        logger.warning("QC %s error: %s", exc.response.status_code, body)
        raise QuickCommerceError(
            f"QuickCommerce API returned {exc.response.status_code}: {body}"
        ) from exc
    except httpx.HTTPError as exc:
        raise QuickCommerceError(f"QuickCommerce request failed: {exc}") from exc

    payload = resp.json()
    try:
        results = payload.get("data", {}).get("results", {})
        return _normalize_results(results)
    except Exception as exc:  # response shape differs from what we parse
        logger.warning(
            "QC parse failed. top-level keys=%s | data keys=%s | error=%s",
            list(payload.keys()),
            list((payload.get("data") or {}).keys()) if isinstance(payload.get("data"), dict) else type(payload.get("data")).__name__,
            exc,
        )
        raise QuickCommerceError(
            f"Failed to parse QuickCommerce response "
            f"(top-level keys={list(payload.keys())}): {exc}"
        ) from exc


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
