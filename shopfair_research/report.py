from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any

from .storage import write_json_atomic


CSS = """
:root{--ink:#17221d;--muted:#5d6b63;--paper:#f3f6f2;--card:#fff;--line:#dce5dd;--green:#08783f;--green2:#b8e0c5;--red:#b23535;--amber:#aa6810;--shadow:0 12px 34px rgba(17,49,31,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:var(--green);text-underline-offset:3px}a:focus-visible,button:focus-visible{outline:3px solid #ffb000;outline-offset:3px}.shell{width:min(1180px,calc(100% - 32px));margin:auto}.hero{padding:64px 0 36px}.eyebrow{color:var(--green);font-size:.76rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.hero h1{max-width:900px;margin:.22em 0 .18em;font:600 clamp(2.6rem,8vw,6.6rem)/.95 Georgia,serif;letter-spacing:-.045em}.hero p{max-width:760px;margin:0;color:var(--muted);font-size:1.08rem}.notice{margin-top:22px;padding:14px 16px;border:1px solid #e7d5a9;background:#fff8e8;border-radius:10px;color:#6d4a0a}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0}.metric,.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}.metric{padding:18px}.metric span{display:block;color:var(--muted);font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em}.metric strong{display:block;margin-top:5px;font-size:clamp(1.45rem,4vw,2.25rem);line-height:1}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin:16px 0}.panel{padding:22px;overflow:hidden}.panel h2{margin:0 0 4px;font-size:1.18rem}.panel>p{margin:0 0 14px;color:var(--muted)}.wide{grid-column:1/-1}.table-wrap{overflow:auto;margin:0 -6px}table{width:100%;border-collapse:collapse;min-width:620px}th,td{padding:10px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.07em}td small{display:block;color:var(--muted);max-width:420px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.up{color:var(--red);font-weight:750}.down{color:var(--green);font-weight:750}.tag{display:inline-block;padding:4px 9px;border-radius:999px;background:var(--green2);color:#07542f;font-size:.76rem;font-weight:750}.empty{padding:22px;border:1px dashed var(--line);border-radius:10px;color:var(--muted)}.bars{display:grid;gap:9px}.bar-row{display:grid;grid-template-columns:minmax(120px,1fr) 3fr 54px;gap:10px;align-items:center}.bar-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bar-track{height:10px;background:#edf1ed;border-radius:999px;overflow:hidden}.bar-fill{height:100%;background:var(--green);border-radius:999px}.chart{width:100%;height:auto}.chart .axis{stroke:#cdd8cf;stroke-width:1}.chart .line{fill:none;stroke:var(--green);stroke-width:3}.chart .dot{fill:var(--card);stroke:var(--green);stroke-width:3}.chart text{font-size:11px;fill:var(--muted)}footer{padding:34px 0 54px;color:var(--muted)}.skip{position:absolute;left:-999px;top:0}.skip:focus{left:16px;top:16px;background:#fff;padding:10px;z-index:5}.nav{display:flex;gap:16px;flex-wrap:wrap;padding:14px 0;border-bottom:1px solid var(--line)}
@media(max-width:800px){.metrics{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.wide{grid-column:auto}.hero{padding-top:42px}}
@media(max-width:480px){.metrics{grid-template-columns:1fr}.shell{width:min(100% - 22px,1180px)}.panel{padding:16px}.hero h1{font-size:2.75rem}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _metric(label: str, value: str) -> str:
    return f'<div class="metric"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def _line_chart(rows: list[dict[str, Any]], field: str, label: str) -> str:
    if len(rows) < 2:
        return '<div class="empty">A trend line appears after the second successful weekly snapshot.</div>'
    width, height = 760, 230
    left, top, right, bottom = 46, 24, 18, 42
    values = [float(row[field]) for row in rows]
    low, high = min(values), max(values)
    padding = max((high - low) * .15, .5)
    low, high = low - padding, high + padding
    plot_w, plot_h = width - left - right, height - top - bottom
    points = []
    for index, value in enumerate(values):
        x = left + index / max(len(rows) - 1, 1) * plot_w
        y = top + (high - value) / max(high - low, 1) * plot_h
        points.append((x, y))
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    marks = "".join(
        f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4"><title>{escape(rows[i]["snapshot_date"])}: {values[i]:,.2f}</title></circle>'
        f'<text x="{x:.1f}" y="{height-14}" text-anchor="middle">{escape(rows[i]["snapshot_date"][5:])}</text>'
        for i, (x, y) in enumerate(points)
    )
    return f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}"><line class="axis" x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}"/><polyline class="line" points="{polyline}"/>{marks}</svg>'


def _movement_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">No qualifying price movements in the latest comparison.</div>'
    body = "".join(
        "<tr>"
        f'<td>{escape(str(row.get("name") or "Unknown"))}<small>{escape(str(row.get("brand") or "Unbranded"))}</small></td>'
        f'<td>{_money(row.get("previous_price"))}</td><td>{_money(row.get("current_price"))}</td>'
        f'<td class="{"up" if float(row.get("change",0))>0 else "down"}">{float(row.get("change_percentage",0)):+.1f}%</td>'
        "</tr>" for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr><th>Product</th><th>Previous</th><th>Current</th><th>Change</th></tr></thead><tbody>{body}</tbody></table></div>'


def _bars(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">No group data is available yet.</div>'
    maximum = max(int(row["products"]) for row in rows) or 1
    return '<div class="bars">' + "".join(
        f'<div class="bar-row"><span class="bar-label" title="{escape(str(row["name"]))}">{escape(str(row["name"]))}</span>'
        f'<span class="bar-track"><span class="bar-fill" style="width:{int(row["products"])/maximum*100:.1f}%"></span></span>'
        f'<strong>{int(row["products"]):,}</strong></div>' for row in rows
    ) + "</div>"


def render_weekly_report(summary: dict[str, Any]) -> str:
    latest = summary["latest"]
    manifest = summary.get("latest_manifest") or {}
    comparison = summary.get("comparison")
    baseline = comparison is None
    status_text = "Baseline established" if baseline else "Weekly comparison available"
    comparison_metrics = (
        _metric("Matched coverage", f'{comparison["coverage_percentage"]:.1f}%')
        + _metric("Price changes", f'{comparison["price_changes"]:,}')
        + _metric("New products", f'{comparison["new_products"]:,}')
        + _metric("Anomalies", f'{comparison["anomalies"]:,}')
        if comparison else
        _metric("Status", "Baseline") + _metric("Products", f'{latest["products"]:,}') + _metric("Department coverage", f'{float(manifest.get("sitemap_coverage_percentage",0)):.1f}%') + _metric("Valid prices", f'{float(manifest.get("valid_price_percentage",0)):.1f}%')
    )
    promotion = summary.get("promotion_history", [])
    latest_promo = promotion[-1] if promotion else {"promotions": 0, "median_discount_percentage": 0}
    anomaly_rows = summary.get("anomalies", [])
    anomaly_html = _movement_table(anomaly_rows)
    return f"""<!doctype html>
<html lang="en"><head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-RSVR6Y389R"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', 'G-RSVR6Y389R');
</script>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Automated weekly Shop Fair public catalog price intelligence and anomaly analysis.">
<title>Weekly Price Intelligence | Shop Fair Research</title><style>{CSS}</style></head>
<body><a class="skip" href="#main">Skip to analysis</a><nav class="shell nav" aria-label="Primary"><a href="index.html">Overview</a><a href="weekly-report.html" aria-current="page">Weekly analysis</a><a href="data/weekly-summary.json">Data contract</a><a href="https://github.com/frankstop/ShopFairResearch">Source</a></nav>
<header class="shell hero"><div class="eyebrow">Public catalog monitor · {escape(latest["snapshot_date"])}</div><h1>What changed this week?</h1><p>Price movements, assortment churn, promotions, volatility, and robust anomaly flags from Shop Fair’s anonymous public online catalog.</p><div class="notice"><strong>Scope:</strong> These are public online catalog observations. Shop Fair of Uniondale (store #2758) is the local market reference, but values are not asserted as Uniondale shelf prices.</div></header>
<main id="main" class="shell"><span class="tag">{escape(status_text)}</span><section class="metrics" aria-label="Latest metrics">{comparison_metrics}</section>
<section class="panel wide"><h2>Collection health</h2><p>{int(manifest.get("category_sitemap_urls",0)):,} departments discovered · {int(manifest.get("requests",0)):,} requests · {float(manifest.get("elapsed_seconds",0))/60:.1f} minutes · {len(manifest.get("errors",[]))} recorded non-fatal source issue(s).</p></section>
<div class="grid"><section class="panel wide"><h2>Catalog size over time</h2><p>Successful snapshots only. Missing observations are not interpolated.</p>{_line_chart(summary["history"],"products","Unique catalog products over time")}</section>
<section class="panel"><h2>Largest increases</h2><p>Highest percentage changes among matched products.</p>{_movement_table(summary.get("largest_increases",[])[:10])}</section>
<section class="panel"><h2>Largest decreases</h2><p>Lowest percentage changes among matched products.</p>{_movement_table(summary.get("largest_decreases",[])[:10])}</section>
<section class="panel wide"><h2>Robust anomaly review</h2><p>Only changes of at least 20% with an absolute MAD-based robust z-score of at least 3.5.</p>{anomaly_html}</section>
<section class="panel"><h2>Largest categories</h2><p>Category membership is retained when products appear on multiple pages.</p>{_bars(summary.get("top_categories",[])[:10])}</section>
<section class="panel"><h2>Largest brands</h2><p>Brand values are not provided directly by this public catalog.</p>{_bars(summary.get("top_brands",[])[:10])}</section>
<section class="panel"><h2>Weekly-ad promotions</h2><p>Best-effort, separately sourced advertised offers.</p><div class="metrics">{_metric("Offers",f'{latest_promo["promotions"]:,}')}{_metric("Median discount",f'{latest_promo["median_discount_percentage"]:.1f}%')}</div></section>
<section class="panel"><h2>Volatility</h2><p>Four- and eight-week log-price volatility begins only after enough successful history exists.</p><div class="metrics">{_metric("4-week series",f'{len(summary.get("volatility_4_week",[])):,}')}{_metric("8-week series",f'{len(summary.get("volatility_8_week",[])):,}')}</div></section></div></main>
<footer class="shell">Independent educational research. Not affiliated with or endorsed by Shop Fair. <a href="METHODOLOGY.html">Methodology and limitations</a>.</footer></body></html>"""


def render_index(summary: dict[str, Any]) -> str:
    latest = summary["latest"]
    manifest = summary.get("latest_manifest") or {}
    baseline = summary.get("comparison") is None
    state = "Baseline established" if baseline else "Current weekly comparison"
    return f"""<!doctype html><html lang="en"><head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-RSVR6Y389R"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', 'G-RSVR6Y389R');
</script>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Longitudinal public Shop Fair catalog price research."><title>Shop Fair Research</title><style>{CSS}</style></head>
<body><a class="skip" href="#main">Skip to content</a><nav class="shell nav" aria-label="Primary"><a href="index.html" aria-current="page">Overview</a><a href="weekly-report.html">Weekly analysis</a><a href="data/weekly-summary.json">Data contract</a><a href="https://github.com/frankstop/ShopFairResearch">Source</a></nav>
<header class="shell hero"><div class="eyebrow">Automated grocery price research</div><h1>Shop Fair, observed over time.</h1><p>A transparent weekly pipeline that turns anonymous public catalog pages into durable price history, assortment signals, promotion tracking, and anomaly review.</p><div class="notice"><strong>Local context:</strong> Shop Fair of Uniondale (store #2758) at 973 Front St, Uniondale, NY establishes the project’s market relevance. The collected values are public online prices and may differ from that store’s shelves.</div></header>
<main id="main" class="shell"><span class="tag">{escape(state)}</span><section class="metrics">{_metric("Products",f'{latest["products"]:,}')}{_metric("Department coverage",f'{float(manifest.get("sitemap_coverage_percentage",0)):.1f}%')}{_metric("Categories",f'{latest["categories"]:,}')}{_metric("Median price",_money(latest["median_price"]))}</section>
<div class="grid"><section class="panel"><h2>Raw observations</h2><p>Immutable, compressed JSONL snapshots preserve product identity, catalog attributes, price, availability, source, and observation time.</p></section><section class="panel"><h2>Derived intelligence</h2><p>Adjacent snapshots produce movements, churn, trends, volatility, promotions, and conservative robust outlier flags.</p></section><section class="panel"><h2>Safety before publication</h2><p>Robots rules, minimum coverage, valid-price, overlap, and product-count gates prevent partial crawls from replacing a healthy baseline.</p></section><section class="panel"><h2>Open methodology</h2><p>The repository includes its schema, limitations, tests, workflow, and machine-readable weekly summary. No account credentials or private APIs are used.</p></section></div>
<p><a href="weekly-report.html">Open the latest weekly price intelligence →</a></p></main><footer class="shell">Independent educational research. Not affiliated with or endorsed by Shop Fair.</footer></body></html>"""


def write_reports(summary: dict[str, Any], docs_dir: Path) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    weekly = render_weekly_report(summary)
    index = render_index(summary)
    outputs = {
        docs_dir / "weekly-report.html": weekly,
        docs_dir / "index.html": index,
    }
    for path, content in outputs.items():
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    write_json_atomic(docs_dir / "data" / "weekly-summary.json", summary)
