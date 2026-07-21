"""CartHistory model — a snapshot of one cart comparison the user ran.

Stores what was in the cart and the prices seen at that moment, so the user can
look back at past comparisons. Both snapshots are JSONB blobs — their shape is
flexible and we never query inside them, only store and return them whole.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.user import User # prevent circular import; only needed for type hints. python ignores type hints at runtime, so this is safe.


class CartHistory(Base):
    __tablename__ = "cart_histories" # create table name, dunders are used to show it's a special config instruction.

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ) 
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), #converts database text to native python UUID objects and vice versa
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # the items the user was comparing (names / queries / quantities).
    cart_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # the per-platform prices and totals computed at comparison time.
    price_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="cart_histories") # deletes the CartHistory if the User is deleted, and vice versa. This is the ORM-side convenience; the database-level foreign key constraint is already set to cascade on delete.
