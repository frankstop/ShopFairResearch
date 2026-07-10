from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"
MARKET_REFERENCE = {
    "store_number": "2758",
    "name": "Shop Fair of Uniondale",
    "address": "973 Front St, Uniondale, NY 11553",
    "note": "Local market reference only; public online prices are not asserted as shelf prices for this store.",
}


@dataclass(frozen=True)
class ProductObservation:
    product_key: str
    name: str
    brand: str | None
    current_price: float
    currency: str
    availability: str | None
    categories: list[str]
    source_url: str
    image_url: str | None
    description: str | None
    package_text: str | None
    price_valid_until: str | None
    observed_at: str
    retailer: str = "Shop Fair"
    price_scope: str = "public_online_catalog"
    market_reference: dict[str, str] = field(default_factory=lambda: dict(MARKET_REFERENCE))
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PromotionObservation:
    promotion_key: str
    name: str
    advertised_price: float
    regular_price: float | None
    unit_price_text: str | None
    offer_text: str | None
    valid_from: str | None
    valid_to: str | None
    source_url: str
    observed_at: str
    product_key: str | None = None
    retailer: str = "Shop Fair"
    price_scope: str = "weekly_ad_best_effort"
    market_reference: dict[str, str] = field(default_factory=lambda: dict(MARKET_REFERENCE))
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_date: str
    observed_at: str
    status: str
    catalog_products: int
    promotions: int
    product_sitemap_urls: int
    category_sitemap_urls: int
    sitemap_coverage_percentage: float
    prior_overlap_percentage: float | None
    valid_price_percentage: float
    requests: int
    errors: list[str]
    elapsed_seconds: float
    price_scope: str = "public_online_catalog"
    market_reference: dict[str, str] = field(default_factory=lambda: dict(MARKET_REFERENCE))
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
