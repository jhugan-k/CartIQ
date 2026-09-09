"""Daily spend guards for the paid Gemini tier.

Rate limits stop one user hammering the API; these stop the BILL. They count
the two things that actually cost money and cap them across all users combined:

  gemini_requests   — every generateContent call (token spend)
  grounded_searches — Google Search grounding, metered separately at
                      5,000/month free, then $14 per 1,000

A per-user limit can't do this job: fifty users each inside their allowance
still spend fifty times the money.

Counters live in Redis under a date-stamped key with a 48h TTL, so a new day
starts clean and nothing needs sweeping.
"""

import logging
from datetime import date

from config import settings
from services.redis_client import get_redis

logger = logging.getLogger("cartiq.budget")

_TTL_SECONDS = 60 * 60 * 48  # outlives the day it counts, then disappears


class BudgetExceeded(Exception):
    """Raised when a daily spend cap is used up."""


# per-kind daily ceiling, read from settings so it is tunable without a deploy.
def _cap(kind: str) -> int:
    return {
        "gemini_requests": settings.daily_gemini_requests,
        "grounded_searches": settings.daily_grounded_searches,
    }[kind]


# today's Redis key for a counter, e.g. "budget:2026-09-09:grounded_searches".
def _key(kind: str) -> str:
    return f"budget:{date.today().isoformat()}:{kind}"


# read how much of today's allowance is already gone.
async def used(kind: str) -> int:
    raw = await get_redis().get(_key(kind))
    return int(raw or 0)


# refuse the request when the day's allowance is gone.
async def ensure(kind: str) -> None:
    """Raise BudgetExceeded if `kind` is at or over its daily cap.

    Deliberately a read-then-act check rather than a reservation: a chat makes
    an unknown number of Gemini calls, so we gate at the door and count the
    real usage afterwards. Concurrent requests can overshoot the cap slightly,
    bounded by how many are in flight — which is fine for a daily budget.
    """
    cap = _cap(kind)
    if cap <= 0:  # 0 disables the feature entirely rather than allowing it
        raise BudgetExceeded(f"{kind} is disabled (cap is 0)")
    try:
        spent = await used(kind)
    except Exception as exc:
        # Redis is the only place the counter lives. Failing open here would
        # mean unlimited spend during an outage, which is the exact thing this
        # module exists to prevent — so default to refusing, and let operators
        # opt into the other behaviour.
        if settings.budget_fail_open:
            logger.warning("budget check failed, allowing (fail-open): %s", exc)
            return
        raise BudgetExceeded(
            "Spend guard unavailable, so the request was refused to protect "
            "the budget. Try again shortly."
        ) from exc
    if spent >= cap:
        logger.warning("daily cap hit: %s at %d/%d", kind, spent, cap)
        raise BudgetExceeded(
            f"CartIQ has hit its daily {kind.replace('_', ' ')} limit "
            f"({cap}). It resets at midnight UTC."
        )


# record real usage after the fact; never raises, since the spend already
# happened and losing the count must not fail the user's request.
async def spend(kind: str, amount: int = 1) -> None:
    if amount <= 0:
        return
    try:
        redis = get_redis()
        key = _key(kind)
        total = await redis.incrby(key, amount)
        if total == amount:  # first write today — set the expiry once
            await redis.expire(key, _TTL_SECONDS)
        cap = _cap(kind)
        if total >= cap * 0.8:
            logger.warning("budget %s at %d/%d today", kind, total, cap)
    except Exception as exc:
        logger.warning("could not record %s spend: %s", kind, exc)


# small snapshot for a status endpoint or a log line.
async def snapshot() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for kind in ("gemini_requests", "grounded_searches"):
        try:
            out[kind] = {"used": await used(kind), "cap": _cap(kind)}
        except Exception:
            out[kind] = {"used": -1, "cap": _cap(kind)}
    return out
