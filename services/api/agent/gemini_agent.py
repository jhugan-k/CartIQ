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
_HTTP_TIMEOUT_MS = 30_000  # per Gemini-request HTTP timeout
# A live QC groupsearch takes ~15s, and a multi-item cart compare fans out
# several of them, so the whole chat gets a generous cap.
_OVERALL_TIMEOUT_S = 90  # hard cap on the whole chat (all tool rounds)

# attempts=1 → no automatic backoff/retry. On the free Gemini tier a 429 then
# surfaces immediately as a clean "try again" instead of the SDK sleeping for
# ~40s of backoff and hanging the request.
_HTTP_OPTIONS = types.HttpOptions(
    timeout=_HTTP_TIMEOUT_MS,
    retry_options=types.HttpRetryOptions(attempts=1),
)

SYSTEM_PROMPT = (
    "You are CartIQ, a shopping assistant for Indian quick-commerce apps "
    "(Blinkit, Zepto, Swiggy Instamart).\n\n"
    "CRITICAL — every message is a FRESH request:\n"
    "- ALWAYS call a tool to look up the EXACT item in the user's CURRENT message, "
    "and answer ONLY from that tool's result. NEVER reuse a price, product, or "
    "platform from earlier in the conversation — prior turns are context for "
    "follow-ups only, NEVER a source of prices. If the earlier answer was about a "
    "different item, ignore its numbers entirely and search the new item.\n\n"
    "STYLE — be brief and to the point:\n"
    "- Lead with the answer in one sentence (e.g. 'Zepto is cheapest at ₹133').\n"
    "- Prefer a compact bullet list or small table over paragraphs. No preamble, "
    "no restating the question, no filler.\n"
    "- Only add a short follow-up offer if genuinely useful; keep it to one line.\n"
    "- Prices in ₹. Never invent prices — always use the tools.\n\n"
    "RULES:\n"
    "- Comparisons: call tool_compare; say which platform is cheapest and by how "
    "much. Per item, show the matched product + pack size briefly (e.g. 'Milk → "
    "Amul Taaza 1 L ₹69') since the match may be a different brand/size.\n"
    "- Flag fake discounts (offer price == MRP).\n"
    "- Each line item has `status`: 'ok' | 'out_of_stock' | 'no_data'. For "
    "'no_data' say 'no data for <platform>' (a coverage gap) — NEVER 'out of "
    "stock'. Only 'out_of_stock' means actually out of stock.\n"
    "- Cart: on 'add/remove ... to cart' CALL tool_add_to_cart / "
    "tool_remove_from_cart (never say you can't); confirm in one short line. Use "
    "tool_view_cart when relevant. When you know which app is cheapest/best for an "
    "item, pass its `platform` (blinkit/zepto/swiggy) to tool_add_to_cart so the "
    "cart shows the right app."
)


class GeminiNotConfigured(Exception):
    """Raised when no GEMINI_API_KEY is set."""


class GeminiError(Exception):
    """Raised when the Gemini API call fails (quota, transient, etc.)."""


_MAX_HISTORY = 8  # keep only recent turns so old prices can't anchor the model


# convert recent chat turns into Gemini's message format, dropping older ones
# so stale prices can't anchor the model's answer.
def _history_to_contents(history: list[ChatMessage]) -> list[types.Content]:
    contents: list[types.Content] = []
    for m in history[-_MAX_HISTORY:]:
        role = "model" if m.role == "model" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m.text)]))
    return contents


# pull the plain-text answer out of a model response.
def _extract_text(parts) -> str:
    return "".join(p.text for p in parts if getattr(p, "text", None)).strip()


# public entrypoint: set per-request context and run the agent under a hard
# timeout so a slow vendor call can never hang the request forever.
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
    # make the user id + location visible to the tools for this request.
    current_user_id.set(user_id)
    current_pincode.set(pincode)
    try:
        return await asyncio.wait_for(_drive(message, history), _OVERALL_TIMEOUT_S)
    except asyncio.TimeoutError as exc:
        raise GeminiError(
            "That took too long — fetching live prices for several items can be "
            "slow. Try again (repeat searches are cached and much faster), or "
            "compare fewer items at once."
        ) from exc


# the function-calling loop: ask Gemini, run any tools it requests, feed the
# results back, and repeat until it returns a normal text reply.
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

        # record the model's tool-calling turn.
        contents.append(candidate.content)

        # execute each requested tool and collect the responses.
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
