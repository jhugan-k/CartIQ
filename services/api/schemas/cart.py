"""Virtual cart schemas.

The virtual cart is a per-user shopping list that BOTH the user (via the UI) and
the AI agent (via tools) can modify. It's session-scoped, stored in Redis.
"""

from pydantic import BaseModel, Field


class CartLineItem(BaseModel):
    id: str
    name: str
    quantity: int = 1
    added_by: str = "user"  # "user" or "assistant"
    # platform the AI recommends this item from (blinkit/zepto/swiggy), if known.
    platform: str | None = None


class CartState(BaseModel):
    items: list[CartLineItem] = Field(default_factory=list)


class AddToCartRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=1)
    platform: str | None = None


class UpdateQtyRequest(BaseModel):
    quantity: int = Field(ge=1)
