"""The tools the AI agent can call.

Each function reuses the Part 7 route handlers (which take plain args, no
FastAPI Depends), so there is ONE implementation of the business logic shared by
the REST API, the MCP server, and the Gemini agent. The functions return
compact, JSON-serializable dicts (trimmed to keep the token cost down).

The `FUNCTION_DECLARATIONS` describe these tools to Gemini; `DISPATCH` maps a
tool name back to the coroutine that runs it.
"""

from google.genai import types

from agent.context import current_pincode, current_user_id
from routers.alternatives import alternatives as _alternatives_route
from routers.compare import compare as _compare_route
from routers.search import search as _search_route
from schemas.compare import DEFAULT_PINCODE, CartCompareRequest, CartItem
from services import cart_store, geocode


# current request's pincode, falling back to the default.
def _pincode() -> str:
    return current_pincode.get() or DEFAULT_PINCODE


# resolve the request's pincode into coordinates for the vendor API.
async def _location() -> tuple[float, float, str]:
    """Resolve the current pincode to (lat, lon, pincode) for QC calls."""
    pin = _pincode()
    lat, lon = await geocode.pincode_to_latlon(pin)
    return lat, lon, pin

_MAX_PRODUCTS = 5  # cap products per platform sent back to the model


# trim a product down to the few fields the model needs (keeps tokens cheap).
def _compact_product(p) -> dict:
    return {
        "name": p.name,
        "brand": p.brand,
        "quantity": p.quantity,
        "mrp": p.mrp,
        "offer_price": p.offer_price,
        "available": p.available,
        "fake_discount": p.fake_discount,
    }


# ---------- Tool implementations ----------

# tool: search one product across platforms and return compact results.
async def tool_search(query: str, platforms: str = "blinkit,zepto,swiggy") -> dict:
    """Search a single product across platforms."""
    lat, lon, pin = await _location()
    resp = await _search_route(q=query, platforms=platforms, lat=lat, lon=lon, pincode=pin)
    return {
        "query": resp.query,
        "platforms": [
            {
                "platform": pr.platform,
                "products": [_compact_product(p) for p in pr.products[:_MAX_PRODUCTS]],
            }
            for pr in resp.platforms
        ],
    }


# tool: price a multi-item cart on each platform and name the cheapest.
async def tool_compare(items: list[dict], platforms: str = "blinkit,zepto,swiggy") -> dict:
    """Price a multi-item cart on each platform and find the cheapest."""
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    cart_items = [
        CartItem(query=i["query"], quantity=int(i.get("quantity", 1))) for i in items
    ]
    lat, lon, pin = await _location()
    req = CartCompareRequest(
        items=cart_items, platforms=platform_list, lat=lat, lon=lon, pincode=pin
    )
    resp = await _compare_route(req)
    return {
        "cheapest_platform": resp.cheapest_platform,
        "platform_totals": [
            {
                "platform": t.platform,
                "total": t.total,
                "unavailable": t.unavailable,
                "line_items": [
                    {
                        "query": li.query,
                        "product_name": li.product_name,
                        "offer_price": li.offer_price,
                        "units": li.units,
                        "line_total": li.line_total,
                        "available": li.available,
                        "status": li.status,
                    }
                    for li in t.line_items
                ],
            }
            for t in resp.platform_totals
        ],
    }


# tool: find substitutes for an item the user can't get.
async def tool_alternatives(product_name: str, brand: str = "") -> dict:
    """Find substitute products for an item by dropping its brand."""
    lat, lon, pin = await _location()
    resp = await _alternatives_route(
        product_name=product_name, brand=brand or None, lat=lat, lon=lon, pincode=pin
    )
    return {
        "searched": resp.query,
        "platforms": [
            {
                "platform": pr.platform,
                "products": [_compact_product(p) for p in pr.products[:_MAX_PRODUCTS]],
            }
            for pr in resp.platforms
        ],
    }


# ---------- Virtual cart tools (mutate the shared per-user cart) ----------

_PLATFORMS = {"blinkit", "zepto", "swiggy"}


# tool: put an item in the user's cart, optionally tagged with the best app.
async def tool_add_to_cart(name: str, quantity: int = 1, platform: str = "") -> dict:
    """Add an item to the user's virtual cart, optionally tagged with the
    recommended platform."""
    uid = current_user_id.get()
    if not uid:
        return {"error": "No signed-in user — cannot modify the cart."}
    plat = platform.strip().lower()
    plat = plat if plat in _PLATFORMS else None
    items = await cart_store.add_item(
        uid, name, int(quantity), added_by="assistant", platform=plat
    )
    return {
        "ok": True,
        "added": {"name": name, "quantity": int(quantity), "platform": plat},
        "cart": items,
    }


# tool: take an item out of the user's cart by name.
async def tool_remove_from_cart(name: str) -> dict:
    """Remove matching item(s) from the user's virtual cart by name."""
    uid = current_user_id.get()
    if not uid:
        return {"error": "No signed-in user — cannot modify the cart."}
    items = await cart_store.remove_by_name(uid, name)
    return {"ok": True, "removed": name, "cart": items}


# tool: read back what's currently in the user's cart.
async def tool_view_cart() -> dict:
    """Return the current contents of the user's virtual cart."""
    uid = current_user_id.get()
    if not uid:
        return {"error": "No signed-in user."}
    return {"cart": await cart_store.get_cart(uid)}


# ---------- Gemini function declarations ----------

_platforms_schema = types.Schema(
    type="STRING",
    description="Comma-separated platforms. Default 'blinkit,zepto,swiggy'.",
)

FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="tool_search",
        description="Search for a single product across quick-commerce platforms "
        "and return prices, availability and fake-discount flags.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query": types.Schema(
                    type="STRING",
                    description="Product to search, e.g. 'amul butter'.",
                ),
                "platforms": _platforms_schema,
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="tool_compare",
        description="Price a cart of multiple items on each platform and report "
        "which platform is cheapest overall. Use this when the user wants a total "
        "or to compare a basket of items.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "items": types.Schema(
                    type="ARRAY",
                    description="Cart items to price.",
                    items=types.Schema(
                        type="OBJECT",
                        properties={
                            "query": types.Schema(type="STRING"),
                            "quantity": types.Schema(type="INTEGER"),
                        },
                        required=["query"],
                    ),
                ),
                "platforms": _platforms_schema,
            },
            required=["items"],
        ),
    ),
    types.FunctionDeclaration(
        name="tool_alternatives",
        description="Find substitute products for an item (e.g. when a specific "
        "brand is unavailable) by searching a vaguer, brand-stripped term.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "product_name": types.Schema(type="STRING"),
                "brand": types.Schema(
                    type="STRING",
                    description="Brand to strip out, if known.",
                ),
            },
            required=["product_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="tool_add_to_cart",
        description="Add an item to the user's virtual cart (a saved shopping "
        "list). Use this whenever the user asks to add/put something in their cart.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "name": types.Schema(
                    type="STRING", description="Item name, e.g. 'Coke Zero'."
                ),
                "quantity": types.Schema(type="INTEGER"),
                "platform": types.Schema(
                    type="STRING",
                    description="Recommended platform for this item: 'blinkit', "
                    "'zepto', or 'swiggy'. Set it when you know the cheapest/"
                    "available app; omit if unknown.",
                ),
            },
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="tool_remove_from_cart",
        description="Remove an item from the user's virtual cart by name.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"name": types.Schema(type="STRING")},
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="tool_view_cart",
        description="Look at what is currently in the user's virtual cart.",
        parameters=types.Schema(type="OBJECT", properties={}),
    ),
]

DISPATCH = {
    "tool_search": tool_search,
    "tool_compare": tool_compare,
    "tool_alternatives": tool_alternatives,
    "tool_add_to_cart": tool_add_to_cart,
    "tool_remove_from_cart": tool_remove_from_cart,
    "tool_view_cart": tool_view_cart,
}
