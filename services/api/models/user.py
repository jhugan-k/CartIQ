"""User model — one row per registered account."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.cart_history import CartHistory
    from models.wishlist import WishlistItem


class User(Base):
    __tablename__ = "users" # table name, dunders are used to show it's a special config instruction.
    # create columns with types and constraints. Mapped[] is a type hint for SQLAlchemy's ORM.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    ) # unique identifier for each user
    
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    #  email is unique and indexed for fast lookups, cannot be null
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    #  hashed password, cannot be null
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    #  timestamp of when the user was created, defaults to current time

    # ORM-side conveniences — no extra columns. Deleting a user cascades to both.
    wishlist_items: Mapped[list["WishlistItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    ) # many to one relationship with WishlistItem, deleting a user deletes their wishlist items
    cart_histories: Mapped[list["CartHistory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    ) # many to one relationship with CartHistory, deleting a user deletes their cart histories
