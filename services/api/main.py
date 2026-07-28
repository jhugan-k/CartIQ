"""CartIQ API entrypoint.

Creates the FastAPI app, enables CORS for the frontend, mounts every router,
and exposes a /health check. Run locally with:

    uvicorn main:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from config import settings
from rate_limit import limiter
from routers import alternatives, auth, cart, chat, compare, search, wishlist
from services.qc_client import QuickCommerceError

app = FastAPI(
    title="CartIQ API",
    version="1.0.0",
    description="Quick-commerce cart comparator across Blinkit, Zepto and Swiggy.",
)

# Rate limiting: register the shared limiter, a 429 handler (adds Retry-After
# and X-RateLimit-* headers), and the middleware that enforces the global
# default limit on every route. Per-route @limiter.limit(...) decorators layer
# stricter limits on top.
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


@app.exception_handler(QuickCommerceError)
async def quickcommerce_error_handler(request: Request, exc: QuickCommerceError):
    """Turn upstream QuickCommerce failures into a clean 502 with the reason,
    instead of an opaque 500."""
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health", tags=["health"])
@limiter.exempt  # infra health checks must never be throttled
async def health(request: Request) -> dict:
    return {"status": "ok", "mock_qc": settings.use_mock_qc}
