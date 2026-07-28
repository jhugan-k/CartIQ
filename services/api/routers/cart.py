"""Virtual cart routes — the user-facing CRUD (all auth-protected).

The AI mutates the same cart via tools (agent/tools.py), so both stay in sync.
"""

from fastapi import APIRouter, Depends, Request

from dependencies import get_current_user
from models import User
from rate_limit import limiter
from schemas.cart import AddToCartRequest, CartState, UpdateQtyRequest
from services import cart_store

router = APIRouter(prefix="/cart", tags=["cart"])


# return the user's current virtual cart.
@router.get("", response_model=CartState)
async def get_cart(user: User = Depends(get_current_user)) -> CartState:
    return CartState(items=await cart_store.get_cart(str(user.id)))


# add an item to the cart on the user's behalf.
@router.post("/add", response_model=CartState)
@limiter.limit("60/minute")  # per-user write ceiling (Redis mutation)
async def add_to_cart(
    request: Request,
    body: AddToCartRequest,
    user: User = Depends(get_current_user),
) -> CartState:
    items = await cart_store.add_item(
        str(user.id), body.name, body.quantity, "user", body.platform
    )
    return CartState(items=items)


# change the quantity of one cart item.
@router.patch("/item/{item_id}", response_model=CartState)
@limiter.limit("60/minute")
async def update_item(
    request: Request,
    item_id: str,
    body: UpdateQtyRequest,
    user: User = Depends(get_current_user),
) -> CartState:
    return CartState(items=await cart_store.update_qty(str(user.id), item_id, body.quantity))


# remove one item from the cart.
@router.delete("/item/{item_id}", response_model=CartState)
@limiter.limit("60/minute")
async def remove_item(
    request: Request, item_id: str, user: User = Depends(get_current_user)
) -> CartState:
    return CartState(items=await cart_store.remove_item(str(user.id), item_id))


# empty the whole cart.
@router.delete("", response_model=CartState)
@limiter.limit("60/minute")
async def clear_cart(
    request: Request, user: User = Depends(get_current_user)
) -> CartState:
    return CartState(items=await cart_store.clear(str(user.id)))
