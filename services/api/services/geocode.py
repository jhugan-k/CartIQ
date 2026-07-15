"""Pincode → latitude/longitude.

The QuickCommerce API keys its results off lat/lon (that's how Blinkit/Zepto/
Swiggy resolve your serviceable store), so a pincode alone doesn't change prices
or fix Zepto returning nothing. This resolves a pincode to real coordinates:

1. A built-in table of major-metro prefixes (offline, instant, covers most cases)
2. A cached Nominatim (OpenStreetMap) lookup for anything else
3. Fall back to Delhi if all else fails

Results are cached in Redis for 30 days — pincodes don't move.
"""

import httpx

from schemas.compare import DEFAULT_LAT, DEFAULT_LON
from services.redis_client import get_cache, set_cache

_GEO_TTL = 60 * 60 * 24 * 30  # 30 days

# First-3-digits of pincode → (lat, lon) of the city centre. Major metros.
_METRO: dict[str, tuple[float, float]] = {
    "110": (28.6139, 77.2090),  # Delhi
    "201": (28.5355, 77.3910),  # Noida
    "122": (28.4595, 77.0266),  # Gurgaon
    "400": (19.0760, 72.8777),  # Mumbai
    "411": (18.5204, 73.8567),  # Pune
    "560": (12.9716, 77.5946),  # Bengaluru
    "500": (17.3850, 78.4867),  # Hyderabad
    "600": (13.0827, 80.2707),  # Chennai
    "700": (22.5726, 88.3639),  # Kolkata
    "380": (23.0225, 72.5714),  # Ahmedabad
    "302": (26.9124, 75.7873),  # Jaipur
    "160": (30.7333, 76.7794),  # Chandigarh
    "226": (26.8467, 80.9462),  # Lucknow
    "462": (23.2599, 77.4126),  # Bhopal
    "395": (21.1702, 72.8311),  # Surat
}


async def pincode_to_latlon(pincode: str | None) -> tuple[float, float]:
    pin = (pincode or "").strip()
    if not pin:
        return DEFAULT_LAT, DEFAULT_LON

    # 1) Metro prefix table — instant, no network.
    hit = _METRO.get(pin[:3])
    if hit:
        return hit

    # 2) Redis-cached geocode.
    cached = await get_cache(f"geo:{pin}")
    if cached:
        return cached["lat"], cached["lon"]

    # 3) Nominatim (OSM). Free; requires a User-Agent; be gentle.
    try:
        async with httpx.AsyncClient(
            timeout=8.0, headers={"User-Agent": "CartIQ/1.0 (portfolio project)"}
        ) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "postalcode": pin,
                    "country": "India",
                    "format": "json",
                    "limit": 1,
                },
            )
            data = resp.json()
            if data:
                lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
                await set_cache(f"geo:{pin}", {"lat": lat, "lon": lon}, ttl=_GEO_TTL)
                return lat, lon
    except Exception:
        pass  # network/parse failure → fall through to default

    # 4) Default.
    return DEFAULT_LAT, DEFAULT_LON
