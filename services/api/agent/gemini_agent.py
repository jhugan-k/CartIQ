"""Gemini agent — turns a natural-language message into tool calls and a reply.

Flow (a manual function-calling loop):
  1. Send the conversation + tool declarations to Gemini.
  2. If Gemini asks to call tool(s), run them and feed the results back.
  3. Repeat until Gemini returns a plain-text answer.

We drive the loop manually (rather than the SDK's auto-calling) because our
tools are async and it keeps every step explicit and debuggable.
"""

import asyncio

import google.genai as genai
from google.genai import errors as genai_errors
from google.genai import types

from config import settings
from schemas.chat import ChatMessage
from agent.context import current_pincode, current_user_id
from agent.tools import DISPATCH, FUNCTION_DECLARATIONS

_MAX_TOOL_ROUNDS = 5  # safety cap on tool-call iterations
_HTTP_TIMEOUT_MS = 25_000  # per-request HTTP timeout
_OVERALL_TIMEOUT_S = 30  # hard cap on the whole chat (all tool rounds)

# attempts=1 → no automatic backoff/retry. On the free Gemini tier a 429 then
# surfaces immediately as a clean "try again" instead of the SDK sleeping for
# ~40s of backoff and hanging the request.
_HTTP_OPTIONS = types.HttpOptions(
    timeout=_HTTP_TIMEOUT_MS,
    retry_options=types.HttpRetryOptions(attempts=1),
)

SYSTEM_PROMPT = (
    "You are CartIQ, a helpful shopping assistant for Indian quick-commerce apps "
    "(Blinkit, Zepto, Swiggy Instamart). Use the provided tools to look up real "
    "prices — never invent prices. When comparing a basket, call tool_compare and "
    "clearly state which platform is cheapest and by how much. Point out fake "
    "discounts (where the offer price equals the MRP). Be concise; format prices "
    "in ₹. If an item is unavailable on a platform, say so and offer to find "
    "alternatives.\n\n"
    "The user has a VIRTUAL CART you can manage. When they ask to add or remove "
    "items ('add coke zero to cart', 'put 2 milk in my cart'), CALL "
    "tool_add_to_cart / tool_remove_from_cart — do NOT say you cannot modify the "
    "cart. After changing the cart, confirm briefly what you did. Use tool_view_cart "
    "to check the cart when relevant."
)


class GeminiNotConfigured(Exception):
    """Raised when no GEMINI_API_KEY is set."""


class GeminiError(Exception):
    """Raised when the Gemini API call fails (quota, transient, etc.)."""


def _history_to_contents(history: list[ChatMessage]) -> list[types.Content]:
    contents: list[types.Content] = []
    for m in history:
        role = "model" if m.role == "model" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.text)]))
    return contents


def _extract_text(parts) -> str:
    return "".join(p.text for p in parts if getattr(p, "text", None)).strip()


async def run_chat(
    message: str,
    history: list[ChatMessage],
    user_id: str | None = None,
    pincode: str | None = None,
) -> tuple[str, list[str]]:
    """Return (reply_text, list_of_tool_names_used).

    Hard-capped at _OVERALL_TIMEOUT_S so a slow/rate-limited Gemini call surfaces
    a clean error instead of hanging the request (and the UI) indefinitely.
    """
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set")
    # Make the user id + location visible to the tools for this request.
    current_user_id.set(user_id)
    current_pincode.set(pincode)
    try:
        return await asyncio.wait_for(_drive(message, history), _OVERALL_TIMEOUT_S)
    except asyncio.TimeoutError as exc:
        raise GeminiError(
            "The assistant took too long to respond (likely a rate limit). "
            "Please try again in a few seconds."
        ) from exc


async def _drive(message: str, history: list[ChatMessage]) -> tuple[str, list[str]]:
    client = genai.Client(api_key=settings.gemini_api_key, http_options=_HTTP_OPTIONS)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=FUNCTION_DECLARATIONS)],
        temperature=0.3,
    )

    contents = _history_to_contents(history)
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    tools_used: list[str] = []

    for _ in range(_MAX_TOOL_ROUNDS):
        try:
            resp = await client.aio.models.generate_content(
                model=settings.gemini_model, contents=contents, config=config
            )
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) == 429:
                raise GeminiError(
                    "Gemini quota exceeded for this API key/model. Try again later "
                    "or switch GEMINI_MODEL."
                ) from exc
            raise GeminiError(f"Gemini request failed: {exc}") from exc
        except genai_errors.APIError as exc:
            raise GeminiError(f"Gemini request failed: {exc}") from exc
        except Exception as exc:  # httpx timeouts / network errors from the SDK
            raise GeminiError(f"Gemini request failed: {exc}") from exc
        candidate = resp.candidates[0]
        parts = candidate.content.parts or []
        function_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

        if not function_calls:
            return _extract_text(parts) or "(no response)", tools_used

        # Record the model's tool-calling turn.
        contents.append(candidate.content)

        # Execute each requested tool and collect the responses.
        response_parts = []
        for fc in function_calls:
            tools_used.append(fc.name)
            handler = DISPATCH.get(fc.name)
            args = dict(fc.args) if fc.args else {}
            if handler is None:
                result = {"error": f"unknown tool {fc.name}"}
            else:
                try:
                    result = await handler(**args)
                except Exception as exc:  # surface tool errors to the model
                    result = {"error": str(exc)}
            response_parts.append(
                types.Part.from_function_response(name=fc.name, response=result)
            )

        contents.append(types.Content(role="tool", parts=response_parts))

    return (
        "I wasn't able to finish that in a reasonable number of steps. "
        "Could you narrow the request?",
        tools_used,
    )
