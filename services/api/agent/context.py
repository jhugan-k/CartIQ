"""Per-request context for the agent.

The Gemini tools are dispatched with arguments the model chooses — which never
include the user's identity. We stash the current user id in a ContextVar so the
cart tools know whose cart to mutate, without the model having to pass it.
"""

from contextvars import ContextVar

current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)

# the delivery pincode for the current request — location changes prices and
# availability, so tools pass it to the search API (falls back to a default).
current_pincode: ContextVar[str | None] = ContextVar("current_pincode", default=None)
