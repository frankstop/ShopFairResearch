# Shop Fair Research

[![Weekly catalog pipeline](https://github.com/frankstop/ShopFairResearch/actions/workflows/weekly_crawl.yml/badge.svg)](https://github.com/frankstop/ShopFairResearch/actions/workflows/weekly_crawl.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-08783f.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-08783f.svg)](LICENSE)

Automated longitudinal research on Shop Fair's anonymous public online catalog. Every Sunday, the project discovers the current departments (featured aisles), collects structured product observations from category API pagination endpoints, validates the result, compares it with prior successful weeks, and publishes [price intelligence](https://frankstop.github.io/ShopFairResearch/weekly-report.html).

The Uniondale Shop Fair at **973 Front St, Uniondale, NY 11553 (store ID 2758 on Mercato.com)** establishes the local market context. Collected prices come from Shop Fair's public online catalog on Mercato.com and are **not asserted to be Uniondale shelf prices**.

## What the pipeline produces

- Immutable compressed catalog and promotion snapshots under `data/snapshots/`
- Coverage, overlap, valid-price, and product-drop safety gates
- Week-to-week price increases, decreases, assortment churn, and availability changes
- Category and brand trends, advertised promotion summaries, and four/eight-week volatility
- Conservative anomaly flags requiring both a 20% price move and a robust MAD z-score of 3.5
- A static [project overview](https://frankstop.github.io/ShopFairResearch/) and [weekly report](https://frankstop.github.io/ShopFairResearch/weekly-report.html)
- A stable [machine-readable weekly summary](https://frankstop.github.io/ShopFairResearch/data/weekly-summary.json)

No account, loyalty card, private API, CAPTCHA workaround, or authenticated state is used.

## Architecture

```mermaid
flowchart LR
    A[Sunday schedule] --> B[robots.txt gate]
    B --> C[Aisle discovery]
    C --> D[Category API paginator]
    D --> E[JSON normalization and deduplication]
    E --> F[Coverage and quality gates]
    F --> G[Compressed immutable snapshots]
    G --> H[Time-series and anomaly analysis]
    H --> I[GitHub Pages and JSON contract]
```

See [Architecture](docs/ARCHITECTURE.md), [Data Dictionary](docs/DATA_DICTIONARY.md), and [Methodology and Limitations](docs/METHODOLOGY.md) for the full contracts.

## Run locally

Python 3.11 or newer is required. The runtime has no third-party dependencies.

```bash
python3 -m unittest discover -v

# Small live smoke run into a temporary directory. Thresholds are intentionally
# lowered only for the smoke test; do not use this as a production baseline.
python3 -m shopfair_research run \
  --root /tmp/shopfair-smoke \
  --max-categories 2 \
  --minimum-products 1 \
  --minimum-department-coverage 0 \
  --delay 1

# Production collection and reporting
python3 -m shopfair_research run --verbose

# Rebuild reports from existing snapshots without network access
python3 -m shopfair_research report
```

The production defaults require at least 1,000 products and 90% department coverage. Later runs must also retain at least 80% overlap with the prior snapshot and avoid an unexplained product-count drop above 25%.

## Data-use boundary

The collector identifies itself, runs serially with at least one second between requests, honors current robots rules, and uses only public first-party category and products pages.

## Status semantics

The first healthy run establishes a real baseline. A real week-to-week comparison appears only after the second healthy run. The project does not manufacture historical snapshots, interpolate missing prices, or present predictive-model claims.

## License and affiliation

Code is released under the [MIT License](LICENSE). Collected observations remain attributable to their source URLs. This independent educational project is not affiliated with or endorsed by Shop Fair or Mercato.com.
