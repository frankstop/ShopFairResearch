from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import logging
import time
import json
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from .models import ProductObservation, PromotionObservation
from .parsers import parse_product, merge_products


LOGGER = logging.getLogger(__name__)
BASE_URL = "https://www.mercato.com"
STORE_URL_NAME = "shop-fair-supermarket-3"
STOREFRONT_URL = f"{BASE_URL}/shop/{STORE_URL_NAME}"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "ShopFairResearch/1.0 (+https://github.com/frankstop/ShopFairResearch)"


@dataclass
class SourceInventory:
    category_ids: list[int]
    category_names: dict[int, str]


class PoliteClient:
    def __init__(
        self,
        delay_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        retries: int = 3,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self.delay_seconds = max(delay_seconds, 0.0)
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.opener = opener
        self.requests = 0
        self._last_request_at = 0.0

    def fetch_bytes(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.delay_seconds:
                time.sleep(self.delay_seconds - elapsed)
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Encoding": "gzip",
                },
            )
            try:
                self.requests += 1
                self._last_request_at = time.monotonic()
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    payload = response.read()
                    encoding = response.headers.get("Content-Encoding", "")
                    if encoding == "gzip" or payload.startswith(b"\x1f\x8b"):
                        payload = gzip.decompress(payload)
                    return payload
            except HTTPError as error:
                last_error = error
                if error.code != 429 and error.code < 500:
                    break
            except (URLError, TimeoutError, OSError) as error:
                last_error = error
            if attempt < self.retries:
                time.sleep(2**attempt)
        raise CollectionError(f"Failed to fetch {url}: {last_error}")

    def fetch_text(self, url: str) -> str:
        return self.fetch_bytes(url).decode("utf-8", errors="replace")


class CollectionError(RuntimeError):
    pass


def verify_robots(client: PoliteClient) -> str:
    robots_text = client.fetch_text(ROBOTS_URL)
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(robots_text.splitlines())
    if not parser.can_fetch(USER_AGENT, f"{BASE_URL}/shop/shop-fair-supermarket-3"):
        raise CollectionError("robots.txt does not allow catalog collection under /shop/")
    return robots_text


def discover_sources(client: PoliteClient) -> SourceInventory:
    # Try HTML page first
    try:
        html = client.fetch_text(STOREFRONT_URL)
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
        if match:
            data = json.loads(match.group(1))
            initialState = data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("data", {})
            aisles = initialState.get("storeResults", {}).get("data", {}).get("aisles", {}).get("data", [])
            if not aisles:
                aisles = initialState.get("store", {}).get("data", {}).get("currentStoreData", {}).get("data", {}).get("featuredAisles", [])
            if aisles:
                category_ids = []
                category_names = {}
                for aisle in aisles:
                    aisle_id = aisle.get("id")
                    aisle_name = aisle.get("name")
                    if aisle_id and aisle_name:
                        category_ids.append(int(aisle_id))
                        category_names[int(aisle_id)] = aisle_name
                if category_ids:
                    return SourceInventory(category_ids=sorted(category_ids), category_names=category_names)
    except Exception as e:
        LOGGER.warning("Could not extract aisles from storefront HTML: %s", e)
    
    # Fallback to store products API
    try:
        api_url = f"{BASE_URL}/api/store/products/{STORE_URL_NAME}?limit=1&offset=0"
        response_text = client.fetch_text(api_url)
        res = json.loads(response_text)
        featured_aisles = res.get("featuredAisles", [])
        if featured_aisles:
            category_ids = []
            category_names = {}
            for aisle in featured_aisles:
                aisle_id = aisle.get("id")
                aisle_name = aisle.get("name")
                if aisle_id and aisle_name:
                    category_ids.append(int(aisle_id))
                    category_names[int(aisle_id)] = aisle_name
            if category_ids:
                return SourceInventory(category_ids=sorted(category_ids), category_names=category_names)
    except Exception as e:
        raise CollectionError(f"Failed to discover category sources: {e}") from e
    
    raise CollectionError("No categories or aisles discovered from storefront or API")


def collect_catalog(
    client: PoliteClient,
    inventory: SourceInventory,
    observed_at: str | None = None,
    max_categories: int | None = None,
) -> tuple[list[ProductObservation], list[PromotionObservation], int, list[str]]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    category_ids = inventory.category_ids[:max_categories] if max_categories else inventory.category_ids
    products: dict[str, ProductObservation] = {}
    promotions: dict[str, PromotionObservation] = {}
    errors: list[str] = []
    crawled_departments = 0
    
    for index, cat_id in enumerate(category_ids, 1):
        category_name = inventory.category_names.get(cat_id, "Uncategorized")
        try:
            # Pass a huge limit to fetch everything in one shot (no limits)
            limit = 100000
            api_url = f"{BASE_URL}/api/store/products-grouped/{STORE_URL_NAME}?productCategoryIds={cat_id}&limit={limit}&sort=featured"
            try:
                payload_text = client.fetch_text(api_url)
                res = json.loads(payload_text)
            except Exception as e:
                raise CollectionError(f"API fetch failed: {e}")
            
            categories_list = res.get("categories", [])
            if categories_list:
                cat_data = categories_list[0]
                prod_list = cat_data.get("products", [])
                for p_dict in prod_list:
                    try:
                        prod_obs, promo_obs = parse_product(p_dict, category_name, observed_at)
                        existing = products.get(prod_obs.product_key)
                        products[prod_obs.product_key] = merge_products(existing, prod_obs) if existing else prod_obs
                        if promo_obs:
                            promotions[promo_obs.promotion_key] = promo_obs
                    except Exception as e:
                        pass
            
            crawled_departments += 1
        except Exception as error:
            if len(errors) < 100:
                errors.append(f"Category {cat_id} ({category_name}): {error}")
        
        LOGGER.info("Catalog progress %s/%s: %s unique products", index, len(category_ids), len(products))
        time.sleep(client.delay_seconds)
        
    return (
        sorted(products.values(), key=lambda item: item.product_key),
        sorted(promotions.values(), key=lambda item: item.promotion_key),
        crawled_departments,
        errors,
    )
