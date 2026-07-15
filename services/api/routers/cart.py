"""Virtual cart routes — the user-facing CRUD (all auth-protected).

The AI mutates the same cart via tools (agent/tools.py), so both stay in sync.
"""

from fastapi import APIRouter, Depends

from dependencies import get_current_user
from models import User
from schemas.cart import AddToCartRequest, CartState, UpdateQtyRequest
from services import cart_store

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartState)
async def get_cart(user: User = Depends(get_current_user)) -> CartState:
    return CartState(items=await cart_store.get_cart(str(user.id)))


@router.post("/add", response_model=CartState)
async def add_to_cart(
    body: AddToCartRequest, user: User = Depends(get_current_user)
) -> CartState:
    items = await cart_store.add_item(
        str(user.id), body.name, body.quantity, "user", body.platform
    )
    return CartState(items=items)


@router.patch("/item/{item_id}", response_model=CartState)
async def update_item(
    item_id: str, body: UpdateQtyRequest, user: User = Depends(get_current_user)
) -> CartState:
    return CartState(items=await cart_store.update_qty(str(user.id), item_id, body.quantity))


@router.delete("/item/{item_id}", response_model=CartState)
async def remove_item(item_id: str, user: User = Depends(get_current_user)) -> CartState:
    return CartState(items=await cart_store.remove_item(str(user.id), item_id))


@router.delete("", response_model=CartState)
async def clear_cart(user: User = Depends(get_current_user)) -> CartState:
    return CartState(items=await cart_store.clear(str(user.id)))
