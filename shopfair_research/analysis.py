from __future__ import annotations

from collections import Counter, defaultdict
import json
from math import log
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

from .storage import read_jsonl_gz, snapshot_paths


def _date_from_path(path: Path) -> str:
    return path.name.split(".", 1)[0]


def _keyed(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def catalog_stats(date: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [float(row["current_price"]) for row in rows if float(row.get("current_price") or 0) > 0]
    categories = {category for row in rows for category in row.get("categories", []) if category}
    brands = {row.get("brand") for row in rows if row.get("brand")}
    available = sum(1 for row in rows if str(row.get("availability", "")).lower() == "instock")
    return {
        "snapshot_date": date,
        "products": len(rows),
        "categories": len(categories),
        "brands": len(brands),
        "average_price": round(mean(prices), 2) if prices else 0.0,
        "median_price": round(median(prices), 2) if prices else 0.0,
        "available_products": available,
    }


def _mad(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    center = median(values)
    return center, median(abs(value - center) for value in values)


def compare_catalogs(
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    common = previous.keys() & current.keys()
    changes: list[dict[str, Any]] = []
    availability_changes: list[dict[str, Any]] = []
    for key in common:
        old = previous[key]
        new = current[key]
        old_price = float(old["current_price"])
        new_price = float(new["current_price"])
        difference = round(new_price - old_price, 2)
        percentage = round((difference / old_price) * 100, 2) if old_price else 0.0
        if difference:
            changes.append(
                {
                    "product_key": key,
                    "name": new.get("name") or old.get("name") or "Unknown product",
                    "brand": new.get("brand"),
                    "categories": new.get("categories", []),
                    "previous_price": old_price,
                    "current_price": new_price,
                    "change": difference,
                    "change_percentage": percentage,
                }
            )
        if old.get("availability") != new.get("availability"):
            availability_changes.append(
                {
                    "product_key": key,
                    "name": new.get("name") or old.get("name"),
                    "previous": old.get("availability"),
                    "current": new.get("availability"),
                }
            )
    percentages = [row["change_percentage"] for row in changes]
    center, mad = _mad(percentages)
    anomalies: list[dict[str, Any]] = []
    for change in changes:
        robust_z = 0.6745 * (change["change_percentage"] - center) / mad if mad else 0.0
        if abs(change["change_percentage"]) >= 20 and abs(robust_z) >= 3.5:
            anomalies.append({**change, "robust_z_score": round(robust_z, 2)})
    increases = sum(1 for row in changes if row["change"] > 0)
    decreases = sum(1 for row in changes if row["change"] < 0)
    comparison = {
        "matched_products": len(common),
        "coverage_percentage": round(len(common) / max(len(previous), 1) * 100, 2),
        "price_changes": len(changes),
        "price_increases": increases,
        "price_decreases": decreases,
        "unchanged_prices": len(common) - len(changes),
        "new_products": len(current.keys() - previous.keys()),
        "removed_products": len(previous.keys() - current.keys()),
        "availability_changes": len(availability_changes),
        "median_price_change_percentage": round(median(percentages), 2) if percentages else 0.0,
        "average_price_change_percentage": round(mean(percentages), 2) if percentages else 0.0,
        "anomalies": len(anomalies),
    }
    return comparison, changes, anomalies


def promotion_stats(date: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    discounts = [
        (float(row["regular_price"]) - float(row["advertised_price"])) / float(row["regular_price"]) * 100
        for row in rows
        if row.get("regular_price") and float(row["regular_price"]) > float(row.get("advertised_price") or 0)
    ]
    return {
        "snapshot_date": date,
        "promotions": len(rows),
        "promotions_with_regular_price": len(discounts),
        "median_discount_percentage": round(median(discounts), 1) if discounts else 0.0,
        "average_discount_percentage": round(mean(discounts), 1) if discounts else 0.0,
    }


def _top_group_trends(changes: list[dict[str, Any]], field: str, limit: int = 10) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in changes:
        values = row.get(field)
        labels = values if isinstance(values, list) else [values]
        for label in labels:
            if label:
                grouped[str(label)].append(float(row["change_percentage"]))
    ranked = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].lower()))[:limit]
    return [
        {
            "name": label,
            "changed_products": len(values),
            "median_change_percentage": round(median(values), 2),
            "average_change_percentage": round(mean(values), 2),
        }
        for label, values in ranked
    ]


def _volatility(history: list[dict[str, dict[str, Any]]], current: dict[str, dict[str, Any]], weeks: int) -> list[dict[str, Any]]:
    if len(history) < weeks:
        return []
    rows: list[dict[str, Any]] = []
    for key, item in current.items():
        prices: list[float] = []
        for snapshot in history[-weeks:]:
            if key in snapshot:
                price = float(snapshot[key]["current_price"])
                if price > 0:
                    prices.append(log(price))
        if len(prices) == weeks:
            rows.append(
                {
                    "product_key": key,
                    "name": item.get("name"),
                    "weeks": weeks,
                    "log_price_volatility": round(pstdev(prices), 4),
                }
            )
    return sorted(rows, key=lambda row: row["log_price_volatility"], reverse=True)[:20]


def build_summary(snapshot_dir: Path) -> dict[str, Any]:
    catalog_files = snapshot_paths(snapshot_dir, "catalog")
    if not catalog_files:
        raise ValueError("No catalog snapshots found")
    catalog_rows = [read_jsonl_gz(path) for path in catalog_files]
    catalog_history = [_keyed(rows, "product_key") for rows in catalog_rows]
    history = [catalog_stats(_date_from_path(path), rows) for path, rows in zip(catalog_files, catalog_rows)]

    comparisons: list[dict[str, Any]] = []
    latest_changes: list[dict[str, Any]] = []
    latest_anomalies: list[dict[str, Any]] = []
    for index in range(1, len(catalog_history)):
        comparison, changes, anomalies = compare_catalogs(catalog_history[index - 1], catalog_history[index])
        comparisons.append(
            {
                "from_date": _date_from_path(catalog_files[index - 1]),
                "to_date": _date_from_path(catalog_files[index]),
                **comparison,
            }
        )
        if index == len(catalog_history) - 1:
            latest_changes = changes
            latest_anomalies = anomalies

    promotion_files = snapshot_paths(snapshot_dir, "promotions")
    promotions_by_date = {_date_from_path(path): read_jsonl_gz(path) for path in promotion_files}
    promotion_history = [promotion_stats(date, rows) for date, rows in sorted(promotions_by_date.items())]
    latest_date = _date_from_path(catalog_files[-1])
    latest_promotions = _keyed(promotions_by_date.get(latest_date, []), "promotion_key")
    previous_promotions: dict[str, dict[str, Any]] = {}
    if len(promotion_files) >= 2:
        previous_promotions = _keyed(read_jsonl_gz(promotion_files[-2]), "promotion_key")

    increases = sorted((row for row in latest_changes if row["change"] > 0), key=lambda row: row["change_percentage"], reverse=True)
    decreases = sorted((row for row in latest_changes if row["change"] < 0), key=lambda row: row["change_percentage"])
    latest_catalog = catalog_history[-1]
    brand_counts = Counter(row.get("brand") for row in latest_catalog.values() if row.get("brand"))
    category_counts = Counter(category for row in latest_catalog.values() for category in row.get("categories", []) if category)
    manifest_history = []
    for manifest_path in sorted(snapshot_dir.glob("????-??-??.manifest.json")):
        manifest_history.append(json.loads(manifest_path.read_text(encoding="utf-8")))
    latest_manifest = manifest_history[-1] if manifest_history else None

    return {
        "schema_version": "1.0",
        "status": "baseline_established" if len(catalog_files) == 1 else "weekly_comparison_available",
        "generated_from": [path.name for path in catalog_files[-2:]],
        "latest": history[-1],
        "latest_manifest": latest_manifest,
        "manifest_history": manifest_history,
        "previous": history[-2] if len(history) >= 2 else None,
        "comparison": comparisons[-1] if comparisons else None,
        "history": history,
        "comparisons": comparisons,
        "largest_increases": increases[:20],
        "largest_decreases": decreases[:20],
        "anomalies": sorted(latest_anomalies, key=lambda row: abs(row["robust_z_score"]), reverse=True)[:30],
        "category_trends": _top_group_trends(latest_changes, "categories"),
        "brand_trends": _top_group_trends(latest_changes, "brand"),
        "top_categories": [{"name": name, "products": count} for name, count in category_counts.most_common(15)],
        "top_brands": [{"name": name, "products": count} for name, count in brand_counts.most_common(15)],
        "promotion_history": promotion_history,
        "promotion_entries": sorted(latest_promotions.keys() - previous_promotions.keys()),
        "promotion_exits": sorted(previous_promotions.keys() - latest_promotions.keys()),
        "latest_promotions": list(latest_promotions.values()),
        "volatility_4_week": _volatility(catalog_history, latest_catalog, 4),
        "volatility_8_week": _volatility(catalog_history, latest_catalog, 8),
        "methodology": {
            "identity": "/item/{slug}/{productId}; templated from Mercato payload",
            "price_scope": "Public online catalog, not asserted as Uniondale shelf pricing",
            "anomaly_rule": "Absolute change >= 20% and robust MAD z-score >= 3.5",
            "missing_values": "Preserved; never interpolated",
        },
    }
