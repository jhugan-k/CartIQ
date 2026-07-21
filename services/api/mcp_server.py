"""CartIQ MCP server.

Exposes CartIQ's tools over the Model Context Protocol so any MCP-compatible
client (Claude Desktop, other agents) can use them — the SAME tool functions the
Gemini agent and REST API use. Run as a standalone stdio server:

    python mcp_server.py

MCP is an open protocol that standardizes how LLM clients discover and call
external tools. Wrapping our logic as an MCP server means the capability isn't
locked to one model or app.
"""

from mcp.server.fastmcp import FastMCP

from agent.tools import tool_alternatives, tool_compare, tool_search

mcp = FastMCP("cartiq")


# MCP tool: search a product across platforms.
@mcp.tool()
async def search(query: str, platforms: str = "blinkit,zepto,swiggy") -> dict:
    """Search a product across quick-commerce platforms with prices."""
    return await tool_search(query=query, platforms=platforms)


# MCP tool: price a cart and find the cheapest platform.
@mcp.tool()
async def compare(items: list[dict], platforms: str = "blinkit,zepto,swiggy") -> dict:
    """Price a cart of items on each platform and find the cheapest."""
    return await tool_compare(items=items, platforms=platforms)


# MCP tool: find substitutes for an item.
@mcp.tool()
async def alternatives(product_name: str, brand: str = "") -> dict:
    """Find substitute products for an item by dropping its brand."""
    return await tool_alternatives(product_name=product_name, brand=brand)


if __name__ == "__main__":
    mcp.run()  # stdio transport
