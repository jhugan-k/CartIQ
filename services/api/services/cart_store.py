"""Redis-backed virtual cart, one per user.

Stored as a JSON list under `cart:{user_id}` with a 24h TTL (session-scoped).
Both the REST cart routes and the AI cart tools go through this single module,
so the user and the assistant always mutate the same source of truth.
"""

import json
import uuid

from services.redis_client import get_redis

_CART_TTL = 60 * 60 * 24  # 24 hours


# build the per-user Redis key that holds this user's cart.
def _key(user_id: str) -> str:
    return f"cart:{user_id}"


# read the user's cart back from Redis (empty list if they don't have one yet).
async def get_cart(user_id: str) -> list[dict]:
    raw = await get_redis().get(_key(user_id))
    return json.loads(raw) if raw else []


# write the cart back to Redis, refreshing its 24h expiry.
async def _save(user_id: str, items: list[dict]) -> None:
    await get_redis().set(_key(user_id), json.dumps(items), ex=_CART_TTL)


# add an item to the cart, bumping the quantity if that name is already there.
# called by both the user (REST route) and the AI (tool), so it's the shared truth.
async def add_item(
    user_id: str,
    name: str,
    quantity: int = 1,
    added_by: str = "user",
    platform: str | None = None,
) -> list[dict]:
    """Add an item, merging quantity if the same name already exists."""
    name = name.strip()
    items = await get_cart(user_id)
    for it in items:
        if it["name"].lower() == name.lower():
            it["quantity"] += max(1, quantity)
            if platform:  # a known recommendation updates the tag
                it["platform"] = platform
            await _save(user_id, items)
            return items
    items.append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "quantity": max(1, quantity),
            "added_by": added_by,
            "platform": platform,
        }
    )
    await _save(user_id, items)
    return items


# set a new quantity for one item (never below 1).
async def update_qty(user_id: str, item_id: str, quantity: int) -> list[dict]:
    items = await get_cart(user_id)
    for it in items:
        if it["id"] == item_id:
            it["quantity"] = max(1, quantity)
    await _save(user_id, items)
    return items


# drop a single item by its id (used by the sidebar's delete button).
async def remove_item(user_id: str, item_id: str) -> list[dict]:
    items = [it for it in await get_cart(user_id) if it["id"] != item_id]
    await _save(user_id, items)
    return items


# drop items by fuzzy name match, since the AI only knows what the user called it.
async def remove_by_name(user_id: str, name: str) -> list[dict]:
    """Remove items whose name contains the given text (for the AI tool)."""
    needle = name.strip().lower()
    items = [it for it in await get_cart(user_id) if needle not in it["name"].lower()]
    await _save(user_id, items)
    return items


# empty the cart by deleting the key outright.
async def clear(user_id: str) -> list[dict]:
    await get_redis().delete(_key(user_id))
    return []
