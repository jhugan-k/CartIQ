"""Search schemas — the normalized shape of product data.

The raw QuickCommerce API response is messy and platform-specific. The QC client
(Part 7) maps it into these clean `Product` objects, so the rest of the app —
and the frontend — never sees the external API's format.
"""

from pydantic import BaseModel, Field, model_validator


class Product(BaseModel):
    """One product on one platform, normalized."""

    platform: str
    item_id: str | None = None
    name: str
    brand: str | None = None
    mrp: float
    offer_price: float
    quantity: str | None = None  # e.g. "500 g", "1 L"
    rating: float | None = None
    rating_count: int | None = None
    available: bool = True
    image_url: str | None = None
    deeplink: str | None = None
    # Computed below — not sent by the API.
    fake_discount: bool = False

    @model_validator(mode="after")
    def flag_fake_discount(self) -> "Product":
        """A 'discount' where offer_price == mrp isn't a real discount."""
        self.fake_discount = self.offer_price >= self.mrp
        return self


class PlatformResults(BaseModel):
    """All products found for a query on a single platform."""

    platform: str
    products: list[Product] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """GET /search response — results grouped by platform."""

    query: str
    platforms: list[PlatformResults] = Field(default_factory=list)
