# Methodology and Limitations

## What is measured

The unit of analysis is a product observation on Shop Fair's anonymous public online catalog on Mercato.com. The project records what the first-party page published at collection time. Shop Fair of Uniondale #2758 supplies local context; the project does not assert that online values equal its shelf prices.

## Product matching

Adjacent weeks are matched by canonical relative path `/item/{slug}/{productId}`. URLs are not UPCs. A changed URL or ID can appear as one removal and one addition even when the underlying retail item is unchanged.

## Missing data

Missing products and failed weeks remain missing. Prices are never interpolated. A partial crawl cannot replace the prior baseline because coverage, overlap, valid-price, and product-drop gates run before publication.

## Anomalies and volatility

Price anomalies require an absolute movement of at least 20% and an absolute robust z-score of at least 3.5, using the weekly median and median absolute deviation. This is a review signal, not proof of an error or unusual business event.

Four- and eight-week volatility use the population standard deviation of log prices and appear only for products observed in every required week. No forecast or predictive-quality claim is made.

## Promotions

Weekly-ad extraction is best effort and stored separately. Sourced inline from product `priceView.originalPrice` API payloads. Regular prices, unit prices, eligibility rules, loyalty requirements, validity dates, and local applicability may be absent. Promotion failures do not invalidate the catalog snapshot, but they are recorded in its manifest.

## Responsible access

The collector identifies itself, checks robots rules, runs serially with a one-second minimum delay, retries temporary failures conservatively, and avoids sign-in, private APIs, CAPTCHAs, search/browse routes disallowed to general crawlers, and personalized offers.

## Data-mining basis

The design treats weekly observations as ordered time-series data, preserving missingness and separating point-outlier review from data-quality failures. Method-family grounding: Charu C. Aggarwal, *Data Mining: The Textbook*, section 14.2–14.7, PDF pages 478–507.
