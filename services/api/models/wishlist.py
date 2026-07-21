"""WishlistItem model — a product a user saved, stored WITHOUT prices.

Prices are fetched live only when the user searches (lazy loading) so we don't
burn QuickCommerce credits keeping every wishlist item priced.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.user import User


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # the search term used to look this product up (e.g. "amul butter").
    product_query: Mapped[str] = mapped_column(String(255), nullable=False)
    # known platform-specific item IDs, e.g. {"blinkit": "abc", "zepto": "xyz"}.
    # JSONB so adding a new platform needs no schema migration.
    platform_item_ids: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="wishlist_items")
