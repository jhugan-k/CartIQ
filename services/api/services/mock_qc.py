"""Canned QuickCommerce responses for development.

Used when settings.use_mock_qc is true (the trial API credits are exhausted).
The shape mirrors the real /v1/groupsearch `data.results` object: a dict keyed
by platform, each value a list of raw product dicts with the real field names
(id, name, brand, mrp, offer_price, available, quantity, images, rating, ...).
So the same normalization code path runs for mock and live data.
"""

import random

_PLATFORMS = ["blinkit", "zepto", "swiggy"]

# A few base products keyed by a search term. Prices are jittered per platform
# so comparisons are non-trivial.
_CATALOG: dict[str, list[dict]] = {
    "butter": [
        {"name": "Amul Butter", "brand": "Amul", "mrp": 62.0, "quantity": "100 g"},
        {"name": "Amul Butter", "brand": "Amul", "mrp": 295.0, "quantity": "500 g"},
        {"name": "Mother Dairy Butter", "brand": "Mother Dairy", "mrp": 60.0, "quantity": "100 g"},
    ],
    "milk": [
        {"name": "Amul Gold Milk", "brand": "Amul", "mrp": 34.0, "quantity": "500 ml"},
        {"name": "Mother Dairy Full Cream Milk", "brand": "Mother Dairy", "mrp": 35.0, "quantity": "500 ml"},
    ],
    "paneer": [
        {"name": "Amul Malai Paneer", "brand": "Amul", "mrp": 95.0, "quantity": "200 g"},
        {"name": "Mother Dairy Paneer", "brand": "Mother Dairy", "mrp": 89.0, "quantity": "200 g"},
    ],
    "bread": [
        {"name": "Britannia Brown Bread", "brand": "Britannia", "mrp": 45.0, "quantity": "400 g"},
        {"name": "Harvest Gold White Bread", "brand": "Harvest Gold", "mrp": 40.0, "quantity": "400 g"},
    ],
}

# Generic fallback so any query returns something in mock mode.
_GENERIC = [
    {"name": "{q} (Store Brand)", "brand": "Generic", "mrp": 99.0, "quantity": "1 unit"},
]


def _platform_price(mrp: float, platform: str, idx: int) -> tuple[float, bool]:
    """Deterministic-ish per-platform offer price + availability."""
    rng = random.Random(f"{platform}-{mrp}-{idx}")
    # Discount 0–18%; occasionally a fake discount (offer == mrp).
    if rng.random() < 0.2:
        offer = mrp  # fake discount case
    else:
        offer = round(mrp * (1 - rng.uniform(0.02, 0.18)), 2)
    available = rng.random() > 0.15  # ~15% unavailable
    return offer, available


def _raw_product(base: dict, platform: str, idx: int, query: str) -> dict:
    name = base["name"].format(q=query.title())
    mrp = base["mrp"]
    offer, available = _platform_price(mrp, platform, idx)
    return {
        "id": f"{platform}-{abs(hash((name, platform, mrp))) % 10**8}",
        "name": name,
        "brand": base.get("brand"),
        "mrp": mrp,
        "offer_price": offer,
        "available": available,
        "quantity": base.get("quantity"),
        "images": [f"https://placehold.co/200?text={platform}"],
        "rating": round(random.Random(name).uniform(3.5, 4.8), 1),
        "rating_count": random.Random(name).randint(50, 5000),
        "deeplink": f"https://{platform}.example/product/{idx}",
        "platform": {"name": platform, "sla": "10 mins"},
    }


def mock_groupsearch(query: str, platforms: list[str]) -> dict[str, list[dict]]:
    """Return {platform: [raw_product, ...]} mimicking data.results."""
    key = next((k for k in _CATALOG if k in query.lower()), None)
    bases = _CATALOG[key] if key else [
        {**g, "name": g["name"].format(q=query)} for g in _GENERIC
    ]
    results: dict[str, list[dict]] = {}
    for platform in platforms:
        if platform not in _PLATFORMS:
            continue
        results[platform] = [
            _raw_product(base, platform, idx, query)
            for idx, base in enumerate(bases)
        ]
    return results
