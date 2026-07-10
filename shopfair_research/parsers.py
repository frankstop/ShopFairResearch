from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .models import ProductObservation, PromotionObservation


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = re.sub(r"/{2,}", "/", parts.path)
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower() or "www.mercato.com", path, "", ""))


def _price(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None
    return round(parsed, 2) if parsed > 0 else None


def extract_slug_and_id(prod: dict[str, Any]) -> tuple[str, str]:
    long_url = prod.get("longUrl") or ""
    parts = [p for p in long_url.split("/") if p]
    if len(parts) >= 5 and parts[2] == "item":
        return parts[3], parts[4]
    
    # fallback
    name = prod.get("name") or "product"
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    product_id = str(prod.get("productId") or prod.get("storeProductId") or "0")
    return slug, product_id


def extract_package_text(price_display: str) -> str | None:
    if not price_display:
        return None
    cleaned = re.sub(r"^\$\d+(?:\.\d+)?\s*", "", price_display).strip()
    return cleaned if cleaned else None


def parse_product(
    prod: dict[str, Any],
    category_name: str,
    observed_at: str,
) -> tuple[ProductObservation, PromotionObservation | None]:
    slug, product_id = extract_slug_and_id(prod)
    product_key = f"/item/{slug}/{product_id}"
    
    name = prod.get("name", "").strip()
    current_price = _price(prod.get("price")) or 0.0
    
    availability = "InStock" if prod.get("inStock") else "OutOfStock"
    
    image_url = prod.get("largeImageUrl") or prod.get("mediumImageUrl") or None
    
    # absolute share URL for promotions / source URL
    source_url = f"https://www.mercato.com/item/{slug}/{prod.get('productId') or product_id}"
    
    package_text = extract_package_text(prod.get("priceDisplay", ""))
    
    product_obs = ProductObservation(
        product_key=product_key,
        name=name,
        brand=None,  # Mercato does not provide brand field in products payload
        current_price=current_price,
        currency="USD",
        availability=availability,
        categories=[category_name],
        source_url=source_url,
        image_url=image_url,
        description=None,
        package_text=package_text,
        price_valid_until=None,
        observed_at=observed_at,
    )
    
    # Sourced inline from product priceView.originalPrice API payloads
    price_view = prod.get("priceView") or {}
    original_price_str = price_view.get("originalPrice")
    promo_obs = None
    
    if original_price_str:
        regular_price = _price(original_price_str)
        if regular_price and regular_price > current_price:
            key_material = f"{product_key}|{current_price}|{regular_price}"
            promotion_key = hashlib.sha256(key_material.encode()).hexdigest()[:20]
            promo_obs = PromotionObservation(
                promotion_key=promotion_key,
                product_key=product_key,
                name=name,
                advertised_price=current_price,
                regular_price=regular_price,
                unit_price_text=prod.get("priceDisplay"),
                offer_text=None,
                valid_from=None,
                valid_to=None,
                source_url=source_url,
                observed_at=observed_at,
            )
            
    return product_obs, promo_obs


def merge_products(existing: ProductObservation, incoming: ProductObservation) -> ProductObservation:
    categories = sorted(set(existing.categories) | set(incoming.categories))
    values = existing.to_dict()
    values["categories"] = categories
    if not values.get("brand") and incoming.brand:
        values["brand"] = incoming.brand
    if not values.get("package_text") and incoming.package_text:
        values["package_text"] = incoming.package_text
    return ProductObservation(**{key: value for key, value in values.items() if key != "schema_version"})
