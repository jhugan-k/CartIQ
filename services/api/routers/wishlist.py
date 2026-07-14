"""Wishlist routes: GET / POST / DELETE /wishlist (all auth-protected).

Wishlist items store NO prices — just the product name + the query used to look
it up. Prices are fetched live only when the user searches (lazy loading).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import get_current_user
from models import User, WishlistItem
from schemas.wishlist import WishlistItemCreate, WishlistItemResponse

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[WishlistItemResponse])
async def list_wishlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WishlistItem]:
    result = await db.execute(
        select(WishlistItem)
        .where(WishlistItem.user_id == user.id)
        .order_by(WishlistItem.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=WishlistItemResponse, status_code=status.HTTP_201_CREATED)
async def add_wishlist(
    body: WishlistItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WishlistItem:
    item = WishlistItem(
        user_id=user.id,
        product_name=body.product_name,
        product_query=body.product_query,
        platform_item_ids=body.platform_item_ids,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wishlist(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    item = await db.get(WishlistItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.delete(item)
    await db.commit()
