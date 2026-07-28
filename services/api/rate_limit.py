"""Rate limiting — one shared Limiter for the whole app.

Backed by the same Redis instance as the cache, so limits are enforced across
every worker process / instance (an in-process counter would let each worker
grant the full quota). If Redis is unavailable we FAIL OPEN: `swallow_errors`
plus an in-memory fallback mean a Redis blip degrades limiting rather than
taking the API down — consistent with how services/redis_client.py treats the
cache as best-effort.

Keying strategy (see `_client_key`):
- Authenticated requests are keyed on the JWT subject (the user id), so a user's
  quota follows them regardless of IP, and the expensive /chat route is metered
  per person rather than per network.
- Unauthenticated requests (login, register, public search) fall back to the
  client IP — the only stable identifier we have before a token exists.

Applying limits: a global ceiling is set here via `default_limits` (enforced by
SlowAPIMiddleware in main.py); individual routes tighten it with
`@limiter.limit(...)`. Both must pass, so a decorated route is bounded by the
stricter of the two.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings
from utils.auth import decode_access_token


# identify the caller: the signed-in user when we can, else the source IP.
def _client_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        # decode_access_token verifies signature+expiry and returns None on any
        # problem, so a forged/expired token can't spoof another user's bucket;
        # it just falls through to per-IP keying below.
        sub = decode_access_token(auth[7:])
        if sub:
            return f"user:{sub}"
    return f"ip:{get_remote_address(request)}"


# reuse the cache's Redis as the counter store so limits hold across processes.
limiter = Limiter(
    key_func=_client_key,
    storage_uri=settings.redis_url,
    default_limits=["240/minute"],  # generous global ceiling; routes tighten it
    swallow_errors=True,            # Redis down → allow the request, don't 500
    in_memory_fallback_enabled=True,
)
