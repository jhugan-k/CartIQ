"""CartIQ API entrypoint.

Creates the FastAPI app, enables CORS for the frontend, mounts every router,
and exposes a /health check. Run locally with:

    uvicorn main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import settings
from mcp_server import mcp
from mcp.server.transport_security import TransportSecuritySettings
from rate_limit import limiter
from routers import alternatives, auth, cart, chat, compare, search, wishlist
from services import budget
from services.qc_client import QuickCommerceError

# uvicorn leaves the root logger at WARNING, so app INFO logs (e.g. the agent's
# raw tool-output dumps) would be swallowed. Configure a root handler at INFO so
# they reach stdout locally and in Render's logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# The MCP server as an ASGI app, so one Render service serves both the REST API
# and MCP. `stateless_http` keeps each call self-contained: no server-side
# session to lose when the free instance sleeps or restarts, which is what a
# remote client hitting a cold service needs.
_mcp_app = mcp.streamable_http_app(
    streamable_http_path="/",  # mounted at /mcp below, so "/" here avoids /mcp/mcp
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=settings.mcp_allowed_hosts_list,
        allowed_origins=settings.mcp_allowed_hosts_list,
    ),
)


class MCPTrailingSlash:
    """Serve /mcp and /mcp/ identically.

    Mounting at "/mcp" makes Starlette answer a request for exactly "/mcp" with
    a 307 to "/mcp/". Some MCP clients do not follow a redirect on POST and
    simply report the server as unreachable — Claude Desktop's connector check
    shows it as "Not found: 307". The whole point of a remote server is a link
    people can paste, and nobody pastes a trailing slash, so rewrite the path
    before routing instead of pushing the problem onto whoever gets the link.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = dict(scope, path="/mcp/", raw_path=b"/mcp/")
        await self.app(scope, receive, send)


# Mounting a Starlette app does NOT run its lifespan, and the MCP session
# manager is started there — without this the endpoint accepts connections and
# then fails on the first request. Drive it from the parent app's lifespan.
@asynccontextmanager
async def lifespan(_: FastAPI):
    async with _mcp_app.router.lifespan_context(_mcp_app):
        yield


app = FastAPI(
    title="CartIQ API",
    version="1.0.0",
    description="Quick-commerce cart comparator across Blinkit, Zepto and Swiggy.",
    lifespan=lifespan,
)

# Rate limiting: register the shared limiter, a 429 handler (adds Retry-After
# and X-RateLimit-* headers), and the middleware that enforces the global
# default limit on every route. Per-route @limiter.limit(...) decorators layer
# stricter limits on top.
# Added first so it wraps everything and rewrites the path before routing.
app.add_middleware(MCPTrailingSlash)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(compare.router)
app.include_router(alternatives.router)
app.include_router(wishlist.router)
app.include_router(cart.router)
app.include_router(chat.router)

# Remote MCP endpoint: https://<host>/mcp — the link you hand to any MCP client.
app.mount("/mcp", _mcp_app)


@app.exception_handler(QuickCommerceError)
async def quickcommerce_error_handler(request: Request, exc: QuickCommerceError):
    """Turn upstream QuickCommerce failures into a clean 502 with the reason,
    instead of an opaque 500."""
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health", tags=["health"])
@limiter.exempt  # infra health checks must never be throttled
async def health(request: Request) -> dict:
    return {"status": "ok", "mock_qc": settings.use_mock_qc}


# Deliberately NOT part of /health: Render polls that every few seconds, and
# each budget read costs Redis commands we would rather spend on the cache.
@app.get("/budget", tags=["health"])
async def budget_status(request: Request) -> dict:
    """Today's spend against the daily caps. `used: -1` means Redis is
    unreachable, in which case chat is refused unless BUDGET_FAIL_OPEN is set."""
    return {"date": "today (UTC)", "caps": await budget.snapshot()}
