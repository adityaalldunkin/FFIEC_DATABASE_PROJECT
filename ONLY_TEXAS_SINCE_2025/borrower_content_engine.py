#!/usr/bin/env python3
"""
Borrower-facing content expansion for Lenni static site.

Generates market insights, borrower scenarios, playbook pages, and JSON feeds
from live bank portfolio data + editorial YAML.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from loan_mix import MIX_KEYS, MIX_LABELS, mix_score

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ANALYSIS = ROOT / "analysis"
SCENARIOS_YAML = CONTENT / "borrower_scenarios.yaml"
SITE_BASE = "http://lenni-borrower.s3-website.us-east-2.amazonaws.com"
SPECIALIST_PCT = 8
ICP_MIN_M = 500
ICP_MAX_M = 2000
ICP_PAGE_SIZE = 20


def esc(text) -> str:
    return html.escape(str(text) if text is not None else "")


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:80] or "page"


def fmt_money_m(v: float) -> str:
    if v >= 1000:
        return f"${v/1000:.1f}B"
    return f"${v:.0f}M"


def hhi(values: list[float]) -> float:
    import numpy as np

    x = np.array([v for v in values if v > 0], dtype=float)
    if len(x) == 0 or x.sum() == 0:
        return 0.0
    shares = x / x.sum()
    return float((shares**2).sum())


def gini(values: list[float]) -> float:
    import numpy as np

    x = np.sort(np.array([v for v in values if v > 0], dtype=float))
    if len(x) == 0:
        return 0.0
    n = len(x)
    cum = np.cumsum(x)
    return float((n + 1 - 2 * np.sum(cum) / cum[-1]) / n)


def compute_market_stats(banks: list[dict]) -> dict:
    """Derive borrower-facing market statistics from enriched bank records."""
    n = len(banks)
    icp = [b for b in banks if b.get("icp")]
    assets = [b["assets"] for b in banks]
    loans = [b["loans"] for b in banks]
    lta = [b["loanToAsset"] for b in banks if b.get("loanToAsset")]

    asset_bands = [
        ("<$100M", lambda a: a < 100),
        ("$100–250M", lambda a: 100 <= a < 250),
        ("$250–500M", lambda a: 250 <= a < 500),
        ("$500M–$1B", lambda a: 500 <= a < 1000),
        ("$1–2B", lambda a: 1000 <= a < 2000),
        ("$2–5B", lambda a: 2000 <= a < 5000),
        (">$5B", lambda a: a >= 5000),
    ]
    band_counts = []
    for label, pred in asset_bands:
        band_counts.append({"band": label, "count": sum(1 for a in assets if pred(a))})

    availability = []
    concentration = []
    for key in MIX_KEYS:
        label = MIX_LABELS[key]
        usd_vals = [b.get("mixUsd", {}).get(key, 0) for b in banks]
        active = [v for v in usd_vals if v > 0]
        pcts = [mix_score(b["mix"], key) for b in banks if b.get("mixUsd", {}).get(key, 0) > 0]
        specialists = sum(1 for b in banks if mix_score(b["mix"], key) >= SPECIALIST_PCT)
        avail_pct = round(len(active) / n * 100) if n else 0
        availability.append({
            "key": key,
            "label": label,
            "banks_with_balance": len(active),
            "availability_pct": avail_pct,
            "specialists": specialists,
            "median_exposure_m": int(sorted(active)[len(active) // 2]) if active else 0,
            "p75_exposure_m": int(sorted(active)[int(len(active) * 0.75)]) if active else 0,
        })
        h = hhi(active)
        g = gini(active)
        top5 = 0
        if active:
            s = sorted(active, reverse=True)
            top5 = round(sum(s[:5]) / sum(s) * 100)
        concentration.append({
            "key": key,
            "label": label,
            "hhi": round(h * 10000),
            "gini": round(g * 100),
            "top5_pct": top5,
            "structure": "Highly concentrated" if h > 0.15 else "Moderate" if h > 0.08 else "Fragmented",
        })

    availability.sort(key=lambda x: -x["availability_pct"])
    concentration.sort(key=lambda x: -x["hhi"])

    city_counts: dict[str, int] = {}
    for b in banks:
        city_counts[b["city"]] = city_counts.get(b["city"], 0) + 1
    top_cities = sorted(city_counts.items(), key=lambda x: -x[1])[:15]

    metro_counts: dict[str, int] = {}
    for b in banks:
        m = b.get("metro") or "Other"
        metro_counts[m] = metro_counts.get(m, 0) + 1
    top_metros = sorted(metro_counts.items(), key=lambda x: -x[1])[:12]

    consumer_heavy = sum(
        1 for b in banks
        if b["mix"].get("cons", 0) + b["mix"].get("res", 0) > 40
    )
    portfolio_style = sum(
        1 for b in banks
        if b["mix"].get("inv", 0) + b["mix"].get("own", 0) + b["mix"].get("ci", 0) > 50
    )

    cre_ci_overlap = sum(
        1 for b in banks
        if mix_score(b["mix"], "inv") >= SPECIALIST_PCT and mix_score(b["mix"], "ci") >= SPECIALIST_PCT
    )

    med_assets = sorted(assets)[len(assets) // 2] if assets else 0
    med_loans = sorted(loans)[len(loans) // 2] if loans else 0
    med_lta = sorted(lta)[len(lta) // 2] if lta else 0

    mf_specialists_deep = sum(1 for b in banks if mix_score(b["mix"], "mf") >= 15)

    return {
        "bank_count": n,
        "icp_count": len(icp),
        "below_icp": sum(1 for a in assets if a < ICP_MIN_M),
        "above_icp": sum(1 for a in assets if a > ICP_MAX_M),
        "median_assets_m": med_assets,
        "median_loans_m": med_loans,
        "median_lta": med_lta,
        "asset_bands": band_counts,
        "availability": availability,
        "concentration": concentration,
        "top_cities": top_cities,
        "top_metros": top_metros,
        "consumer_heavy_count": consumer_heavy,
        "portfolio_style_count": portfolio_style,
        "cre_ci_overlap": cre_ci_overlap,
        "mf_deep_specialists": mf_specialists_deep,
        "widest_product": availability[0]["label"] if availability else "",
        "narrowest_product": availability[-1]["label"] if availability else "",
        "most_concentrated": concentration[0]["label"] if concentration else "",
    }


def load_scenarios() -> list[dict]:
    if not SCENARIOS_YAML.is_file():
        return []
    data = yaml.safe_load(SCENARIOS_YAML.read_text(encoding="utf-8"))
    return data.get("scenarios") or []


def insight_catalog(stats: dict) -> list[dict]:
    """Twelve documented insights with live statistics woven in."""
    avail = {a["key"]: a for a in stats["availability"]}
    conc = stats["concentration"]
    widest = stats["availability"][0] if stats["availability"] else {}
    narrowest = stats["availability"][-1] if stats["availability"] else {}
    top_city = stats["top_cities"][0] if stats["top_cities"] else ("Dallas", 0)

    return [
        {
            "id": "i-01",
            "code": "I-01",
            "slug": "i-01-product-choice-breadth",
            "title": "Product choice breadth — how many banks can fund your deal?",
            "theme": "Product choice breadth",
            "priority": "High",
            "summary": (
                f"{widest.get('label', 'C&I')} has the widest Texas lender pool "
                f"({widest.get('banks_with_balance', 0)} of {stats['bank_count']} banks, "
                f"{widest.get('availability_pct', 0)}% availability). "
                f"{narrowest.get('label', 'Lease')} is the narrowest "
                f"({narrowest.get('banks_with_balance', 0)} banks, "
                f"{narrowest.get('availability_pct', 0)}% availability)."
            ),
            "body": [
                "Availability measures how many Texas banks report a non-zero balance in your product category on the latest FFIEC Call Report. High availability means you can run a competitive process with 10–15 banks. Low availability means fewer realistic options — relationship quality and specialist fit matter more than volume outreach.",
                "Specialists (≥8% of total loans in the category) are your highest-probability first calls. The table below shows live counts from the latest Texas bank panel.",
            ],
            "borrower_action": "Prioritize high-availability categories for competitive terms; for niche products, target specialists only.",
        },
        {
            "id": "i-02",
            "code": "I-02",
            "slug": "i-02-market-structure",
            "title": "Market structure — concentration and competition by product",
            "theme": "Market structure",
            "priority": "High",
            "summary": (
                f"Most concentrated Texas lending markets: "
                + "; ".join(
                    f"{c['label']} (top 5 banks = {c['top5_pct']}%)"
                    for c in conc[:3]
                )
                + "."
            ),
            "body": [
                "The Herfindahl-Hirschman Index (HHI) measures how much of a product market is held by a few banks. Above 1,500 (on the ×10,000 scale) is highly concentrated — borrowers may have limited alternatives at the largest institutions. Below 800 is fragmented — more banks compete, which can improve terms if you shop.",
                "Consumer lending tends to be the most concentrated product in Texas. C&I and investor CRE are more fragmented — build an 8–10 bank shortlist including mid-size community banks, not just the largest names.",
            ],
            "borrower_action": "In concentrated markets, still build an 8–10 bank list including mid-size community banks.",
        },
        {
            "id": "i-03",
            "code": "I-03",
            "slug": "i-03-deal-size-fit",
            "title": "Deal size fit — is your loan material to the bank?",
            "theme": "Deal size fit",
            "priority": "Medium",
            "summary": (
                f"Median Texas bank gross loans are {fmt_money_m(stats['median_loans_m'])}. "
                "A $3M CRE loan is material for many community banks but small for regional portfolios."
            ),
            "body": [
                "Compare your requested loan size to the median and 75th-percentile product exposure of banks you target. Banks where your deal is above their median exposure in that product are more likely to engage — it is meaningful to their book and credit committee.",
                "If your deal is far below the 25th percentile for active lenders in that category, you may be too small for their process unless you offer relationship value (deposits, treasury, cross-sell). Disclose size early to avoid wasted cycles.",
            ],
            "borrower_action": "Disclose loan size early; ask if it clears internal hold limits.",
        },
        {
            "id": "i-04",
            "code": "I-04",
            "slug": "i-04-specialist-targeting",
            "title": "Specialist targeting — the 8% portfolio rule",
            "theme": "Specialist targeting",
            "priority": "Medium",
            "summary": (
                f"Texas has {avail.get('inv', {}).get('specialists', 0)} investor CRE specialists, "
                f"{avail.get('mf', {}).get('specialists', 0)} multifamily specialists, and "
                f"{avail.get('ci', {}).get('specialists', 0)} C&I specialists at the ≥8% threshold."
            ),
            "body": [
                "A bank with ≥8% of its loan book in your product category is a specialist — they have demonstrated appetite. Above 15% is a deep specialist. These banks are your highest-probability first calls for that product.",
                "Portfolio percentage is computed as category balance ÷ total loans (RCON2122) for the same bank and quarter. It is a specialization signal, not a guarantee of approval — but it beats guessing from marketing copy.",
            ],
            "borrower_action": "Lead with NOI, occupancy, and sponsor track record for CRE outreach.",
        },
        {
            "id": "i-05",
            "code": "I-05",
            "slug": "i-05-bank-size-fit",
            "title": "Bank size fit — community banks vs regionals",
            "theme": "Bank size fit",
            "priority": "High",
            "summary": (
                f"{stats['portfolio_style_count']} Texas banks are portfolio-style commercial lenders "
                f"(CRE + C&I > 50% of loans). {stats['consumer_heavy_count']} are consumer-heavy — "
                "usually a poor fit for commercial borrowers."
            ),
            "body": [
                "FFIEC 041 filers are typically community banks with simpler structures and faster credit committees. Portfolio-style banks (investor CRE + owner-occupied CRE + C&I > 50% of loans) are the best fit for commercial borrowers — they are not retail mortgage or credit-card shops.",
                "Regional banks (larger balance sheets) can hold bigger tickets but may be more price-driven and slower. Match bank size to deal size and relationship goals.",
            ],
            "borrower_action": "Prefer community portfolio-style banks for relationship-driven CRE/C&I deals.",
        },
        {
            "id": "i-06",
            "code": "I-06",
            "slug": "i-06-icp-opportunity",
            "title": "ICP opportunity — the $500M–$2B sweet spot",
            "theme": "ICP opportunity",
            "priority": "High",
            "summary": (
                f"{stats['icp_count']} Texas banks sit in the $500M–$2B asset band — "
                f"large enough for $2M–$25M relationship credits, small enough to value sponsors."
            ),
            "body": [
                "The ICP band captures community banks with meaningful commercial lending capacity without megabank bureaucracy. Median gross loans in this segment are typically $400M–$800M — your deal size relative to their book matters.",
                f"Below $500M: {stats['below_icp']} banks (often very local). Above $2B: {stats['above_icp']} banks (more regional). Use the paginated ICP bank directory to build city-specific shortlists.",
            ],
            "borrower_action": "Shortlist 3–5 ICP banks in your city with ≥8% in your product category.",
        },
        {
            "id": "i-07",
            "code": "I-07",
            "slug": "i-07-geography",
            "title": "Geography — HQ city vs where banks actually lend",
            "theme": "Geography",
            "priority": "Medium",
            "summary": (
                f"{top_city[0]} leads Texas bank HQ count with {top_city[1]} institutions. "
                "HQ city is a starting point — branch footprint determines local presence."
            ),
            "body": [
                "FFIEC panel city is headquarters. FDIC branch data shows where banks operate. A Dallas HQ bank may lend statewide; an Amarillo HQ bank may have branches across the Panhandle.",
                "When building outreach lists, combine city landing pages, branch tables on bank profiles, and portfolio mix — not HQ alone.",
            ],
            "borrower_action": "Verify branch coverage in your market; do not limit outreach to HQ city only.",
        },
        {
            "id": "i-08",
            "code": "I-08",
            "slug": "i-08-market-momentum",
            "title": "Market momentum — growing or running off a product book?",
            "theme": "Market momentum",
            "priority": "Medium",
            "summary": "Texas bank loan books grew over the last five reporting quarters — ask lenders if their book in your sector grew too.",
            "body": [
                "Five-quarter Call Report trends show whether Texas banks are expanding or contracting product lines. A bank growing CRE or C&I is more likely to engage new deals than one running off the book.",
                "Use this as a conversation opener: 'I see Texas banks grew total loans over the last year — how did your [product] portfolio trend?'",
            ],
            "borrower_action": "Ask lenders about recent portfolio growth in your product category.",
        },
        {
            "id": "i-09",
            "code": "I-09",
            "slug": "i-09-lender-diligence",
            "title": "Lender diligence — stress signals in public data",
            "theme": "Lender diligence",
            "priority": "Medium",
            "summary": "Most Texas banks show very low 90+ day past-due ratios; a small tail warrants extra questions, not automatic exclusion.",
            "body": [
                "Call Reports include asset quality metrics by category. Elevated past-due ratios relative to peers may signal appetite constraints or portfolio stress — worth asking about in first meetings.",
                "This is diligence, not disqualification. Community banks can have lumpy quarters. Ask about charge-off trends and whether your deal type is in their growth plan.",
            ],
            "borrower_action": "Ask about charge-offs and appetite in your product category before exclusivity.",
        },
        {
            "id": "i-10",
            "code": "I-10",
            "slug": "i-10-bank-archetypes",
            "title": "Bank archetypes — filter consumer-heavy lenders",
            "theme": "Bank archetypes",
            "priority": "Medium",
            "summary": (
                f"{stats['portfolio_style_count']} banks are portfolio-style commercial lenders; "
                f"{stats['consumer_heavy_count']} are consumer-heavy (residential + consumer > 40%)."
            ),
            "body": [
                "Every bank profile on Lenni shows full eleven-category portfolio mix. Commercial borrowers should prioritize banks where CRE and C&I dominate — not credit cards and 1–4 family mortgages.",
                "Dominant product per bank reveals archetype: CRE shop, C&I shop, agricultural bank, or retail consumer bank. Match archetype to your deal.",
            ],
            "borrower_action": "Filter out consumer-heavy banks before outreach; check mix bars on each profile.",
        },
        {
            "id": "i-11",
            "code": "I-11",
            "slug": "i-11-cross-sell",
            "title": "Cross-sell — one bank for property debt and operating lines",
            "theme": "Cross-sell",
            "priority": "Medium",
            "summary": (
                f"{stats['cre_ci_overlap']} Texas banks are specialists in both investor CRE and C&I "
                "(≥8% each) — candidates for bundled relationships."
            ),
            "body": [
                "Co-occurrence analysis shows investor CRE specialists frequently overlap with C&I specialists. Sponsors who need warehouse debt plus a working capital line can often structure both with one relationship bank.",
                "Bundling can reduce legal costs and covenant complexity vs splitting across institutions — but negotiate cross-collateralization carefully.",
            ],
            "borrower_action": "For CRE + operating line needs, prioritize dual-specialist banks.",
        },
        {
            "id": "i-12",
            "code": "I-12",
            "slug": "i-12-outreach-planning",
            "title": "Outreach planning — how many banks to call",
            "theme": "Outreach planning",
            "priority": "High",
            "summary": (
                f"Build a 10–15 bank shortlist for C&I and investor CRE. Multifamily has only "
                f"~{stats['mf_deep_specialists']} deep specialists (≥15%) statewide."
            ),
            "body": [
                "Outreach intensity should match product availability. Wide pools (C&I, investor CRE): competitive process with 10–15 banks. Narrow pools (multifamily, construction, ag): 6–8 targeted specialists.",
                "Use availability tables and specialist counts to calibrate effort. Quality of fit beats quantity of calls.",
            ],
            "borrower_action": "Match outreach list size to product availability; track responses in a simple CRM.",
        },
    ]


def enhanced_head(title: str, desc: str, canonical: str = "", depth: int = 0, og_type: str = "website") -> str:
    prefix = "../" * depth
    can_url = f"{SITE_BASE}/{canonical}" if canonical else ""
    can_tag = f'<link rel="canonical" href="{esc(can_url)}"/>' if can_url else ""
    og_url = can_url or f"{SITE_BASE}/index.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"/>
<meta name="robots" content="index, follow"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(desc)}"/>
<meta property="og:type" content="{og_type}"/>
<meta property="og:url" content="{esc(og_url)}"/>
<meta name="twitter:card" content="summary"/>
<meta name="twitter:title" content="{esc(title)}"/>
<meta name="twitter:description" content="{esc(desc)}"/>
{can_tag}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}styles.css"/>
</head>"""


def expansion_nav(active: str = "", depth: int = 0) -> str:
    prefix = "../" * depth
    links = [
        (f"{prefix}index.html", "Home", "home"),
        (f"{prefix}market/texas-overview.html", "Texas Market", "market"),
        (f"{prefix}insights/index.html", "Insights", "insights"),
        (f"{prefix}scenarios/index.html", "Stories", "scenarios"),
        (f"{prefix}index.html#loans", "Loan Types", "loans"),
        (f"{prefix}index.html#banks", "Find Banks", "banks"),
        (f"{prefix}guides/borrower-playbook.html", "Playbook", "playbook"),
        (f"{prefix}guides/glossary.html", "Glossary", "glossary"),
        (f"{prefix}guides/faq.html", "FAQ", "faq"),
    ]
    parts = []
    for href, label, key in links:
        cls = ' class="active"' if key == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    return (
        f'<header class="nav"><div class="wrap nav-row">'
        f'<a href="{prefix}index.html" class="logo"><span class="dot"></span>Lenni<span>Borrower</span></a>'
        f'<nav class="nav-links">{"".join(parts)}</nav></div></header>'
    )


def json_ld_article(title: str, desc: str, url_path: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "url": f"{SITE_BASE}/{url_path}",
        "publisher": {"@type": "Organization", "name": "Lenni"},
        "about": "Texas commercial lending and community bank selection",
    }
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def pagination_html(base_path: str, page: int, total_pages: int, depth: int) -> str:
    if total_pages <= 1:
        return ""
    prefix = "../" * depth
    parts = []
    for p in range(1, total_pages + 1):
        if p == page:
            parts.append(f'<span class="page-current">{p}</span>')
        else:
            href = f"{prefix}{base_path}" if p == 1 else f"{prefix}{base_path.replace('.html', '')}/page-{p}.html"
            parts.append(f'<a href="{href}">{p}</a>')
    return f'<nav class="pagination" aria-label="Pagination">{" ".join(parts)}</nav>'


def render_table(headers: list[str], rows: list[list]) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
    return f'<table class="data-table"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def render_texas_overview(stats: dict, period: str, depth: int = 1) -> str:
    band_rows = [[b["band"], str(b["count"])] for b in stats["asset_bands"]]
    city_rows = [[c, str(n)] for c, n in stats["top_cities"][:10]]
    metro_rows = [[m, str(n)] for m, n in stats["top_metros"][:8]]
    desc = (
        f"Texas commercial lending market: {stats['bank_count']} banks, "
        f"{stats['icp_count']} in $500M–$2B ICP band, median assets {fmt_money_m(stats['median_assets_m'])}. "
        f"FFIEC data {period}."
    )
    path = "market/texas-overview.html"
    return f"""{enhanced_head("Texas Commercial Lending Market Overview | Lenni", desc, path, depth)}
{json_ld_article("Texas Commercial Lending Market Overview", desc, path)}
<body>
{expansion_nav("market", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → Texas Market Overview</nav>
<h1 class="serif">Texas commercial lending market</h1>
<p class="lead">Evidence-based overview for borrowers shopping Texas community banks. All figures from FFIEC Call Reports, period ending {esc(period)}.</p>

<section class="stat-cards">
  <div class="stat-card"><b>{stats['bank_count']}</b><span>Texas banks tracked</span></div>
  <div class="stat-card"><b>{stats['icp_count']}</b><span>ICP ($500M–$2B)</span></div>
  <div class="stat-card"><b>{fmt_money_m(stats['median_assets_m'])}</b><span>Median assets</span></div>
  <div class="stat-card"><b>{fmt_money_m(stats['median_loans_m'])}</b><span>Median gross loans</span></div>
  <div class="stat-card"><b>{stats['median_lta']}%</b><span>Median loans/assets</span></div>
  <div class="stat-card"><b>{stats['portfolio_style_count']}</b><span>Portfolio-style lenders</span></div>
</section>

<section class="content-section">
  <h2 class="serif">Why Texas community banks matter for borrowers</h2>
  <p>Texas is a commercial-lending state. The typical bank holds <b>{stats['median_lta']}%</b> of assets in loans — mostly CRE and C&I, not credit cards. Unlike generic bank finders, Lenni ranks lenders by <em>actual portfolio mix</em> from regulatory filings, not marketing pages.</p>
  <p><b>{stats['icp_count']} banks</b> sit in the $500M–$2B sweet spot: large enough for $2M–$25M relationship credits, small enough to value sponsor relationships. <a href="market/icp-banks.html">Browse the full ICP directory →</a></p>
</section>

<section class="content-section">
  <h2 class="serif">Asset band distribution</h2>
  <p class="muted">How Texas banks cluster by size — helps match your deal to the right institution.</p>
  {render_table(["Asset band", "Banks"], band_rows)}
  <p><a href="market/asset-bands.html">Detailed asset band guide →</a></p>
</section>

<section class="content-section">
  <h2 class="serif">Top HQ cities</h2>
  {render_table(["City", "Banks HQ'd here"], city_rows)}
  <p class="muted">See <a href="../index.html#banks">city landing pages</a> for bank lists per city.</p>
</section>

<section class="content-section">
  <h2 class="serif">Metro areas</h2>
  {render_table(["Metro", "Banks"], metro_rows)}
</section>

<section class="content-section">
  <h2 class="serif">Explore further</h2>
  <div class="card-grid">
    <a class="content-card" href="product-availability.html"><h3>Product availability</h3><p>How many banks fund each loan type</p></a>
    <a class="content-card" href="../insights/index.html"><h3>12 borrower insights</h3><p>EDA findings with actions</p></a>
    <a class="content-card" href="../scenarios/index.html"><h3>Borrower stories</h3><p>Real-world Texas deal scenarios</p></a>
    <a class="content-card" href="../guides/borrower-playbook.html"><h3>Borrower playbook</h3><p>Step-by-step outreach guide</p></a>
  </div>
</section>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni · <a href="../guides/methodology.html">Methodology</a> · <a href="../llms.txt">LLMs</a></p></div></footer>
</body></html>"""


def render_product_availability(stats: dict, period: str, banks: list[dict], depth: int = 1) -> str:
    rows = []
    for a in stats["availability"]:
        rows.append([
            a["label"],
            str(a["banks_with_balance"]),
            f"{a['availability_pct']}%",
            str(a["specialists"]),
            fmt_money_m(a["median_exposure_m"]),
            fmt_money_m(a["p75_exposure_m"]),
        ])
    conc_rows = [[c["label"], str(c["hhi"]), str(c["top5_pct"]), c["structure"]] for c in stats["concentration"]]
    path = "market/product-availability.html"
    desc = "Live Texas bank product availability by loan category from FFIEC Call Reports."
    return f"""{enhanced_head("Texas Loan Product Availability by Bank Count | Lenni", desc, path, depth)}
<body>
{expansion_nav("market", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → <a href="texas-overview.html">Market</a> → Product availability</nav>
<h1 class="serif">Product availability across Texas banks</h1>
<p class="lead">How many Texas banks report each loan category on the Call Report (period {esc(period)}). Use this to calibrate outreach list size.</p>

<section class="content-section">
  <h2 class="serif">Availability by product</h2>
  <p class="muted">Specialists = banks with ≥{SPECIALIST_PCT}% of total loans in the category.</p>
  {render_table(["Product", "Banks w/ balance", "Availability", "Specialists (≥8%)", "Median exposure", "P75 exposure"], rows)}
</section>

<section class="content-section">
  <h2 class="serif">Market concentration</h2>
  {render_table(["Product", "HHI ×10k", "Top 5 share", "Structure"], conc_rows)}
</section>

<section class="content-section notice">
  <p><b>Borrower takeaway:</b> {esc(stats['widest_product'])} has the widest lender pool; {esc(stats['narrowest_product'])} is the narrowest. Match outreach intensity to availability — see <a href="../insights/i-12-outreach-planning.html">Insight I-12</a>.</p>
</section>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def render_asset_bands(stats: dict, period: str, depth: int = 1) -> str:
    rows = [[b["band"], str(b["count"])] for b in stats["asset_bands"]]
    path = "market/asset-bands.html"
    return f"""{enhanced_head("Texas Bank Asset Bands — Size Guide for Borrowers | Lenni", "How Texas banks distribute by asset size and what it means for your deal.", path, depth)}
<body>
{expansion_nav("market", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → <a href="texas-overview.html">Market</a> → Asset bands</nav>
<h1 class="serif">Texas bank asset bands</h1>
<p class="lead">Match your deal size and relationship goals to the right bank size segment.</p>

<section class="content-section">
  {render_table(["Asset band", "Number of banks"], rows)}
</section>

<section class="content-section">
  <h2 class="serif">What each band means for borrowers</h2>
  <ul class="fit-list">
    <li><b>&lt;$100M — $250M:</b> Very local; best for small CRE/C&I under $1M where you know the market president.</li>
    <li><b>$250M–$500M:</b> Growing commercial capacity; good for $1M–$5M relationship deals.</li>
    <li><b>$500M–$2B (ICP):</b> Sweet spot for $2M–$25M credits — {stats['icp_count']} banks. <a href="icp-banks.html">ICP directory →</a></li>
    <li><b>$2B–$5B:</b> Regional players; larger tickets, more committee layers.</li>
    <li><b>&gt;$5B:</b> {stats['asset_bands'][-1]['count']} megabanks; price-competitive but less relationship-driven.</li>
  </ul>
</section>
<p class="tiny muted">FFIEC Call Report · {esc(period)}</p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def render_icp_banks_page(
    banks: list[dict], period: str, page: int, total_pages: int, depth: int = 1
) -> str:
    icp_banks = sorted([b for b in banks if b.get("icp")], key=lambda x: -x["loans"])
    start = (page - 1) * ICP_PAGE_SIZE
    chunk = icp_banks[start : start + ICP_PAGE_SIZE]
    rows = []
    for i, b in enumerate(chunk, start + 1):
        top_spec = b.get("specialties", [{}])[0]
        spec_txt = f"{top_spec.get('label', '')} {top_spec.get('pct', 0)}%" if top_spec else "—"
        rows.append([
            str(i),
            f'<a href="../{esc(b["pageUrl"])}">{esc(b["name"])}</a>',
            b["city"],
            fmt_money_m(b["assets"]),
            fmt_money_m(b["loans"]),
            f"{b['crePct']}%",
            f"{b['ciPct']}%",
            spec_txt,
        ])
    base = "market/icp-banks.html"
    path = base if page == 1 else f"market/icp-banks/page-{page}.html"
    pag = pagination_html(base, page, total_pages, depth)
    body_rows = ""
    for row in rows:
        body_rows += "<tr>" + "".join(
            f"<td>{c}</td>" if "<a " in str(c) else f"<td>{esc(c)}</td>" for c in row
        ) + "</tr>"
    return f"""{enhanced_head(f"Texas ICP Community Banks — Page {page} | Lenni", f"{len(icp_banks)} Texas banks in $500M–$2B asset band ranked by loan portfolio.", path, depth)}
<body>
{expansion_nav("market", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → <a href="texas-overview.html">Market</a> → ICP banks</nav>
<h1 class="serif">ICP community banks ($500M–$2B)</h1>
<p class="lead">{len(icp_banks)} Texas banks in the mid-market sweet spot · Page {page} of {total_pages}</p>

<section class="content-section">
  <table class="data-table">
    <thead><tr><th>#</th><th>Bank</th><th>City</th><th>Assets</th><th>Loans</th><th>CRE %</th><th>C&amp;I %</th><th>Top specialty</th></tr></thead>
    <tbody>{body_rows}</tbody>
  </table>
  {pag}
</section>
<p class="tiny muted">FFIEC {esc(period)} · Click any bank for full portfolio mix and branches.</p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def render_insights_index(insights: list[dict], depth: int = 1) -> str:
    cards = ""
    for ins in insights:
        cards += (
            f'<a class="content-card insight-card" href="{esc(ins["slug"])}.html">'
            f'<span class="pill">{esc(ins["code"])}</span>'
            f'<h3>{esc(ins["title"])}</h3>'
            f'<p class="muted">{esc(ins["summary"][:180])}…</p>'
            f'<span class="tiny">Read insight →</span></a>'
        )
    path = "insights/index.html"
    desc = "Twelve data-driven insights for Texas commercial borrowers from FFIEC Call Report analysis."
    return f"""{enhanced_head("12 Borrower Insights from Texas Bank Data | Lenni", desc, path, depth)}
{json_ld_article("Texas Borrower Insights", desc, path)}
<body>
{expansion_nav("insights", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → Insights</nav>
<h1 class="serif">Borrower insights from Texas bank data</h1>
<p class="lead">Documented findings from exploratory analysis of {len(insights)} insight categories — each with evidence, explanation, and a concrete borrower action.</p>
<div class="card-grid insight-grid">{cards}</div>
<section class="content-section">
  <h2 class="serif">How to use these insights</h2>
  <ol class="checklist">
    <li>Identify your loan product on the <a href="../index.html#loans">loan types page</a></li>
    <li>Read the matching insight for outreach strategy</li>
    <li>Build a bank shortlist using portfolio mix filters</li>
    <li>Follow the <a href="../guides/borrower-playbook.html">borrower playbook</a> for calls and term sheets</li>
  </ol>
</section>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni · <a href="../market/texas-overview.html">Market data</a></p></div></footer>
</body></html>"""


def render_insight_page(ins: dict, stats: dict, period: str, depth: int = 1) -> str:
    path = f"insights/{ins['slug']}.html"
    body_paras = "".join(f"<p>{esc(p)}</p>" for p in ins.get("body", []))
    avail_table = ""
    if ins["code"] in ("I-01", "I-12", "I-04"):
        rows = [
            [a["label"], str(a["banks_with_balance"]), str(a["specialists"])]
            for a in stats["availability"]
        ]
        avail_table = f"""
<section class="content-section">
  <h2 class="serif">Live data — product specialists</h2>
  {render_table(["Product", "Banks reporting", "Specialists ≥8%"], rows)}
</section>"""
    conc_table = ""
    if ins["code"] == "I-02":
        rows = [[c["label"], str(c["hhi"]), c["structure"]] for c in stats["concentration"][:8]]
        conc_table = f"""
<section class="content-section">
  <h2 class="serif">Concentration by product</h2>
  {render_table(["Product", "HHI ×10k", "Structure"], rows)}
</section>"""
    return f"""{enhanced_head(f"{ins['title']} | Lenni Insights", ins['summary'], path, depth, "article")}
{json_ld_article(ins['title'], ins['summary'], path)}
<body>
{expansion_nav("insights", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → <a href="index.html">Insights</a> → {esc(ins['code'])}</nav>
<article>
<h1 class="serif">{esc(ins['title'])}</h1>
<p class="meta"><span class="pill">{esc(ins['code'])}</span> {esc(ins['theme'])} · Priority: {esc(ins['priority'])}</p>
<p class="lead">{esc(ins['summary'])}</p>
{body_paras}
{avail_table}
{conc_table}
<section class="content-section approach-box">
  <h2 class="serif">What to do next</h2>
  <p><b>Borrower action:</b> {esc(ins['borrower_action'])}</p>
  <p><a href="../guides/borrower-playbook.html">Open the borrower playbook →</a> ·
  <a href="../scenarios/index.html">Read deal scenarios →</a></p>
</section>
</article>
<p class="tiny muted">FFIEC Call Report analysis · {esc(period)}</p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni · <a href="index.html">All insights</a></p></div></footer>
</body></html>"""


def render_scenarios_index(scenarios: list[dict], depth: int = 1) -> str:
    cards = ""
    for sc in scenarios:
        cards += (
            f'<a class="content-card scenario-card" href="{esc(sc["slug"])}.html">'
            f'<span class="pill">{esc(sc.get("location", "Texas"))}</span>'
            f'<h3>{esc(sc["title"])}</h3>'
            f'<p class="muted">{esc(sc.get("summary", "")[:200])}</p>'
            f'<span class="tiny">{esc(sc.get("deal_size", ""))} →</span></a>'
        )
    path = "scenarios/index.html"
    desc = "Texas borrower deal scenarios with bank outreach strategies grounded in FFIEC data."
    return f"""{enhanced_head("Texas Borrower Deal Scenarios & Stories | Lenni", desc, path, depth)}
<body>
{expansion_nav("scenarios", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → Borrower stories</nav>
<h1 class="serif">Texas borrower deal scenarios</h1>
<p class="lead">Real-world deal stories showing how to use Call Report data, specialist targeting, and geographic strategy. Each scenario links to loan guides and live bank rankings.</p>
<div class="card-grid scenario-grid">{cards}</div>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def render_scenario_page(sc: dict, banks: list[dict], period: str, depth: int = 1) -> str:
    path = f"scenarios/{sc['slug']}.html"
    desc = sc.get("summary", "")[:300]
    insights_links = ""
    for code in sc.get("eda_insights", []):
        slug_map = {
            "I-01": "i-01-product-choice-breadth",
            "I-02": "i-02-market-structure",
            "I-03": "i-03-deal-size-fit",
            "I-04": "i-04-specialist-targeting",
            "I-05": "i-05-bank-size-fit",
            "I-06": "i-06-icp-opportunity",
            "I-07": "i-07-geography",
            "I-08": "i-08-market-momentum",
            "I-09": "i-09-lender-diligence",
            "I-10": "i-10-bank-archetypes",
            "I-11": "i-11-cross-sell",
            "I-12": "i-12-outreach-planning",
        }
        slug = slug_map.get(code, "")
        if slug:
            insights_links += f'<a href="../insights/{slug}.html">{esc(code)}</a> '
    data_pts = "".join(f"<li>{esc(p)}</li>" for p in sc.get("data_points", []))
    actions = "".join(f"<li>{esc(p)}</li>" for p in sc.get("action_plan", []))
    questions = "".join(f"<li>{esc(q)}</li>" for q in sc.get("questions_to_ask", []))
    guides = ""
    for g in sc.get("related_guides", []):
        guides += f'<li><a href="../{esc(g)}">{esc(g)}</a></li>'

    parent_key = {"multifamily": "mf", "investor-cre": "inv", "owner-occupied-cre": "own",
                  "commercial-construction": "con", "ci-business": "ci", "residential-14": "res",
                  "ag-farmland": "farm"}.get(sc.get("loan_parent", ""), "ci")
    city_banks = [b for b in banks if b["city"].lower() == sc.get("location", "").lower()]
    city_banks = sorted(city_banks, key=lambda x: -mix_score(x["mix"], parent_key))[:8]
    bank_rows = ""
    for b in city_banks:
        pct = mix_score(b["mix"], parent_key)
        if pct < 3:
            continue
        bank_rows += (
            f'<tr><td><a href="../{esc(b["pageUrl"])}">{esc(b["name"])}</a></td>'
            f'<td>{pct}%</td><td>{fmt_money_m(b["assets"])}</td></tr>'
        )

    return f"""{enhanced_head(f"{sc['title']} | Lenni Borrower Story", desc, path, depth, "article")}
{json_ld_article(sc['title'], desc, path)}
<body>
{expansion_nav("scenarios", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → <a href="index.html">Stories</a> → {esc(sc.get('persona', 'Scenario'))}</nav>
<article>
<h1 class="serif">{esc(sc['title'])}</h1>
<p class="meta">{esc(sc.get('persona', ''))} · {esc(sc.get('location', 'Texas'))} · {esc(sc.get('deal_size', ''))}</p>
<p class="lead">{esc(sc.get('summary', ''))}</p>

<section class="content-section">
  <h2 class="serif">The situation</h2>
  <p>{esc(sc.get('situation', ''))}</p>
</section>

<section class="content-section">
  <h2 class="serif">What the data says</h2>
  <ul class="fit-list">{data_pts}</ul>
  <p class="muted">Related insights: {insights_links}</p>
</section>

<section class="content-section approach-box">
  <h2 class="serif">Action plan</h2>
  <ol class="checklist">{actions}</ol>
</section>

<section class="content-section">
  <h2 class="serif">Questions to ask lenders</h2>
  <ul class="checklist">{questions}</ul>
</section>

<section class="content-section">
  <h2 class="serif">Banks in {esc(sc.get('location', 'Texas'))} — relevant portfolio mix</h2>
  <table class="data-table">
    <thead><tr><th>Bank</th><th>Category %</th><th>Assets</th></tr></thead>
    <tbody>{bank_rows or '<tr><td colspan="3">See statewide specialist rankings on loan type pages.</td></tr>'}</tbody>
  </table>
</section>

<section class="content-section">
  <h2 class="serif">Related guides</h2>
  <ul>{guides}</ul>
</section>
</article>
<p class="tiny muted">Scenario for education · FFIEC data {esc(period)} · Not financial advice</p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni · <a href="index.html">All stories</a></p></div></footer>
</body></html>"""


def render_borrower_playbook(stats: dict, period: str, depth: int = 1) -> str:
    path = "guides/borrower-playbook.html"
    desc = "Complete guide to finding and approaching Texas community banks using FFIEC Call Report data."
    return f"""{enhanced_head("Texas Commercial Borrower Playbook | Lenni", desc, path, depth)}
{json_ld_article("Texas Commercial Borrower Playbook", desc, path)}
<body>
{expansion_nav("playbook", depth)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → Borrower playbook</nav>
<h1 class="serif">Texas commercial borrower playbook</h1>
<p class="lead">A step-by-step guide to finding the right Texas community bank using public Call Report data — not guesswork.</p>

<section class="content-section">
  <h2 class="serif">Step 1 — Define your loan product</h2>
  <p>Match your deal to one of seven parent categories and 27 sub-types on the <a href="../index.html#loans">loan types page</a>. Regulatory line items (RCON codes) determine how banks report your product — use the <a href="glossary.html">glossary</a> if terms are unfamiliar.</p>
</section>

<section class="content-section">
  <h2 class="serif">Step 2 — Check product availability</h2>
  <p>{esc(stats['widest_product'])} has the widest Texas lender pool; {esc(stats['narrowest_product'])} is the narrowest. See the <a href="../market/product-availability.html">live availability table</a> and <a href="../insights/i-12-outreach-planning.html">Insight I-12</a> for outreach list sizing.</p>
</section>

<section class="content-section">
  <h2 class="serif">Step 3 — Size your bank target</h2>
  <p>Median Texas bank assets: {fmt_money_m(stats['median_assets_m'])}. For $2M–$25M relationship deals, start with <b>{stats['icp_count']} ICP banks</b> ($500M–$2B). <a href="../market/icp-banks.html">Browse ICP directory →</a></p>
</section>

<section class="content-section">
  <h2 class="serif">Step 4 — Filter by portfolio mix (≥8% specialist rule)</h2>
  <p>Banks with ≥8% of loans in your category are specialists. Use loan type pages for ranked tables, or bank profile mix bars. Avoid consumer-heavy banks ({stats['consumer_heavy_count']} in Texas have &gt;40% consumer+residential).</p>
</section>

<section class="content-section">
  <h2 class="serif">Step 5 — Add geography</h2>
  <p>Start with HQ city and branch footprint — not the same thing. <a href="../insights/i-07-geography.html">Insight I-07</a>. Use <a href="../index.html#banks">city pages</a> and branch tables on bank profiles.</p>
</section>

<section class="content-section">
  <h2 class="serif">Step 6 — Build your shortlist</h2>
  <ul class="checklist">
    <li>C&I / investor CRE: 10–15 banks</li>
    <li>Multifamily / construction: 6–8 specialists ({stats['mf_deep_specialists']} deep multifamily specialists statewide)</li>
    <li>Ag / farmland: 4–6 ag-focused banks</li>
  </ul>
</section>

<section class="content-section">
  <h2 class="serif">Step 7 — Prepare your package</h2>
  <p>Each sub-type guide lists what to prepare and how to open the conversation. Read the guide for your specific deal before calling.</p>
</section>

<section class="content-section">
  <h2 class="serif">Step 8 — Run parallel conversations</h2>
  <p>Contact 3 banks per week. Disclose deal size early. Ask hold limits, covenant package, and timeline. Compare at least 3 term sheets before exclusivity.</p>
</section>

<section class="content-section">
  <h2 class="serif">Step 9 — Diligence the lender</h2>
  <p>Ask about portfolio growth, charge-offs, and appetite. <a href="../insights/i-09-lender-diligence.html">Insight I-09</a>. Public data is a starting point — first-call questions fill the gaps.</p>
</section>

<section class="content-section approach-box">
  <h2 class="serif">Quick links</h2>
  <p><a href="../scenarios/index.html">Borrower deal scenarios</a> ·
  <a href="../insights/index.html">12 data insights</a> ·
  <a href="../market/texas-overview.html">Market overview</a> ·
  <a href="outreach-checklist.html">Printable checklist</a></p>
</section>
<p class="tiny muted">FFIEC {esc(period)} · {stats['bank_count']} banks · Not financial advice</p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def render_outreach_checklist(depth: int = 1) -> str:
    path = "guides/outreach-checklist.html"
    items = [
        "Defined loan product and sub-type",
        "Checked product availability (wide vs narrow pool)",
        "Sized deal vs median bank exposure",
        "Built shortlist with ≥8% specialists",
        "Filtered out consumer-heavy banks",
        "Verified branch coverage in my market",
        "Prepared sub-type document checklist",
        "Drafted opening script from guide",
        "Listed 5 questions to ask each bank",
        "Set parallel outreach schedule (3 banks/week)",
        "Tracking responses in spreadsheet/CRM",
        "Comparing ≥3 term sheets before exclusivity",
    ]
    lis = "".join(f"<li><label><input type='checkbox' disabled/> {esc(i)}</label></li>" for i in items)
    return f"""{enhanced_head("Bank Outreach Checklist for Texas Borrowers | Lenni", "Printable checklist for commercial loan bank outreach.", path, depth)}
<body>
{expansion_nav("playbook", depth)}
<main class="wrap page">
<h1 class="serif">Bank outreach checklist</h1>
<p class="lead">Use before and during your Texas community bank search.</p>
<ul class="checklist checklist-print">{lis}</ul>
<p><a href="borrower-playbook.html">← Back to playbook</a></p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def write_robots_txt(site: Path) -> None:
    (site / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_BASE}/sitemap.xml\n",
        encoding="utf-8",
    )


def write_market_json(site: Path, stats: dict, insights: list[dict], scenarios: list[dict], period: str) -> None:
    payload = {
        "period": period,
        "site": SITE_BASE,
        "stats": stats,
        "insights": [{k: ins[k] for k in ("id", "code", "title", "summary", "borrower_action", "theme")} for ins in insights],
        "scenarios": [
            {k: sc[k] for k in ("slug", "title", "summary", "location", "deal_size", "persona") if k in sc}
            for sc in scenarios
        ],
    }
    (site / "data" / "market_insights.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def write_llms_expansion(site: Path, banks: list[dict], period: str, insights: list[dict], scenarios: list[dict], parents) -> None:
    lines = [
        "# Lenni Texas Community Bank Index",
        f"> {len(banks)} Texas banks · FFIEC {period} · Full borrower content index for search engines and LLMs",
        "",
        "## Purpose",
        "Lenni helps Texas commercial borrowers find community banks by real FFIEC Call Report portfolio mix — not marketing copy.",
        "",
        "## Main entry points",
        "- index.html — interactive bank finder and deal workspace",
        "- market/texas-overview.html — Texas lending market statistics",
        "- market/product-availability.html — banks per loan product",
        "- market/icp-banks.html — $500M–$2B community banks (paginated)",
        "- insights/index.html — 12 documented borrower insights from EDA",
        "- scenarios/index.html — 12 Texas deal scenarios with action plans",
        "- guides/borrower-playbook.html — step-by-step outreach guide",
        "- guides/glossary.html — MDRM / RCON term definitions",
        "- guides/faq.html — borrower FAQ",
        "- guides/methodology.html — data sources and limitations",
        "- data/banks.json — machine-readable bank records",
        "- data/market_insights.json — market stats and insight summaries",
        "- data/loan_products.json — loan taxonomy",
        "",
        "## Borrower insights",
    ]
    for ins in insights:
        lines.append(f"- insights/{ins['slug']}.html — {ins['code']}: {ins['title']}")
    lines.append("\n## Borrower scenarios")
    for sc in scenarios:
        lines.append(f"- scenarios/{sc['slug']}.html — {sc['title']}")
    lines.append("\n## Loan type guides")
    for parent in parents:
        lines.append(f"- loan-types/{parent['slug']}.html — {parent['name']}")
        for st in parent.get("subtypes") or []:
            lines.append(f"- loan-types/{parent['slug']}/{st['slug']}.html — {st['title']}")
    lines.append("\n## Top banks by assets")
    for b in sorted(banks, key=lambda x: -x["assets"])[:30]:
        lines.append(f"- {b['pageUrl']} — {b['name']}, {b['city']} TX, {fmt_money_m(b['assets'])} assets")
    lines.append("\n## Specialist methodology")
    lines.append(f"Banks with ≥{SPECIALIST_PCT}% of total loans in a category are labeled specialists.")
    lines.append("ICP = $500M–$2B total assets.")
    (site / "llms.txt").write_text("\n".join(lines), encoding="utf-8")
    (site / "llms-full.txt").write_text("\n".join(lines) + f"\n\n## All bank profile URLs ({len(banks)})\n" + "\n".join(f"- {b['pageUrl']}" for b in banks), encoding="utf-8")


def write_expansion_pages(
    site: Path,
    banks: list[dict],
    period: str,
    urls: list[str],
    load_parents_fn,
) -> dict:
    """Generate all expansion content pages; append URLs to urls list."""
    stats = compute_market_stats(banks)
    insights = insight_catalog(stats)
    scenarios = load_scenarios()

    (site / "market").mkdir(exist_ok=True)
    (site / "insights").mkdir(exist_ok=True)
    (site / "scenarios").mkdir(exist_ok=True)

    pages = [
        ("market/texas-overview.html", render_texas_overview(stats, period)),
        ("market/product-availability.html", render_product_availability(stats, period, banks)),
        ("market/asset-bands.html", render_asset_bands(stats, period)),
    ]
    for rel, html_content in pages:
        (site / rel).write_text(html_content, encoding="utf-8")
        urls.append(rel)

    icp_banks = [b for b in banks if b.get("icp")]
    icp_pages = max(1, (len(icp_banks) + ICP_PAGE_SIZE - 1) // ICP_PAGE_SIZE)
    icp_dir = site / "market" / "icp-banks"
    icp_dir.mkdir(exist_ok=True)
    for p in range(1, icp_pages + 1):
        html_content = render_icp_banks_page(banks, period, p, icp_pages)
        if p == 1:
            rel = "market/icp-banks.html"
            (site / rel).write_text(html_content, encoding="utf-8")
        else:
            rel = f"market/icp-banks/page-{p}.html"
            (icp_dir / f"page-{p}.html").write_text(html_content, encoding="utf-8")
        urls.append(rel)

    (site / "insights" / "index.html").write_text(render_insights_index(insights), encoding="utf-8")
    urls.append("insights/index.html")
    for ins in insights:
        rel = f"insights/{ins['slug']}.html"
        (site / "insights" / f"{ins['slug']}.html").write_text(
            render_insight_page(ins, stats, period), encoding="utf-8"
        )
        urls.append(rel)

    (site / "scenarios" / "index.html").write_text(render_scenarios_index(scenarios), encoding="utf-8")
    urls.append("scenarios/index.html")
    for sc in scenarios:
        rel = f"scenarios/{sc['slug']}.html"
        (site / "scenarios" / f"{sc['slug']}.html").write_text(
            render_scenario_page(sc, banks, period), encoding="utf-8"
        )
        urls.append(rel)

    (site / "guides" / "borrower-playbook.html").write_text(
        render_borrower_playbook(stats, period), encoding="utf-8"
    )
    urls.append("guides/borrower-playbook.html")
    (site / "guides" / "outreach-checklist.html").write_text(render_outreach_checklist(), encoding="utf-8")
    urls.append("guides/outreach-checklist.html")

    write_robots_txt(site)
    urls.append("robots.txt")
    write_market_json(site, stats, insights, scenarios, period)
    urls.append("data/market_insights.json")
    write_llms_expansion(site, banks, period, insights, scenarios, load_parents_fn())
    urls.append("llms.txt")
    urls.append("llms-full.txt")

    return stats
