"""Re-export every schema for convenient imports (`from schemas import Token`)."""

from schemas.auth import Token, UserLogin, UserRegister, UserResponse
from schemas.compare import (
    CartCompareRequest,
    CartCompareResponse,
    CartItem,
    PlatformLineItem,
    PlatformTotal,
)
from schemas.search import PlatformResults, Product, SearchResponse
from schemas.wishlist import WishlistItemCreate, WishlistItemResponse

__all__ = [
    # auth
    "Token",
    "UserLogin",
    "UserRegister",
    "UserResponse",
    # wishlist
    "WishlistItemCreate",
    "WishlistItemResponse",
    # search
    "Product",
    "PlatformResults",
    "SearchResponse",
    # compare
    "CartItem",
    "CartCompareRequest",
    "PlatformLineItem",
    "PlatformTotal",
    "CartCompareResponse",
]
