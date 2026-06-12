#!/usr/bin/env python3
"""
Generate a ~50-page comprehensive guide:
  - Every CSV in exports/ explained in detail
  - Every EDA analysis (1–25) explained in detail

  python build_comprehensive_eda_guide.py
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
ANALYSIS = ROOT / "analysis"
OUT_PDF = ANALYSIS / "Lenni_Texas_EDA_Comprehensive_Guide.pdf"

NAVY = "#203048"
CHARS_PER_PAGE = 2100


def load_stats() -> dict:
    """Load live numbers so the document reflects actual data."""
    latest = pd.read_csv(EXPORTS / "texas_bank_profiles_latest.csv", dtype={"id_rssd": int})
    master = pd.read_csv(EXPORTS / "texas_master_joined.csv", dtype={"id_rssd": int})
    lat = latest.dropna(subset=["total_assets"])
    icp = lat[lat["icp_fit"] == "ICP ($500M–$2B)"]
    q = master.groupby("reporting_period").agg(
        banks=("id_rssd", "nunique"),
        median_assets=("total_assets", "median"),
        median_loans=("total_loans_gross", "median"),
        icp_banks=("icp_fit", lambda s: (s == "ICP ($500M–$2B)").sum()),
    ).reset_index()
    q["period_sort"] = pd.to_datetime(q["reporting_period"])
    q = q.sort_values("period_sort")
    top_cities = lat.groupby("city")["id_rssd"].nunique().sort_values(ascending=False).head(5)
    low_consumer = lat[lat["consumer_to_loans"].fillna(1) < 0.15]
    stats = lat[["total_assets", "total_loans_gross", "ci_loans", "cre_proxy_total", "loan_to_asset_ratio"]].describe()
    return {
        "latest_period": latest["reporting_period"].iloc[0],
        "n_latest": len(latest),
        "n_with_assets": len(lat),
        "n_icp": len(icp),
        "pct_icp": 100 * len(icp) / len(lat),
        "median_assets_icp_m": icp["total_assets"].median() / 1e6,
        "median_loans_icp_m": icp["total_loans_gross"].median() / 1e6,
        "master_rows": len(master),
        "q_table": q.to_string(index=False),
        "top_cities": "\n".join(f"  • {c}: {n} banks" for c, n in top_cities.items()),
        "n_low_consumer": len(low_consumer),
        "pct_low_consumer": 100 * len(low_consumer) / len(lat),
        "stats_table": stats.round(2).to_string(),
        "asset_bands": pd.read_csv(ANALYSIS / "asset_band_counts.csv").to_string(index=False),
        "segments": pd.read_csv(ANALYSIS / "lenni_market_segments.csv").to_string(index=False),
    }


def split_pages(title: str, body: str) -> list[tuple[str, str]]:
    """Split long body into page-sized chunks."""
    pages: list[tuple[str, str]] = []
    current = ""
    for para in body.split("\n\n"):
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= CHARS_PER_PAGE:
            current = candidate
        else:
            if current:
                pages.append((title if not pages else f"{title} (continued)", current))
            if len(para) <= CHARS_PER_PAGE:
                current = para
            else:
                words = para.split()
                chunk = ""
                for w in words:
                    if len(chunk) + len(w) + 1 > CHARS_PER_PAGE:
                        pages.append((title if not pages else f"{title} (continued)", chunk))
                        chunk = w
                    else:
                        chunk = f"{chunk} {w}".strip()
                current = chunk
    if current:
        pages.append((title if not pages else f"{title} (continued)", current))
    return pages or [(title, body)]


def write_page(pdf: PdfPages, title: str, body: str) -> None:
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    wrapped = "\n".join(
        textwrap.fill(line, width=92) if line.strip() and not line.startswith("  ") else line
        for line in body.split("\n")
    )
    fig.text(0.06, 0.96, title, fontsize=12, fontweight="bold", va="top", color=NAVY)
    fig.text(0.06, 0.92, wrapped, fontsize=8.2, va="top", family="sans-serif", linespacing=1.35)
    fig.text(0.06, 0.04, "Lenni Texas FFIEC Data — Comprehensive Guide", fontsize=7, color="gray")
    plt.axis("off")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def add_section(pdf: PdfPages, title: str, body: str) -> int:
    n = 0
    for t, b in split_pages(title, body):
        write_page(pdf, t, b)
        n += 1
    return n


def build_sections(s: dict) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []

    sections.append((
        "Cover — Lenni Texas Community Bank Data: Comprehensive Guide",
        f"""Generated: {datetime.now().strftime('%B %d, %Y')}

Document purpose
This guide explains, in plain language, every CSV file in the ONLY_TEXAS_SINCE_2025/exports/ folder and every analysis (1 through 25) in the Lenni Texas Bank Exploratory Data Analysis (EDA). It is written for sales, research, and leadership teams at Lenni who need to understand what the FFIEC Call Report data shows about Texas community banks — without reading Python code or regulatory taxonomy manuals first.

Data scope
• Geography: Texas (State = TX) only
• Source: FFIEC Central Data Repository Public Web Service (Call Report XBRL)
• Periods: Five quarters from Q1 2025 through Q1 2026 (3/31/2025, 6/30/2025, 9/30/2025, 12/31/2025, 3/31/2026)
• Filings downloaded: 1,825 bank-quarter XBRL files (100% of Texas filers marked has_filed=True)
• Parsed facts: 2,186,590 rows in texas_xbrl_facts.csv
• Master joined table: 1,825 rows (one per bank per quarter)

Lenni context (from lenni_contenxt.txt)
Lenni (Convey by Lenni) sells a white-labeled borrower–lender hub to Texas community banks. Primary buyer: Chief Lending Officer (CLO). Ideal Customer Profile (ICP): banks with $500 million to $2 billion in total assets. Texas has roughly 360 community banks; Lenni's thesis is that most lack a human at the front of online loan inquiries. This dataset does NOT measure online application presence — it profiles balance sheets and loan portfolios so Lenni can prioritize CLO conversations by size, geography, and lending mix.

How to read this document
Part A (CSV files): what each export contains, column-by-column, with join keys and example use cases.
Part B (EDA analyses 1–25): the business question, methodology, actual results from your data, and Lenni sales implications.
Part C: synthesis, limitations, and how to regenerate outputs.

Latest-quarter snapshot ({s['latest_period']})
• Banks on latest panel: {s['n_latest']}
• Banks with total asset data: {s['n_with_assets']}
• Banks in Lenni ICP ($500M–$2B): {s['n_icp']} ({s['pct_icp']:.1f}% of banks with assets)
• Median ICP total assets: ${s['median_assets_icp_m']:.1f} million
• Median ICP gross loans: ${s['median_loans_icp_m']:.1f} million"""
    ))

    sections.append((
        "Part A — Overview of the exports/ folder",
        """The exports/ folder is the analytical layer built on top of raw XBRL filings in archive/call/. Files fall into three generations:

Generation 1 — Core FFIEC extract (from pull_texas_since_2025.py)
  texas_institutions.csv   Who must file each quarter (Panel of Reporters)
  texas_filings.csv        Manifest of downloaded XBRL files
  texas_xbrl_facts.csv     Every parsed line item from every filing

Generation 2 — MDRM-enriched loan views (from extract_texas_loans.py)
  texas_loans_summary.csv              Main loan category lines (~17 metrics per bank-quarter)
  texas_loans_labeled.csv              All Schedule RC-C / loan-related lines with Fed labels
  texas_loan_products_mdrm_catalog.csv Reference dictionary of MDRM codes

Generation 3 — Joined tables for Lenni EDA (from build_lenni_eda_report.py)
  texas_master_joined.csv         Wide table: institution + filing + metrics + derived ratios
  texas_bank_profiles_latest.csv  Latest quarter only (one row per bank)
  texas_loans_joined_long.csv     Long loan lines enriched with ICP flag and assets

Universal join keys
Every table can be linked with:
  id_rssd  — Federal Reserve RSSD identifier (stable bank ID, e.g. 917555)
  reporting_period — Quarter end date as MM/DD/YYYY (e.g. 3/31/2026)

Amount units
XBRL fact values in this pipeline are stored as parsed numeric USD amounts (value_num). On the Call Report, many line items are reported in thousands of dollars; the parser stores the number as filed. When comparing to public UBPR displays, confirm scaling. Ratios (loan_to_asset_ratio, cre_to_loans) are unitless and safe for cross-bank comparison.

Recommended reading order for new users
1. texas_institutions.csv — understand the universe
2. texas_bank_profiles_latest.csv — one row per bank for prospecting
3. texas_loans_summary.csv — loan mix without wide-table complexity
4. texas_master_joined.csv — full history and derived metrics
5. texas_xbrl_facts.csv — only when you need a line item not in summary

File sizes (approximate)
  texas_institutions.csv          ~0.1 MB
  texas_filings.csv               ~0.4 MB
  texas_loans_summary.csv         ~30 MB
  texas_master_joined.csv         ~1 MB
  texas_bank_profiles_latest.csv  ~0.2 MB
  texas_loans_joined_long.csv     ~34 MB
  texas_loan_products_mdrm_catalog.csv ~13 MB
  texas_loans_labeled.csv         ~805 MB (use filtered imports)
  texas_xbrl_facts.csv            ~208 MB (use filtered imports)"""
    ))

    # --- CSV FILE SECTIONS ---
    csv_docs = [
        ("Part A — File 1: texas_institutions.csv",
         """Purpose
Lists every Texas bank on the FFIEC Panel of Reporters for each included quarter. This comes from API method RetrievePanelOfReporters — it is the official list of who is expected to file a Call Report, not the contents of the XBRL file itself.

Grain (what one row means)
One row = one bank × one reporting_period. The same id_rssd appears five times (once per quarter). Total rows: 1,825.

Columns (all 7)
  id_rssd (integer, required)
    Federal Reserve RSSD ID. Primary key with reporting_period. Stable across mergers unless FFIEC reassigns. Example: 488653 for National Bank of Andrews.

  name (text, required)
    Legal/reporting name from FFIEC panel. May have trailing spaces in raw API; trimmed in scripts.

  state (text, required)
    Always TX in this extract (filter applied at download).

  city (text, required)
    Headquarters city from panel address. Used in EDA analyses 6 and 20 for geographic concentration and one-bank-per-market planning.

  filing_type (text/numeric, required)
    Call Report form code. 051 = FFIEC 031 (larger/complex banks). 041 = FFIEC 041 (community bank short form). Mapped in joined tables to form_size.

  reporting_period (text, required)
    Quarter end MM/DD/YYYY. Five values in this dataset: 3/31/2025, 6/30/2025, 9/30/2025, 12/31/2025, 3/31/2026.

  has_filed (boolean, required)
    True if FFIEC marks the bank as having submitted for that quarter. Only True rows were downloaded. In this extract, all 1,825 rows have has_filed=True because non-filers were not pulled.

Relationships
  institutions (1) → (0..1) filings per period if has_filed=True
  institutions + filings → many xbrl_facts

Typical analyses
  Count banks per quarter (EDA 17)
  Filter to city for market exclusivity maps
  Join to metrics for ICP segmentation

Example row
  id_rssd=488653, name=NATIONAL BANK OF ANDREWS, THE, city=ANDREWS, filing_type=051, reporting_period=3/31/2026, has_filed=True

Lenni use
This is the denominator for "how many Texas banks exist in FFIEC data." Lenni cites ~360 community banks; latest quarter panel shows 352–377 depending on period — large money-center branches and specialty charters are included, so ICP filtering on assets is essential."""),

        ("Part A — File 2: texas_filings.csv",
         """Purpose
Filing manifest: one row per successfully downloaded Call Report XBRL facsimile from RetrieveFacsimile. Proves what was retrieved, when, where stored on disk, and file integrity (SHA-256).

Grain
One row per (id_rssd, reporting_period) download. Rows: 1,825 — matches institutions where has_filed=True.

Columns (all 10)
  id_rssd — joins to institutions
  institution_name — denormalized name at download time
  state — TX
  city — from panel; may be empty if rebuilt from archive only
  reporting_period — quarter end
  facsimile_format — XBRL (default), or PDF/SDF if requested
  retrieved_at — ISO 8601 UTC timestamp of download batch
  file_path — absolute path to raw .xbrl under archive/call/<period>/
  sha256 — 64-character hex hash of raw bytes; used for deduplication
  file_size_bytes — file size; typical Call Report XBRL 50KB–500KB

Example
  .../archive/call/9-30-2025/623052.xbrl, sha256=e706acc1..., size ~59KB

Data quality notes
If pull_texas_since_2025.py was stopped and restarted, CSV may reflect last run only while archive stays complete. Rebuild with rebuild_csv_from_archive.py.

Provenance chain
  API request → raw bytes → archive file → parser → texas_xbrl_facts.csv
  filings.csv is the audit trail between API and parser.

Lenni use
Rarely needed for sales decks. Essential for engineering: verify a bank-quarter exists before joining, re-parse if FFIEC amends a filing (new sha256)."""),

        ("Part A — File 3: texas_xbrl_facts.csv",
         """Purpose
The fact table: every numeric and text value extracted from XBRL Call Report filings. This is the largest and most granular export (~2.19 million rows, ~208 MB).

Grain
One row = one XBRL fact (one reported value for one concept in one context) for one bank-quarter.

Columns (all 8)
  id_rssd, institution_name, reporting_period — keys
  concept — XBRL element name, often RCON/RCFD prefix or full QName in braces
  context_ref — XBRL context ID (defines instant vs duration, scenario)
  unit_ref — usually USD
  value_text — raw string value
  value_num — parsed float; empty if non-numeric disclosure

How facts are produced
1. Download XBRL XML from FFIEC
2. Parse with lxml (ffiec_cdr.parser)
3. Walk tree for elements with contextRef/unitRef
4. Deduplicate within filing; cap 50,000 facts per filing

Volume
~800–1,200 facts per bank per quarter; full Texas extract 2,186,590 rows.

Important concepts for Lenni EDA
  RCON2170 / RCFD2170 — total assets (balance sheet)
  RCON2122 — total loans and leases, gross
  RCON1766 — commercial and industrial loans
  RCONF158–F162 — commercial real estate construction and secured categories

Analysis tips
  Do NOT filter concept LIKE '%loan%' — returns zero rows. Use MDRM codes (RCON*, RCONF*, Schedule RC-C).
  In Google Sheets: filter one reporting_period or one id_rssd at a time.
  Join to MDRM catalog for English labels.

Limitations
  Mixed metadata (dei:EntityRegistrantName) and financial facts
  Multiple contexts per concept require care
  Not pre-mapped to human labels — use loan exports for that

Lenni use
Source of truth for balance-sheet metrics in joined tables. build_lenni_eda_report.py chunk-reads this file for RCON2170, RCON1766, RCON2122."""),

        ("Part A — File 4: texas_loans_summary.csv",
         """Purpose
Curated loan portfolio export: ~17 main Call Report loan line items per bank-quarter, enriched with Federal Reserve MDRM dictionary labels. Best starting point for loan mix analysis in Excel or Google Sheets.

Grain
One row = one bank × one quarter × one MDRM loan line item. Rows: 31,396 (~17 lines × ~360 banks × 5 quarters, varying by form).

Columns (14)
  id_rssd, institution_name, reporting_period — keys
  mdrm_code — e.g. RCON2122, RCONF161, RCON1545
  item_name — official Fed short name (e.g. TOTAL LOANS AND LEASES; NET OF UNEARNED INCOME)
  line_description — duplicate short label for Sheets compatibility
  mdrm_description — full Fed definition (up to 800 chars)
  mdrm_category — loan_or_lease, schedule_rc_c, or loan_related_prefix
  reporting_form — FFIEC 031 or 041
  item_type — F = financial line item
  value_num — reported amount (USD parsed from XBRL)
  value_text, context_ref, unit_ref — traceability to raw XBRL

Key MDRM codes in summary (used in EDA pivot)
  RCON2122 — total_loans_gross
  RCON2145 — total_loans_net
  RCON2130 — allowance_loan_losses
  RCON1420 — farmland_loans
  RCON1460 — multifamily_re_loans
  RCONF158/F159 — construction / land development
  RCONF160/F161 — owner-occupied and other nonfarm nonresidential RE
  RCONF162 — commercial_re_loans (in pivot)
  RCON1545 — credit_card_plans
  RCON1583 — other_consumer_loans
  RCON1754 — lease_financing
  RCON5367/5368 — past due 30–89 and 90+ days
  RCON1403 — residential_1_4_family
  RCON1590 — ag_production_loans
  RCON1766 — ci_loans (also pulled from xbrl_facts)

Example interpretation
  RCONF161 OTHER NONFARM NONRESIDENTIAL at $1.73B for IBC — CRE income-property lending; core Lenni prospect profile.

Regeneration
  python ONLY_TEXAS_SINCE_2025/extract_texas_loans.py --summary

Lenni use
Feeds pivot in build_lenni_eda_report.py → wide metrics on master joined table."""),

        ("Part A — File 5: texas_loans_labeled.csv",
         """Purpose
Complete loan and Schedule RC-C related facts for Texas banks — every MDRM-matched loan line, not just the ~17 summary categories. Rows: 937,816 (~805 MB).

Grain
One row = one loan-related MDRM line per bank-quarter (many lines per bank).

Columns
Same 14 columns as texas_loans_summary.csv. Difference is breadth: includes granular RC-C sub-lines, nonaccrual breakdowns, held-for-sale, junior liens, etc.

When to use summary vs labeled
  Use summary (31K rows) for: dashboards, ICP profiling, Sheets, CLO one-pagers
  Use labeled (938K rows) for: deep credit analysis, niche product research, finding rare line items

Categories in mdrm_category
  loan_or_lease — high-level loan totals and categories
  schedule_rc_c — detailed RC-C part I and II lines
  loan_related_prefix — RCON/RCFD codes matching loan patterns

Performance
  Too large for Google Sheets full import. Use Python/SQL or filter to one id_rssd or one period.

Relationship
  summary.csv is a filtered subset of labeled.csv focused on main categories for readability.

Lenni use
Optional depth for credit analysts. Sales team should default to summary + bank_profiles_latest."""),

        ("Part A — File 6: texas_loan_products_mdrm_catalog.csv",
         """Purpose
Reference code book: Federal Reserve MDRM definitions for loan and lease line items, flagged whether each code appears in Texas data.

Grain
One row per MDRM code definition. Rows: 24,015.

Columns (7)
  mdrm_code — e.g. RCON2122
  item_name — short regulatory name
  mdrm_description — full definition from MDRM_CSV.csv
  mdrm_category — loan_or_lease, schedule_rc_c, etc.
  reporting_form — which Call Report forms use this line
  item_type — F financial, etc.
  in_texas_data — boolean: code observed in Texas extract

Source
Downloaded from https://www.federalreserve.gov/apps/mdrm/pdf/MDRM.zip (~91 MB), stored locally in data/mdrm/ (gitignored).

Use cases
  Lookup unfamiliar RCON code seen in xbrl_facts
  Build custom filters for new product research
  Train new team members on Call Report vocabulary

Example
  RCON2122 → TOTAL LOANS AND LEASES; NET OF UNEARNED INCOME — the standard total loan portfolio measure.

Lenni use
Demystifies regulatory jargon for CLO conversations. Pair code + item_name when discussing portfolio composition."""),

        ("Part A — File 7: texas_master_joined.csv",
         """Purpose
The master analytical table: institutions + filing metadata + wide loan/balance-sheet metrics + derived ratios for every bank-quarter. Primary dataset for time-series and EDA. Rows: 1,825. Columns: 41.

Join logic
1. texas_institutions LEFT JOIN texas_filings on (id_rssd, reporting_period)
2. LEFT JOIN pivoted loan metrics from texas_loans_summary (LOAN_METRICS dict)
3. LEFT JOIN pivoted XBRL metrics from texas_xbrl_facts (total_assets, ci_loans)
4. Compute derived fields

Institution & filing columns
  id_rssd, name, state, city, filing_type, reporting_period, has_filed
  retrieved_at, file_path, sha256, file_size_bytes

Loan metric columns (USD, wide format)
  ag_production_loans, allowance_loan_losses, commercial_re_loans, credit_card_plans
  farmland_loans, lease_financing, multifamily_re_loans, other_construction_ld
  other_consumer_loans, other_nonfarm_nonres_re, owner_occupied_nonfarm_re
  past_due_30_89, past_due_90_plus, residential_1_4_family, residential_construction
  total_loans_gross, total_loans_net, ci_loans, total_assets, total_loans_gross_xbrl

Derived columns (critical for Lenni)
  assets_usd, loans_gross_usd — aliases for clarity
  loan_to_asset_ratio = total_loans_gross / total_assets
  allowance_ratio = allowance / gross loans
  cre_proxy_total = sum of CRE-related RC-C lines (construction, multifamily, nonfarm nonresidential, farmland, etc.)
  cre_to_loans, ci_to_loans, consumer_to_loans — mix ratios
  icp_fit — "ICP ($500M–$2B)" or "Outside ICP" based on total_assets
  form_size — FFIEC 031 (larger) vs 041 (community) label

ICP rule
  total_assets >= $500,000,000 AND <= $2,000,000,000 → ICP

Lenni use
Single file for quarterly trends (EDA 7, 14), QoQ growth (EDA 13, 24), and historical ICP counts."""),

        ("Part A — File 8: texas_bank_profiles_latest.csv",
         """Purpose
Latest-quarter snapshot: one row per Texas bank that filed in the most recent period ({latest_period}). Same 41 columns as master joined. Rows: 360 (354 with total_assets).

Why a separate file
Sales and CLO outreach usually need "current state" not five-quarter history. This file is filtered to the latest reporting_period only.

Key fields for prospecting
  name, city, id_rssd — identity and geography
  total_assets, total_loans_gross, ci_loans, cre_proxy_total — size and mix
  icp_fit — immediate Lenni segment flag
  loan_to_asset_ratio, cre_to_loans, ci_to_loans, consumer_to_loans — portfolio character
  form_size — regulatory complexity proxy

Latest-quarter segments
{s_segments}

Asset band counts (latest)
{s_asset_bands}

Top ICP banks by loan portfolio (examples)
  FIRSTBANK SOUTHWEST (Amarillo) — $1.35B loans, $1.86B assets
  FIRST NATIONAL BANK OF CENTRAL TEXAS (Waco) — $1.30B loans
  NORTH DALLAS BANK & TRUST CO. (Dallas) — $1.28B loans

Lenni use
Primary prospect file. Filter icp_fit == "ICP ($500M–$2B)" → 105 banks. Sort by total_loans_gross for CLO prioritization.""".format(
            latest_period=s["latest_period"], s_segments=s["segments"], s_asset_bands=s["asset_bands"])),

        ("Part A — File 9: texas_loans_joined_long.csv",
         """Purpose
Long-format loan data enriched with institution context: every row from texas_loans_summary plus bank name, city, filing type, form_size, icp_fit, and total_assets from the joined master table.

Grain
One row = one loan line item per bank-quarter (same 31,396 rows as summary).

Extra columns vs summary
  name, city, filing_type, form_size, icp_fit, total_assets

When to use
  Pivot tables in Sheets: sum value_num by item_name filtered to icp_fit = ICP
  Compare loan categories across cities without merging manually
  Export subsets for Drake/Catherine research workflows

Columns (20 total)
  All 14 from loans_summary plus 6 institution/enrichment fields listed above.

Example workflow
1. Filter reporting_period = 3/31/2026
2. Filter icp_fit = ICP ($500M–$2B)
3. Pivot: rows = item_name, values = sum of value_num
4. Result: aggregate loan mix for Lenni ICP universe

Lenni use
Best for ad-hoc "show me CRE vs C&I across ICP banks" without writing SQL."""),
    ]

    for title, body in csv_docs:
        sections.append((title, body))

    # --- EDA ANALYSES ---
    eda = [
        ("Part B — EDA Analysis 1: Asset size distribution",
         f"""Business question
How are Texas banks distributed by total asset size, and where does Lenni's $500M–$2B ICP band sit on that distribution?

Data & filters
  Source: texas_bank_profiles_latest.csv
  Column: total_assets (RCON2170 from XBRL), converted to millions for chart
  Filter: drop banks missing total_assets ({s['n_latest'] - s['n_with_assets']} banks missing)
  Universe: {s['n_with_assets']} banks with asset data

Methodology
  Histogram with 40 bins, x-axis clipped at $10 billion for readability (outliers above still in data)
  Green shaded band from $500M to $2,000M marks Lenni ICP

Results
  Median total assets (all banks): see summary stats — $433M (50th percentile)
  ICP banks: {s['n_icp']} ({s['pct_icp']:.1f}% of banks with assets)
  Distribution is right-skewed: many small community banks, fewer regional giants

Lenni interpretation
  Roughly one-third of filing Texas banks fall in ICP — large enough TAM for one-bank-per-market strategy without chasing money-center scale.
  Banks below $500M may lack budget for $2.5K–$5K/mo Lenni subscription; above $2B may have internal digital teams.

Sales action
  Use chart in decks to show "where we hunt" vs full Texas universe.

Caveats
  Total assets is point-in-time from Call Report; does not include pending mergers."""),

        ("Part B — EDA Analysis 2: Lenni ICP fit",
         f"""Business question
How many Texas banks fall inside vs outside Lenni's $500M–$2B asset ICP?

Methodology
  icp_fit = (total_assets >= 500M AND <= 2B) → "ICP ($500M–$2B)" else "Outside ICP"
  Bar chart of counts

Results (latest quarter)
  ICP: {s['n_icp']} banks
  Outside ICP: {s['n_with_assets'] - s['n_icp']} banks with assets
  Share in ICP: {s['pct_icp']:.1f}%
  Lenni context cites ~360 TX community banks; FFIEC panel latest = {s['n_latest']}

Lenni interpretation
  ICP is asset-based only — does not yet filter "community" charter type or digital gap.
  105 banks is the actionable CLO prospect pool from FFIEC alone.

Sales action
  Export lenni_icp_prospect_list.csv (Analysis 22) for ranked outreach.

Caveats
  6 banks missing asset data excluded from ICP calculation."""),

        ("Part B — EDA Analysis 3: Call Report form type",
         """Business question
What proportion of Texas banks file FFIEC 031 (larger) vs 041 (community short form)?

Methodology
  filing_type 051 → form_size "FFIEC 031 (larger)"
  filing_type 041 → form_size "FFIEC 041 (community)"
  Bar chart of counts on latest quarter

Results
  Mix of 031 and 041 filers; many Texas "community" names file 031 if over asset/complexity thresholds.

Lenni interpretation
  Form type is a complexity proxy, not ICP proxy. A $600M bank may still file 031.
  Do not exclude 031 filers from ICP outreach — CLO buyer is the same.

Caveats
  filing_type stored as string; some rows map to "Other" if code differs."""),

        ("Part B — EDA Analysis 4: Aggregate loan categories — ICP banks",
         f"""Business question
For Lenni ICP banks only, what is the aggregate dollar volume by major loan category?

Methodology
  Filter icp_fit = ICP ($500M–$2B)
  Sum across ICP banks: ci_loans, cre_proxy_total, credit_card_plans, other_consumer_loans, lease_financing
  Bar chart in USD (not ratios)

Results
  CRE proxy and C&I dominate aggregate volume vs consumer cards
  Median ICP bank: ${s['median_loans_icp_m']:.0f}M gross loans

Lenni interpretation
  Confirms Lenni thesis: Texas ICP banks are portfolio/commercial lenders, not credit-card-centric retail shops.
  Convey messaging ("real lender at the front of CRE/C&I inquiries") matches data.

Sales action
  Lead with CRE/C&I pain points in CLO calls for ICP segment."""),

        ("Part B — EDA Analysis 5: Loan-to-asset ratio",
         f"""Business question
How levered to lending is the typical Texas bank (loans ÷ assets)?

Methodology
  loan_to_asset_ratio = total_loans_gross / total_assets
  Histogram clipped 0–1.2; 35 bins

Results (from summary statistics)
{s['stats_table']}

  Median loan_to_asset_ratio ≈ 0.62 (50th percentile)
  25th–75th percentile: 0.50 – 0.74

Lenni interpretation
  Most banks are lending-heavy (60%+ loans/assets) — loan origination is core revenue, so online loan capture matters to CLO.

Caveats
  Banks with zero loans create edge cases; ratio clipped in chart."""),

        ("Part B — EDA Analysis 6: Top cities by bank count",
         f"""Business question
Where are Texas banks geographically concentrated? Critical for Lenni one-bank-per-market exclusivity.

Methodology
  Group latest quarter by city; count distinct id_rssd; top 15 horizontal bar chart

Results (top 5)
{s['top_cities']}

Lenni interpretation
  DFW and Houston metros have highest bank density — competitive for exclusivity, rich for pipeline.
  Smaller cities may have one dominant community bank — ideal for "we chose you" positioning.

Sales action
  Cross-reference Monday.com pipeline with city counts; prioritize unfilled markets."""),

        ("Part B — EDA Analysis 7: Quarterly median assets & loans",
         f"""Business question
Is the Texas banking sector growing? How do median assets and loans trend across five quarters?

Methodology
  Group texas_master_joined by reporting_period
  Dual-axis line chart: median total_assets and median total_loans_gross ($ millions)

Quarterly data
{s['q_table']}

Lenni interpretation
  Panel size varies 352–377 — bank count drop reflects panel changes, not necessarily failures.
  Median assets stable ~$400–433M — sector not rapidly consolidating in this window.

Caveats
  Five quarters is short for structural trend claims."""),

        ("Part B — EDA Analysis 8: Top 15 ICP banks by loan portfolio",
         """Business question
Which ICP banks have the largest loan books — highest-impact CLO relationships?

Methodology
  Filter ICP; sort by total_loans_gross descending; top 15 horizontal bar chart
  Labels: bank name + city

Results (top examples)
  FIRSTBANK SOUTHWEST (Amarillo) — $1.35B loans
  FIRST NATIONAL BANK OF CENTRAL TEXAS (Waco) — $1.30B
  NORTH DALLAS BANK & TRUST (Dallas) — $1.28B
  COMMUNITY NATIONAL BANK & TRUST (Corsicana) — $1.19B
  CENTRAL NATIONAL BANK (Waco) — $1.15B

Lenni interpretation
  Top ICP banks by loans are regional portfolio lenders — high loan volume = high value of incremental funded deals from Convey.

Sales action
  Tier 1 prospect list for Doak/Drake executive outreach."""),

        ("Part B — EDA Analysis 9: C&I vs CRE scatter — ICP banks",
         """Business question
Among ICP banks, is lending driven more by commercial & industrial or by commercial real estate?

Methodology
  Scatter plot: x = ci_loans ($M), y = cre_proxy_total ($M)
  Each point = one ICP bank; alpha for overlap

Results
  Wide dispersion — some banks C&I-heavy, some CRE-heavy, many balanced
  CRE proxy sums: construction, multifamily, owner-occupied nonfarm, other nonfarm nonresidential, farmland, etc.

Lenni interpretation
  No single "Texas ICP archetype" — messaging stays portfolio-lender broad, not CRE-only.
  Banks in upper-right quadrant (high C&I and high CRE) are highest-value Convey targets.

Caveats
  CRE proxy is summed RC-C lines, not identical to UBPR CRE definition."""),

        ("Part B — EDA Analysis 10: Allowance for loan losses ratio",
         """Business question
What credit reserve posture do Texas banks show (allowance ÷ gross loans)?

Methodology
  allowance_ratio = allowance_loan_losses / total_loans_gross
  Histogram clipped 0–5%; 30 bins

Results
  Most banks cluster at low allowance ratios (well under 2%)
  Reflects relatively benign credit environment in 2025–2026 window

Lenni interpretation
  Not a primary sales filter — but extreme outliers may indicate stress conversations (compliance sensitivity).

Caveats
  Allowance reporting differs by form; some banks report zero in summary line."""),

        ("Part B — EDA Analysis 11: 90+ day past-due stress proxy",
         """Business question
Which banks show elevated non-performing loan signals?

Methodology
  past_due_90_plus / total_loans_gross per bank
  Histogram clipped 0–10%

Results
  Majority of banks show very low 90+ past-due ratios
  Tail of distribution = potential credit stress (manual review)

Lenni interpretation
  Stressed banks may deprioritize new software — lower priority for outbound unless turnaround story.

Caveats
  Past-due lines are reporting-category dependent; not CECL expected loss."""),

        ("Part B — EDA Analysis 12: Consumer vs commercial orientation",
         """Business question
Is a bank consumer-lending oriented or commercial/portfolio oriented?

Methodology
  consumer_to_loans = (credit_cards + other_consumer) / total_loans
  ci_to_loans = ci_loans / total_loans
  Scatter plot both ratios (0–1)

Results
  Many Texas banks cluster with moderate C&I share and low consumer share
  Aligns with Lenni borrower personas (CRE hustlers, not mortgage shoppers)

Lenni interpretation
  Prioritize banks with high ci_to_loans and low consumer_to_loans for Convey positioning.

Sales action
  Complements Analysis 25 (low consumer share count)."""),

        ("Part B — EDA Analysis 13: Quarter-over-quarter loan growth",
         """Business question
How fast are loan portfolios changing quarter to quarter?

Methodology
  Sort master by id_rssd, reporting_period
  loan_growth = pct_change(total_loans_gross) within bank
  Histogram clipped -30% to +30%

Results
  Most banks show modest QoQ loan growth (single-digit %)
  Extreme values often reflect acquisitions, bulk loan sales, or reporting reclasses

Lenni interpretation
  Growing loan books = growing need to capture online inquiries before they go to competitors.

Caveats
  First quarter per bank has no prior — excluded from growth calc."""),

        ("Part B — EDA Analysis 14: ICP bank count by period",
         f"""Business question
Is Lenni's addressable ICP pool stable over time?

Methodology
  Count icp_fit = ICP per reporting_period; bar chart

Results
{s['q_table']}

  ICP counts range ~105–113 across five quarters — stable TAM

Lenni interpretation
  Asset-band counts shift slightly as banks grow into or out of $500M–$2B band.
  Monitor quarterly re-runs after FFIEC sync for pipeline refresh."""),

        ("Part B — EDA Analysis 15: Asset band TAM sizing",
         f"""Business question
How many banks fall in each asset band — for market sizing slides?

Methodology
  Bins: <$100M, $100–250M, $250–500M, $500M–$1B, $1–2B, $2–5B, >$5B
  Bar chart; exported to asset_band_counts.csv

Results
{s['asset_bands']}

  Lenni ICP spans $500M–$1B (68 banks) + $1–2B (37 banks) = 105 total

Lenni interpretation
  $500M–$1B segment is larger — may be sweeter spot for price sensitivity ($2.5K/mo).
  >$5B banks (15) are out of ICP but include names that skew metro averages."""),

        ("Part B — EDA Analysis 16: Median loan-mix ratios — ICP",
         """Business question
For a typical ICP bank, what share of loans is CRE, C&I, consumer, residential 1–4?

Methodology
  Median across ICP banks of: cre_to_loans, ci_to_loans, consumer_to_loans, residential_1_4_family / total_loans
  Bar chart of median ratios

Results
  CRE and C&I medians dominate consumer and 1–4 family shares
  Confirms aggregate Analysis 4 at median-bank level

Lenni interpretation
  Use median ratios in pitch: "Typical $500M–$2B Texas bank looks like X% CRE, Y% C&I."

Caveats
  Medians hide bimodal distribution — always show scatter (Analysis 9) too."""),

        ("Part B — EDA Analysis 17: Filing panel size by quarter",
         f"""Business question
How many Texas banks file each quarter — is the panel shrinking?

Methodology
  Count distinct id_rssd per reporting_period from master joined

Results
{s['q_table']}

Lenni interpretation
  ~352–377 filers — use as denominator for "percent of Texas banks" claims.
  Pair with external IBAT/community bank counts for charter-type filtering."""),

        ("Part B — EDA Analysis 18: CRE concentration — ICP banks",
         """Business question
How concentrated in CRE are ICP banks (cre_proxy / gross loans)?

Methodology
  Histogram of cre_to_loans for ICP only; clipped 0–1; 25 bins

Results
  Many ICP banks show CRE proxy at 30–70% of loan book
  Validates commercial real estate as core economic driver

Lenni interpretation
  High CRE concentration banks feel online CRE inquiry pain acutely — strong Convey use cases.

Caveats
  CRE proxy ≠ total commercial real estate on UBPR; construction lines included."""),

        ("Part B — EDA Analysis 19: Loan portfolio size by form type",
         """Business question
Do FFIEC 031 filers carry larger loan books than 041 filers?

Methodology
  Box plot: total_loans_gross by form_size (031 larger vs 041 community)

Results
  031 filers show higher median and wider upper whisker — expected
  Overlap exists — community form does not always mean small loans

Lenni interpretation
  Use form_size as secondary sort, not primary ICP filter."""),

        ("Part B — EDA Analysis 20: Top 10 cities — ICP bank count",
         f"""Business question
Which cities have the most ICP-sized banks (exclusive market planning)?

Methodology
  Filter ICP; group by city; count banks; top 10 bar chart

Results
  Metro areas (Dallas, Houston, San Antonio corridors) lead ICP counts
  Combines with Analysis 6 but filtered to ICP only

Lenni interpretation
  Dense ICP cities require faster exclusivity decisions — "bank #2 across town" messaging.

Sales action
  Map ICP city counts to Monday.com deal stages."""),

        ("Part B — EDA Analysis 21: Summary statistics table",
         f"""Business question
What are mean, median, quartiles for key financial fields (latest quarter)?

Methodology
  pandas describe() on total_assets, total_loans_gross, ci_loans, cre_proxy_total, loan_to_asset_ratio
  Exported to summary_statistics_latest.csv

Results
{s['stats_table']}

Lenni interpretation
  Mean >> median on assets/loans — distorted by few mega-banks; use median for "typical bank" slides.
  Mean total assets ~$1.41B but median ~$433M — always report median for community bank story.

Caveats
  354 banks with complete asset data in describe output."""),

        ("Part B — EDA Analysis 22: ICP prospect CSV export",
         f"""Business question
Produce actionable ranked prospect list for sales.

Methodology
  Filter ICP latest quarter; export columns: id_rssd, name, city, filing_type, total_assets, total_loans_gross, ci_loans, cre_proxy_total, loan_to_asset_ratio, cre_to_loans, ci_to_loans
  Sort by total_loans_gross descending
  File: analysis/lenni_icp_prospect_list.csv ({s['n_icp']} rows)

Lenni interpretation
  This is the operational bridge from EDA to CRM — import to Monday.com or Salesforce.

Sales action
  Tier 1 = top 20 by loans; Tier 2 = next 40; Tier 3 = remainder ICP."""),

        ("Part B — EDA Analysis 23: Loan category heatmap by asset band",
         """Business question
How does median loan mix shift as banks get larger?

Methodology
  Group latest quarter by asset_band
  Median of ci_loans, cre_proxy_total, residential_1_4_family, credit_card_plans, other_consumer, ag_production ($M)
  Heatmap (rows = bands, cols = categories)

Results
  Larger bands show higher absolute $ medians across categories
  CRE and C&I absolute medians rise faster than consumer in upper bands

Lenni interpretation
  Validates ICP band as "big enough to matter" for loan volume without being money-center.

Caveats
  Heatmap shows medians, not ratios — read alongside Analysis 16."""),

        ("Part B — EDA Analysis 24: Asset growth QoQ",
         """Business question
Are banks growing balance sheets quarter over quarter?

Methodology
  asset_growth = pct_change(total_assets) by bank
  Histogram clipped -20% to +20%

Results
  Most banks show low single-digit asset growth QoQ
  Spikes may reflect M&A or large deposit/loan events

Lenni interpretation
  Banks growing into $500M from below may enter ICP next quarter — watch $250–500M band (76 banks)."""),

        ("Part B — EDA Analysis 25: Low consumer share banks",
         f"""Business question
How many banks are portfolio/commercial oriented (consumer < 15% of loans)?

Methodology
  consumer_to_loans < 0.15 → "Consumer <15%"
  Bar chart comparing counts

Results
  {s['n_low_consumer']} banks ({s['pct_low_consumer']:.0f}%) have consumer loans under 15% of portfolio
  Remainder have higher consumer mix

Lenni interpretation
  Majority alignment with Lenni commercial borrower personas — not retail mortgage shops.
  Strongest Convey fit per lenni_contenxt.txt (CRE hustlers, portfolio real estate).

Sales action
  Combine with ICP filter for "perfect fit" shortlist: ICP + consumer <15%."""),
    ]

    for title, body in eda:
        body += """

How to reproduce from CSV
  Open texas_bank_profiles_latest.csv (latest quarter) or texas_master_joined.csv (all quarters).
  Apply filters and formulas described above. Cross-check counts against analysis/ CSV exports where noted."""
        sections.append((title, body))

    # Detailed column reference for master joined (split across pages)
    col_ref = """
Column-by-column reference for texas_master_joined.csv and texas_bank_profiles_latest.csv (41 fields).

IDENTITY & PANEL (from texas_institutions.csv)
  id_rssd — Integer Federal Reserve ID. Primary key with reporting_period. Never share externally as sole identifier without name; use together in CRM.
  name — Institution legal name from FFIEC panel. Trim spaces before matching.
  state — Always TX in this extract.
  city — Panel city; used in geographic EDA. May differ from branch network footprint.
  filing_type — Raw form code (051, 041, etc.). See form_size for readable label.
  reporting_period — Quarter end MM/DD/YYYY. Five values in dataset.
  has_filed — Boolean; True for all rows in joined table (only filers downloaded).

FILING PROVENANCE (from texas_filings.csv)
  retrieved_at — UTC timestamp when XBRL was downloaded. Batch runs share timestamp.
  file_path — Absolute path to .xbrl in archive/. Enables re-parse without re-download.
  sha256 — Content hash. If FFIEC amends filing, hash changes on re-download.
  file_size_bytes — Raw file size. Anomaly detection for truncated downloads.

LOAN PORTFOLIO AMOUNTS — USD (from texas_loans_summary pivot)
  total_loans_gross — RCON2122. Headline loan book. Use for ranking prospects.
  total_loans_net — RCON2145. After unearned income; often close to gross.
  allowance_loan_losses — RCON2130. Reserve for credit losses; used in allowance_ratio.
  ci_loans — RCON1766. Commercial & industrial; core operating business lending.
  commercial_re_loans — RCONF162. Commercial real estate category per RC-C.
  owner_occupied_nonfarm_re — RCONF160. Owner-occupied commercial property.
  other_nonfarm_nonres_re — RCONF161. Income-producing CRE (hotels, retail centers).
  multifamily_re_loans — RCON1460. 5+ unit residential investment property.
  residential_construction — RCONF158. 1–4 family construction and development.
  other_construction_ld — RCONF159. Land development and other construction.
  farmland_loans — RCON1420. Farmland-secured agricultural real estate.
  residential_1_4_family — RCON1403. 1–4 family residential mortgage portfolio.
  credit_card_plans — RCON1545. Revolving credit card receivables.
  other_consumer_loans — RCON1583. Non-card consumer installment loans.
  lease_financing — RCON1754. Lease financing receivables.
  ag_production_loans — RCON1590. Agricultural production operating credit.
  past_due_30_89 — RCON5367. Loans 30–89 days past due (early stress).
  past_due_90_plus — RCON5368. Loans 90+ days past due (NPL proxy).

BALANCE SHEET (from texas_xbrl_facts chunk read)
  total_assets — RCON2170. Defines icp_fit band. Most important single metric for Lenni.
  total_loans_gross_xbrl — Duplicate pull of RCON2122 from facts file; used to fill gaps if loan pivot missing.

DERIVED ALIASES
  assets_usd — Same as total_assets; clarity for USD labeling in exports.
  loans_gross_usd — Same as total_loans_gross.

DERIVED RATIOS (computed in build_lenni_eda_report.py)
  loan_to_asset_ratio — total_loans_gross / total_assets. Lending intensity.
  allowance_ratio — allowance_loan_losses / total_loans_gross. Reserve adequacy signal.
  cre_proxy_total — Sum of farmland, multifamily, construction, owner-occupied nonfarm, other nonfarm nonresidential, commercial_re (when present). CRE exposure proxy.
  cre_to_loans — cre_proxy_total / total_loans_gross. Share of book in CRE categories.
  ci_to_loans — ci_loans / total_loans_gross. C&I share.
  consumer_to_loans — (credit_cards + other_consumer) / total_loans_gross. Retail orientation.

SEGMENTATION FLAGS
  icp_fit — "ICP ($500M–$2B)" if total_assets in band; else "Outside ICP". Primary Lenni filter.
  form_size — "FFIEC 031 (larger)" for filing_type 051; "FFIEC 041 (community)" for 041; else Other.
"""
    sections.append(("Appendix — Master joined column reference (Part 1)", col_ref[:len(col_ref)//2]))
    sections.append(("Appendix — Master joined column reference (Part 2)", col_ref[len(col_ref)//2:]))

    sections.append((
        "Part C — Synthesis, limitations, and regeneration",
        f"""Executive synthesis
This Texas FFIEC extract gives Lenni a quantitative foundation for CLO-led sales. Five quarters of Call Report XBRL data for 1,825 bank-quarters paint a consistent picture: roughly {s['pct_icp']:.0f}% of latest-quarter filers with asset data ({s['n_icp']} banks) sit in the $500M–$2B ICP band; those banks are predominantly commercial and CRE portfolio lenders rather than consumer-card or retail-mortgage shops; geographic concentration in DFW, Houston, and secondary metros supports one-bank-per-market planning; and loan books are large relative to assets (median loan-to-asset ~62%).

What FFIEC data proves vs what it cannot prove
  PROVES: asset size, loan portfolio composition, credit stress proxies, quarterly trends, city location, form type
  CANNOT PROVE: online loan application presence, LOS vendor, digital maturity, borrower messaging gap — Lenni's "267/360 no online app" stat requires separate field research (Texas Community Bank Index / Addy workstream)

Recommended workflow for Lenni team
1. Start from texas_bank_profiles_latest.csv filtered to ICP
2. Rank using lenni_icp_prospect_list.csv (loan volume) and Analysis 25 (low consumer share)
3. Layer city exclusivity from Analyses 6 and 20
4. Use texas_loans_joined_long.csv for custom pivot questions in Sheets
5. Re-run build_lenni_eda_report.py after each FFIEC sync

File regeneration commands
  cd /Users/adityarajiv/Documents/ffiec-cdr && source .venv/bin/activate
  python ONLY_TEXAS_SINCE_2025/build_lenni_eda_report.py
  python ONLY_TEXAS_SINCE_2025/build_comprehensive_eda_guide.py

Related outputs
  Lenni_Texas_Bank_EDA_Report.pdf — 25 charts (visual companion to this guide)
  Lenni_Texas_EDA_Comprehensive_Guide.pdf — this document

Data lineage reminder
  FFIEC PWS API → archive XBRL → parser → CSV exports → join/EDA scripts → analysis folder

Contact for questions
  Engineering: regenerate scripts in ONLY_TEXAS_SINCE_2025/
  Sales enablement: lenni_icp_prospect_list.csv + this guide Part B analyses 8, 22, 25"""
    ))

    sections.append((
        "Appendix — MDRM code reference for joined-table columns",
        """The wide columns in texas_master_joined.csv map to Federal Reserve MDRM codes extracted from Call Report Schedule RC and RC-C:

Balance sheet (from XBRL facts)
  total_assets ← RCON2170 (Total assets)
  ci_loans ← RCON1766 (Commercial and industrial loans)
  total_loans_gross ← RCON2122 (Total loans and leases, net of unearned income)

Loan portfolio (from texas_loans_summary pivot)
  RCON2122 total_loans_gross — headline loan book size
  RCON2145 total_loans_net — after unearned income adjustments
  RCON2130 allowance_loan_losses — ALLL for credit reserve ratio
  RCON1420 farmland_loans — agricultural real estate secured
  RCON1460 multifamily_re_loans — 5+ unit residential CRE
  RCONF158 residential_construction — 1–4 family construction
  RCONF159 other_construction_ld — land development and other construction
  RCONF160 owner_occupied_nonfarm_re — owner-occupied commercial property
  RCONF161 other_nonfarm_nonres_re — income-producing CRE (hotels, retail, etc.)
  RCONF162 commercial_re_loans — commercial RE category per RC-C
  RCON1545 credit_card_plans — revolving credit card receivables
  RCON1583 other_consumer_loans — non-card consumer
  RCON1754 lease_financing — lease receivables
  RCON1403 residential_1_4_family — 1–4 family residential loans
  RCON1590 ag_production_loans — agricultural production operating
  RCON5367 past_due_30_89 — past due 30–89 days (stress signal)
  RCON5368 past_due_90_plus — past due 90+ days (stress signal)

Derived metrics (not raw MDRM)
  cre_proxy_total — sum of CRE-related lines listed in build_lenni_eda_report.py
  cre_to_loans — cre_proxy_total / total_loans_gross
  ci_to_loans — ci_loans / total_loans_gross
  consumer_to_loans — (credit_card + other_consumer) / total_loans_gross
  loan_to_asset_ratio — total_loans_gross / total_assets
  allowance_ratio — allowance / total_loans_gross
  icp_fit — binary segment from total_assets vs $500M–$2B thresholds

For full English definitions open texas_loan_products_mdrm_catalog.csv and search mdrm_code."""
    ))

    sections.append((
        "Appendix — Worked example: reading one bank end-to-end",
        """Example bank: UBANK (id_rssd 917555, Huntington, TX) — latest quarter 3/31/2026

Step 1 — institutions.csv
  Find row id_rssd=917555, reporting_period=3/31/2026 → has_filed=True, city=HUNTINGTON

Step 2 — filings.csv
  Same keys → file_path points to archive/call/3-31-2026/917555.xbrl, sha256 for integrity

Step 3 — bank_profiles_latest.csv
  total_assets = $942,084,000 → icp_fit = "ICP ($500M–$2B)"
  total_loans_gross = $734,206,000
  loan_to_asset_ratio ≈ 0.78 (lending-heavy)
  cre_proxy_total = $484,881,000 → cre_to_loans ≈ 0.66 (CRE-focused)
  ci_loans = $157,575,000 → ci_to_loans ≈ 0.21
  consumer_to_loans ≈ 0 (minimal card/consumer)

Step 4 — loans_joined_long.csv
  Filter id_rssd=917555 → ~17 rows, one per MDRM summary line with same icp_fit and total_assets repeated

Step 5 — Sales narrative for Lenni
  UBANK is ICP-sized, CRE-heavy, low consumer — matches Convey CLO pitch.
  Next step NOT in FFIEC data: confirm whether UBANK has online loan application + human at front.

This walkthrough repeats for any id_rssd — use RSSD as stable key across all files."""
    ))

    sections.append((
        "Appendix — Google Sheets and Excel practical guide",
        """Import order (avoid timeout)
1. texas_bank_profiles_latest.csv (360 rows) — full import OK
2. texas_master_joined.csv (1,825 rows) — full import OK
3. texas_loans_summary.csv — filter one period first OR use Python
4. Never full-import texas_xbrl_facts or texas_loans_labeled into Sheets

Useful Sheet formulas (after importing bank_profiles_latest)
  Count ICP: =COUNTIF(icp_fit_column, "ICP ($500M–$2B)")
  Filter view: Data → Create a filter → icp_fit = ICP
  Sort prospects: Data → Sort range → total_loans_gross descending

Pivot example on loans_joined_long
  Rows: item_name
  Values: SUM of value_num
  Filter: icp_fit = ICP, reporting_period = 3/31/2026
  Result: aggregate loan mix for 105-bank ICP universe

Excel Power Query
  Get Data → From CSV → merge institutions + filings on id_rssd + reporting_period
  Same join logic as build_lenni_eda_report.py

Refresh cadence
  After each FFIEC sync re-run pull_texas_since_2025.py, extract_texas_loans.py, build_lenni_eda_report.py, then re-export to SharePoint."""
    ))

    sections.append((
        "Appendix — Chart-by-chart companion to Lenni_Texas_Bank_EDA_Report.pdf",
        """The visual PDF (Lenni_Texas_Bank_EDA_Report.pdf) contains the same 25 analyses as Part B of this guide. Use them together:

  Analysis 1 histogram → Part B Analysis 1 (asset distribution)
  Analysis 2 ICP bar → Part B Analysis 2
  ... through Analysis 25 consumer share bar → Part B Analysis 25

Front matter pages in visual PDF
  Title page — purpose and joined table list
  Analysis index — numbered 1–25
  Joined table schema — column reference (expanded in Part A Files 7–9 here)
  Executive findings — bullet summary from live run
  Recommendations — five action items for Lenni team

Regenerate both documents after data refresh:
  python build_lenni_eda_report.py
  python build_comprehensive_eda_guide.py"""
    ))

    sections.append((
        "Appendix — Credit and ratio interpretation glossary",
        """loan_to_asset_ratio
  What: Gross loans divided by total assets. Higher = bank earns more from lending vs securities/fees.
  Typical TX range: 0.50–0.74 (IQR). Above 0.80 = very lending-centric.

cre_to_loans
  What: Sum of CRE-related RC-C lines divided by gross loans. Not identical to UBPR "CRE concentration."
  High values (>0.50): bank lives on commercial real estate — Lenni sweet spot.

ci_to_loans
  What: Commercial & industrial loans / gross loans. Operating business lending.

consumer_to_loans
  What: (Credit cards + other consumer) / gross loans. Low values (<0.15) = portfolio lender profile.

allowance_ratio
  What: ALLL / gross loans. Rising trend across quarters at a single bank may signal credit concern.

past_due_90_plus / total_loans
  What: Rough NPL proxy from past-due reporting lines. Compare within peer band, not absolute threshold.

icp_fit
  What: Binary flag from total_assets only. Manual overlay: charter type, digital gap, relationship status."""
    ))

    sections.append((
        "Appendix — Join diagram and entity relationships",
        """Logical data model (all exports)

  texas_institutions (id_rssd, reporting_period)
          |
          | has_filed = True
          v
  texas_filings (id_rssd, reporting_period) ---> archive/.../id_rssd.xbrl
          |
          | 1 : many (parse)
          v
  texas_xbrl_facts (id_rssd, reporting_period, concept, context_ref)
          |
          | filter + MDRM enrich
          v
  texas_loans_summary / texas_loans_labeled
          |
          | pivot wide + merge XBRL metrics
          v
  texas_master_joined (bank-quarter wide)
          |
          | filter latest period
          v
  texas_bank_profiles_latest (bank-level snapshot)

  texas_loans_joined_long = loans_summary LEFT JOIN institution fields from master

Cardinality rules
  At most one filing row per (id_rssd, reporting_period) per successful download
  Many fact rows per filing (800–1200 typical)
  ~17 summary loan rows per bank-quarter in summary file
  One master joined row per bank-quarter (1,825 total)

Integrity checks performed
  progress.json lists 1,825 completed period|RSSD pairs
  Archive contains 1,825 .xbrl files across five quarter folders
  sha256 on each filing enables amend detection

Using joins in Excel / Sheets
  VLOOKUP/XLOOKUP on id_rssd + reporting_period
  Or Power Query merge on both keys
  Never merge on name alone — names change and duplicate"""
    ))

    sections.append((
        "Appendix — Lenni sales playbook using this data",
        """Step 1 — Build the prospect universe
  Filter texas_bank_profiles_latest.csv where icp_fit = "ICP ($500M–$2B)" → 105 banks.
  Sort by total_loans_gross descending (same order as lenni_icp_prospect_list.csv).

Step 2 — Tier prioritization
  Tier 1 (top 15 by loans): executive outreach — Analysis 8 names (FirstBank Southwest, FNBC Waco, etc.)
  Tier 2 (next 40): Drake full-cycle sequence with CRE/C&I talk track
  Tier 3 (remainder ICP): nurture / conference follow-up

Step 3 — Geographic exclusivity
  Use Analysis 6 and 20 city counts. Before signing Bank A in Dallas, check how many ICP banks share city.
  Apply one-bank-per-market rule from lenni_contenxt.txt — document pass/no-pass in Monday.com.

Step 4 — Portfolio-fit messaging
  Pull ci_to_loans and cre_to_loans for prospect. High CRE + high C&I → "portfolio lender" script.
  consumer_to_loans < 0.15 → emphasize CRE/C&I online capture, not retail mortgage (Analysis 25).

Step 5 — CFO / board defense
  Use median ICP assets (~$866M) and median loans (~$586M) from this guide cover stats.
  Anchor: five incremental CRE loans/month × $500K+ average = material NII vs Lenni subscription cost.

Step 6 — What to add from non-FFIEC research
  Online application audit (267/360 stat), LOS vendor, Core provider, relationship history from Dunkin network.
  FFIEC data opens the door; relationship intelligence closes it."""
    ))

    sections.append((
        "Appendix — Frequently asked questions",
        """Q: Why don't loan filters on concept='loan' work in xbrl_facts?
A: FFIEC uses MDRM codes (RCON2122), not English words. Use loan summary exports.

Q: Why do ICP counts differ slightly by quarter (105 vs 110)?
A: Banks grow into or out of $500M–$2B as assets change quarter to quarter.

Q: Can I use this data to prove a bank has no online loan application?
A: No. That requires separate Texas Community Bank Index / manual research.

Q: Why is mean assets much higher than median?
A: A few large Texas banks (regional/national) skew the mean; use median for typical community bank story.

Q: What's the difference between texas_loans_summary and texas_loans_labeled?
A: Summary has ~17 main categories per bank-quarter; labeled has all RC-C detail (~938K rows).

Q: How often should we refresh?
A: After each new FFIEC reporting period (quarterly). Re-run pull, extract, build_lenni_eda_report, this guide.

Q: Which file do I send a CLO?
A: Do not send raw CSV. Use prospect list + 1-page chart from EDA PDF. Share SharePoint link for analysts.

Q: Are dollar amounts in thousands or units?
A: Parsed as filed in XBRL value_num. Call Report lines are typically reported in thousands; verify against UBPR for a given bank when precision matters for one deal."""
    ))

    sections.append((
        "Appendix — Troubleshooting data issues",
        """Missing total_assets for a bank
  Cause: RCON2170 not extracted from XBRL for that filing (form variant or parse edge case).
  Fix: Check raw xbrl_facts for id_rssd; re-parse from archive if needed.

filings.csv row count lower than expected
  Cause: Script restarted with write-mode CSV while archive complete.
  Fix: python rebuild_csv_from_archive.py

ICP count doesn't match manual filter
  Cause: Comparing latest (360 rows) vs all quarters (1825 rows); or null assets excluded.
  Fix: Filter reporting_period to latest only; use icp_fit column not manual asset filter.

Sheets import fails on large files
  Cause: texas_loans_labeled (~805MB) or xbrl_facts (~208MB) exceed limits.
  Fix: Filter in Python first; import subsets.

Duplicate bank names
  Cause: Different id_rssd can have similar names; mergers change names not always RSSD.
  Fix: Always join on id_rssd + reporting_period, never name alone."""
    ))

    return sections


def main() -> int:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    stats = load_stats()
    sections = build_sections(stats)

    page_count = 0
    with PdfPages(OUT_PDF) as pdf:
        for title, body in sections:
            page_count += add_section(pdf, title, body)
        d = pdf.infodict()
        d["Title"] = "Lenni Texas EDA Comprehensive Guide"
        d["Author"] = "FFIEC CDR Pipeline"
        d["Subject"] = "CSV documentation and EDA analysis guide"
        d["CreationDate"] = datetime.now()

    print(f"Wrote {OUT_PDF} ({page_count} pages)")
    if page_count < 50:
        print(f"WARNING: {page_count} pages — target was ~50; content may need expansion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
