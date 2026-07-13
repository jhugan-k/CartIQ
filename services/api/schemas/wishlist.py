"""Wishlist schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WishlistItemCreate(BaseModel):
    """POST /wishlist body."""

    product_name: str = Field(min_length=1, max_length=255)
    product_query: str = Field(min_length=1, max_length=255)
    # Optional known platform item IDs — user may save just a name for now.
    platform_item_ids: dict[str, str] = Field(default_factory=dict)


class WishlistItemResponse(BaseModel):
    """A saved wishlist item as returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_name: str
    product_query: str
    platform_item_ids: dict[str, str]
    created_at: datetime
