"""Gemini agent — turns a natural-language message into tool calls and a reply.

Flow (a manual function-calling loop):
  1. Send the conversation + tool declarations to Gemini.
  2. If Gemini asks to call tool(s), run them and feed the results back.
  3. Repeat until Gemini returns a plain-text answer.

We drive the loop manually (rather than the SDK's auto-calling) because our
tools are async and it keeps every step explicit and debuggable.
"""

import asyncio
import json
import logging
import random

import google.genai as genai
from google.genai import errors as genai_errors
from google.genai import types

from config import settings
from schemas.chat import ChatMessage
from agent.context import current_pincode, current_user_id
from agent.tools import DISPATCH, FUNCTION_DECLARATIONS

# logs the exact JSON each tool returns BEFORE the model sees it, so we can tell
# whether a wrong price came from the tool/QC API or from the model mangling it.
logger = logging.getLogger("cartiq.agent")

_MAX_TOOL_ROUNDS = 5  # safety cap on tool-call iterations
# Per-request HTTP timeout. 30s was too tight: an advisory turn sends ~20
# products back and the model has to reason over all of them, which took longer
# than that and surfaced as a blank "Gemini request failed:" in the UI. 60s
# still leaves room inside _OVERALL_TIMEOUT_S for a second round.
_HTTP_TIMEOUT_MS = 60_000
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

# Transient server-side failures: the model is overloaded (503) or we hit a
# gateway/internal error. Nothing about the request is wrong and they usually
# clear within a second or two, so these are the only statuses worth retrying —
# a 429 (quota) or any other 4xx will not fix itself.
_RETRYABLE_STATUSES = {500, 502, 503, 504}
_MAX_ATTEMPTS = 3  # 1 initial call + 2 retries
_RETRY_BASE_DELAY_S = 1.0  # doubled each retry, plus jitter

# The agent's whole behaviour contract. Two things it must hold at once:
# prices are never allowed to come from the model, and reasoning is opt-in
# so a routine price lookup doesn't pay for an analysis nobody asked for.
SYSTEM_PROMPT = """You are CartIQ, a shopping assistant for Indian quick-commerce apps
(Blinkit, Zepto, Swiggy Instamart).

CRITICAL — every message is a FRESH request:
- ALWAYS call a tool to look up the EXACT item in the user's CURRENT message,
  and take every price, product and platform ONLY from that tool's result.
  NEVER reuse a price from earlier in the conversation, and NEVER state a price
  from your own knowledge — prior turns are context for follow-ups only, NEVER
  a source of prices. If the earlier answer was about a different item, ignore
  its numbers entirely and search the new item.

TWO MODES — default to the cheap one:
1. LOOKUP (the default, and almost every message): the user wants a price, a
   total, or availability. Answer in one or two lines straight from the tool
   result. Do NOT analyse ingredients, weigh options, rank products, or
   volunteer a recommendation. Do NOT pass detailed=true.
2. ADVISORY (only when the user explicitly asks): they ask which product is
   best, what to buy, whether something is worth it, for value for money, or to
   analyse what a product contains or whether it suits them. Only then pass
   detailed=true to the search tools and give a reasoned answer.
Never enter ADVISORY mode on your own initiative. A plain price question gets a
plain price answer — extra analysis nobody asked for is a bug, not a bonus.

IN ADVISORY MODE:
- Prices, pack sizes and availability STILL come only from the tools.
- Product knowledge (what an ingredient does, what suits dry or oily skin, why
  a formulation matters) MAY come from your own knowledge. Say plainly which
  parts are general knowledge rather than live data, and do not state a
  product's ingredient list as fact unless the tool data showed it to you.
- Judge value on `unit_price`, never sticker price: a larger pack at a higher
  price is usually cheaper per unit, and two packs of the same item can have
  identical unit prices.
- Treat `rating` as a weak signal, and say so when `rating_count` is small.
- Recommend ONE option and justify it in a sentence or two. No essays.

STYLE — be brief and to the point:
- Lead with the answer in one sentence (e.g. 'Zepto is cheapest at ₹133').
- Prefer a compact bullet list or small table over paragraphs. No preamble, no
  restating the question, no filler.
- Only add a short follow-up offer if genuinely useful; keep it to one line.
- Prices in ₹. Never invent prices — always use the tools.

RULES:
- Comparisons: call tool_compare; say which platform is cheapest and by how
  much. Per item, show the matched product + pack size briefly (e.g. 'Milk →
  Amul Taaza 1 L ₹69') since the match may be a different brand/size.
- Flag fake discounts (offer price == MRP).
- Each line item has `status`: 'ok' | 'out_of_stock' | 'no_data'. For 'no_data'
  say 'no data for <platform>' (a coverage gap) — NEVER 'out of stock'. Only
  'out_of_stock' means actually out of stock.
- Cart: on 'add/remove ... to cart' CALL tool_add_to_cart /
  tool_remove_from_cart (never say you can't); confirm in one short line. Use
  tool_view_cart when relevant. When you know which app is cheapest/best for an
  item, pass its `platform` (blinkit/zepto/swiggy) to tool_add_to_cart so the
  cart shows the right app."""


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


# one Gemini call, with a short retry on the transient 5xx the hosted models
# throw under load.
async def _generate(
    client: genai.Client,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
) -> types.GenerateContentResponse:
    """Call generate_content, retrying only self-clearing server errors.

    The shared flash/flash-lite endpoints return 503 UNAVAILABLE ("high demand")
    often enough that a single attempt makes the chat look broken. The SDK's own
    backoff stays off (see _HTTP_OPTIONS) because it also sleeps ~40s on a 429;
    this loop retries the overload statuses only, and briefly. Worst case it
    adds ~3.5s, well inside _OVERALL_TIMEOUT_S.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return await client.aio.models.generate_content(
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
            if getattr(exc, "code", None) not in _RETRYABLE_STATUSES:
                raise GeminiError(f"Gemini request failed: {exc}") from exc
            last_exc = exc  # overloaded — fall through to the backoff below
        except Exception as exc:  # httpx timeouts / network errors from the SDK
            # A timeout's str() is empty, which rendered as a bare "Gemini
            # request failed:" with nothing after it. Say something useful.
            detail = str(exc) or f"{type(exc).__name__} after {_HTTP_TIMEOUT_MS // 1000}s"
            raise GeminiError(f"Gemini request failed: {detail}") from exc

        if attempt < _MAX_ATTEMPTS - 1:
            # jitter so several concurrent chats don't retry in lockstep and
            # re-overload the same model.
            delay = _RETRY_BASE_DELAY_S * 2**attempt + random.uniform(0, 0.4)
            logger.warning(
                "Gemini %s on %s — retrying in %.1fs (attempt %d/%d)",
                getattr(last_exc, "code", "5xx"),
                settings.gemini_model,
                delay,
                attempt + 1,
                _MAX_ATTEMPTS,
            )
            await asyncio.sleep(delay)

    raise GeminiError(
        "Gemini is temporarily overloaded and didn't recover after a few "
        "retries. Please try again in a moment."
    ) from last_exc


# run one tool call and wrap its result for the model.
async def _run_tool(fc) -> types.Part:
    """Execute a single tool call. Never raises — a failure goes back to the
    model as data so it can recover or explain, rather than killing the chat."""
    handler = DISPATCH.get(fc.name)
    args = dict(fc.args) if fc.args else {}
    if handler is None:
        result = {"error": f"unknown tool {fc.name}"}
    else:
        try:
            result = await handler(**args)
        except Exception as exc:  # surface tool errors to the model
            result = {"error": str(exc)}
    # log the raw tool result the model is about to consume. This is the ground
    # truth: if a price here is wrong it's the tool/QC API; if it's right here
    # but wrong in the reply, the model corrupted it.
    logger.info(
        "TOOL %s args=%s -> %s",
        fc.name,
        json.dumps(args, ensure_ascii=False, default=str),
        json.dumps(result, ensure_ascii=False, default=str),
    )
    return types.Part.from_function_response(name=fc.name, response=result)


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
        resp = await _generate(client, contents, config)
        candidate = resp.candidates[0]
        parts = candidate.content.parts or []
        function_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

        if not function_calls:
            return _extract_text(parts) or "(no response)", tools_used

        # record the model's tool-calling turn.
        contents.append(candidate.content)

        # Run this round's tools CONCURRENTLY. A live QC search is ~15s, so
        # three lookups cost ~45s of the 90s budget when run one after another
        # and ~15s when gathered — which is what lets an advisory request (more
        # searches per round) finish at all. Each task inherits a copy of the
        # current context, so the pincode/user-id contextvars still resolve.
        tools_used.extend(fc.name for fc in function_calls)
        response_parts = list(
            await asyncio.gather(*(_run_tool(fc) for fc in function_calls))
        )

        # gemini expects function results back under the "user" role — "tool" is
        # the OpenAI convention and is rejected here with a 400.
        contents.append(types.Content(role="user", parts=response_parts))

    return (
        "I wasn't able to finish that in a reasonable number of steps. "
        "Could you narrow the request?",
        tools_used,
    )
