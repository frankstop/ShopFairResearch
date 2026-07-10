from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path
import time

from .analysis import build_summary
from .models import SnapshotManifest
from .report import write_reports
from .sources import PoliteClient, collect_catalog, discover_sources, verify_robots, fetch_target_catalog_size
from .storage import read_jsonl_gz, snapshot_paths, write_json_atomic, write_jsonl_gz_atomic


LOGGER = logging.getLogger(__name__)


def validate_collection(
    products: list,
    crawled_departments: int,
    total_departments: int,
    previous_path: Path | None,
    minimum_products: int,
    minimum_department_coverage: float,
    target_catalog_size: int = 0,
) -> tuple[float, float | None, float]:
    product_keys = {product.product_key for product in products}
    coverage = crawled_departments / max(total_departments, 1) * 100
    valid_prices = sum(1 for product in products if product.current_price > 0) / max(len(products), 1) * 100
    if len(product_keys) < minimum_products:
        raise ValueError(f"Collected {len(product_keys):,} unique products; minimum is {minimum_products:,}")
    if coverage < minimum_department_coverage:
        raise ValueError(f"Department coverage {coverage:.1f}% is below {minimum_department_coverage:.1f}%")
    if valid_prices < 95:
        raise ValueError(f"Valid positive price rate {valid_prices:.1f}% is below 95%")
        
    # Verify complete scan of the entire storefront catalog
    if target_catalog_size > 0:
        actual_ratio = len(product_keys) / target_catalog_size * 100
        if len(product_keys) < target_catalog_size * 0.95:
            raise ValueError(
                f"Crawl integrity failed: Collected {len(product_keys):,} products but the store target catalog size "
                f"is {target_catalog_size:,} (coverage {actual_ratio:.1f}% is below 95% threshold)"
            )
            
    overlap: float | None = None
    if previous_path:
        previous = {row["product_key"] for row in read_jsonl_gz(previous_path)}
        overlap = len(previous & product_keys) / max(len(previous), 1) * 100
        product_drop = (len(previous) - len(product_keys)) / max(len(previous), 1) * 100
        if overlap < 80:
            raise ValueError(f"Prior snapshot overlap {overlap:.1f}% is below 80%")
        if product_drop > 25:
            raise ValueError(f"Product count dropped {product_drop:.1f}%, above the 25% gate")
    return round(coverage, 2), round(overlap, 2) if overlap is not None else None, round(valid_prices, 2)


def run_pipeline(
    root: Path,
    snapshot_date: str,
    delay_seconds: float = 1.0,
    minimum_products: int = 1000,
    minimum_department_coverage: float = 90.0,
    max_categories: int | None = None,
) -> SnapshotManifest:
    started = time.monotonic()
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client = PoliteClient(delay_seconds=delay_seconds)
    verify_robots(client)
    inventory = discover_sources(client)
    
    # Fetch target catalog size from the products API
    target_catalog_size = fetch_target_catalog_size(client) if max_categories is None else 0
    if target_catalog_size > 0:
        LOGGER.warning("Target storefront catalog size discovered: %s products", target_catalog_size)
    
    products, promotions, crawled_depts, catalog_errors = collect_catalog(
        client, inventory, observed_at, max_categories=max_categories
    )
    snapshot_dir = root / "data" / "snapshots"
    catalog_path = snapshot_dir / f"{snapshot_date}.catalog.jsonl.gz"
    promotion_path = snapshot_dir / f"{snapshot_date}.promotions.jsonl.gz"
    manifest_path = snapshot_dir / f"{snapshot_date}.manifest.json"
    prior_files = [path for path in snapshot_paths(snapshot_dir, "catalog") if path != catalog_path]
    previous_path = prior_files[-1] if prior_files else None
    
    total_depts = len(inventory.category_ids[:max_categories]) if max_categories else len(inventory.category_ids)
    
    coverage, overlap, valid_prices = validate_collection(
        products,
        crawled_depts,
        total_depts,
        previous_path,
        minimum_products,
        minimum_department_coverage,
        target_catalog_size,
    )
    manifest = SnapshotManifest(
        snapshot_date=snapshot_date,
        observed_at=observed_at,
        status="healthy",
        catalog_products=len(products),
        promotions=len(promotions),
        product_sitemap_urls=target_catalog_size if target_catalog_size > 0 else len(products),
        category_sitemap_urls=total_depts,   # mapped to total departments
        sitemap_coverage_percentage=coverage, # mapped to department coverage
        prior_overlap_percentage=overlap,
        valid_price_percentage=valid_prices,
        requests=client.requests,
        errors=catalog_errors,
        elapsed_seconds=round(time.monotonic() - started, 2),
    )
    new_paths = [catalog_path, promotion_path, manifest_path]
    try:
        write_jsonl_gz_atomic(catalog_path, products)
        write_jsonl_gz_atomic(promotion_path, promotions)
        write_json_atomic(manifest_path, manifest.to_dict())
        summary = build_summary(snapshot_dir)
        write_reports(summary, root / "docs")
    except BaseException:
        for path in new_paths:
            path.unlink(missing_ok=True)
        raise
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and analyze the anonymous public Shop Fair catalog")
    parser.add_argument("command", choices=["run", "report"], nargs="?", default="run")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--minimum-products", type=int, default=1000)
    parser.add_argument("--minimum-department-coverage", type=float, default=90.0)
    parser.add_argument("--max-categories", type=int)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")
    if args.command == "report":
        write_reports(build_summary(args.root / "data" / "snapshots"), args.root / "docs")
        return
    manifest = run_pipeline(
        args.root,
        args.date,
        delay_seconds=args.delay,
        minimum_products=args.minimum_products,
        minimum_department_coverage=args.minimum_department_coverage,
        max_categories=args.max_categories,
    )
    LOGGER.warning("Healthy snapshot: %s products, %.1f%% department coverage", manifest.catalog_products, manifest.sitemap_coverage_percentage)


if __name__ == "__main__":
    main()
