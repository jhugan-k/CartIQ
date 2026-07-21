"""Chat schemas — the natural-language interface to CartIQ."""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """One prior turn. role is 'user' or 'model' (Gemini's naming)."""

    role: str
    text: str


class ChatRequest(BaseModel):
    """POST /chat body."""

    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    # delivery pincode for location-accurate prices (optional).
    pincode: str | None = None


class ChatResponse(BaseModel):
    """POST /chat response."""

    reply: str
    tools_used: list[str] = Field(default_factory=list)
