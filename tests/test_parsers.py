import unittest

from shopfair_research.parsers import (
    canonical_url,
    extract_slug_and_id,
    extract_package_text,
    parse_product,
    merge_products,
)
from shopfair_research.models import ProductObservation


class ParserTests(unittest.TestCase):
    def test_canonical_url(self) -> None:
        self.assertEqual(
            canonical_url("HTTPS://www.Mercato.com/item/milk/123?x=1"),
            "https://www.mercato.com/item/milk/123",
        )

    def test_extract_slug_and_id(self) -> None:
        prod = {"longUrl": "/shop/shop-fair-supermarket-3/item/yellow-bananas/12900497"}
        self.assertEqual(extract_slug_and_id(prod), ("yellow-bananas", "12900497"))
        
        prod_fallback = {"name": "Whole Milk", "productId": 77952}
        self.assertEqual(extract_slug_and_id(prod_fallback), ("whole-milk", "77952"))

    def test_extract_package_text(self) -> None:
        self.assertEqual(extract_package_text("$0.90 per lb"), "per lb")
        self.assertEqual(extract_package_text("$4.29 each"), "each")
        self.assertEqual(extract_package_text("$2.99 16 oz"), "16 oz")
        self.assertIsNone(extract_package_text(""))

    def test_parse_product_with_and_without_promotion(self) -> None:
        prod = {
            "name": "Yellow Bananas",
            "price": 0.9,
            "inStock": True,
            "largeImageUrl": "https://example.com/bananas.jpg",
            "longUrl": "/shop/shop-fair-supermarket-3/item/yellow-bananas/12900497",
            "priceDisplay": "$0.90 per lb",
            "priceView": {"price": "$0.90", "type": "pound"},
            "productId": 12900497,
        }
        
        p_obs, promo_obs = parse_product(prod, "Fruits & Veggies", "2026-07-09T00:00:00Z")
        self.assertEqual(p_obs.name, "Yellow Bananas")
        self.assertEqual(p_obs.current_price, 0.9)
        self.assertEqual(p_obs.product_key, "/item/yellow-bananas/12900497")
        self.assertEqual(p_obs.package_text, "per lb")
        self.assertIsNone(promo_obs)

        # with promotion
        prod["priceView"]["originalPrice"] = "$1.20"
        p_obs, promo_obs = parse_product(prod, "Fruits & Veggies", "2026-07-09T00:00:00Z")
        self.assertIsNotNone(promo_obs)
        self.assertEqual(promo_obs.name, "Yellow Bananas")
        self.assertEqual(promo_obs.advertised_price, 0.9)
        self.assertEqual(promo_obs.regular_price, 1.2)
        self.assertEqual(promo_obs.product_key, "/item/yellow-bananas/12900497")

    def test_merge_products(self) -> None:
        p1 = ProductObservation(
            product_key="/item/milk/123",
            name="Milk",
            brand=None,
            current_price=2.99,
            currency="USD",
            availability="InStock",
            categories=["Dairy"],
            source_url="https://example.com",
            image_url=None,
            description=None,
            package_text="1 gal",
            price_valid_until=None,
            observed_at="2026-07-09T00:00:00Z",
        )
        p2 = ProductObservation(
            product_key="/item/milk/123",
            name="Milk",
            brand="BrandX",
            current_price=2.99,
            currency="USD",
            availability="InStock",
            categories=["Refrigerated"],
            source_url="https://example.com",
            image_url=None,
            description=None,
            package_text=None,
            price_valid_until=None,
            observed_at="2026-07-09T00:00:00Z",
        )
        merged = merge_products(p1, p2)
        self.assertEqual(merged.categories, ["Dairy", "Refrigerated"])
        self.assertEqual(merged.brand, "BrandX")
        self.assertEqual(merged.package_text, "1 gal")


if __name__ == "__main__":
    unittest.main()
