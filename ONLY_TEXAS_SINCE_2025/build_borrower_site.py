#!/usr/bin/env python3
"""
Build multi-page Lenni borrower static site from FFIEC + FDIC + branch data.

  python build_borrower_site.py

Outputs:
  borrower_site/index.html          — main interactive finder
  borrower_site/data/banks.json     — enriched bank records
  borrower_site/banks/*.html        — SEO bank profile pages
  borrower_site/cities/*.html       — city landing pages
  borrower_site/loan-types/*.html           — parent loan type hubs
  borrower_site/loan-types/*/*.html         — sub-type guides (from content/loan_products.yaml)
  borrower_site/data/loan_products.json     — loan taxonomy for chat / integrations
  borrower_site/guides/*.html       — glossary, FAQ, methodology, playbook, checklist
  borrower_site/market/*.html       — Texas market overview, product availability, ICP banks (paginated)
  borrower_site/insights/*.html     — 12 EDA-backed borrower insights
  borrower_site/scenarios/*.html    — 12 borrower deal scenario stories
  borrower_site/robots.txt
  borrower_site/llms.txt / llms-full.txt
  borrower_site/data/market_insights.json
  ../2026-06-07-lenni-borrower-experience.html  — copy of index for S3 deploy
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from build_borrower_website import (
    MAJOR_METROS,
    build_banks,
    describe_bank,
    format_products_js,
    metro_for,
    render_html,
    safe_num,
    title_case_city,
    top_specialties,
)
from loan_mix import (
    MIX_COLORS,
    MIX_KEYS,
    MIX_LABELS,
    compute_mix,
    enrich_profiles_with_supplemental,
    mix_parts_usd,
    mix_score,
)
from bank_enrichment import (
    json_ld_for_bank,
    load_enrichment_map,
    merge_enrichment,
    render_bank_enrichment_html,
)
from loan_product_loader import load_parents, loan_products_json, products_for_js
from borrower_content_engine import write_expansion_pages, expansion_nav as site_nav

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
EXPORTS = ROOT / "exports"
ANALYSIS = ROOT / "analysis"
SITE = REPO / "borrower_site"
OUT_LEGACY = REPO / "2026-06-07-lenni-borrower-experience.html"
ENRICHMENT_DIR = ROOT / "enrichment"

MIX_LABELS = MIX_LABELS
MIX_COLORS = MIX_COLORS

BKCLASS_LABELS = {
    "N": "National bank",
    "NM": "State-chartered commercial bank",
    "SM": "State member Fed bank",
    "SB": "Federal savings bank",
    "SI": "State savings bank",
    "SL": "State savings & loan",
}


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:80] or "bank"


def esc(text) -> str:
    return html.escape(str(text) if text is not None else "")


def fmt_url(webaddr: str) -> str:
    if not webaddr or str(webaddr).strip() in ("", "nan"):
        return ""
    u = str(webaddr).strip()
    if not u.startswith("http"):
        u = "https://" + u
    return u


def fmt_money_m(v: float) -> str:
    if v >= 1000:
        return f"${v/1000:.1f}B"
    return f"${v:.0f}M"


def fmt_date(ymd: str) -> str:
    if not ymd or str(ymd) in ("nan", ""):
        return ""
    try:
        return datetime.strptime(str(ymd)[:10], "%m/%d/%Y").strftime("%B %d, %Y")
    except ValueError:
        return str(ymd)


def load_enriched_banks() -> tuple[list[dict], str]:
    profiles = pd.read_csv(EXPORTS / "texas_bank_profiles_latest.csv", dtype={"id_rssd": int})
    profiles = profiles.dropna(subset=["total_assets", "total_loans_gross"])
    profiles = profiles[profiles["total_loans_gross"] > 0].copy()

    profiles = enrich_profiles_with_supplemental(profiles)

    fdic = pd.read_csv(REPO / "institutions.csv", low_memory=False)
    fdic_tx = fdic[(fdic["STALP"] == "TX") & (fdic["ACTIVE"] == 1)].copy()
    fdic_tx["FED_RSSD"] = pd.to_numeric(fdic_tx["FED_RSSD"], errors="coerce")

    merged = profiles.merge(
        fdic_tx,
        left_on="id_rssd",
        right_on="FED_RSSD",
        how="left",
        suffixes=("", "_fdic"),
    )

    loc = pd.read_csv(REPO / "locations.csv", low_memory=False)
    loc_tx = loc[loc["STALP"] == "TX"].copy()
    loc_tx["CERT"] = pd.to_numeric(loc_tx["CERT"], errors="coerce")

    branch_groups: dict[int, list[dict]] = {}
    branch_cities: dict[int, set[str]] = {}
    for cert, grp in loc_tx.groupby("CERT"):
        cert = int(cert)
        branches = []
        for _, br in grp.iterrows():
            branches.append({
                "name": str(br.get("OFFNAME") or "").strip(),
                "address": str(br.get("ADDRESS") or "").strip(),
                "city": title_case_city(str(br.get("CITY") or "")),
                "county": str(br.get("COUNTY") or "").strip(),
                "zip": str(br.get("ZIP") or "").strip(),
                "main": bool(br.get("MAINOFF") == 1),
            })
        branch_groups[cert] = branches
        branch_cities[cert] = {b["city"] for b in branches if b["city"]}

    period = str(profiles["reporting_period"].iloc[0]) if len(profiles) else ""
    enrichment_map = load_enrichment_map()
    banks: list[dict] = []

    for _, row in merged.iterrows():
        mix = compute_mix(row)
        mix_usd = mix_parts_usd(row)
        city = str(row.get("city") or "").strip()
        metro = metro_for(city)
        assets_m = round(safe_num(row.get("total_assets")) / 1_000_000)
        loans_m = round(safe_num(row.get("total_loans_gross")) / 1_000_000)
        icp = row.get("icp_fit") == "ICP ($500M–$2B)"
        name = str(row.get("name") or row.get("NAME") or "").strip()
        cert = row.get("CERT")
        cert_int = int(cert) if pd.notna(cert) else None
        branches = branch_groups.get(cert_int, []) if cert_int else []
        served_cities = sorted(branch_cities.get(cert_int, {title_case_city(city)})) if cert_int else [title_case_city(city)]
        web = fmt_url(str(row.get("WEBADDR") or ""))
        bkclass = str(row.get("BKCLASS") or "")
        deposits_m = round(safe_num(row.get("DEP")) / 1_000_000) if pd.notna(row.get("DEP")) else None
        offices = int(row["OFFICES"]) if pd.notna(row.get("OFFICES")) else len(branches)
        community = bool(row.get("CB") == 1) if pd.notna(row.get("CB")) else None

        bank = {
            "id": int(row["id_rssd"]),
            "slug": f"{int(row['id_rssd'])}-{slugify(name)}",
            "name": name,
            "city": title_case_city(city),
            "county": str(row.get("COUNTY") or "").strip().title(),
            "metro": metro,
            "markets": [metro, title_case_city(city)],
            "assets": assets_m,
            "loans": loans_m,
            "deposits": deposits_m,
            "loanToAsset": round(safe_num(row.get("loan_to_asset_ratio")) * 100, 1),
            "crePct": round(safe_num(row.get("cre_to_loans")) * 100, 1),
            "ciPct": round(safe_num(row.get("ci_to_loans")) * 100, 1),
            "icp": icp,
            "period": period,
            "mix": mix,
            "mixUsd": {k: round(mix_usd.get(k, 0)) for k in MIX_KEYS},
            "specialties": [{"label": l, "pct": p} for l, p in top_specialties(mix, 4)],
            "desc": describe_bank(name, city, metro, mix, assets_m, icp),
            "cert": cert_int,
            "website": web,
            "hqAddress": str(row.get("ADDRESS") or "").strip(),
            "zip": str(row.get("ZIP") or "").strip(),
            "established": fmt_date(str(row.get("ESTYMD") or "")),
            "offices": offices,
            "branchCount": len(branches),
            "branches": branches[:25],
            "servedCities": served_cities[:40],
            "bkclass": bkclass,
            "bkclassLabel": BKCLASS_LABELS.get(bkclass, bkclass),
            "communityBank": community,
            "cbsa": str(row.get("CBSA_METRO_NAME") or "").strip(),
            "pageUrl": f"banks/{int(row['id_rssd'])}-{slugify(name)}.html",
        }
        banks.append(merge_enrichment(bank, enrichment_map.get(int(row["id_rssd"]))))

    banks.sort(key=lambda b: -b["assets"])
    return banks, period


def load_glossary() -> list[dict]:
    cat = pd.read_csv(REPO / "texas_loan_products_mdrm_catalog.csv")
    cat = cat[cat["in_texas_data"].astype(str).str.lower() == "yes"].copy()
    priority_codes = [
        "RCON2122", "RCON1766", "RCON1460", "RCONF161", "RCONF160", "RCONF158",
        "RCONF159", "RCON1420", "RCON1403", "RCON1545", "RCON1590", "RCON2130",
        "RCON5368", "RCON2170",
    ]
    items = []
    for code in priority_codes:
        row = cat[cat["mdrm_code"] == code]
        if row.empty:
            continue
        r = row.iloc[0]
        desc = str(r["mdrm_description"])[:400]
        items.append({
            "code": code,
            "name": str(r["item_name"]).strip(),
            "description": desc,
            "category": str(r["mdrm_category"]),
        })
    extra = cat[~cat["mdrm_code"].isin(priority_codes)].head(30)
    for _, r in extra.iterrows():
        items.append({
            "code": str(r["mdrm_code"]),
            "name": str(r["item_name"]).strip()[:120],
            "description": str(r["mdrm_description"])[:300],
            "category": str(r["mdrm_category"]),
        })
    return items


SITE_BASE = "http://lenni-borrower.s3-website.us-east-2.amazonaws.com"


def base_head(title: str, desc: str, canonical: str = "", depth: int = 0) -> str:
    prefix = "../" * depth
    can_url = f"{SITE_BASE}/{canonical}" if canonical else ""
    can = f'<link rel="canonical" href="{esc(can_url)}"/>' if can_url else ""
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
<meta property="og:type" content="website"/>
<meta property="og:url" content="{esc(og_url)}"/>
<meta name="twitter:card" content="summary"/>
{can}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{prefix}styles.css"/>
</head>"""


def render_mix_bars(mix: dict, highlight: str | None = None, show_zero: bool = True) -> str:
    max_v = max((mix.get(k, 0) for k in MIX_KEYS), default=1) or 1
    rows = []
    for key in MIX_KEYS:
        label = MIX_LABELS[key]
        v = mix.get(key, 0)
        if not show_zero and v < 1:
            continue
        hl = " hl" if key == highlight else ""
        zero = " zero" if v < 1 else ""
        color = MIX_COLORS[key]
        width = max(v / max_v * 100, 2) if v > 0 else 0
        rows.append(
            f'<div class="bar-row{hl}{zero}"><div class="lbl">{esc(label)}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{width:.0f}%;background:{color}"></div></div>'
            f'<div class="val">{v}%</div></div>'
        )
    return "\n".join(rows)


def render_mix_table(mix: dict, mix_usd: dict, total_loans_m: float) -> str:
    rows = []
    for key in MIX_KEYS:
        pct = mix.get(key, 0)
        usd = mix_usd.get(key, 0)
        if usd >= 1_000_000:
            amt = f"${usd / 1_000_000:.2f}M"
        elif usd >= 1_000:
            amt = f"${usd / 1_000:.0f}K"
        else:
            amt = f"${usd:,.0f}" if usd else "—"
        rows.append(
            f"<tr><td>{esc(MIX_LABELS[key])}</td><td><b>{pct}%</b></td><td>{amt}</td></tr>"
        )
    total_label = f"${total_loans_m:.1f}M" if total_loans_m < 1000 else f"${total_loans_m/1000:.2f}B"
    return (
        '<table class="data-table mix-table"><thead><tr><th>Category</th><th>Share</th><th>Reported balance</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody>"
        f'<tfoot><tr><td><b>Total loans</b></td><td><b>100%</b></td><td><b>{total_label}</b></td></tr></tfoot></table>'
    )


def render_bank_page(bank: dict, period: str) -> str:
    web_link = (
        f'<a href="{esc(bank["website"])}" target="_blank" rel="noopener" class="btn btn-primary">Visit website →</a>'
        if bank.get("website")
        else '<span class="muted">Website not in FDIC record</span>'
    )
    branch_rows = ""
    for br in bank.get("branches", [])[:20]:
        main = " <span class='pill'>Main office</span>" if br.get("main") else ""
        branch_rows += (
            f"<tr><td>{esc(br.get('name') or 'Branch')}{main}</td>"
            f"<td>{esc(br.get('address'))}</td><td>{esc(br.get('city'))}</td>"
            f"<td>{esc(br.get('county'))}</td><td>{esc(br.get('zip'))}</td></tr>"
        )
    icp_badge = '<span class="pill icp-badge">Community bank · $500M–$2B</span>' if bank["icp"] else ""
    comm_badge = '<span class="pill live-badge">FDIC community bank</span>' if bank.get("communityBank") else ""
    good_fit = []
    for spec in bank.get("specialties", [])[:3]:
        if spec["pct"] >= 15 and spec["label"] != "Unclassified":
            good_fit.append(f"<li>Strong in <b>{esc(spec['label'])}</b> ({spec['pct']}% of loan book)</li>")
    if bank["mix"].get("uncat", 0) >= 20:
        good_fit.append(
            f"<li><b>{bank['mix']['uncat']}%</b> of loans are unclassified in the Call Report detail we map — "
            "see full breakdown below</li>"
        )
    if bank["icp"]:
        good_fit.append("<li>Mid-size Texas community bank — typical Lenni CLO prospect segment</li>")
    if bank.get("branchCount", 0) > 5:
        good_fit.append(f"<li>Multi-branch lender ({bank['branchCount']} Texas locations)</li>")

    enrich_html = render_bank_enrichment_html(bank, esc=esc)
    json_ld = ""
    if bank.get("webEnrichment"):
        json_ld = f'<script type="application/ld+json">{json_ld_for_bank(bank)}</script>\n'

    return f"""{base_head(
        f"{bank['name']} — Commercial Lending in {bank['city']}, TX | Lenni",
        f"{bank['name']} in {bank['city']}, Texas: {fmt_money_m(bank['assets'])} assets, "
        f"{fmt_money_m(bank['loans'])} loans. Portfolio mix from FFIEC Call Report {period}.",
        bank["pageUrl"],
        depth=1,
    )}
{json_ld}<body>
{site_nav(depth=1)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → <a href="../index.html#banks">Banks</a> → {esc(bank['name'])}</nav>
<div class="page-hero">
  <h1 class="serif">{esc(bank['name'])}</h1>
  <p class="meta">{esc(bank['city'])}, {esc(bank['county'])} County · {esc(bank['metro'])} · {icp_badge} {comm_badge}</p>
  <p class="lead">{esc(bank['desc'])}</p>
  <div class="hero-actions">{web_link} <a href="../index.html#banks" class="btn btn-ghost">Compare banks</a></div>
</div>

<section class="stat-cards">
  <div class="stat-card"><b>{fmt_money_m(bank['assets'])}</b><span>Total assets</span></div>
  <div class="stat-card"><b>{fmt_money_m(bank['loans'])}</b><span>Gross loans</span></div>
  <div class="stat-card"><b>{bank['loanToAsset']}%</b><span>Loans / assets</span></div>
  <div class="stat-card"><b>{bank['crePct']}%</b><span>CRE share</span></div>
  <div class="stat-card"><b>{bank['ciPct']}%</b><span>C&amp;I share</span></div>
  <div class="stat-card"><b>{bank.get('branchCount', bank.get('offices', 0))}</b><span>TX branches</span></div>
</section>

<section class="content-section">
  <h2 class="serif">Loan portfolio mix</h2>
  <p class="muted">From FFIEC Call Report, period ending {esc(period)}. All categories shown — percent of total loans (RCON2122) in each bucket.</p>
  <div class="mix">{render_mix_bars(bank['mix'])}</div>
  {render_mix_table(bank['mix'], bank.get('mixUsd', {}), bank['loans'])}
</section>

<section class="content-section">
  <h2 class="serif">Good fit if you need…</h2>
  <ul class="fit-list">{''.join(good_fit) or '<li>Diversified community bank lending</li>'}</ul>
</section>

<section class="content-section">
  <h2 class="serif">Institution details</h2>
  <table class="data-table">
    <tr><th>FDIC certificate</th><td>{esc(bank.get('cert') or '—')}</td></tr>
    <tr><th>Federal Reserve RSSD</th><td>{bank['id']}</td></tr>
    <tr><th>Headquarters</th><td>{esc(bank.get('hqAddress'))}, {esc(bank['city'])}, TX {esc(bank.get('zip'))}</td></tr>
    <tr><th>Charter type</th><td>{esc(bank.get('bkclassLabel'))}</td></tr>
    <tr><th>Established</th><td>{esc(bank.get('established') or '—')}</td></tr>
    <tr><th>Deposits (FDIC)</th><td>{fmt_money_m(bank['deposits']) if bank.get('deposits') else '—'}</td></tr>
    <tr><th>Metro area (FDIC)</th><td>{esc(bank.get('cbsa') or bank['metro'])}</td></tr>
    <tr><th>Website</th><td>{f'<a href="{esc(bank["website"])}" target="_blank" rel="noopener">{esc(bank["website"])}</a>' if bank.get('website') else '—'}</td></tr>
  </table>
</section>

{enrich_html}

<section class="content-section">
  <h2 class="serif">Branch locations ({bank.get('branchCount', 0)} in Texas)</h2>
  <p class="muted">Source: FDIC Summary of Deposits branch records. Showing up to 20 locations.</p>
  <table class="data-table branch-table">
    <thead><tr><th>Office</th><th>Address</th><th>City</th><th>County</th><th>ZIP</th></tr></thead>
    <tbody>{branch_rows or '<tr><td colspan="5">Branch list not linked — HQ city shown above.</td></tr>'}</tbody>
  </table>
  {f'<p class="tiny muted">Also serves: {esc(", ".join(bank.get("servedCities", [])[:15]))}{"…" if len(bank.get("servedCities", [])) > 15 else ""}</p>' if bank.get('servedCities') else ''}
</section>

<section class="content-section notice">
  <p><b>Data sources:</b> Loan portfolio from <a href="https://cdr.ffiec.gov/public/">FFIEC Call Report</a> ({esc(period)}).
  Institution and branch data from <a href="https://banks.data.fdic.gov/">FDIC BankFind</a>.
  Not financial advice. Rates and credit decisions are made by the bank, not Lenni.</p>
</section>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni · Texas community bank finder · <a href="../guides/methodology.html">Methodology</a></p></div></footer>
</body></html>"""


def render_city_page(city: str, banks_hq: list[dict], banks_branch: list[dict], period: str) -> str:
    slug = slugify(city)
    total_assets = sum(b["assets"] for b in banks_hq)
    icp_count = sum(1 for b in banks_hq if b["icp"])
    rows = ""
    for i, b in enumerate(sorted(banks_hq, key=lambda x: -x["loans"])[:25], 1):
        rows += (
            f'<tr><td>{i}</td><td><a href="../{esc(b["pageUrl"])}">{esc(b["name"])}</a></td>'
            f'<td>{fmt_money_m(b["assets"])}</td><td>{fmt_money_m(b["loans"])}</td>'
            f'<td>{b["crePct"]}%</td><td>{b["ciPct"]}%</td></tr>'
        )
    return f"""{base_head(
        f"Banks in {city}, Texas — Commercial Lenders | Lenni",
        f"Find {len(banks_hq)} Texas banks headquartered in {city}. Compare assets, loan portfolios, CRE and C&I specialization from FFIEC data.",
        f"cities/{slug}.html",
        depth=1,
    )}
<body>
{site_nav(depth=1)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → Cities → {esc(city)}</nav>
<h1 class="serif">Banks in {esc(city)}, Texas</h1>
<p class="lead">{len(banks_hq)} banks headquartered here · {len(banks_branch)} banks with branches here ·
{icp_count} in $500M–$2B community bank range · Combined assets ~{fmt_money_m(total_assets)}.</p>

<section class="content-section">
  <h2 class="serif">Headquartered in {esc(city)}</h2>
  <table class="data-table">
    <thead><tr><th>#</th><th>Bank</th><th>Assets</th><th>Loans</th><th>CRE %</th><th>C&amp;I %</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="6">No banks with HQ in this city in our dataset.</td></tr>'}</tbody>
  </table>
</section>

<section class="content-section">
  <h2 class="serif">How to use this list</h2>
  <p>Click any bank for full portfolio mix, branch locations, website, and FDIC details.
  Filter by loan type on the <a href="../index.html#loans">loan types page</a> to find specialists for multifamily, CRE, construction, or business lending.</p>
</section>
<p class="tiny muted">FFIEC Call Report data · period {esc(period)}</p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def bank_rank_table_rows(key: str, banks: list[dict], limit: int = 30, depth: int = 1) -> str:
    prefix = "../" * depth
    ranked = sorted(banks, key=lambda b: -mix_score(b["mix"], key))[:limit]
    rows = ""
    for i, b in enumerate(ranked, 1):
        pct = mix_score(b["mix"], key)
        if pct < 3:
            continue
        mix_cols = "".join(
            f"<td class='tiny'>{b['mix'].get(k, 0)}%</td>" for k in MIX_KEYS
        )
        rows += (
            f'<tr><td>{i}</td><td><a href="{prefix}{esc(b["pageUrl"])}">{esc(b["name"])}</a></td>'
            f'<td>{esc(b["city"])}</td><td><b>{pct}%</b></td>{mix_cols}'
            f'<td>{fmt_money_m(b["assets"])}</td></tr>'
        )
    return rows


def mix_table_header() -> str:
    return "".join(f"<th class='tiny'>{esc(MIX_LABELS[k])}</th>" for k in MIX_KEYS)


def specialist_count(key: str, banks: list[dict], threshold: int = 8) -> int:
    return sum(1 for b in banks if mix_score(b["mix"], key) >= threshold)


def render_mix_legend() -> str:
    items = "".join(
        f"<li><b>{esc(MIX_LABELS[k])}</b> — portfolio share from FFIEC Call Report loan schedules</li>"
        for k in MIX_KEYS
    )
    return f"<ul class='mix-legend'>{items}</ul>"


def render_faq_block(faq_items: list) -> str:
    parts = []
    for item in faq_items:
        if isinstance(item, dict) and "q" in item and "a" in item:
            q, a = item["q"], item["a"]
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            q, a = item
        else:
            continue
        parts.append(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>")
    return "".join(parts)


def render_subtype_cards(parent: dict, depth: int = 1) -> str:
    prefix = "../" * depth
    cards = []
    for st in parent.get("subtypes") or []:
        url = f"{prefix}loan-types/{parent['slug']}/{st['slug']}.html"
        cards.append(
            f'<a class="subtype-card" href="{url}">'
            f'<h3>{esc(st["title"])}</h3>'
            f'<p class="muted">{esc(st.get("one_liner", ""))}</p>'
            f'<span class="tiny">Read guide →</span></a>'
        )
    return f'<div class="subtype-grid">{"".join(cards)}</div>'


def render_parent_hub_page(parent: dict, banks: list[dict], period: str) -> str:
    key = parent["key"]
    count_8 = specialist_count(key, banks)
    faq_items = parent.get("faq") or []
    subtype_section = ""
    subtypes = parent.get("subtypes") or []
    if subtypes:
        subtype_section = f"""
<section class="content-section">
  <h2 class="serif">Loan product sub-types</h2>
  <p class="muted">Choose the deal that matches your situation — each guide includes what to prepare and how to approach a bank.</p>
  {render_subtype_cards(parent, depth=1)}
</section>"""
    return f"""{base_head(
        f"{parent['name']} in Texas — Find Specialist Banks | Lenni",
        f"{parent.get('short', '')} Compare {count_8} Texas banks with meaningful "
        f"{parent['name'].lower()} portfolio concentration. FFIEC Call Report data.",
        f"loan-types/{parent['slug']}.html",
        depth=1,
    )}
<body>
{site_nav("loans", depth=1)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../index.html">Home</a> → <a href="../index.html#loans">Loan types</a> → {esc(parent['name'])}</nav>
<h1 class="serif">{esc(parent['name'])} in Texas</h1>
<p class="lead">{esc(parent.get('short', ''))}</p>

<section class="content-section">
  <h2 class="serif">Understanding this loan type</h2>
  <p>{esc(parent.get('learn', ''))}</p>
  <p class="muted"><b>FFIEC line items:</b> {esc(parent.get('lines', ''))}</p>
</section>
{subtype_section}

<section class="content-section">
  <h2 class="serif">Texas banks that specialize ({count_8}+ with 8%+ portfolio share)</h2>
  <table class="data-table mix-wide">
    <thead><tr><th>#</th><th>Bank</th><th>City</th><th>{esc(parent['name'])} %</th>{mix_table_header()}<th>Assets</th></tr></thead>
    <tbody>{bank_rank_table_rows(key, banks)}</tbody>
  </table>
  <p class="tiny muted">Higher % in the highlighted column = more of the bank's loan book is in this category. Full portfolio mix columns shown for context. Data: FFIEC {esc(period)}.</p>
</section>

<section class="content-section">
  <h2 class="serif">Portfolio categories</h2>
  <p class="muted">Every bank profile shows all eleven loan buckets below. Agricultural categories use explicit farmland and ag-production lines only — unmapped balances appear as Unclassified.</p>
  {render_mix_legend()}
</section>

<section class="content-section">
  <h2 class="serif">FAQ</h2>
  <div class="faq">{render_faq_block(faq_items)}</div>
</section>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni · <a href="../index.html">Find banks</a></p></div></footer>
</body></html>"""


def render_related_subtypes(parent: dict, st: dict) -> str:
    slug_map = {s["slug"]: s for s in parent.get("subtypes") or []}
    links = []
    for rel_slug in st.get("related_subtypes") or []:
        rel = slug_map.get(rel_slug)
        if not rel:
            continue
        links.append(
            f'<a href="{esc(rel_slug)}.html">{esc(rel["title"])}</a>'
        )
    if not links:
        return ""
    return (
        '<section class="content-section"><h2 class="serif">Related loan types</h2>'
        f'<p class="related-links">{", ".join(links)}</p></section>'
    )


def render_subtype_page(parent: dict, st: dict, banks: list[dict], period: str) -> str:
    key = parent["key"]
    count_8 = specialist_count(key, banks)
    prep = st.get("what_to_prepare") or []
    prep_html = "".join(f"<li>{esc(item)}</li>" for item in prep)
    approach = st.get("how_to_approach") or {}
    opening = approach.get("opening", "")
    questions = approach.get("questions") or []
    q_html = "".join(f"<li>{esc(q)}</li>" for q in questions)
    not_this = st.get("not_this_product", "")
    not_html = (
        f'<section class="content-section notice"><b>Not this product:</b> {esc(not_this)}</section>'
        if not_this
        else ""
    )
    canonical = f"loan-types/{parent['slug']}/{st['slug']}.html"
    return f"""{base_head(
        f"{st['title']} in Texas — Community Bank Guide | Lenni",
        f"{st.get('one_liner', '')} Find Texas banks active in {parent['name'].lower()} from FFIEC Call Report data.",
        canonical,
        depth=2,
    )}
<body>
{site_nav("loans", depth=2)}
<main class="wrap page">
<nav class="breadcrumb"><a href="../../index.html">Home</a> → <a href="../../index.html#loans">Loan types</a> → <a href="../{esc(parent['slug'])}.html">{esc(parent['name'])}</a> → {esc(st['title'])}</nav>
<h1 class="serif">{esc(st['title'])} in Texas</h1>
<p class="lead">{esc(st.get('one_liner', ''))}</p>

<section class="content-section">
  <h2 class="serif">Who this is for</h2>
  <p>{esc(st.get('who_its_for', ''))}</p>
</section>

<section class="content-section">
  <h2 class="serif">How community banks underwrite it</h2>
  <p>{esc(st.get('how_banks_underwrite', ''))}</p>
  <p class="muted"><b>Parent category:</b> {esc(parent['name'])} · <b>FFIEC:</b> {esc(parent.get('lines', ''))}</p>
</section>

<section class="content-section">
  <h2 class="serif">What to prepare before you call a bank</h2>
  <ul class="checklist">{prep_html}</ul>
</section>

<section class="content-section approach-box">
  <h2 class="serif">How to approach a bank</h2>
  <p><b>Opening:</b> {esc(opening)}</p>
  <p><b>Questions to ask:</b></p>
  <ul class="checklist">{q_html}</ul>
</section>

<section class="content-section">
  <h2 class="serif">Texas banks that specialize in {esc(parent['name'].lower())} ({count_8}+ with 8%+ share)</h2>
  <table class="data-table mix-wide">
    <thead><tr><th>#</th><th>Bank</th><th>City</th><th>{esc(parent['name'])} %</th>{mix_table_header()}<th>Assets</th></tr></thead>
    <tbody>{bank_rank_table_rows(key, banks, depth=2)}</tbody>
  </table>
  <p class="tiny muted">Portfolio % in the highlighted column; all mix columns shown for context (FFIEC {esc(period)}).</p>
</section>

{render_related_subtypes(parent, st)}

<section class="content-section">
  <h2 class="serif">FAQ</h2>
  <div class="faq">{render_faq_block(st.get('faq') or [])}</div>
</section>
{not_html}
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni · <a href="../../index.html">Find banks</a> · <a href="../{esc(parent['slug'])}.html">{esc(parent['name'])} overview</a></p></div></footer>
</body></html>"""


def render_glossary_page(items: list[dict]) -> str:
    rows = ""
    for it in items:
        rows += (
            f'<article class="glossary-item" id="{esc(it["code"])}">'
            f'<h3><code>{esc(it["code"])}</code> — {esc(it["name"])}</h3>'
            f'<p>{esc(it["description"])}</p>'
            f'<span class="pill tiny">{esc(it["category"])}</span></article>'
        )
    return f"""{base_head(
        "Texas Bank Loan Glossary — FFIEC & MDRM Terms | Lenni",
        "Plain-English definitions of Call Report loan line items: RCON codes, CRE, C&I, multifamily, and more.",
        "guides/glossary.html",
        depth=1,
    )}
<body>
{site_nav("glossary", depth=1)}
<main class="wrap page">
<h1 class="serif">Loan &amp; banking glossary</h1>
<p class="lead">Regulatory terms translated for borrowers. Definitions from the Federal Reserve MDRM dictionary, matched to Texas Call Report data.</p>
<div class="glossary-grid">{rows}</div>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer>
</body></html>"""


def render_faq_page() -> str:
    faqs = [
        ("What is this site?", "A free Texas community bank finder built from public FFIEC Call Report and FDIC data. It shows which banks specialize in your loan type based on real portfolio data."),
        ("Where does the data come from?", "FFIEC Central Data Repository (quarterly Call Reports) for loan mix; FDIC BankFind for institution details, websites, and branch locations."),
        ("What is a Call Report?", "A quarterly regulatory filing every insured bank submits to the FFIEC. It includes balance sheet and loan portfolio detail by category."),
        ("How is portfolio % calculated?", "Each category's reported loan balance divided by total loans (RCON2122) for the same bank and quarter. All eleven categories are shown on every bank profile; unmapped Call Report lines appear as Unclassified, not agriculture."),
        ("Does this show interest rates?", "No. Rates are negotiated with the bank. This site shows specialization and size, not pricing."),
        ("Can I apply for a loan here?", "Not yet — use bank websites (linked on profiles) or Lenni Convey when available to reach a lender."),
        ("What is a community bank?", "Typically a locally focused bank; FDIC flags institutions meeting community bank criteria. Lenni focuses on $500M–$2B Texas community banks."),
        ("HQ city vs branches?", "FFIEC panel city is headquarters. FDIC branch data shows where banks operate — a Dallas HQ bank may lend statewide."),
    ]
    body = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faqs)
    return f"""{base_head("FAQ — Texas Bank Finder | Lenni", "Frequently asked questions about the Lenni Texas community bank finder and FFIEC data.", "guides/faq.html", depth=1)}
<body>{site_nav("faq", depth=1)}
<main class="wrap page"><h1 class="serif">Frequently asked questions</h1><div class="faq">{body}</div></main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer></body></html>"""


def render_methodology_page(period: str, bank_count: int) -> str:
    return f"""{base_head("Data Methodology | Lenni Texas Bank Finder", "How we combine FFIEC Call Reports and FDIC data for Texas bank profiles.", "guides/methodology.html", depth=1)}
<body>{site_nav("methodology", depth=1)}
<main class="wrap page">
<h1 class="serif">Data methodology</h1>
<p class="lead">Transparent sourcing for borrowers, researchers, and AI systems.</p>
<h2>Sources</h2>
<ul>
<li><b>FFIEC Call Report XBRL</b> — Texas banks, period ending {esc(period)}. Loan categories from Schedule RC and RC-C.</li>
<li><b>FDIC institutions.csv</b> — Active Texas institutions: certificate, website, HQ address, deposits, charter, community bank flag.</li>
<li><b>FDIC locations.csv</b> — Branch addresses, cities, counties, ZIP codes.</li>
<li><b>Federal Reserve MDRM</b> — Plain-English labels for regulatory line codes.</li>
</ul>
<h2>Join logic</h2>
<p>FFIEC <code>id_rssd</code> = FDIC <code>FED_RSSD</code>. Branches linked by FDIC <code>CERT</code>.</p>
<h2>Limitations</h2>
<ul>
<li>No interest rates, underwriting policies, or online application status in FFIEC/FDIC core data.</li>
<li>Portfolio % is a specialization signal, not a guarantee the bank will approve your deal.</li>
<li>Portfolio categories are mapped from Schedule RC-C and FFIEC 051 supplemental lines. Unmapped balances appear as <b>Unclassified</b>, not agriculture.</li>
</ul>
<p><b>Coverage:</b> {bank_count} Texas banks with complete loan and asset data in the latest quarter.</p>
</main>
<footer class="site-footer"><div class="wrap"><p>© 2026 Lenni</p></div></footer></body></html>"""


def write_styles() -> None:
    SITE.joinpath("styles.css").write_text("""
:root{--ink:#0E1B2A;--ink-2:#1c2e42;--paper:#F7F5F0;--surface:#fff;--accent:#1f9d76;--accent-d:#17795b;--gold:#C8932A;--gold-bg:#FBF1DC;--muted:#5b6b7b;--line:#e7e3d9;--soft:#f0ede5;--shadow:0 1px 2px rgba(14,27,42,.06),0 8px 24px rgba(14,27,42,.06)}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,sans-serif;color:var(--ink);background:var(--paper);line-height:1.55}
a{color:var(--accent-d)}.wrap{max-width:1100px;margin:0 auto;padding:0 24px}
.serif{font-family:Fraunces,Georgia,serif;font-weight:600}
.nav{background:rgba(247,245,240,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:50}
.nav-row{display:flex;align-items:center;gap:20px;height:60px;flex-wrap:wrap}
.logo{font-weight:800;font-size:20px;text-decoration:none;color:var(--ink);display:flex;align-items:center;gap:8px}
.logo .dot{width:10px;height:10px;border-radius:50%;background:var(--accent)}
.logo span{color:var(--muted);font-size:12px;border-left:1px solid var(--line);padding-left:8px;font-weight:600}
.nav-links{display:flex;gap:4px;flex-wrap:wrap}.nav-links a{font-size:14px;padding:7px 11px;border-radius:8px;text-decoration:none;color:var(--ink-2)}
.nav-links a:hover,.nav-links a.active{background:#fff;color:var(--accent-d);font-weight:600}
.page{padding:32px 0 64px}.breadcrumb{font-size:13px;color:var(--muted);margin-bottom:20px}
.breadcrumb a{color:var(--muted)}.page-hero{margin-bottom:32px}.page-hero h1{font-size:clamp(28px,4vw,42px);margin-bottom:10px}
.meta{color:var(--muted);font-size:15px}.lead{font-size:17px;color:var(--ink-2);max-width:65ch;margin-top:14px}
.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px;align-items:center}
.btn{display:inline-flex;padding:11px 18px;border-radius:10px;font-weight:600;font-size:14px;text-decoration:none;border:none;cursor:pointer}
.btn-primary{background:var(--accent);color:#fff}.btn-ghost{border:1px solid var(--line);color:var(--ink);background:#fff}
.pill{display:inline-flex;font-size:11px;font-weight:600;padding:3px 9px;border-radius:999px;background:var(--soft);color:var(--muted);margin-left:6px}
.icp-badge{background:var(--gold-bg);color:#8a6414;border:1px solid #ecd9a8}
.live-badge{background:rgba(31,157,118,.1);color:var(--accent-d)}
.stat-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px;margin-bottom:36px}
.stat-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;text-align:center;box-shadow:var(--shadow)}
.stat-card b{display:block;font-size:22px;color:var(--accent-d)}.stat-card span{font-size:12px;color:var(--muted)}
.content-section{margin-bottom:40px}.content-section h2{font-size:24px;margin-bottom:12px}
.muted{color:var(--muted)}.tiny{font-size:12px}
.mix{display:flex;flex-direction:column;gap:8px;margin-top:16px}
.bar-row{display:grid;grid-template-columns:150px 1fr 48px;align-items:center;gap:10px;font-size:13px}
.bar-track{height:10px;background:var(--soft);border-radius:6px;overflow:hidden}
.bar-fill{height:100%;border-radius:6px}.bar-row.zero .val{color:#a8b5c2}.bar-row.zero .bar-fill{background:#e8ecf0}
.bar-row.hl .lbl{font-weight:700;color:var(--accent-d)}
.mix-table{margin-top:20px;font-size:13px}.mix-table td,.mix-table th{padding:8px 10px}
.mix-wide{font-size:12px}.mix-wide .tiny{white-space:nowrap;font-size:11px;color:var(--muted)}
.mix-legend{font-size:14px;color:var(--ink-2);padding-left:20px}.mix-legend li{margin:6px 0}
.data-table{width:100%;border-collapse:collapse;font-size:14px;margin-top:12px}
.data-table th,.data-table td{border:1px solid var(--line);padding:10px 12px;text-align:left}
.data-table th{background:var(--soft);font-weight:600}
.fit-list li{margin-bottom:8px}.notice{background:var(--soft);border-radius:12px;padding:18px;font-size:14px}
.faq details{margin-bottom:12px;border:1px solid var(--line);border-radius:10px;padding:12px 16px;background:var(--surface)}
.faq summary{font-weight:600;cursor:pointer}
.glossary-grid{display:grid;gap:18px}.glossary-item{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px}
.glossary-item h3{font-size:16px;margin-bottom:8px}.glossary-item code{background:var(--soft);padding:2px 6px;border-radius:4px}
.subtype-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;margin-top:16px}
.subtype-card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px;text-decoration:none;color:inherit;transition:.15s}
.subtype-card:hover{border-color:var(--accent);box-shadow:var(--shadow)}
.subtype-card h3{font-size:16px;margin:0 0 8px;color:var(--ink)}
.checklist{margin:12px 0 0 20px;padding:0}.checklist li{margin-bottom:8px}
.approach-box{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:22px}
.related-links a{margin-right:12px;font-weight:600}
.site-footer{background:var(--ink);color:#9fb0c2;padding:32px 0;margin-top:40px;font-size:13px}
.site-footer a{color:#cdd7e2}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;margin-top:20px}
.content-card{display:block;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px;text-decoration:none;color:inherit;transition:.15s;box-shadow:var(--shadow)}
.content-card:hover{border-color:var(--accent);transform:translateY(-2px)}
.content-card h3{font-size:17px;margin:10px 0 8px;color:var(--ink)}
.insight-card .pill,.scenario-card .pill{margin-left:0;margin-bottom:8px}
.pagination{display:flex;gap:8px;margin-top:24px;flex-wrap:wrap;align-items:center}
.pagination a,.pagination span{padding:8px 14px;border-radius:8px;border:1px solid var(--line);text-decoration:none;font-size:14px}
.pagination a:hover{background:var(--soft)}
.pagination .page-current{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:600}
.checklist-print li{margin-bottom:12px;list-style:none}
.checklist-print label{display:flex;gap:10px;align-items:flex-start}
""", encoding="utf-8")


def write_sitemap(urls: list[str]) -> None:
  base = "http://lenni-borrower.s3-website.us-east-2.amazonaws.com"
  lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
  for u in urls:
      lines.append(f"  <url><loc>{base}/{u}</loc></url>")
  lines.append("</urlset>")
  (SITE / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")


def patch_index_with_data(banks: list[dict], period: str, glossary: list[dict]) -> None:
    """Enhance existing index.html to load external JSON and link to static pages."""
    data = {
        "period": period,
        "bankCount": len(banks),
        "icpCount": sum(1 for b in banks if b["icp"]),
        "cityCount": len({b["city"] for b in banks}),
        "metros": [m for m in MAJOR_METROS if any(b["metro"] == m for b in banks)],
        "banks": banks,
    }
    html = render_html(data, products_for_js())
    # Inject links to static pages in nav area & bank profile links
    extra_nav = (
        '<div class="proto-banner" style="padding:5px 12px;font-size:12px">'
        '<a href="market/texas-overview.html" style="color:#9fd4c4;margin:0 8px">Texas Market</a>'
        '<a href="insights/index.html" style="color:#9fd4c4;margin:0 8px">Insights</a>'
        '<a href="scenarios/index.html" style="color:#9fd4c4;margin:0 8px">Stories</a>'
        '<a href="guides/borrower-playbook.html" style="color:#9fd4c4;margin:0 8px">Playbook</a>'
        '<a href="guides/glossary.html" style="color:#9fd4c4;margin:0 8px">Glossary</a>'
        '<a href="llms.txt" style="color:#9fd4c4;margin:0 8px">LLMs</a>'
        '<a href="sitemap.xml" style="color:#9fd4c4;margin:0 8px">Sitemap</a>'
        '</div>'
    )
    html = html.replace('<header class="nav">', extra_nav + '<header class="nav">', 1)
    # Link bank profiles to static pages
    html = html.replace(
        "function openBank(id){",
        "function openBank(id){\n  var b=BANKS.find(function(x){return x.id===id});\n  if(b&&b.pageUrl){window.location.href=b.pageUrl;return;}",
    )
    html = html.replace(
        '<link href="https://fonts.googleapis.com/css2?family=Inter',
        '<link rel="stylesheet" href="styles.css"/>\n<link href="https://fonts.googleapis.com/css2?family=Inter',
    )
    # Add website button on bank profile when available
    html = html.replace(
        '<button class="btn btn-primary" id="bIntro">Talk to a lender →</button>',
        '<a class="btn btn-primary" id="bWebsite" href="#" target="_blank" rel="noopener" style="display:none">Visit website →</a>'
        '<button class="btn btn-ghost" id="bIntro">Talk to a lender →</button>'
        '<a class="btn btn-ghost" id="bStatic" href="#" style="display:none">Full profile page →</a>',
    )
    html = html.replace(
        "document.getElementById('bIntro').onclick=function(){toast('Connect via Lenni Convey when live — bank: '+b.name)};",
        "if(b.website){var w=document.getElementById('bWebsite');w.href=b.website;w.style.display='inline-flex';w.textContent='Visit website →';}\n"
        "if(b.pageUrl){var s=document.getElementById('bStatic');s.href=b.pageUrl;s.style.display='inline-flex';}\n"
        "document.getElementById('bIntro').onclick=function(){toast('Connect via Lenni Convey when live — bank: '+b.name)};",
    )
    # Branches section in bank view
    html = html.replace(
        '<div class="acc"><div class="acc-head" onclick="this.parentNode.classList.toggle(\'open\')"><h3><span style="width:30px',
        '<div class="acc" id="bBranchesAcc"><div class="acc-head" onclick="this.parentNode.classList.toggle(\'open\')"><h3><span style="width:30px;height:30px;border-radius:8px;background:var(--soft);display:inline-flex;align-items:center;justify-content:center">🏢</span> Branches</h3><span>▾</span></div><div class="acc-body"><div id="bBranches" class="muted" style="font-size:14px;margin-top:14px"></div></div></div>\n'
        '<div class="acc"><div class="acc-head" onclick="this.parentNode.classList.toggle(\'open\')"><h3><span style="width:30px',
    )
    html = html.replace(
        "document.getElementById('bMarket').textContent=",
        "var br=document.getElementById('bBranches');if(b.branches&&b.branches.length){br.innerHTML='<table style=\"width:100%;font-size:13px;border-collapse:collapse\">'+b.branches.slice(0,12).map(function(x){return '<tr><td style=\"padding:6px 0;border-bottom:1px solid var(--line)\"><b>'+x.name+'</b><br>'+x.address+', '+x.city+'</td></tr>'}).join('')+'</table><p class=\"tiny muted\">'+(b.branchCount||b.branches.length)+' Texas branches (FDIC)</p>';}else{br.textContent='Branch list available on full profile page.';}\n"
        "document.getElementById('bMarket').textContent=",
    )

    (SITE / "index.html").write_text(html, encoding="utf-8")
    OUT_LEGACY.write_text(html, encoding="utf-8")


def main() -> int:
    print("Loading and merging data…")
    banks, period = load_enriched_banks()
    glossary = load_glossary()

    if SITE.exists():
        import shutil
        shutil.rmtree(SITE)
    (SITE / "data").mkdir(parents=True)
    (SITE / "banks").mkdir()
    (SITE / "cities").mkdir()
    (SITE / "loan-types").mkdir()
    (SITE / "guides").mkdir()

    write_styles()

    # JSON data
    (SITE / "data" / "banks.json").write_text(
        json.dumps({"period": period, "banks": banks}, indent=None), encoding="utf-8"
    )
    (SITE / "data" / "glossary.json").write_text(json.dumps(glossary), encoding="utf-8")
    (SITE / "data" / "loan_products.json").write_text(
        json.dumps(loan_products_json(), indent=2), encoding="utf-8"
    )
    enrich_path = ENRICHMENT_DIR / "bank_website_enrichment.json"
    if enrich_path.is_file():
        import shutil
        shutil.copy(enrich_path, SITE / "data" / "bank_website_enrichment.json")

    urls = ["index.html", "guides/glossary.html", "guides/faq.html", "guides/methodology.html"]

    print(f"Writing {len(banks)} bank pages…")
    for b in banks:
        path = SITE / "banks" / f"{b['slug']}.html"
        path.write_text(render_bank_page(b, period), encoding="utf-8")
        urls.append(f"banks/{b['slug']}.html")

    # City pages — top cities by HQ count
    city_counts: dict[str, list[dict]] = {}
    branch_city_map: dict[str, list[dict]] = {}
    for b in banks:
        city_counts.setdefault(b["city"], []).append(b)
        for c in b.get("servedCities", [b["city"]]):
            branch_city_map.setdefault(c, [])
            if b not in branch_city_map[c]:
                branch_city_map[c].append(b)

    top_cities = sorted(city_counts.keys(), key=lambda c: -len(city_counts[c]))[:40]
    print(f"Writing {len(top_cities)} city pages…")
    for city in top_cities:
        slug = slugify(city)
        path = SITE / "cities" / f"{slug}.html"
        path.write_text(
            render_city_page(city, city_counts[city], branch_city_map.get(city, []), period),
            encoding="utf-8",
        )
        urls.append(f"cities/{slug}.html")

    subtype_count = 0
    print("Writing loan type pages…")
    for parent in load_parents():
        slug = parent["slug"]
        path = SITE / "loan-types" / f"{slug}.html"
        path.write_text(render_parent_hub_page(parent, banks, period), encoding="utf-8")
        urls.append(f"loan-types/{slug}.html")
        subdir = SITE / "loan-types" / slug
        subdir.mkdir(exist_ok=True)
        for st in parent.get("subtypes") or []:
            st_path = subdir / f"{st['slug']}.html"
            st_path.write_text(render_subtype_page(parent, st, banks, period), encoding="utf-8")
            urls.append(f"loan-types/{slug}/{st['slug']}.html")
            subtype_count += 1

    (SITE / "guides" / "glossary.html").write_text(render_glossary_page(glossary), encoding="utf-8")
    (SITE / "guides" / "faq.html").write_text(render_faq_page(), encoding="utf-8")
    (SITE / "guides" / "methodology.html").write_text(
        render_methodology_page(period, len(banks)), encoding="utf-8"
    )

    # Deal-matching JS (workspace + API client)
    static_src = ROOT / "static"
    js_dir = SITE / "js"
    js_dir.mkdir(exist_ok=True)
    for name in ("match-client.js", "workspace.js", "chat-client.js"):
        src = static_src / name
        if src.is_file():
            import shutil
            shutil.copy(src, js_dir / name)
    chat_html = static_src / "chat.html"
    if chat_html.is_file():
        import shutil
        shutil.copy(chat_html, SITE / "chat.html")

    print("Writing market insights, scenarios, and playbook…")
    stats = write_expansion_pages(SITE, banks, period, urls, load_parents)

    write_sitemap(urls)
    patch_index_with_data(banks, period, glossary)

    enrich_count = sum(1 for b in banks if b.get("webEnrichment"))
    expansion_count = len(urls) - len(banks) - len(top_cities) - subtype_count - len(load_parents()) - 4
    print(f"\nDone — {SITE}")
    print(f"  Website enrichment: {enrich_count} banks")
    print(f"  Banks: {len(banks)} pages")
    print(f"  Cities: {len(top_cities)} pages")
    print(f"  Loan types: {len(load_parents())} parent + {subtype_count} sub-type pages")
    print(f"  Expansion: insights, scenarios, market pages, playbook")
    print(f"  ICP banks: {stats['icp_count']} · Portfolio-style lenders: {stats['portfolio_style_count']}")
    print(f"  Total URLs in sitemap: {len(urls)}")
    print(f"\nDeploy: upload entire borrower_site/ folder to S3 (index.html at root)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
