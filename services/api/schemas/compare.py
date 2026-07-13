"""Cart comparison schemas.

The core value of CartIQ: take a cart of items, price it on every platform, and
show which platform is cheapest overall.
"""

from pydantic import BaseModel, Field

# Delhi test location (from QuickCommerce testing).
DEFAULT_LAT = 28.6139
DEFAULT_LON = 77.2090
DEFAULT_PINCODE = "110063"


class CartItem(BaseModel):
    """One line the user wants to buy."""

    query: str = Field(min_length=1, max_length=255)  # e.g. "amul butter"
    quantity: int = Field(default=1, ge=1)


class CartCompareRequest(BaseModel):
    """POST /cart/compare body."""

    items: list[CartItem] = Field(min_length=1)
    platforms: list[str] = Field(default_factory=lambda: ["blinkit", "zepto", "swiggy"])
    lat: float = DEFAULT_LAT
    lon: float = DEFAULT_LON
    pincode: str = DEFAULT_PINCODE


class PlatformLineItem(BaseModel):
    """The cheapest matching product for one cart item on one platform."""

    query: str
    product_name: str | None = None
    offer_price: float | None = None
    quantity_label: str | None = None  # the pack size, e.g. "500 g"
    units: int = 1  # how many of this item the user wanted
    line_total: float | None = None  # offer_price * units
    available: bool = True


class PlatformTotal(BaseModel):
    """A full priced cart for a single platform."""

    platform: str
    line_items: list[PlatformLineItem] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)  # queries not found
    total: float = 0.0


class CartCompareResponse(BaseModel):
    """POST /cart/compare response — one priced cart per platform + the winner."""

    platform_totals: list[PlatformTotal] = Field(default_factory=list)
    cheapest_platform: str | None = None
