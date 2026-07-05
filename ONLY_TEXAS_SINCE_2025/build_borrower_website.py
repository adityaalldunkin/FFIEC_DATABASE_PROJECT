#!/usr/bin/env python3
"""
Generate borrower-facing Lenni website from real FFIEC Texas data.

  python build_borrower_website.py
  → ../../2026-06-07-lenni-borrower-experience.html
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from loan_mix import (
    MIX_KEYS,
    MIX_LABELS,
    compute_mix,
    describe_bank,
    enrich_profiles_with_supplemental,
    mix_score,
    top_specialties,
)

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
OUT = ROOT.parent / "2026-06-07-lenni-borrower-experience.html"

METRO_MAP: dict[str, str] = {
    "DALLAS": "Dallas–Fort Worth",
    "FORT WORTH": "Dallas–Fort Worth",
    "PLANO": "Dallas–Fort Worth",
    "IRVING": "Dallas–Fort Worth",
    "ARLINGTON": "Dallas–Fort Worth",
    "GRAND PRAIRIE": "Dallas–Fort Worth",
    "GARLAND": "Dallas–Fort Worth",
    "MESQUITE": "Dallas–Fort Worth",
    "RICHARDSON": "Dallas–Fort Worth",
    "CARROLLTON": "Dallas–Fort Worth",
    "HOUSTON": "Houston",
    "PASADENA": "Houston",
    "PEARLAND": "Houston",
    "SUGAR LAND": "Houston",
    "KATY": "Houston",
    "AUSTIN": "Austin",
    "ROUND ROCK": "Austin",
    "CEDAR PARK": "Austin",
    "SAN ANTONIO": "San Antonio",
    "NEW BRAUNFELS": "San Antonio",
    "CORPUS CHRISTI": "Corpus Christi",
    "LUBBOCK": "Lubbock",
    "AMARILLO": "Amarillo",
    "MIDLAND": "Midland–Odessa",
    "ODESSA": "Midland–Odessa",
    "WACO": "Waco",
    "TYLER": "East Texas",
    "LONGVIEW": "East Texas",
    "LUFKIN": "East Texas",
    "HUNTINGTON": "East Texas",
    "BEAUMONT": "Beaumont",
    "MCALLEN": "Rio Grande Valley",
    "BROWNSVILLE": "Rio Grande Valley",
    "LAREDO": "Rio Grande Valley",
    "EL PASO": "El Paso",
    "ABILENE": "Other Texas",
    "SAN ANGELO": "Other Texas",
    "WICHITA FALLS": "Other Texas",
    "TEMPLE": "Central Texas",
    "KILLEEN": "Central Texas",
    "COLLEGE STATION": "College Station",
    "BRYAN": "College Station",
    "CORSICANA": "Central Texas",
    "GRAHAM": "Dallas–Fort Worth",
    "PARIS": "Dallas–Fort Worth",
    "HENDERSON": "East Texas",
    "LONGVIEW": "East Texas",
    "NACOGDOCHES": "East Texas",
    "PALESTINE": "East Texas",
    "SHERMAN": "Dallas–Fort Worth",
    "DENTON": "Dallas–Fort Worth",
    "MCKINNEY": "Dallas–Fort Worth",
    "FRISCO": "Dallas–Fort Worth",
    "LEAGUE CITY": "Houston",
    "CONROE": "Houston",
    "BAYTOWN": "Houston",
    "BEAUMONT": "East Texas",
    "PORT ARTHUR": "East Texas",
    "VICTORIA": "Corpus Christi",
    "HARLINGEN": "Rio Grande Valley",
    "EDINBURG": "Rio Grande Valley",
    "PHARR": "Rio Grande Valley",
    "BROWNWOOD": "Central Texas",
    "STEPHENVILLE": "Dallas–Fort Worth",
    "MINERAL WELLS": "Dallas–Fort Worth",
    "GAINESVILLE": "Dallas–Fort Worth",
    "GREENVILLE": "Dallas–Fort Worth",
    "MOUNT PLEASANT": "Dallas–Fort Worth",
    "TEXARKANA": "East Texas",
    "KERRVILLE": "San Antonio",
    "NEW BRAUNFELS": "San Antonio",
    "GEORGETOWN": "Austin",
    "PFLUGERVILLE": "Austin",
}


def title_case_city(city: str) -> str:
    if not city:
        return "Texas"
    return city.strip().title()


MAJOR_METROS = [
    "Dallas–Fort Worth",
    "Houston",
    "Austin",
    "San Antonio",
    "Midland–Odessa",
    "Corpus Christi",
    "Rio Grande Valley",
    "East Texas",
    "Central Texas",
    "Waco",
    "Lubbock",
    "Amarillo",
    "El Paso",
    "College Station",
    "Other Texas",
]


def metro_for(city: str) -> str:
    key = (city or "").strip().upper()
    return METRO_MAP.get(key, "Other Texas")


def safe_num(v, default=0.0) -> float:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_banks(df: pd.DataFrame) -> list[dict]:
    banks = []
    for _, row in df.iterrows():
        mix = compute_mix(row)
        city = str(row.get("city") or "").strip()
        metro = metro_for(city)
        assets_m = round(safe_num(row.get("total_assets")) / 1_000_000)
        loans_m = round(safe_num(row.get("total_loans_gross")) / 1_000_000)
        icp = row.get("icp_fit") == "ICP ($500M–$2B)"
        name = str(row.get("name") or "").strip()
        banks.append({
            "id": int(row["id_rssd"]),
            "name": name,
            "city": title_case_city(city),
            "metro": metro,
            "markets": [metro, title_case_city(city)],
            "assets": assets_m,
            "loans": loans_m,
            "loanToAsset": round(safe_num(row.get("loan_to_asset_ratio")) * 100, 1),
            "crePct": round(safe_num(row.get("cre_to_loans")) * 100, 1),
            "ciPct": round(safe_num(row.get("ci_to_loans")) * 100, 1),
            "icp": icp,
            "period": str(row.get("reporting_period") or ""),
            "mix": mix,
            "desc": describe_bank(name, city, metro, mix, assets_m, icp),
        })
    banks.sort(key=lambda b: -b["assets"])
    return banks


def format_products_js(products: list[dict]) -> str:
    """Serialize loan product catalog for embedded PRODUCTS array."""
    entries = []
    for p in products:
        subs = []
        for st in p.get("subtypes") or []:
            subs.append(
                "{slug:" + json.dumps(st["slug"])
                + ",title:" + json.dumps(st["title"])
                + ",one_liner:" + json.dumps(st.get("one_liner", ""))
                + ",pageUrl:" + json.dumps(st.get("pageUrl", ""))
                + ",keywords:" + json.dumps(st.get("keywords") or [])
                + "}"
            )
        entries.append(
            "{slug:" + json.dumps(p["slug"])
            + ",key:" + json.dumps(p["key"])
            + ",name:" + json.dumps(p["name"])
            + ",cat:" + json.dumps(p.get("cat", ""))
            + ",short:" + json.dumps(p.get("short", ""))
            + ",learn:" + json.dumps(p.get("learn", ""))
            + ",lines:" + json.dumps(p.get("lines", ""))
            + ",pageUrl:" + json.dumps(p.get("pageUrl", ""))
            + ",subtypes:[" + ",".join(subs) + "]}"
        )
    return "[\n " + ",\n ".join(entries) + "\n]"


def main() -> int:
    from loan_product_loader import products_for_js

    df = pd.read_csv(EXPORTS / "texas_bank_profiles_latest.csv", dtype={"id_rssd": int})
    df = df.dropna(subset=["total_assets", "total_loans_gross"])
    df = df[df["total_loans_gross"] > 0].copy()
    df = enrich_profiles_with_supplemental(df)

    banks = build_banks(df)
    period = banks[0]["period"] if banks else "3/31/2026"
    icp_count = sum(1 for b in banks if b["icp"])
    metros = [m for m in MAJOR_METROS if any(b["metro"] == m for b in banks)]

    data = {
        "period": period,
        "bankCount": len(banks),
        "icpCount": icp_count,
        "cityCount": df["city"].nunique(),
        "metros": metros,
        "banks": banks,
    }

    html = render_html(data, products_for_js())
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({len(banks)} banks, {len(html)/1024:.0f} KB)")
    return 0


def render_html(data: dict, products: list[dict] | None = None) -> str:
    if products is None:
        from loan_product_loader import products_for_js

        products = products_for_js()
    products_js = format_products_js(products)
    payload = json.dumps(data, separators=(",", ":"))
    # Escape for embedding in script tag
    payload = payload.replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Lenni — Texas Bank Finder (Live FFIEC Data)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,500;9..144,600&display=swap" rel="stylesheet">
<style>
:root{{
  --ink:#0E1B2A;--ink-2:#1c2e42;--paper:#F7F5F0;--surface:#ffffff;
  --accent:#1f9d76;--accent-d:#17795b;--gold:#C8932A;--gold-bg:#FBF1DC;
  --muted:#5b6b7b;--line:#e7e3d9;--soft:#f0ede5;
  --mf:#1f9d76;--inv:#2f6fed;--own:#7c3aed;--con:#e08a2b;--ci:#db5461;--res:#58b3c7;--cons:#9aa6b2;
  --farm:#8b6914;--ag:#6b8e23;--lease:#a78bfa;--uncat:#c4ccd6;
  --shadow:0 1px 2px rgba(14,27,42,.06),0 8px 24px rgba(14,27,42,.06);
  --shadow-lg:0 12px 40px rgba(14,27,42,.14);
}}
*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}
body{{font-family:Inter,system-ui,sans-serif;color:var(--ink);background:var(--paper);line-height:1.5;-webkit-font-smoothing:antialiased}}
h1,h2,h3{{margin:0;line-height:1.15;letter-spacing:-.02em}}
a{{color:inherit;text-decoration:none}}
.serif{{font-family:Fraunces,Georgia,serif;font-weight:600;letter-spacing:-.01em}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 24px}}
.btn{{display:inline-flex;align-items:center;gap:8px;border:none;cursor:pointer;font-family:inherit;font-weight:600;font-size:15px;border-radius:11px;padding:13px 20px;transition:.15s}}
.btn-primary{{background:var(--accent);color:#fff}}.btn-primary:hover{{background:var(--accent-d)}}
.btn-ghost{{background:transparent;color:var(--ink);border:1px solid var(--line)}}.btn-ghost:hover{{border-color:var(--ink);background:#fff}}
.btn-dark{{background:var(--ink);color:#fff}}.btn-dark:hover{{background:var(--ink-2)}}
.btn-sm{{padding:8px 14px;font-size:13px;border-radius:9px}}
.pill{{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:4px 10px;border-radius:999px;background:var(--soft);color:var(--muted)}}
.icp-badge{{background:var(--gold-bg);color:#8a6414;border:1px solid #ecd9a8}}
.live-badge{{background:rgba(31,157,118,.12);color:var(--accent-d);border:1px solid rgba(31,157,118,.25)}}
.muted{{color:var(--muted)}}.tiny{{font-size:12px}}.center{{text-align:center}}
.proto-banner{{background:var(--ink);color:#cdd7e2;font-size:12.5px;text-align:center;padding:7px 12px}}
.proto-banner b{{color:#fff}}
header.nav{{position:sticky;top:0;z-index:50;background:rgba(247,245,240,.85);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
.nav-row{{display:flex;align-items:center;gap:28px;height:64px}}
.logo{{font-weight:800;font-size:21px;letter-spacing:-.04em;display:flex;align-items:center;gap:9px;cursor:pointer}}
.logo .dot{{width:11px;height:11px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px rgba(31,157,118,.18)}}
.logo span{{color:var(--muted);font-weight:600;font-size:12px;border-left:1px solid var(--line);padding-left:9px}}
.nav-links{{display:flex;gap:4px;margin-left:6px}}
.nav-links a{{font-size:14.5px;font-weight:500;color:var(--ink-2);padding:8px 12px;border-radius:8px;cursor:pointer}}
.nav-links a:hover,.nav-links a.active{{background:#fff}}.nav-links a.active{{color:var(--accent-d);font-weight:600}}
.nav-right{{margin-left:auto;display:flex;align-items:center;gap:12px}}
.loc{{display:flex;align-items:center;gap:6px;font-size:13px;font-weight:500;color:var(--muted);background:#fff;border:1px solid var(--line);padding:7px 11px;border-radius:9px}}
.loc select{{border:none;background:none;font-family:inherit;font-weight:600;color:var(--ink);font-size:13px;cursor:pointer;outline:none;max-width:160px}}
.view{{display:none;animation:fade .35s ease}}.view.active{{display:block}}
@keyframes fade{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.hero{{padding:72px 0 56px;position:relative;overflow:hidden}}
.hero:before{{content:"";position:absolute;inset:0;background:radial-gradient(900px 380px at 78% -8%,rgba(31,157,118,.12),transparent 60%),radial-gradient(700px 300px at 10% 120%,rgba(47,111,237,.08),transparent 60%);pointer-events:none}}
.hero .eyebrow{{font-size:13px;font-weight:700;color:var(--accent-d);letter-spacing:.06em;text-transform:uppercase;margin-bottom:18px}}
.hero h1{{font-size:clamp(34px,5vw,58px);max-width:14ch}}
.hero h1 em{{font-style:normal;color:var(--accent-d)}}
.hero p.sub{{font-size:19px;color:var(--ink-2);max-width:52ch;margin:20px 0 30px}}
.hero-cta{{display:flex;gap:12px;flex-wrap:wrap}}
.trust{{display:flex;gap:26px;margin-top:38px;flex-wrap:wrap;color:var(--muted);font-size:13.5px}}
.trust b{{color:var(--ink);font-weight:700}}
.sec{{padding:62px 0}}.sec.alt{{background:var(--surface);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
.sec-head{{max-width:60ch;margin-bottom:34px}}
.sec-head .eyebrow{{font-size:12.5px;font-weight:700;color:var(--accent-d);letter-spacing:.06em;text-transform:uppercase}}
.sec-head h2{{font-size:clamp(26px,3.4vw,38px);margin-top:10px}}
.sec-head p{{color:var(--muted);font-size:16.5px;margin-top:12px}}
.grid{{display:grid;gap:18px}}.g3{{grid-template-columns:repeat(3,1fr)}}.g4{{grid-template-columns:repeat(4,1fr)}}.g2{{grid-template-columns:repeat(2,1fr)}}
@media(max-width:900px){{.g3,.g4{{grid-template-columns:repeat(2,1fr)}}.nav-links{{display:none}}}}
@media(max-width:620px){{.g3,.g4,.g2{{grid-template-columns:1fr}}}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:var(--shadow);transition:.18s}}
.card.click{{cursor:pointer}}.card.click:hover{{transform:translateY(-3px);box-shadow:var(--shadow-lg);border-color:#d8d2c4}}
.feat .ic{{width:40px;height:40px;border-radius:11px;background:rgba(31,157,118,.12);display:flex;align-items:center;justify-content:center;margin-bottom:14px;font-size:20px}}
.steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}}
@media(max-width:620px){{.steps{{grid-template-columns:1fr}}}}
.step .n{{font-family:Fraunces,serif;font-size:40px;color:var(--accent);opacity:.45;font-weight:600}}
.searchbar{{display:flex;align-items:center;gap:12px;background:var(--surface);border:1.5px solid var(--line);border-radius:14px;padding:6px 6px 6px 18px;box-shadow:var(--shadow);max-width:680px}}
.searchbar input{{flex:1;border:none;outline:none;font-family:inherit;font-size:16px;padding:12px 0;background:none}}
.searchbar .ai{{font-size:12px;font-weight:700;color:var(--accent-d);background:rgba(31,157,118,.12);padding:5px 9px;border-radius:7px}}
.chips{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}}
.chip{{font-size:13px;color:var(--ink-2);background:#fff;border:1px solid var(--line);padding:7px 12px;border-radius:999px;cursor:pointer}}
.chip:hover{{border-color:var(--accent);color:var(--accent-d)}}
.lc-cat{{font-size:12px;font-weight:600;color:var(--muted)}}
.lc h3{{font-size:18.5px;margin:10px 0 8px}}.lc p{{color:var(--muted);font-size:14px;min-height:38px}}
.lc-meta{{display:flex;justify-content:space-between;align-items:center;margin-top:16px;padding-top:14px;border-top:1px solid var(--line);font-size:13px}}
.mix{{display:flex;flex-direction:column;gap:9px}}
.bar-row{{display:grid;grid-template-columns:140px 1fr 52px;align-items:center;gap:12px;font-size:13px}}
.bar-track{{height:10px;background:var(--soft);border-radius:6px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:6px}}
.bar-row.zero .val{{color:#a8b5c2}}.bar-row.zero .bar-fill{{background:#e8ecf0}}
.bar-row.hl .lbl{{color:var(--accent-d);font-weight:700}}
.rank-row{{display:grid;grid-template-columns:34px 1fr 160px 120px;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:13px;padding:14px 16px;cursor:pointer;transition:.15s}}
.rank-row:hover{{border-color:#d6d0c2;box-shadow:var(--shadow)}}
.rank-row .pos{{font-family:Fraunces,serif;font-size:22px;color:var(--muted)}}
.rank-row .nm{{font-weight:600}}.rank-row .nm small{{display:block;color:var(--muted);font-weight:400;font-size:12.5px}}
.rank-pct{{display:flex;align-items:center;gap:10px}}.rank-pct .t{{flex:1;height:8px;background:var(--soft);border-radius:5px;overflow:hidden}}
.rank-pct .f{{height:100%;background:var(--accent);border-radius:5px}}
@media(max-width:720px){{.rank-row{{grid-template-columns:28px 1fr}}.rank-row .rank-pct,.rank-row .cap{{display:none}}}}
.filters{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:24px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:var(--shadow)}}
.filters label{{font-size:12px;font-weight:600;color:var(--muted);display:block;margin-bottom:4px}}
.filters select,.filters input{{font-family:inherit;font-size:14px;font-weight:500;color:var(--ink);border:1px solid var(--line);border-radius:9px;padding:9px 12px;background:#fff;outline:none;min-width:140px}}
.filters .count{{margin-left:auto;font-size:13px;color:var(--muted)}}
.bank-card h3{{font-size:18px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.bank-stats{{display:flex;gap:20px;margin:14px 0;font-size:13px;flex-wrap:wrap}}
.bank-stats .s b{{display:block;font-size:18px;font-variant-numeric:tabular-nums}}
.bank-stats .s span{{color:var(--muted)}}
.spec-tags{{display:flex;gap:6px;flex-wrap:wrap}}.spec-tags .t{{font-size:11.5px;background:var(--soft);color:var(--ink-2);padding:3px 9px;border-radius:6px;font-weight:500}}
.dhead{{padding:38px 0 26px;border-bottom:1px solid var(--line);background:var(--surface)}}
.back{{font-size:13px;color:var(--muted);cursor:pointer;display:inline-flex;gap:6px;align-items:center;margin-bottom:16px}}
.dhead h1{{font-size:clamp(26px,4vw,40px)}}.dhead .meta{{color:var(--muted);font-size:15px;margin-top:8px}}
.acc{{border:1px solid var(--line);border-radius:14px;background:var(--surface);overflow:hidden;margin-bottom:12px;box-shadow:var(--shadow)}}
.acc-head{{display:flex;align-items:center;justify-content:space-between;padding:18px 20px;cursor:pointer}}
.acc-head h3{{font-size:16.5px;display:flex;align-items:center;gap:10px}}
.acc-body{{display:none;padding:0 20px 22px;border-top:1px solid var(--line)}}
.acc.open .acc-body{{display:block}}
.placeholder{{color:var(--muted);font-size:14px;background:var(--soft);border:1px dashed var(--line);border-radius:10px;padding:16px;margin-top:14px}}
.calc{{display:grid;grid-template-columns:1fr 1fr;gap:26px}}@media(max-width:720px){{.calc{{grid-template-columns:1fr}}}}
.calc-out{{background:var(--ink);color:#fff;border-radius:16px;padding:26px}}
.calc-out .big{{font-family:Fraunces,serif;font-size:44px;font-weight:600}}
.tabs{{display:flex;gap:6px;border-bottom:1px solid var(--line);margin:8px 0 26px;flex-wrap:wrap}}
.tab{{padding:11px 16px;font-weight:600;font-size:14.5px;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}}
.tab.active{{color:var(--accent-d);border-color:var(--accent)}}
.tabpane{{display:none}}.tabpane.active{{display:block}}
.term{{background:#0b1622;border-radius:16px;overflow:hidden;box-shadow:var(--shadow-lg);border:1px solid #1d2c3d}}
.term-bar{{display:flex;align-items:center;gap:8px;padding:12px 16px;background:#10202f;border-bottom:1px solid #1d2c3d}}
.term-bar .d{{width:11px;height:11px;border-radius:50%}}.term-bar .title{{margin-left:10px;color:#8fa3b6;font-size:13px;font-weight:600}}
.term-body{{padding:20px;min-height:300px;max-height:440px;overflow-y:auto;font-size:14.5px}}
.msg{{margin-bottom:16px;max-width:85%}}.msg.u{{margin-left:auto}}
.bub{{padding:13px 16px;border-radius:14px;line-height:1.5}}.msg.u .bub{{background:var(--accent);color:#fff;border-bottom-right-radius:4px}}
.msg.a .bub{{background:#16273a;color:#d7e3ef;border-bottom-left-radius:4px}}
.bub .res{{margin-top:12px;background:#0f1d2c;border:1px solid #20354a;border-radius:10px;padding:12px}}
.bub .res .r{{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #1b2c3e;font-size:13px}}
.term-input{{display:flex;gap:10px;padding:14px;border-top:1px solid #1d2c3d;background:#10202f}}
.term-input input{{flex:1;background:#0b1622;border:1px solid #24384d;border-radius:10px;color:#fff;padding:12px 14px;font-family:inherit;font-size:14px;outline:none}}
.term-sugg{{display:flex;gap:8px;flex-wrap:wrap;padding:0 14px 14px;background:#10202f}}
.term-sugg .s{{font-size:12.5px;color:#9fb6cb;border:1px solid #24384d;border-radius:999px;padding:6px 11px;cursor:pointer}}
footer{{background:var(--ink);color:#9fb0c2;padding:46px 0 40px;margin-top:20px}}
.cta-band{{background:linear-gradient(120deg,var(--accent),#15806a);color:#fff;border-radius:22px;padding:46px;text-align:center;margin:30px 0}}
#toast{{position:fixed;bottom:26px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--ink);color:#fff;padding:13px 20px;border-radius:11px;font-size:14px;opacity:0;transition:.25s;z-index:100;pointer-events:none}}
.stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:28px}}
.stat-grid .card{{text-align:center;padding:18px}}.stat-grid b{{display:block;font-size:28px;color:var(--accent-d)}}
@media(max-width:720px){{.stat-grid{{grid-template-columns:repeat(2,1fr)}}}}
.sess-shell{{background:#ECEEE8;min-height:100vh;padding-bottom:70px}}
.sess-bar{{background:var(--ink);color:#fff}}
.sess-bar .wrap{{display:flex;align-items:center;gap:14px;height:56px}}
.sess-id{{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;background:rgba(255,255,255,.08);color:#9fd4c4;padding:3px 10px;border-radius:6px}}
.sess-grid{{display:grid;grid-template-columns:225px 1fr;gap:26px;padding-top:26px;align-items:start}}
.sess-help{{background:var(--gold-bg);border:1px solid #ecd9a8;border-radius:12px;padding:12px 14px;margin-top:14px;color:#8a6414}}
.sess-panel{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:var(--shadow);margin-bottom:22px}}
.sess-kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:16px}}
.sess-kpi{{border:1px solid var(--line);border-radius:10px;padding:10px 14px;background:#fff}}
.ws-side-head{{font-weight:800;letter-spacing:.08em;color:var(--muted);margin:2px 2px 8px;font-size:11px}}
.ws-addr{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:8px;cursor:pointer;display:flex;flex-direction:column;gap:3px}}
.ws-addr.on{{border-color:var(--accent);box-shadow:0 0 0 2px rgba(31,157,118,.18);background:#f4faf7}}
.ws-x{{align-self:flex-end;color:var(--muted);font-size:11px;cursor:pointer}}
.ws-add{{display:flex;gap:6px;margin:4px 0 10px}}
.ws-add input{{flex:1;min-width:0;border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:12.5px;font-family:inherit}}
.ws-loan-on{{border-color:var(--accent)!important;box-shadow:0 0 0 2px rgba(31,157,118,.22)}}
@media(max-width:880px){{.sess-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<header class="nav"><div class="wrap nav-row">
  <div class="logo" onclick="go('home')"><span class="dot"></span>Lenni<span>Borrower</span></div>
  <nav class="nav-links" id="navlinks">
    <a data-v="home" onclick="go('home')">Home</a>
    <a data-v="loans" onclick="go('loans')">Loan Types</a>
    <a data-v="banks" onclick="go('banks')">Find Banks</a>
    <a data-v="terminal" onclick="go('terminal')">AI Terminal</a>
  </nav>
  <div class="nav-right">
    <div class="loc">📍 <select id="locSel" onchange="setLoc(this.value)"></select></div>
    <button class="btn btn-dark btn-sm" onclick="go('banks')">Find banks</button>
  </div>
</div></header>

<div id="home" class="view active">
  <section class="hero"><div class="wrap">
    <div class="eyebrow">Texas Community Banks · Live FFIEC Data</div>
    <h1 class="serif">The prepared borrower gets <em>the best deal.</em></h1>
    <p class="sub">Build your package once. Take it to the banks that actually do your loan. {data['bankCount']} Texas banks ranked by their real loan portfolios, from public FDIC data. No signup required.</p>
    <div class="searchbar" style="max-width:720px;margin-bottom:12px">
      <span class="ai">AI</span>
      <input id="heroPaste" placeholder="Paste a listing link — Zillow, LoopNet, Crexi — or describe your deal" onkeydown="if(event.key==='Enter')heroAsk()"/>
      <button class="btn btn-primary btn-sm" onclick="heroAsk()">Match my deal →</button>
    </div>
    <p class="tiny muted" style="margin:0 0 26px">Lenni reads the listing, builds your listing profile, and suggests the loan products that fit — then the Texas banks that actually do that loan.</p>
    <div class="hero-cta">
      <button class="btn btn-ghost" onclick="go('loans')">Browse loan types →</button>
      <button class="btn btn-ghost" onclick="go('banks')">See all banks</button>
    </div>
    <div class="trust">
      <div><b>{data['bankCount']}</b> banks with portfolio data</div>
      <div><b>{data['cityCount']}</b> Texas cities</div>
      <div><b>FFIEC</b> Call Report · {data['period']}</div>
    </div>
    <div class="stat-grid">
      <div class="card"><b>{data['icpCount']}</b><span class="muted tiny">Community banks $500M–$2B</span></div>
      <div class="card"><b id="statMf">—</b><span class="muted tiny">Multifamily specialists (10%+)</span></div>
      <div class="card"><b id="statCre">—</b><span class="muted tiny">CRE-heavy lenders (40%+ CRE)</span></div>
      <div class="card"><b id="statCi">—</b><span class="muted tiny">Business lending focus (15%+ C&I)</span></div>
    </div>
  </div></section>

  <section class="sec alt"><div class="wrap">
    <div class="sec-head"><div class="eyebrow">Why this matters</div><h2 class="serif">Regulatory data, translated for borrowers.</h2>
    <p>Every bank files a quarterly Call Report with the FFIEC. We read those filings and show which lenders actually put dollars into your loan category — not who has the best marketing site.</p></div>
    <div class="grid g4">
      <div class="card feat"><div class="ic">🎯</div><h3>Real specialization</h3><p>Portfolio mix from Schedule RC-C — how much of each bank's book is in your loan type.</p></div>
      <div class="card feat"><div class="ic">📍</div><h3>Texas-wide</h3><p>{data['cityCount']} cities from Amarillo to Brownsville. Filter by metro or search by name.</p></div>
      <div class="card feat"><div class="ic">📊</div><h3>Full profiles</h3><p>Assets, loan book size, CRE/C&I/consumer mix, and community bank sizing for each lender.</p></div>
      <div class="card feat"><div class="ic">🤝</div><h3>Prepared conversations</h3><p>Walk in knowing the bank's lending focus before you ask for an intro.</p></div>
    </div>
  </div></section>

  <section class="sec"><div class="wrap">
    <div class="sec-head"><div class="eyebrow">How it works</div><h2 class="serif">Three steps to a smarter bank search.</h2></div>
    <div class="steps">
      <div class="step"><div class="n">01</div><h3>Pick your loan type</h3><p>Multifamily, investor CRE, owner-occupied, construction, or business lending.</p></div>
      <div class="step"><div class="n">02</div><h3>See who specializes</h3><p>Banks ranked by portfolio share in that category — filtered to your Texas market.</p></div>
      <div class="step"><div class="n">03</div><h3>Open a bank profile</h3><p>Full loan mix breakdown, assets, and market — sourced from FFIEC filings.</p></div>
    </div>
  </div></section>

  <section class="sec"><div class="wrap"><div class="cta-band">
    <h2 class="serif">Start with your loan type or search all {data['bankCount']} banks.</h2>
    <p>Data as of FFIEC reporting period {data['period']}. Updated when new quarters are synced.</p>
    <button class="btn btn-primary" onclick="go('loans')">Browse loan types →</button>
  </div></div></section>
</div>

<div id="loans" class="view">
  <section class="sec"><div class="wrap">
    <div class="sec-head"><div class="eyebrow">Loan products</div><h2 class="serif">What kind of deal are you financing?</h2>
    <p>Describe your deal in plain English or browse by category. We map it to FFIEC Call Report loan lines.</p></div>
    <div class="searchbar"><span class="ai">AI</span>
      <input id="loanSearch" placeholder="e.g. refinance a 40-unit apartment building in Dallas" onkeydown="if(event.key==='Enter')aiRoute()"/>
      <button class="btn btn-primary btn-sm" onclick="aiRoute()">Match me →</button>
    </div>
    <div class="chips" id="loanChips"></div>
    <div class="grid g3" id="loanGrid" style="margin-top:30px"></div>
  </div></section>
</div>

<div id="product" class="view">
  <div class="dhead"><div class="wrap">
    <div class="back" onclick="go('loans')">← All loan types</div>
    <div class="row" style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:20px">
      <div><div class="lc-cat" id="pCat"></div><h1 class="serif" id="pName"></h1><div class="meta" id="pSub"></div></div>
      <button class="btn btn-primary" onclick="document.getElementById('pBanks').scrollIntoView({{behavior:'smooth'}})">See specializing banks →</button>
    </div>
  </div></div>
  <section class="sec"><div class="wrap">
    <div class="tabs">
      <div class="tab active" onclick="ptab(this,'tCalc')">Calculator</div>
      <div class="tab" onclick="ptab(this,'tLearn')">Learn</div>
      <div class="tab" onclick="ptab(this,'tData')">Data source</div>
    </div>
    <div class="tabpane active" id="tCalc"><div class="calc">
      <div>
        <h3 class="serif" style="font-size:20px;margin-bottom:18px">Estimate your loan</h3>
        <div class="calc-field"><label style="font-size:13px;font-weight:600;display:flex;justify-content:space-between;margin-bottom:8px">Property value <b id="vVal">$4,000,000</b></label><input type="range" id="cVal" min="500000" max="20000000" step="100000" value="4000000" oninput="calc()"></div>
        <div class="calc-field"><label style="font-size:13px;font-weight:600;display:flex;justify-content:space-between;margin-bottom:8px">LTV <b id="vLtv">70%</b></label><input type="range" id="cLtv" min="50" max="80" step="1" value="70" oninput="calc()"></div>
        <div class="calc-field"><label style="font-size:13px;font-weight:600;display:flex;justify-content:space-between;margin-bottom:8px">Rate <b id="vRate">7.25%</b></label><input type="range" id="cRate" min="5" max="11" step="0.05" value="7.25" oninput="calc()"></div>
        <div class="calc-field"><label style="font-size:13px;font-weight:600;display:flex;justify-content:space-between;margin-bottom:8px">Amortization <b id="vAmort">25 yrs</b></label><input type="range" id="cAmort" min="10" max="30" step="1" value="25" oninput="calc()"></div>
      </div>
      <div class="calc-out">
        <div style="color:#9fb0c2;font-size:13px;text-transform:uppercase;letter-spacing:.06em">Est. monthly payment</div>
        <div class="big" id="oPay">$0</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:22px;border-top:1px solid rgba(255,255,255,.14);padding-top:18px">
          <div><span style="color:#9fb0c2;font-size:12px">Loan amount</span><b id="oLoan" style="display:block;font-size:20px">$0</b></div>
          <div><span style="color:#9fb0c2;font-size:12px">Down payment</span><b id="oDown" style="display:block;font-size:20px">$0</b></div>
        </div>
        <p class="tiny" style="color:#9fb0c2;margin-top:18px">Illustrative only. Use bank profiles to find lenders that specialize in this category.</p>
      </div>
    </div></div>
    <div class="tabpane" id="tLearn"><div style="max-width:70ch"><h3 class="serif" style="font-size:22px;margin-bottom:12px">About this loan type</h3><p class="muted" id="pLearn" style="font-size:16px"></p>
    <p id="pStaticLink" style="margin-top:16px"></p><div id="pSubtypes" style="margin-top:12px;display:flex;flex-wrap:wrap;gap:8px"></div>
    <div class="grid g3" style="margin-top:24px">
      <div class="card"><h3 style="font-size:15px">FFIEC line items</h3><p class="muted" id="pLines" style="margin-top:6px;font-size:13px"></p></div>
      <div class="card"><h3 style="font-size:15px">Texas banks active</h3><p class="muted" id="pCount" style="margin-top:6px"></p></div>
      <div class="card"><h3 style="font-size:15px">Top specialist near you</h3><p class="muted" id="pTop" style="margin-top:6px"></p></div>
    </div></div></div>
    <div class="tabpane" id="tData"><div class="placeholder"><b>Source:</b> FFIEC Central Data Repository Call Report XBRL, Texas banks only, period {data['period']}. Portfolio % = bank's reported loan balance in this category ÷ total loans (RCON2122). MDRM codes mapped via Federal Reserve dictionary.</div></div>
    <div id="pBanks" style="margin-top:46px">
      <div class="sec-head"><h2 class="serif" style="font-size:28px">Texas banks specializing in this loan type</h2>
      <p>Ranked by portfolio share — <b id="pLocLabel"></b>. Higher % = more of the bank's book is in this category.</p></div>
      <div class="rank" id="pRank"></div>
      <p class="tiny muted" style="margin-top:14px">Showing top 25 of {data['bankCount']} Texas banks. Click any row for full profile. <span class="pill icp-badge" style="display:inline-flex">Community $500M–$2B</span> = Lenni core segment.</p>
    </div>
  </div></section>
</div>

<div id="banks" class="view">
  <section class="sec"><div class="wrap">
    <div class="sec-head"><div class="eyebrow">Find banks</div><h2 class="serif">Search {data['bankCount']} Texas lenders.</h2>
    <p>Filter by market, loan type, or name. Every profile is built from real Call Report data.</p></div>
    <div class="filters">
      <div><label>Market</label><select id="fMetro" onchange="renderBanks()"><option value="">All Texas</option></select></div>
      <div><label>Specializes in</label><select id="fLoan" onchange="renderBanks()"><option value="">Any loan type</option></select></div>
      <div><label>Community bank ($500M–$2B)</label><select id="fIcp" onchange="renderBanks()"><option value="">All sizes</option><option value="icp">ICP only ({data['icpCount']})</option></select></div>
      <div><label>Search name</label><input id="fSearch" placeholder="Bank name…" oninput="renderBanks()"/></div>
      <div><label>Sort by</label><select id="fSort" onchange="renderBanks()"><option value="assets">Total assets</option><option value="loans">Loan portfolio</option><option value="spec">Specialization</option></select></div>
      <div class="count" id="bankCount"></div>
    </div>
    <div class="grid g2" id="bankGrid"></div>
  </div></section>
</div>

<div id="bank" class="view">
  <div class="dhead"><div class="wrap">
    <div class="back" onclick="go('banks')">← All banks</div>
    <div class="row" style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:20px">
      <div><h1 class="serif" id="bName"></h1><div class="meta" id="bMeta"></div><div style="margin-top:12px" id="bBadge"></div></div>
      <button class="btn btn-primary" id="bIntro">Talk to a lender →</button>
    </div>
  </div></div>
  <section class="sec"><div class="wrap" style="max-width:840px">
    <div class="bank-stats" style="margin-bottom:24px">
      <div class="s"><b id="bAssets"></b><span>Total assets</span></div>
      <div class="s"><b id="bLoans"></b><span>Gross loans</span></div>
      <div class="s"><b id="bLta"></b><span>Loans / assets</span></div>
      <div class="s"><b id="bCre"></b><span>CRE share</span></div>
      <div class="s"><b id="bCi"></b><span>C&I share</span></div>
    </div>
    <div class="acc open"><div class="acc-head" onclick="this.parentNode.classList.toggle('open')"><h3><span style="width:30px;height:30px;border-radius:8px;background:var(--soft);display:inline-flex;align-items:center;justify-content:center">🏦</span> About this bank</h3><span>▾</span></div>
      <div class="acc-body"><p class="muted" id="bDesc" style="font-size:15px;margin-top:14px"></p>
      <p class="tiny muted" style="margin-top:12px">RSSD ID: <span id="bRssd"></span> · Data period: {data['period']}</p></div></div>
    <div class="acc open"><div class="acc-head" onclick="this.parentNode.classList.toggle('open')"><h3><span style="width:30px;height:30px;border-radius:8px;background:var(--soft);display:inline-flex;align-items:center;justify-content:center">📊</span> Loan portfolio mix <span class="pill live-badge" style="margin-left:6px">FFIEC Call Report</span></h3><span>▾</span></div>
      <div class="acc-body"><p class="muted" style="font-size:14px;margin:14px 0 18px">Each bar shows what share of this bank's total loans fall in that category (from Schedule RC-C / RC).</p><div class="mix" id="bMix"></div></div></div>
    <div class="acc"><div class="acc-head" onclick="this.parentNode.classList.toggle('open')"><h3><span style="width:30px;height:30px;border-radius:8px;background:var(--soft);display:inline-flex;align-items:center;justify-content:center">📍</span> Market</h3><span>▾</span></div>
      <div class="acc-body"><p class="muted" id="bMarket" style="font-size:15px;margin-top:14px"></p></div></div>
    <div class="acc"><div class="acc-head" onclick="this.parentNode.classList.toggle('open')"><h3><span style="width:30px;height:30px;border-radius:8px;background:var(--soft);display:inline-flex;align-items:center;justify-content:center">ℹ️</span> What this data does not include</h3><span>▾</span></div>
      <div class="acc-body"><div class="placeholder">Branch locations, website URLs, online application links, rates, and lender contact info are <b>not</b> in FFIEC Call Reports. Those fields will be added in the Texas Community Bank Index enrichment layer.</div></div></div>
  </div></section>
</div>

<div id="terminal" class="view">
  <section class="sec"><div class="wrap" style="max-width:780px">
    <div class="sec-head center" style="margin:0 auto 28px"><div class="eyebrow">Lenni AI Terminal</div><h2 class="serif">Describe your deal. Get matched to real banks.</h2>
    <p>Plain-English search across {data['bankCount']} Texas banks with live FFIEC portfolio data.</p></div>
    <div class="term">
      <div class="term-bar"><span class="d" style="background:#ff5f57"></span><span class="d" style="background:#febc2e"></span><span class="d" style="background:#28c840"></span><span class="title">Lenni · {data['bankCount']} TX banks</span></div>
      <div class="term-body" id="termBody"><div class="msg a"><div class="bub">👋 Tell me your deal — property type, rough amount, and city. I'll rank Texas banks by how much of their portfolio matches your loan type.</div></div></div>
      <div class="term-sugg" id="termSugg"></div>
      <div class="term-input"><input id="termIn" placeholder="Type your deal…" onkeydown="if(event.key==='Enter'){{termAsk(this.value);this.value=''}}"><button class="btn btn-primary btn-sm" onclick="var i=document.getElementById('termIn');termAsk(i.value);i.value=''">Send</button></div>
    </div>
  </div></section>
</div>

<div id="session" class="view">
  <div class="sess-shell">
    <div class="sess-bar"><div class="wrap">
      <div class="logo" style="color:#fff" onclick="go('home')"><span class="dot"></span>Lenni</div>
      <span style="font-size:13px;color:#9fb0c2;font-weight:600">Borrower workspace</span>
      <span class="sess-id" id="sId">SESSION —</span>
    </div></div>
    <div class="wrap sess-grid">
      <aside class="ws-side">
        <div id="wsSide"></div>
        <div class="ws-add">
          <input id="wsPaste" placeholder="Paste another listing link…" onkeydown="if(event.key==='Enter')wsAdd()"/>
          <button class="btn btn-primary btn-sm" onclick="wsAdd()">+ Add</button>
        </div>
        <div class="sess-help tiny">Each address gets its own workspace — land info, loan info, and your info.</div>
        <div style="margin-top:14px"><a class="btn btn-ghost btn-sm" onclick="go('home')">← Exit to home</a></div>
      </aside>
      <main id="wsMain"><div class="sess-panel"><p class="muted">Paste a listing to start…</p></div></main>
    </div>
  </div>
</div>

<footer><div class="wrap">
  <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:30px">
    <div style="max-width:300px"><div class="logo" style="color:#fff"><span class="dot"></span>Lenni<span style="color:#6f879c">Borrower</span></div>
    <p style="font-size:13.5px;margin-top:12px">Texas community bank finder powered by FFIEC Call Report data. {data['bankCount']} banks · period {data['period']}.</p></div>
    <div><h4 style="color:#fff;font-size:14px;margin-bottom:12px">Explore</h4>
      <a onclick="go('loans')" style="display:block;font-size:13.5px;padding:4px 0;cursor:pointer">Loan types</a>
      <a onclick="go('banks')" style="display:block;font-size:13.5px;padding:4px 0;cursor:pointer">All banks</a>
      <a onclick="go('terminal')" style="display:block;font-size:13.5px;padding:4px 0;cursor:pointer">AI terminal</a></div>
  </div>
  <div style="border-top:1px solid #21354a;margin-top:30px;padding-top:20px;font-size:12px;color:#6f879c">Live FFIEC public data · Not financial advice · © 2026 Lenni</div>
</div></footer>

<div id="toast"></div>

<script>
var DATA = {payload};
var BANKS = DATA.banks;
var LOC = DATA.metros[0] || 'Dallas–Fort Worth';

var PRODUCTS = {products_js};

var MIXMETA=[['mf','Multifamily','var(--mf)'],['inv','Investor CRE','var(--inv)'],['own','Owner-occupied CRE','var(--own)'],
 ['con','Construction','var(--con)'],['ci','C&I / Business','var(--ci)'],['res','1–4 Residential','var(--res)'],
 ['cons','Consumer','var(--cons)'],['farm','Farmland','var(--farm)'],['ag','Ag production','var(--ag)'],
 ['lease','Lease financing','var(--lease)'],['uncat','Unclassified','var(--uncat)']];

function mixScore(b,key){{
  if(key==='oth') return (b.mix.farm||0)+(b.mix.ag||0);
  return b.mix[key]||0;
}}

function go(v){{
  document.querySelectorAll('.view').forEach(function(e){{e.classList.remove('active')}});
  document.getElementById(v).classList.add('active');
  document.querySelectorAll('#navlinks a').forEach(function(a){{a.classList.toggle('active',a.dataset.v===v)}});
  window.scrollTo(0,0);
}}
function setLoc(v){{LOC=v;renderLoans();if(CUR)renderRank();}}
function assetStr(a){{return a>=1000?'$'+(a/1000).toFixed(1)+'B':'$'+a+'M'}}
function lenderCount(key){{return BANKS.filter(function(b){{return mixScore(b,key)>=8}}).length}}
function banksNear(metro){{return BANKS.filter(function(b){{return !metro||b.markets.indexOf(metro)>-1||b.metro===metro}})}}
function topBank(key,metro){{
  var list=banksNear(metro).slice().sort(function(a,b){{return mixScore(b,key)-mixScore(a,key)}});
  return list[0]||BANKS[0];
}}
function icpPill(b){{return b.icp?'<span class="pill icp-badge">Community $500M–$2B</span>':''}}

function initLoc(){{
  var s=document.getElementById('locSel');
  DATA.metros.forEach(function(m){{var o=document.createElement('option');o.value=m;o.textContent=m;s.appendChild(o)}});
  s.value=LOC;
  var fm=document.getElementById('fMetro');
  DATA.metros.forEach(function(m){{var o=document.createElement('option');o.value=m;o.textContent=m;fm.appendChild(o)}});
}}

function initStats(){{
  document.getElementById('statMf').textContent=BANKS.filter(function(b){{return b.mix.mf>=10}}).length;
  document.getElementById('statCre').textContent=BANKS.filter(function(b){{return b.crePct>=40}}).length;
  document.getElementById('statCi').textContent=BANKS.filter(function(b){{return b.ciPct>=15}}).length;
}}

function renderLoans(){{
  var g=document.getElementById('loanGrid');g.innerHTML='';
  PRODUCTS.forEach(function(p){{
    var tb=topBank(p.key,LOC);
    var cnt=lenderCount(p.key);
    var subN=(p.subtypes&&p.subtypes.length)?p.subtypes.length:0;
    g.innerHTML+='<div class="card click lc" onclick="openProduct(\\''+p.slug+'\\')">'+
      '<div class="lc-cat">'+p.cat+'</div><h3 class="serif">'+p.name+'</h3><p>'+p.short+'</p>'+
      '<div class="lc-meta"><span class="muted"><b style="color:var(--ink)">'+cnt+'</b> banks (8%+ share)</span>'+
      '<span style="font-weight:600">'+tb.name.split(' ').slice(0,3).join(' ')+'</span></div>'+
      '<div class="tiny muted" style="margin-top:8px">Top near '+LOC+': '+mixScore(tb,p.key)+'% portfolio'+
      (subN?' · '+subN+' sub-types':'')+'</div>'+
      (p.pageUrl?'<div class="tiny" style="margin-top:6px"><a href="'+p.pageUrl+'" onclick="event.stopPropagation()">Full guide →</a></div>':'')+
      '</div>';
  }});
  var chips=document.getElementById('loanChips');
  chips.innerHTML=['apartment bridge Dallas','owner-occupied warehouse Houston','retail investor San Antonio','ground up construction Austin','business line of credit Waco']
    .map(function(t){{return '<span class="chip" onclick="document.getElementById(\\'loanSearch\\').value=\\''+t+'\\';aiRoute()">'+t+'</span>'}}).join('');
}}

var CUR=null;
function openProduct(slug){{
  CUR=PRODUCTS.find(function(p){{return p.slug===slug}});
  document.getElementById('pCat').textContent=CUR.cat;
  document.getElementById('pName').textContent=CUR.name;
  document.getElementById('pSub').textContent=CUR.short;
  document.getElementById('pLearn').textContent=CUR.learn;
  document.getElementById('pLines').textContent=CUR.lines;
  document.getElementById('pCount').textContent=lenderCount(CUR.key)+' Texas banks have 8%+ of loans in this category';
  var tb=topBank(CUR.key,LOC);
  document.getElementById('pTop').textContent=tb.name+' ('+mixScore(tb,CUR.key)+'% near '+LOC+')';
  var sl=document.getElementById('pStaticLink');
  if(CUR.pageUrl){{sl.innerHTML='<a href="'+CUR.pageUrl+'" class="btn btn-ghost btn-sm">Full guide page →</a>';}}else{{sl.innerHTML='';}}
  var stdiv=document.getElementById('pSubtypes');
  if(CUR.subtypes&&CUR.subtypes.length){{
    stdiv.innerHTML=CUR.subtypes.map(function(s){{
      return '<a href="'+s.pageUrl+'" class="chip" style="text-decoration:none;font-size:12px">'+s.title+'</a>';
    }}).join('');
  }}else{{stdiv.innerHTML='';}}
  document.querySelectorAll('#product .tab').forEach(function(t,i){{t.classList.toggle('active',i===0)}});
  document.querySelectorAll('#product .tabpane').forEach(function(p){{p.classList.remove('active')}});
  document.getElementById('tCalc').classList.add('active');
  calc();renderRank();go('product');
}}

function renderRank(){{
  document.getElementById('pLocLabel').textContent='filtered to '+LOC+' when possible';
  var list=banksNear(LOC).slice().sort(function(a,b){{return mixScore(b,CUR.key)-mixScore(a,CUR.key)}}).slice(0,25);
  if(list.length<5) list=BANKS.slice().sort(function(a,b){{return mixScore(b,CUR.key)-mixScore(a,CUR.key)}}).slice(0,25);
  var max=mixScore(list[0],CUR.key)||1;
  var r=document.getElementById('pRank');r.innerHTML='';
  list.forEach(function(b,i){{
    var cap=Math.round(b.loans*mixScore(b,CUR.key)/100);
    r.innerHTML+='<div class="rank-row" onclick="openBank('+b.id+')">'+
      '<div class="pos">'+(i+1)+'</div>'+
      '<div class="nm">'+b.name+' '+icpPill(b)+'<small>'+b.city+' · '+b.metro+' · '+assetStr(b.assets)+'</small></div>'+
      '<div class="rank-pct"><div class="t"><div class="f" style="width:'+(mixScore(b,CUR.key)/max*100)+'%"></div></div><b>'+mixScore(b,CUR.key)+'%</b></div>'+
      '<div class="cap tiny muted" style="text-align:right">~'+assetStr(cap)+'<br>est. in category</div></div>';
  }});
}}

function ptab(el,id){{
  el.parentNode.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('active')}});el.classList.add('active');
  document.querySelectorAll('#product .tabpane').forEach(function(p){{p.classList.remove('active')}});
  document.getElementById(id).classList.add('active');
}}

function calc(){{
  var val=+document.getElementById('cVal').value,ltv=+document.getElementById('cLtv').value,rate=+document.getElementById('cRate').value,amort=+document.getElementById('cAmort').value;
  document.getElementById('vVal').textContent='$'+val.toLocaleString();
  document.getElementById('vLtv').textContent=ltv+'%';
  document.getElementById('vRate').textContent=rate.toFixed(2)+'%';
  document.getElementById('vAmort').textContent=amort+' yrs';
  var loan=val*ltv/100,down=val-loan,r=rate/100/12,n=amort*12;
  var pay=r>0?loan*r/(1-Math.pow(1+r,-n)):loan/n;
  document.getElementById('oPay').textContent='$'+Math.round(pay).toLocaleString();
  document.getElementById('oLoan').textContent='$'+Math.round(loan).toLocaleString();
  document.getElementById('oDown').textContent='$'+Math.round(down).toLocaleString();
}}

function fillLoanFilter(){{
  PRODUCTS.forEach(function(p){{var o=document.createElement('option');o.value=p.key;o.textContent=p.name;document.getElementById('fLoan').appendChild(o)}});
}}

function renderBanks(){{
  var metro=document.getElementById('fMetro').value,key=document.getElementById('fLoan').value,
      icp=document.getElementById('fIcp').value,sort=document.getElementById('fSort').value,
      q=document.getElementById('fSearch').value.toLowerCase();
  var list=BANKS.filter(function(b){{
    if(metro&&b.metro!==metro&&b.markets.indexOf(metro)<0) return false;
    if(icp==='icp'&&!b.icp) return false;
    if(q&&b.name.toLowerCase().indexOf(q)<0&&b.city.toLowerCase().indexOf(q)<0) return false;
    return true;
  }});
  if(sort==='assets') list.sort(function(a,b){{return b.assets-a.assets}});
  if(sort==='loans') list.sort(function(a,b){{return b.loans-a.loans}});
  if(sort==='spec'&&key) list.sort(function(a,b){{return mixScore(b,key)-mixScore(a,key)}});
  document.getElementById('bankCount').textContent=list.length+' banks';
  var g=document.getElementById('bankGrid');g.innerHTML='';
  list.slice(0,60).forEach(function(b){{
    var specs=MIXMETA.slice().sort(function(x,y){{return b.mix[y[0]]-b.mix[x[0]]}}).slice(0,3);
    g.innerHTML+='<div class="card click bank-card" onclick="openBank('+b.id+')">'+
      '<h3 class="serif">'+b.name+' '+icpPill(b)+'</h3>'+
      '<div class="tiny muted">'+b.city+' · '+b.metro+'</div>'+
      '<div class="bank-stats">'+
      '<div class="s"><b>'+assetStr(b.assets)+'</b><span>Assets</span></div>'+
      '<div class="s"><b>'+assetStr(b.loans)+'</b><span>Loans</span></div>'+
      (key?'<div class="s"><b style="color:var(--accent-d)">'+mixScore(b,key)+'%</b><span>in type</span></div>':'')+
      '</div><div class="spec-tags">'+specs.map(function(m){{return '<span class="t">'+m[1]+' '+b.mix[m[0]]+'%</span>'}}).join('')+'</div></div>';
  }});
  if(list.length>60) g.innerHTML+='<p class="muted center tiny">Showing top 60 of '+list.length+' — narrow filters to see more.</p>';
}}

function openBank(id){{
  var b=BANKS.find(function(x){{return x.id===id}});
  document.getElementById('bName').textContent=b.name;
  document.getElementById('bMeta').textContent=b.city+', Texas · '+b.metro+' · RSSD '+b.id;
  document.getElementById('bBadge').innerHTML=b.icp?'<span class="pill icp-badge">Community bank · $500M–$2B (Lenni core segment)</span>':'<span class="pill">Outside $500M–$2B size band</span>';
  document.getElementById('bAssets').textContent=assetStr(b.assets);
  document.getElementById('bLoans').textContent=assetStr(b.loans);
  document.getElementById('bLta').textContent=b.loanToAsset+'%';
  document.getElementById('bCre').textContent=b.crePct+'%';
  document.getElementById('bCi').textContent=b.ciPct+'%';
  document.getElementById('bDesc').textContent=b.desc;
  document.getElementById('bRssd').textContent=b.id;
  document.getElementById('bMarket').textContent='Headquartered in '+b.city+', Texas. Primary market: '+b.metro+'. FFIEC panel city is HQ — branch footprint may extend beyond this city.';
  document.getElementById('bIntro').onclick=function(){{toast('Connect via Lenni Convey when live — bank: '+b.name)}};
  var max=Math.max.apply(null,MIXMETA.map(function(m){{return b.mix[m[0]]||0}}));
  var hlKey=CUR?CUR.key:null;
  if(hlKey==='oth') hlKey=null;
  var mix=document.getElementById('bMix');mix.innerHTML='';
  MIXMETA.forEach(function(m){{
    var v=b.mix[m[0]]||0;
    var z=v<1?' zero':'';
    mix.innerHTML+='<div class="bar-row'+z+(m[0]===hlKey?' hl':'')+'"><div class="lbl">'+m[1]+'</div>'+
      '<div class="bar-track"><div class="bar-fill" style="width:'+(v>0?Math.max(v/max*100,2):0)+'%;background:'+m[2]+'"></div></div>'+
      '<div style="text-align:right;font-weight:700">'+v+'%</div></div>';
  }});
  go('bank');
}}

function aiRoute(){{
  var q=document.getElementById('loanSearch').value;
  if(!q.trim()){{go('loans');return}}
  if(typeof LenniWS!=='undefined'){{LenniWS.startSession(q);return}}
  var subHit=null, hit='mf';
  PRODUCTS.forEach(function(p){{
    (p.subtypes||[]).forEach(function(s){{
      (s.keywords||[]).forEach(function(kw){{
        if(kw&&q.indexOf(kw.toLowerCase())>-1){{subHit=s;hit=p.key;}}
      }});
    }});
  }});
  if(!subHit){{
    if(/owner|operate|occupied|my business|warehouse/.test(q)) hit='own';
    else if(/construction|ground|build|develop/.test(q)) hit='con';
    else if(/retail|office|industrial|strip|investor|tenant|income/.test(q)) hit='inv';
    else if(/working capital|equipment|line of credit|business|sba|ci/.test(q)) hit='ci';
    else if(/farmland|ag |ranch|farm/.test(q)) hit='oth';
    else if(/single family|1-4|home loan|residential(?! construction)/.test(q)) hit='res';
  }}
  ['Dallas','Houston','Austin','San Antonio','Fort Worth','Midland','Waco','Amarillo','Lubbock','Corpus Christi'].forEach(function(m){{
    if(q.indexOf(m.toLowerCase())>-1){{var sel=document.getElementById('locSel');for(var i=0;i<sel.options.length;i++) if(sel.options[i].text.indexOf(m)>-1||sel.options[i].value.indexOf(m)>-1){{LOC=sel.options[i].value;sel.value=LOC}}}}
  }});
  if(subHit&&subHit.pageUrl){{window.location.href=subHit.pageUrl;return;}}
  openProduct(PRODUCTS.find(function(p){{return p.key===hit}}).slug);
  toast('Matched to: '+PRODUCTS.find(function(p){{return p.key===hit}}).name);
}}

function termAsk(t){{
  if(!t||!t.trim()) return;
  var body=document.getElementById('termBody');
  body.innerHTML+='<div class="msg u"><div class="bub">'+t.replace(/</g,'&lt;')+'</div></div>';
  body.scrollTop=body.scrollHeight;
  if(typeof LenniMatch!=='undefined'){{
    LenniMatch.matchDeal(t, LOC).then(function(match){{
      var p=match.listing_profile;
      var prod=match.primary_product;
      var rows=(match.recommended_banks||[]).slice(0,5).map(function(b){{
        return '<div class="r"><b>'+b.name+'</b><span style="color:var(--accent)">'+b.portfolio_pct+'%</span></div><div class="r"><span style="color:#8fa3b6">'+b.city+' · '+assetStr(b.assets_m)+'</span>'+(b.icp?'<span style="color:var(--gold)">Community bank</span>':'')+'</div>';
      }}).join('');
      var pname=prod?prod.title:(p.property_type||'Loan match');
      body.innerHTML+='<div class="msg a"><div class="bub">Mapped to <b>'+pname+'</b> in <b>'+(p.metro||LOC)+'</b>. '+(p.summary||'')+'<div class="res">'+rows+'</div><div style="margin-top:10px;font-size:12.5px;color:#8fa3b6"><button class="btn btn-primary btn-sm" onclick="LenniWS.startSession(\\''+t.replace(/'/g,"\\\\'")+'\\')">Open workspace →</button></div></div></div>';
      body.scrollTop=body.scrollHeight;
    }});
    return;
  }}
  var q=t.toLowerCase(),key='mf',metro=null;
  DATA.metros.forEach(function(m){{if(q.indexOf(m.toLowerCase().split(' ')[0])>-1) metro=m}});
  if(/owner|operate|occupied/.test(q)) key='own';
  else if(/construction|ground|build/.test(q)) key='con';
  else if(/retail|office|industrial|investor/.test(q)) key='inv';
  else if(/business|working capital|equipment|sba/.test(q)) key='ci';
  else if(/farm|ag |ranch/.test(q)) key='oth';
  else if(/home|1-4|residential/.test(q)) key='res';
  var pname=PRODUCTS.find(function(p){{return p.key===key}}).name;
  var list=banksNear(metro).sort(function(a,b){{return mixScore(b,key)-mixScore(a,key)}}).slice(0,5);
  if(!list.length) list=BANKS.slice().sort(function(a,b){{return mixScore(b,key)-mixScore(a,key)}}).slice(0,5);
  var rows=list.map(function(b){{
    return '<div class="r"><b>'+b.name+'</b><span style="color:var(--accent)">'+mixScore(b,key)+'%</span></div><div class="r"><span style="color:#8fa3b6">'+b.city+' · '+assetStr(b.assets)+'</span>'+(b.icp?'<span style="color:var(--gold)">Community bank</span>':'')+'</div>';
  }}).join('');
  setTimeout(function(){{
    body.innerHTML+='<div class="msg a"><div class="bub">Mapped to <b>'+pname+'</b>'+(metro?' in <b>'+metro+'</b>':'')+'. Top matches from FFIEC data:<div class="res">'+rows+'</div><div style="margin-top:10px;font-size:12.5px;color:#8fa3b6">Click a bank name in Find Banks for the full portfolio breakdown.</div></div></div>';
    body.scrollTop=body.scrollHeight;
  }},300);
  body.scrollTop=body.scrollHeight;
}}

var _t;
function toast(m){{var e=document.getElementById('toast');e.textContent=m;e.style.opacity=1;e.style.transform='translateX(-50%) translateY(0)';e.style.position='fixed';e.style.bottom='26px';e.style.left='50%';clearTimeout(_t);_t=setTimeout(function(){{e.style.opacity=0}},2400)}}

document.getElementById('termSugg').innerHTML=[
  '$3M apartment bridge loan in Dallas','Owner-occupied warehouse in Houston',
  'Investor retail center San Antonio','Ground-up construction Austin','Business line of credit Waco'
].map(function(s){{return '<span class="s" onclick="termAsk(\\''+s+'\\')">'+s+'</span>'}}).join('');

initLoc();initStats();renderLoans();fillLoanFilter();renderBanks();calc();
</script>
<script>window.LENNI_API_BASE = window.LENNI_API_BASE || "http://127.0.0.1:8000";</script>
<script src="js/match-client.js"></script>
<script src="js/workspace.js"></script>
</body>
</html>"""


if __name__ == "__main__":
    raise SystemExit(main())
