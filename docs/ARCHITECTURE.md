# Architecture

The scheduled pipeline is complete only when collection, validation, derivation, tests, and publication all succeed.

## Raw observations

`shopfair_research.sources` first verifies robots rules, then discovers the current category/department IDs of the store. It fetches allowed public category pages paginating through products serially using the first-party products-grouped REST API.

Products are deduplicated by canonical relative key `/item/{slug}/{productId}`. That key is stable enough for this source. When a product appears under multiple categories, the snapshot preserves all memberships.

Each successful date produces:

- `YYYY-MM-DD.catalog.jsonl.gz`
- `YYYY-MM-DD.promotions.jsonl.gz`
- `YYYY-MM-DD.manifest.json`

Files are written through temporary paths and replaced atomically. A failed validation leaves the previous healthy baseline untouched.

## Validation boundary

The first baseline requires at least 1,000 unique priced products, 90% department coverage, and 95% valid positive prices. Subsequent snapshots additionally require at least 80% key overlap with the prior snapshot and reject an unexplained product-count drop over 25%.

Promotion collection is inline best effort and cannot invalidate an otherwise healthy catalog snapshot.

## Derived time series

`shopfair_research.analysis` reads only successful compressed snapshots. It preserves temporal order and missing observations, then produces adjacent-week comparisons, price distributions, assortment churn, availability changes, group trends, promotion transitions, volatility, and robust price-movement anomalies.

The stable derived contract is `docs/data/weekly-summary.json`. HTML is a rendering of that same object; it does not recompute metrics independently.

## Published surfaces

- `docs/index.html`: scope, latest health, and pipeline explanation
- `docs/weekly-report.html`: current comparison and historical analysis
- `docs/data/weekly-summary.json`: machine-readable contract
- `docs/METHODOLOGY.html`: human-readable methods and limitations

GitHub Pages serves `main/docs`. The scheduled workflow commits raw and derived outputs together only after the test suite passes.
