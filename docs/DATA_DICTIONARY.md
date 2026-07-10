# Data Dictionary

## ProductObservation

| Field | Meaning |
|---|---|
| `product_key` | Canonical public relative path `/item/{slug}/{productId}`; not a UPC |
| `name`, `brand` | Source-provided product identity fields (brand is None) |
| `current_price`, `currency` | Positive public online catalog price and currency |
| `availability` | Source-provided availability label |
| `categories` | Every discovered category membership |
| `source_url` | Public first-party evidence URL |
| `image_url`, `description` | Optional source-provided catalog metadata |
| `package_text` | Optional best-effort URL/display-derived package hint; nullable |
| `price_valid_until` | Source-provided offer validity date when present |
| `observed_at` | UTC collection timestamp |
| `price_scope` | Always `public_online_catalog` for catalog observations |
| `market_reference` | Shop Fair of Uniondale #2758 context and explicit limitation |
| `schema_version` | Contract version |

## PromotionObservation

`promotion_key` is a deterministic hash of the source offer fields. `advertised_price`, optional `regular_price`, optional unit-price text, offer text, validity dates, and source URL describe a best-effort public weekly-ad observation. Promotions are never silently merged with catalog observations.

## SnapshotManifest

The manifest records snapshot health, raw counts, sitemap counts, measured coverage, prior overlap, valid-price rate, request count, elapsed time, and capped error details. It is the audit record for accepting or rejecting a crawl.

## WeeklySummary

The published JSON includes latest and previous snapshot statistics, every adjacent comparison, latest movers and anomalies, category/brand summaries, promotion history, promotion transitions, four/eight-week volatility, and the methodology labels needed to interpret the result.
