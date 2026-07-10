from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopfair_research.storage import read_jsonl_gz, snapshot_paths


def main() -> None:
    root = ROOT
    summary_path = root / "docs" / "data" / "weekly-summary.json"
    index_path = root / "docs" / "index.html"
    report_path = root / "docs" / "weekly-report.html"
    for path in (summary_path, index_path, report_path, root / "docs" / "METHODOLOGY.html"):
        if not path.exists() or path.stat().st_size == 0:
            raise SystemExit(f"Missing required output: {path}")
    summary = json.loads(summary_path.read_text())
    latest_path = snapshot_paths(root / "data" / "snapshots", "catalog")[-1]
    latest_rows = read_jsonl_gz(latest_path)
    if summary["latest"]["products"] != len(latest_rows):
        raise SystemExit("Published product count does not match the latest snapshot")
    manifests = sorted((root / "data" / "snapshots").glob("????-??-??.manifest.json"))
    latest_manifest = json.loads(manifests[-1].read_text())
    if summary.get("latest_manifest", {}).get("sitemap_coverage_percentage") != latest_manifest["sitemap_coverage_percentage"]:
        raise SystemExit("Published coverage does not match the latest snapshot manifest")
    if "public online catalog" not in report_path.read_text().lower():
        raise SystemExit("Published report is missing the price-scope limitation")
    print(f"Verified {len(latest_rows):,} latest products and all public outputs")


if __name__ == "__main__":
    main()
