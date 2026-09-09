"""Chat route: POST /chat — the natural-language entrypoint.

Auth-protected so the agent knows which user's cart to manage. Hands the message
to the Gemini agent, which decides which tools to call and returns a reply.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from agent.gemini_agent import GeminiError, GeminiNotConfigured, run_chat
from services.budget import BudgetExceeded
from dependencies import get_current_user
from models import User
from rate_limit import limiter
from schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


# the natural-language entrypoint: hand the message to the Gemini agent and
# translate any agent failure into a clean HTTP error.
#
# Tightest limit in the app: every call spends paid Gemini tokens and vendor
# credits, so it is metered PER USER (a leaked token can't drain the budget
# from one IP). The daily cap matters most now that Gemini bills for real — one
# client looping overnight is the realistic way to run up a bill.
#
# This is only half the protection: per-user limits bound one caller, while
# services/budget.py caps total spend across everyone. Both are needed —
# fifty users each inside this limit still cost fifty times the money.
@router.post("/chat", response_model=ChatResponse)
@limiter.limit("8/minute;50/hour;120/day")
async def chat(
    request: Request, body: ChatRequest, user: User = Depends(get_current_user)
) -> ChatResponse:
    try:
        reply, tools_used = await run_chat(
            body.message, body.history, user_id=str(user.id), pincode=body.pincode
        )
    except GeminiNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat is unavailable: GEMINI_API_KEY is not configured.",
        )
    except BudgetExceeded as exc:
        # A spend cap is a "come back later", not a server fault — 429 with a
        # Retry-After so clients back off instead of hammering.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "3600"},
        )
    except GeminiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
    return ChatResponse(reply=reply, tools_used=tools_used)
