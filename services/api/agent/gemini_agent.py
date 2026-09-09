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
from services import budget
from services.budget import BudgetExceeded

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

# url_context only fetches URLs it sees in TEXT — a URL inside a functionResponse
# payload is invisible to it (verified: the model claimed pages were
# "inaccessible" without ever fetching one). So after each tool round we repeat
# the product links as a text part. Capped, because an advisory search can
# return ~18 of them and the point is for the model to open 2-3.
_MAX_PAGE_HINTS = 12
_PAGE_HINT = (
    "Product pages you can open to read real ingredient lists. Open only the "
    "2-3 you actually shortlist. This list is about PAGE ACCESS ONLY — it must "
    "not narrow which products you consider. Compare and rank every product "
    "the tool returned, including ones absent from this list:\n"
)
# Verified 2026-09-09: the fetcher reads Blinkit product pages fine but Swiggy
# Instamart returns URL_RETRIEVAL_STATUS_ERROR. Offering a URL that can't be
# fetched costs a wasted round trip and makes the model tell the user about
# "platform blocks", so only advertise hosts known to work. Zepto is untested —
# it has not returned results for any query we've tried.
_READABLE_PAGE_HOSTS = ("blinkit.com",)
_PAGE_HINT_PARTIAL = (
    "\nPages for the remaining products can't be opened — search the web for "
    "those products' ingredients instead. They still compete on equal terms: "
    "keep them in the comparison and recommend one if it is genuinely the best "
    "value."
)
_NO_PAGES_HINT = (
    "None of these product pages can be opened. Search the web for the "
    "ingredients of the products you shortlist, and only fall back to general "
    "knowledge if that also turns up nothing. Do not tell the user about "
    "scraping or platform blocks — that is our problem, not theirs."
)

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
- READ THE PACK LABEL for the 2-3 candidates you shortlist — not all of them,
  that is slow. Try these in order:
  1. Open the product page `url` from the tool result.
  2. If it won't open, SEARCH THE WEB for that product's ingredients. A
     formulation belongs to the product, not to the app selling it, so the
     brand's own page answers just as well as the listing.
  3. Only if both fail, fall back to general knowledge and label it as such.
- WEB SEARCH IS FOR FORMULATION FACTS ONLY. Never take a product, price, pack
  size or availability from a search result, and NEVER recommend a product the
  tools did not return. If a search surfaces some other product, ignore it
  entirely — it may not even be buyable on these apps. Every product you name
  and every price you quote must appear in the tool result you were given.
- Never mention scraping, blocked pages or technical restrictions — they mean
  nothing to the user. NEVER present an ingredient list as fact unless you
  actually read it from a page or a search result.
- Interpreting those ingredients (what a surfactant does, what suits dry or
  oily skin, why a formulation matters) is your own expertise — use it, and be
  clear about which parts are general knowledge rather than live data.
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
- Never emit citation markers like [1.1] or [2.3]. The user sees plain text
  with no source list, so they read as noise. If a claim came from a product
  page you opened, just say so in words.

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
    # Cheapest possible rejection: refuse at the door once the day's token
    # budget is gone, before any vendor call is made. Raises BudgetExceeded,
    # which the chat route turns into a 429.
    await budget.ensure("gemini_requests")
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


# pull (name, url) pairs out of a tool result so they can be shown as text.
def _product_pages(result) -> list[tuple[str, str]]:
    """Walk a tool result for products carrying a page URL.

    Only the detailed product shape includes `url`, so this returns nothing for
    ordinary price lookups — which is what keeps page-reading opt-in.
    """
    found: list[tuple[str, str]] = []

    def walk(node):
        if isinstance(node, dict):
            url, name = node.get("url"), node.get("name")
            if isinstance(url, str) and isinstance(name, str):
                found.append((name, url))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(result)
    return found


# run one tool call and wrap its result for the model.
async def _run_tool(fc) -> tuple[types.Part, list[tuple[str, str]]]:
    """Execute a single tool call, returning its response part and any product
    pages it mentioned. Never raises — a failure goes back to the model as data
    so it can recover or explain, rather than killing the chat."""
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
    return (
        types.Part.from_function_response(name=fc.name, response=result),
        _product_pages(result),
    )


# the function-calling loop: ask Gemini, run any tools it requests, feed the
# results back, and repeat until it returns a normal text reply.
async def _drive(message: str, history: list[ChatMessage]) -> tuple[str, list[str]]:
    client = genai.Client(api_key=settings.gemini_api_key, http_options=_HTTP_OPTIONS)
    tools = [
        types.Tool(function_declarations=FUNCTION_DECLARATIONS),
        # Lets the model read a product page itself — the QC API returns no
        # ingredient data at all. Works on Blinkit; Swiggy blocks the fetcher
        # (see _READABLE_PAGE_HOSTS). Costs nothing beyond tokens.
        types.Tool(url_context=types.UrlContext()),
    ]

    # Grounding is the one metered capability (5,000 searches/month free, then
    # $14 per 1,000), so it is the one we drop when the day's budget is gone.
    # Dropping the tool degrades gracefully: price lookups are untouched and an
    # advisory answer falls back to page reading plus labelled general
    # knowledge, instead of the whole chat failing over a cost cap.
    try:
        await budget.ensure("grounded_searches")
        # Search is here to explain a formulation, not to price one. Left to
        # itself the model began recommending products the tools never returned
        # and quoting prices read off the web — exactly what "prices only from
        # tools" guards against. Restricting retail domains would be the
        # structural fix, but `exclude_domains` is Gemini Enterprise only, so
        # the SYSTEM_PROMPT rule is the only guard. Re-check it when the prompt
        # changes.
        tools.append(types.Tool(google_search=types.GoogleSearch()))
    except BudgetExceeded as exc:
        logger.warning("grounding disabled for this chat: %s", exc)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=tools,
        # Required whenever a built-in tool and our function declarations appear
        # together; without it the API rejects the request outright.
        tool_config=types.ToolConfig(include_server_side_tool_invocations=True),
        temperature=0.3,
    )

    contents = _history_to_contents(history)
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    tools_used: list[str] = []

    for _ in range(_MAX_TOOL_ROUNDS):
        resp = await _generate(client, contents, config)
        candidate = resp.candidates[0]

        # Record what this round actually cost. Requests bill tokens; grounded
        # searches bill separately per search, so count the queries the model
        # really ran rather than assuming one per round.
        await budget.spend("gemini_requests")
        grounding = getattr(candidate, "grounding_metadata", None)
        searches = getattr(grounding, "web_search_queries", None) or []
        if searches:
            await budget.spend("grounded_searches", len(searches))

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
        results = await asyncio.gather(*(_run_tool(fc) for fc in function_calls))
        response_parts = [part for part, _ in results]

        # Repeat any product links as text so url_context can actually see them,
        # but only the ones its fetcher can really open.
        pages = [page for _, found in results for page in found]
        readable = [
            page
            for page in pages
            if any(host in page[1] for host in _READABLE_PAGE_HOSTS)
        ][:_MAX_PAGE_HINTS]
        if readable:
            listing = "\n".join(f"- {name}: {url}" for name, url in readable)
            hint = _PAGE_HINT + listing
            if len(readable) < len(pages):
                hint += _PAGE_HINT_PARTIAL
            response_parts.append(types.Part.from_text(text=hint))
        elif pages:
            response_parts.append(types.Part.from_text(text=_NO_PAGES_HINT))

        # gemini expects function results back under the "user" role — "tool" is
        # the OpenAI convention and is rejected here with a 400.
        contents.append(types.Content(role="user", parts=response_parts))

    return (
        "I wasn't able to finish that in a reasonable number of steps. "
        "Could you narrow the request?",
        tools_used,
    )
