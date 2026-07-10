import tempfile
import unittest
from pathlib import Path

from shopfair_research.analysis import build_summary, compare_catalogs
from shopfair_research.storage import write_jsonl_gz_atomic


def product(key: str, price: float, category: str = "Pantry", brand: str = "Acme") -> dict:
    return {
        "product_key": key,
        "name": f"Product {key}",
        "brand": brand,
        "current_price": price,
        "availability": "InStock",
        "categories": [category],
    }


class AnalysisTests(unittest.TestCase):
    def test_adjacent_comparison_and_anomaly_rule(self) -> None:
        old = {str(i): product(str(i), 10.0) for i in range(1, 7)}
        prices = [10.1, 10.2, 10.3, 10.4, 10.5, 30.0]
        new = {str(i): product(str(i), prices[i - 1]) for i in range(1, 7)}
        comparison, changes, anomalies = compare_catalogs(old, new)
        self.assertEqual(comparison["matched_products"], 6)
        self.assertEqual(comparison["price_increases"], 6)
        self.assertEqual(len(changes), 6)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["product_key"], "6")

    def test_baseline_then_weekly_summary_and_volatility_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshots = Path(tmp)
            write_jsonl_gz_atomic(snapshots / "2026-07-05.catalog.jsonl.gz", [product("a", 2), product("b", 3)])
            baseline = build_summary(snapshots)
            self.assertEqual(baseline["status"], "baseline_established")
            self.assertIsNone(baseline["comparison"])
            self.assertIsNone(baseline["latest_manifest"])
            
            write_jsonl_gz_atomic(snapshots / "2026-07-12.catalog.jsonl.gz", [product("a", 2.5), product("c", 4)])
            weekly = build_summary(snapshots)
            self.assertEqual(weekly["status"], "weekly_comparison_available")
            self.assertEqual(weekly["comparison"]["new_products"], 1)
            self.assertEqual(weekly["comparison"]["removed_products"], 1)
            self.assertEqual(weekly["volatility_4_week"], [])


if __name__ == "__main__":
    unittest.main()
