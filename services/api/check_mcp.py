"""Verify the CartIQ MCP endpoint is reachable and actually answering.

    python check_mcp.py                          # production
    python check_mcp.py http://127.0.0.1:8000/mcp/   # a local uvicorn

Exits non-zero if anything fails, so it works as a smoke test in a deploy
pipeline or a cron check.

It runs the same three steps a real MCP client does — initialize, list tools,
call one — because each fails differently and the difference is the diagnosis:
  * initialize fails      -> not mounted, service asleep, or Host not allowed
  * initialize ok, no tools -> server up but tools not registered
  * tools ok, call fails   -> CartIQ itself (credits, Redis, upstream vendor)
"""

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = "https://cartiq-api.onrender.com/mcp/"


# the SDK renamed fields between 1.x and 2.x; read whichever exists.
def _field(obj, *names, default=None):
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


async def check(url: str) -> bool:
    print(f"checking {url}\n")
    try:
        async with streamable_http_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                info = await session.initialize()
                server = _field(info, "server_info", "serverInfo")
                print(f"[ok] handshake   {server.name} "
                      f"(protocol {_field(info, 'protocol_version', 'protocolVersion')})")

                tools = (await session.list_tools()).tools
                if not tools:
                    print("[!!] no tools registered")
                    return False
                print(f"[ok] tools       {', '.join(t.name for t in tools)}")

                result = await session.call_tool(
                    "search", {"query": "amul butter", "pincode": "110063"}
                )
                payload = json.loads(result.content[0].text) if result.content else {}
                if payload.get("error"):
                    print(f"[!!] tool call   {payload['error']}: "
                          f"{payload.get('message', '')}")
                    return False
                platforms = payload.get("platforms", [])
                total = sum(len(p.get("products", [])) for p in platforms)
                print(f"[ok] tool call   {total} products across "
                      f"{len(platforms)} platform(s)")
                for p in platforms:
                    first = (p.get("products") or [{}])[0]
                    print(f"                 {p['platform']:9s} "
                          f"{first.get('name', '(none)')[:34]:34s} "
                          f"{first.get('unit_price', '')}")
                return True
    except Exception as exc:
        # A cold Render instance takes ~30-50s to wake and usually shows up here
        # as a timeout on the very first attempt; a second run normally passes.
        print(f"[!!] {type(exc).__name__}: {str(exc)[:200]}")
        return False


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    sys.exit(0 if asyncio.run(check(target)) else 1)
