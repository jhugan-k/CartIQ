"""Chat route: POST /chat — the natural-language entrypoint.

Auth-protected so the agent knows which user's cart to manage. Hands the message
to the Gemini agent, which decides which tools to call and returns a reply.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from agent.gemini_agent import GeminiError, GeminiNotConfigured, run_chat
from dependencies import get_current_user
from models import User
from schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest, user: User = Depends(get_current_user)
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
    except GeminiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        )
    return ChatResponse(reply=reply, tools_used=tools_used)
