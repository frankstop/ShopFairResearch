from __future__ import annotations

import json
from pathlib import Path


manifests = sorted(Path("data/snapshots").glob("????-??-??.manifest.json"))
if not manifests:
    raise SystemExit("No snapshot manifest found")
manifest = json.loads(manifests[-1].read_text())
print("## Shop Fair weekly catalog")
print(f"- Status: **{manifest['status']}**")
print(f"- Products: **{manifest['catalog_products']:,}**")
print(f"- Department coverage: **{manifest['sitemap_coverage_percentage']:.1f}%**")
print(f"- Prior overlap: **{manifest['prior_overlap_percentage'] if manifest['prior_overlap_percentage'] is not None else 'baseline'}**")
print(f"- Promotions: **{manifest['promotions']:,}**")
print(f"- Requests: **{manifest['requests']:,}**")
print(f"- Collection errors recorded: **{len(manifest['errors'])}**")
