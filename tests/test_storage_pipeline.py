from dataclasses import replace
from email.message import Message
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from shopfair_research.models import ProductObservation
from shopfair_research.pipeline import validate_collection
from shopfair_research.report import write_reports
from shopfair_research.analysis import build_summary
from shopfair_research.sources import PoliteClient, verify_robots
from shopfair_research.storage import read_jsonl_gz, write_jsonl_gz_atomic


def observation(key: str, price: float = 2.0) -> ProductObservation:
    return ProductObservation(
        product_key=key,
        name="Test Product",
        brand=None,
        current_price=price,
        currency="USD",
        availability="InStock",
        categories=["Test"],
        source_url=key,
        image_url=None,
        description=None,
        package_text=None,
        price_valid_until=None,
        observed_at="2026-07-09T00:00:00Z",
    )


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.headers = Message()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return self.payload


class StoragePipelineTests(unittest.TestCase):
    def test_gzip_roundtrip_and_atomic_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.jsonl.gz"
            write_jsonl_gz_atomic(path, [observation("/item/test/1")])
            rows = read_jsonl_gz(path)
            self.assertEqual(rows[0]["current_price"], 2.0)
            self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())

    def test_partial_crawl_cannot_replace_existing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "2026-07-05.catalog.jsonl.gz"
            write_jsonl_gz_atomic(existing, [observation(f"/item/test/{i}") for i in range(10)])
            with self.assertRaisesRegex(ValueError, "minimum"):
                validate_collection(
                    [observation("/item/test/1")],
                    1,
                    10,
                    existing,
                    minimum_products=5,
                    minimum_department_coverage=60.0
                )
            self.assertEqual(len(read_jsonl_gz(existing)), 10)

    def test_overlap_and_drop_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "2026-07-05.catalog.jsonl.gz"
            write_jsonl_gz_atomic(existing, [observation(f"/item/test/{i}") for i in range(10)])
            with self.assertRaisesRegex(ValueError, "overlap"):
                validate_collection(
                    [observation(f"/item/new-{i}") for i in range(10)],
                    10,
                    10,
                    existing,
                    minimum_products=1,
                    minimum_department_coverage=10.0
                )

    def test_robots_rule_change_blocks_collection(self) -> None:
        class Client:
            def fetch_text(self, url):
                return "User-agent: *\nDisallow: /shop/\n"
        with self.assertRaisesRegex(Exception, "does not allow"):
            verify_robots(Client())

    def test_retry_after_server_error(self) -> None:
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 503, "unavailable", {}, BytesIO())
            return FakeResponse(b"ok")
        client = PoliteClient(delay_seconds=0, retries=1, opener=opener)
        self.assertEqual(client.fetch_text("https://example.com"), "ok")
        self.assertEqual(len(calls), 2)

    def test_offline_fixture_pipeline_writes_all_public_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "data" / "snapshots"
            write_jsonl_gz_atomic(snapshots / "2026-07-05.catalog.jsonl.gz", [observation("/item/test/a")])
            summary = build_summary(snapshots)
            write_reports(summary, root / "docs")
            self.assertTrue((root / "docs" / "index.html").exists())
            self.assertTrue((root / "docs" / "weekly-report.html").exists())
            self.assertTrue((root / "docs" / "data" / "weekly-summary.json").exists())
            self.assertIn("Baseline established", (root / "docs" / "weekly-report.html").read_text())


if __name__ == "__main__":
    unittest.main()
