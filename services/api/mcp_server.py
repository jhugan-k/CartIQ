"""CartIQ MCP server — the same tools, exposed to any MCP client.

Model Context Protocol is an open standard for how LLM clients discover and
call external tools. Wrapping CartIQ's logic as an MCP server means the
capability is not locked to our chat UI or to Gemini: Claude, ChatGPT or any
other MCP-aware client can price a cart across Blinkit, Zepto and Swiggy.

Two ways to run it:

  Local (stdio), for a desktop client that launches us as a subprocess:
      python mcp_server.py

  Remote (Streamable HTTP), mounted on the main API by main.py, so a single
  Render service serves both the REST API and MCP at:
      https://<host>/mcp

WHAT IS AND IS NOT EXPOSED
Only the read-only tools. The cart tools are deliberately absent: they act on a
specific signed-in user, and an anonymous MCP caller has no identity to act as
-- they would fail confusingly at best and touch the wrong cart at worst.

WHY EACH TOOL TAKES A PINCODE
The REST API and the chat agent read the pincode from a per-request contextvar
that defaults to Delhi. That is wrong for an endpoint anyone can call from
anywhere, so location is an explicit argument here and we set the contextvar
per call from it.

COST
Every search spends QuickCommerce credits (one per platform), which is real
money for an endpoint with no login. Each tool checks the shared daily budget
in services/budget.py before calling out, and the whole endpoint stops for the
day rather than billing without limit.
"""

import logging

from mcp.server.mcpserver import MCPServer

from agent.context import current_pincode, current_user_id
from agent.tools import tool_alternatives, tool_compare, tool_search
from schemas.compare import DEFAULT_PINCODE
from services import budget
from services.budget import BudgetExceeded

logger = logging.getLogger("cartiq.mcp")

mcp = MCPServer(
    "cartiq",
    title="CartIQ",
    instructions=(
        "Compare live grocery prices across Indian quick-commerce apps "
        "(Blinkit, Zepto, Swiggy Instamart). Prices are location-specific, so "
        "pass the user's Indian pincode when you know it. Every result comes "
        "from a live lookup: never state a price this server did not return."
    ),
)

# One search costs a credit per platform, so the default fan-out is 3.
_PLATFORM_COST = 3


# apply the caller's location for this request and confirm we can afford it.
async def _prepare(pincode: str | None, platforms: str) -> dict | None:
    """Set the per-call location and charge the daily QuickCommerce budget.

    Returns an error dict when the day's allowance is gone, or None to proceed.
    It returns rather than raises because an exception out of an MCP tool
    reaches the client as a bare "Error executing tool search" — the calling
    model cannot tell a spending cap from a broken server. A returned dict is
    readable, so the model can tell its user to come back tomorrow.
    """
    # No MCP caller is a signed-in CartIQ user; being explicit stops any cart
    # tool that might be added later from silently acting as someone.
    current_user_id.set(None)
    current_pincode.set((pincode or DEFAULT_PINCODE).strip())
    try:
        await budget.ensure("qc_searches")
    except BudgetExceeded as exc:
        logger.warning("MCP call refused: %s", exc)
        return {
            "error": "daily_limit_reached",
            "message": str(exc),
            "retry_after": "midnight UTC",
        }
    cost = len([p for p in platforms.split(",") if p.strip()]) or _PLATFORM_COST
    await budget.spend("qc_searches", cost)
    return None


# MCP tool: search a product across platforms.
@mcp.tool()
async def search(
    query: str,
    pincode: str = DEFAULT_PINCODE,
    platforms: str = "blinkit,zepto,swiggy",
) -> dict:
    """Search one product across Indian quick-commerce apps.

    Returns each platform's matches with price, MRP, pack size, a comparable
    per-unit price, availability, and a flag for fake discounts (offer == MRP).

    Args:
        query: Product to look for, e.g. "amul butter".
        pincode: 6-digit Indian pincode. Prices and stock vary by area.
        platforms: Comma-separated subset of blinkit,zepto,swiggy.
    """
    refused = await _prepare(pincode, platforms)
    if refused:
        return refused
    return await tool_search(query=query, platforms=platforms, detailed=True)


# MCP tool: price a whole cart and name the cheapest platform.
@mcp.tool()
async def compare_cart(
    items: list[dict],
    pincode: str = DEFAULT_PINCODE,
    platforms: str = "blinkit,zepto,swiggy",
) -> dict:
    """Price a basket on each app and report which is cheapest overall.

    Args:
        items: Cart lines, e.g. [{"query": "milk", "quantity": 2}].
        pincode: 6-digit Indian pincode.
        platforms: Comma-separated subset of blinkit,zepto,swiggy.
    """
    refused = await _prepare(pincode, platforms)
    if refused:
        return refused
    return await tool_compare(items=items, platforms=platforms)


# MCP tool: find substitutes for an item.
@mcp.tool()
async def alternatives(
    product_name: str,
    brand: str = "",
    pincode: str = DEFAULT_PINCODE,
) -> dict:
    """Find substitutes for a product, e.g. when a brand is unavailable.

    Args:
        product_name: The item to replace.
        brand: Brand to strip from the search, if known.
        pincode: 6-digit Indian pincode.
    """
    refused = await _prepare(pincode, "blinkit,zepto,swiggy")
    if refused:
        return refused
    return await tool_alternatives(
        product_name=product_name, brand=brand, detailed=True
    )


if __name__ == "__main__":
    mcp.run()  # stdio, for a locally launched client
