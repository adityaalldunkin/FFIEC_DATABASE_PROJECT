"""Borrower-focused EDA content for each project data file."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from eda_extras import append_file_documentation

ROOT = Path(__file__).resolve().parent
TODAY = datetime.now().strftime("%Y-%m-%d")


def _section(title: str) -> list[tuple[str, object]]:
    return [(title, ""), ("", "")]


def _kv(rows: list[tuple[str, object]]) -> list[tuple[str, object]]:
    return rows


def _load_full_csv(name: str, skip: int = 0) -> pd.DataFrame:
    return pd.read_csv(ROOT / name, skiprows=skip, low_memory=False)


def _tx_active_institutions() -> pd.DataFrame:
    inst = _load_full_csv("institutions.csv")
    tx = inst[inst["STALP"] == "TX"].copy()
    tx["ASSET_M"] = pd.to_numeric(tx["ASSET"], errors="coerce") / 1000
    return tx[tx["ACTIVE"] == 1]


def build_eda(path: Path, df: pd.DataFrame, meta: dict) -> list[tuple[str, object]]:
    name = path.name
    builders = {
        "institutions_definitions.csv": _eda_institutions_definitions,
        "events_definitions.csv": _eda_events_definitions,
        "institutions.csv": _eda_institutions,
        "locations.csv": _eda_locations,
        "locations_definitions.csv": _eda_locations_definitions,
        "sod_variables_definitions.csv": _eda_sod_definitions,
        "texas_filings.csv": _eda_texas_filings,
        "texas_institutions.csv": _eda_texas_institutions,
        "texas_loans_labeled.csv": _eda_texas_loans_labeled,
        "texas_loan_products_mdrm_catalog.csv": _eda_loan_catalog,
        "texas_mdrm_loan_taxonomy.csv": _eda_taxonomy_csv,
        "26.05.18.All.Loan.Types.UBPR.Reference.xlsx": _eda_ubpr_reference,
        "All Financial Reports.xlsx": _eda_all_financial_reports,
        "texas_mdrm_loan_taxonomy.xlsx": _eda_taxonomy_xlsx,
        "asset_band_counts.csv": _eda_asset_band_counts,
        "lenni_icp_prospect_list.csv": _eda_icp_prospect_list,
        "lenni_market_segments.csv": _eda_market_segments,
        "summary_statistics_latest.csv": _eda_summary_statistics,
    }
    key = name if name in builders else path.name
    if key in builders:
        rows = builders[key](path, df, meta)
    else:
        rows = _eda_generic(path, df, meta)
    return append_file_documentation(rows, path.name)


def _header(path: Path, meta: dict, what: str, why: str) -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = [
        ("Source file (full name)", path.name),
        ("Source path", meta.get("path", str(path.relative_to(ROOT)))),
        ("Analysis status", "Complete"),
        ("Analyzed on", TODAY),
        ("", ""),
        ("What this file is", what),
        ("Why a Texas borrower should care", why),
        ("", ""),
    ]
    if meta.get("data_note"):
        rows.append(("Data sheet note", meta["data_note"]))
        rows.append(("", ""))
    return rows


def _decision_guide(items: list[tuple[str, str]]) -> list[tuple[str, object]]:
    rows = _section("Borrower decision guide")
    for q, a in items:
        rows.append((q, a))
    rows.append(("", ""))
    return rows


def _connections(items: list[tuple[str, str]]) -> list[tuple[str, object]]:
    rows = _section("How this connects to other files")
    for k, v in items:
        rows.append((k, v))
    rows.append(("", ""))
    return rows


def _caveats(items: list[str]) -> list[tuple[str, object]]:
    rows = _section("Data quality and caveats")
    for item in items:
        rows.append(("•", item))
    rows.append(("", ""))
    return rows


def _eda_institutions_definitions(path: Path, df: pd.DataFrame, meta: dict) -> list:
    defs = df if not df.empty else pd.read_csv(path, skiprows=1)
    borrower_fields = [
        "CERT", "NAME", "ASSET", "DEP", "CITY", "STALP", "ZIP", "WEBADDR",
        "CB", "BKCLASS", "ACTIVE", "OFFICES", "ROA", "ROE", "COUNTY", "CBSA",
    ]
    key = defs[defs["Variable Name"].isin(borrower_fields)][
        ["Variable Name", "Variable Label", "Variable Definition"]
    ].copy()
    key["Variable Definition"] = key["Variable Definition"].str.slice(0, 200) + "..."

    themes = pd.DataFrame([
        {"Theme": "Geography / market", "Variables": 20, "Borrower use": "Find banks in your city, county, or metro"},
        {"Theme": "Bank identity & contact", "Variables": 14, "Borrower use": "Legal name, website, branch count"},
        {"Theme": "Safety & status", "Variables": 18, "Borrower use": "Confirm bank is open, insured, community-focused"},
        {"Theme": "Size & performance", "Variables": 8, "Borrower use": "Compare bank scale, ROA/ROE context"},
        {"Theme": "Structural history", "Variables": 15, "Borrower use": "Merger/acquisition context (advanced)"},
    ])

    rows = _header(
        path, meta,
        "FDIC data dictionary for institution-level fields in BankFind / FFIEC CDR.",
        "Before comparing Texas banks, you need plain-English definitions for fields like CERT, ASSET, BKCLASS, and CB (community bank). This file explains what each column in institutions.csv means.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Grain", "One row per regulatory field definition"),
        ("Rows", len(defs)),
        ("Columns", "Variable Name, Variable Label, Variable Definition"),
        ("Format quirk", "Row 1 is a title row; headers start on row 2"),
        ("", ""),
    ]
    rows += _section("Key fields for borrowers")
    rows.append(("__table__", key))
    rows += _section("Content themes")
    rows.append(("__table__", themes))
    rows += _decision_guide([
        ("How do I identify a bank across the site?", "Use CERT (FDIC certificate number) — it joins to texas_filings, loan data, and borrower_site bank pages."),
        ("What does 'community bank' mean here?", "CB=1 marks FDIC community-bank research program members — often relationship-oriented lenders, Lenni's core audience."),
        ("Is the bank still operating?", "ACTIVE=1 means open and FDIC-insured; exclude ACTIVE=0 when building a shortlist."),
        ("How big is the bank?", "ASSET is total assets in thousands of dollars; divide by 1,000 for millions."),
    ])
    rows += _caveats([
        "Reference only — no loan balances or product specialization.",
        "TRACT row has a definition but missing Variable Label.",
        "Some codes (BKCLASS, TRUST) have long coded-value legends — read full definition text in data sheet.",
    ])
    rows += _connections([
        ("institutions.csv", "Live values for these field definitions"),
        ("texas_institutions.csv", "Texas subset keyed by RSSD id"),
        ("locations.csv", "Branch-level geography using overlapping CERT/CBSA fields"),
    ])
    return rows


def _eda_events_definitions(path: Path, df: pd.DataFrame, meta: dict) -> list:
    ev = df if not df.empty else pd.read_csv(path)
    merger_kw = ev[ev["Variable Label"].astype(str).str.contains("merg|acqui|fail|close", case=False, na=False)]
    rows = _header(
        path, meta,
        "FDIC data dictionary for institution structural events (mergers, failures, charter changes).",
        "Borrowers want stability. This explains event codes behind CHANGEC fields — useful if a bank on your shortlist recently merged or rebranded.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Grain", "One row per event-related variable"),
        ("Rows", len(ev)),
        ("Null labels", int(ev["Variable Label"].isna().sum())),
        ("", ""),
    ]
    rows += _section("Sample event fields (merger / acquisition related)")
    sample = merger_kw.head(12)[["Variable Name", "Variable Label"]]
    rows.append(("__table__", sample))
    rows += _decision_guide([
        ("Should I worry about a recent merger?", "Check institutions.csv CHANGEC1–CHANGEC15; look up codes here. Recent M&A can mean new credit policy or relationship manager turnover."),
        ("Does this show loan products?", "No — only institutional lifecycle events."),
    ])
    rows += _caveats([
        "Not needed for first-pass bank matching; use for diligence on finalists.",
        "Event codes are regulatory — pair with institutions.csv for actual values.",
    ])
    rows += _connections([
        ("institutions.csv", "CHANGEC1–CHANGEC15 columns reference these definitions"),
        ("institutions_definitions.csv", "Defines CHANGEC fields at summary level"),
    ])
    return rows


def _eda_institutions(path: Path, df: pd.DataFrame, meta: dict) -> list:
    inst = _load_full_csv("institutions.csv")
    tx = inst[inst["STALP"] == "TX"].copy()
    tx["ASSET_M"] = pd.to_numeric(tx["ASSET"], errors="coerce") / 1000
    active = tx[tx["ACTIVE"] == 1]
    icp = active[(active["ASSET_M"] >= 500) & (active["ASSET_M"] <= 2000)]

    bands = pd.cut(
        active["ASSET_M"],
        bins=[0, 100, 250, 500, 1000, 2000, 5000, 1e9],
        labels=["<$100M", "$100–250M", "$250–500M", "$500M–$1B", "$1–2B", "$2–5B", ">$5B"],
    ).value_counts().sort_index()

    bkclass = active["BKCLASS"].value_counts().head(8).reset_index()
    bkclass.columns = ["BKCLASS", "Active TX banks"]

    top_cities = (
        active.groupby(active["CITY"].str.strip().str.title())["CERT"]
        .count()
        .sort_values(ascending=False)
        .head(12)
        .reset_index()
    )
    top_cities.columns = ["City", "Active banks"]

    rows = _header(
        path, meta,
        "National FDIC institution registry (all U.S. banks) with 140 attributes per institution.",
        "Filter to Texas (STALP=TX) and ACTIVE=1 to build a shortlist. ASSET sizes the bank; CITY/COUNTY/CBSA locate it; WEBADDR links to the bank site; CB flags community lenders.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("National rows", f"{len(inst):,}"),
        ("Texas rows (all statuses)", f"{len(tx):,}"),
        ("Texas active & insured", f"{len(active):,}"),
        ("Texas active community banks (CB=1)", int((active["CB"] == 1).sum())),
        ("Lenni ICP band ($500M–$2B assets)", f"{len(icp):,}"),
        ("Banks with website on file", f"{active['WEBADDR'].notna().sum()} of {len(active)}"),
        ("", ""),
    ]
    rows += _section("Texas active banks by asset band")
    rows.append(("__table__", bands.reset_index().rename(columns={"index": "asset_band", "ASSET_M": "count"})))
    rows += _section("Texas active banks by charter class (BKCLASS)")
    rows.append(("__table__", bkclass))
    rows += _section("Top Texas cities by active bank count")
    rows.append(("__table__", top_cities))
    rows += _decision_guide([
        ("Which banks fit Lenni's sweet spot?", f"~{len(icp)} active Texas banks are $500M–$2B — see lenni_market_segments.csv and lenni_icp_prospect_list.csv for loan-mix detail."),
        ("How do I find banks near me?", "Filter CITY, COUNTY, or CBSA; confirm branch footprint in locations.csv."),
        ("Community bank vs regional?", "CB=1 and asset band <$2B often mean relationship lending; >$5B may have dedicated CRE desks but less local focus."),
    ])
    rows += _caveats([
        "ASSET is in thousands of dollars (FDIC convention).",
        "Includes inactive/closed institutions nationally — always filter ACTIVE=1 and STALP=TX for borrower shortlists.",
        "ROA/ROE are regulatory snapshots; not a substitute for credit policy conversations.",
    ])
    rows += _connections([
        ("institutions_definitions.csv", "Column definitions"),
        ("texas_institutions.csv", "Texas banks with latest Call Report filing metadata"),
        ("locations.csv", "Branch addresses for map-based search"),
    ])
    return rows


def _eda_locations(path: Path, df: pd.DataFrame, meta: dict) -> list:
    cities = []
    tx_count = 0
    main_off = 0
    for chunk in pd.read_csv(ROOT / "locations.csv", chunksize=100_000, low_memory=False):
        tx = chunk[chunk["STALP"] == "TX"] if "STALP" in chunk.columns else chunk
        tx_count += len(tx)
        if "MAINOFF" in tx.columns:
            main_off += (tx["MAINOFF"] == 1).sum()
        if "CITY" in tx.columns:
            cities.extend(tx["CITY"].str.strip().str.title().dropna().tolist())

    city_counts = (
        pd.Series(cities).value_counts().head(15).reset_index().rename(columns={"index": "City", "count": "Branch records"})
    )

    rows = _header(
        path, meta,
        "FDIC branch and office location file — every physical banking office in the U.S.",
        "Borrowers choose lenders partly on geography. This file shows where a bank actually has offices — critical for 'local relationship' community banks vs. banks headquartered elsewhere.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Texas branch/office records (estimated)", f"{tx_count:,}"),
        ("Texas HQ / main offices (MAINOFF=1)", main_off),
        ("Unique Texas cities with a branch", len(set(cities))),
        ("Columns in file", 30),
        ("", ""),
    ]
    rows += _section("Top 15 Texas cities by branch count")
    rows.append(("__table__", city_counts))
    rows += _decision_guide([
        ("Does this bank have a local office?", "Join CERT from institutions.csv; filter STALP=TX and your CITY."),
        ("HQ vs branch?", "MAINOFF=1 is headquarters; other rows are branches — ask for the commercial lending office, not just any branch."),
        ("Metro vs rural?", "Use CBSA/COUNTY fields to see if the bank covers your market or only has one distant branch."),
    ])
    rows += _caveats([
        "Large file (~78k rows nationally in full extract); data sheet may show a sample.",
        "Branch presence ≠ lending appetite for your deal type — pair with loan taxonomy files.",
    ])
    rows += _connections([
        ("institutions.csv", "Join on CERT"),
        ("locations_definitions.csv", "Field definitions for branch attributes"),
    ])
    return rows


def _eda_locations_definitions(path: Path, df: pd.DataFrame, meta: dict) -> list:
    ld = df if not df.empty else pd.read_csv(path)
    rows = _header(
        path, meta,
        "Data dictionary for FDIC branch/location fields (NAME, TITLE, DEFINITION format).",
        "Explains branch-level fields when reading locations.csv — e.g., MAINOFF, SERVTYPE, OFFTYPE.",
    )
    rows += _section("Dataset overview")
    rows += [("Rows", len(ld)), ("Columns", ", ".join(ld.columns)), ("", "")]
    rows += _section("All location field definitions")
    rows.append(("__table__", ld))
    rows += _decision_guide([
        ("Which fields matter for borrowers?", "MAINOFF (HQ), CITY, COUNTY, STALP, CBSA — geographic fit."),
    ])
    rows += _connections([("locations.csv", "Values for these definitions")])
    return rows


def _eda_sod_definitions(path: Path, df: pd.DataFrame, meta: dict) -> list:
    sod = df if not df.empty else pd.read_csv(path)
    rows = _header(
        path, meta,
        "Definitions for Summary of Deposits (SOD) survey variables — deposit market structure.",
        "Advanced diligence: shows how regulators classify branch deposit services. Less critical for CRE borrowers than loan taxonomy, but useful for deposit relationships and local market share research.",
    )
    rows += _section("Dataset overview")
    rows += [("Rows", len(sod)), ("", "")]
    rows += _section("Field definitions (sample)")
    rows.append(("__table__", sod.head(20)))
    rows += _caveats(["SOD is deposit-focused, not loan-product focused.", "Use after primary bank matching on loan data."])
    return rows


def _eda_texas_filings(path: Path, df: pd.DataFrame, meta: dict) -> list:
    fil = _load_full_csv("texas_filings.csv")
    periods = fil["reporting_period"].value_counts().sort_index().reset_index()
    periods.columns = ["reporting_period", "filing_count"]
    size_stats = fil["file_size_bytes"].describe()

    rows = _header(
        path, meta,
        "Index of downloaded Texas bank Call Report XBRL filings (one row per bank per period).",
        "Confirms which Texas banks filed regulatory reports and when — the raw source behind loan balances on the borrower site. Fresher filings = more current portfolio data.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Rows", f"{len(fil):,}"),
        ("Unique Texas banks (RSSD)", fil["id_rssd"].nunique()),
        ("Reporting periods covered", ", ".join(sorted(fil["reporting_period"].unique()))),
        ("Format", fil["facsimile_format"].value_counts().to_dict()),
        ("Median XBRL file size (bytes)", int(size_stats["50%"])),
        ("", ""),
    ]
    rows += _section("Filings per reporting period")
    rows.append(("__table__", periods))
    rows += _decision_guide([
        ("Is my bank's data current?", "Match id_rssd to texas_institutions.csv; check latest reporting_period."),
        ("Why do counts vary by quarter?", "New charters, mergers, and reporting exemptions change the Texas bank count (~352–377 per period)."),
    ])
    rows += _caveats([
        "Technical index — borrowers don't read XBRL directly; use derived files (texas_loans_labeled.csv).",
        "file_path points to local archive paths on the analyst machine.",
    ])
    rows += _connections([
        ("texas_institutions.csv", "Same bank universe with has_filed flag"),
        ("texas_loans_labeled.csv", "Parsed loan line items from these filings"),
    ])
    return rows


def _eda_texas_institutions(path: Path, df: pd.DataFrame, meta: dict) -> list:
    ti = _load_full_csv("texas_institutions.csv")
    filed = ti["has_filed"].value_counts().reset_index()
    filed.columns = ["has_filed", "count"]
    cities = ti["city"].str.strip().str.title().value_counts().head(12).reset_index()
    cities.columns = ["City", "Banks"]

    rows = _header(
        path, meta,
        "Texas bank roster with latest Call Report filing status (RSSD id, name, city, period).",
        "Your starting point for 'which Texas banks exist and filed recently.' Join to loan files on id_rssd to rank banks for your deal.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Texas banks listed", len(ti)),
        ("Unique cities", ti["city"].str.strip().nunique()),
        ("Filing type (Call Report)", ti["filing_type"].value_counts().to_dict()),
        ("Latest reporting period", ti["reporting_period"].mode().iloc[0]),
        ("", ""),
    ]
    rows += _section("Filing status")
    rows.append(("__table__", filed))
    rows += _section("Top cities by bank count")
    rows.append(("__table__", cities))
    rows += _decision_guide([
        ("How do I match to FDIC CERT?", "Use institutions.csv FED_RSSD / RSSD fields or borrower_site bank slugs — id_rssd is FFIEC internal id."),
        ("Only banks that filed?", "Filter has_filed=True for banks with extractable portfolio data."),
    ])
    rows += _connections([
        ("texas_filings.csv", "Detailed filing archive metadata"),
        ("texas_loans_labeled.csv", "Loan balances per bank"),
        ("lenni_icp_prospect_list.csv", "ICP banks with computed loan mix"),
    ])
    return rows


def _eda_texas_loans_labeled(path: Path, df: pd.DataFrame, meta: dict) -> list:
    cats = {}
    forms = {}
    periods = {}
    banks = set()
    n = 0
    for chunk in pd.read_csv(ROOT / "texas_loans_labeled.csv", chunksize=200_000, low_memory=False):
        n += len(chunk)
        banks.update(chunk["id_rssd"].unique())
        for k, v in chunk["mdrm_category"].value_counts().items():
            cats[k] = cats.get(k, 0) + v
        for k, v in chunk["reporting_form"].value_counts().items():
            forms[k] = forms.get(k, 0) + v
        for k, v in chunk["reporting_period"].value_counts().items():
            periods[k] = periods.get(k, 0) + v

    cat_df = pd.DataFrame(sorted(cats.items(), key=lambda x: -x[1]), columns=["mdrm_category", "rows"])[:8]
    form_df = pd.DataFrame(sorted(forms.items(), key=lambda x: -x[1]), columns=["reporting_form", "rows"])[:8]
    period_df = pd.DataFrame(sorted(periods.items(), key=lambda x: -x[1]), columns=["reporting_period", "rows"])

    rows = _header(
        path, meta,
        "Bank-level regulatory loan line items parsed from Texas Call Reports — the core quantitative file for matching borrowers to lenders.",
        "Shows what each Texas bank actually holds on its balance sheet (CRE, C&I, multifamily, ag, etc.). Use this to rank banks by portfolio fit for your loan type.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Total rows (full file)", f"{n:,}"),
        ("Texas banks represented", len(banks)),
        ("Grain", "Bank × reporting period × MDRM regulatory line item"),
        ("Key columns", "id_rssd, institution_name, mdrm_code, line_description, value_num, mdrm_category"),
        ("", ""),
    ]
    rows += _section("Rows by regulatory category")
    rows.append(("__table__", cat_df))
    rows += _section("Rows by Call Report form (bank size)")
    rows.append(("__table__", form_df))
    rows += _section("Rows by reporting period")
    rows.append(("__table__", period_df))
    rows += _decision_guide([
        ("How do I find multifamily lenders?", "Join mdrm_code to texas_mdrm_loan_taxonomy.csv where Loan Product Category = Multifamily; filter value_num > 0."),
        ("Can I compare two banks?", "Filter same reporting_period and sum value_num for your product's MDRM codes."),
        ("What is a typical match signal?", "Higher non-zero balance in your product category + geographic fit from institutions/locations."),
    ])
    rows += _caveats([
        "Regulatory line items ≠ named loan products on bank websites — taxonomy file maps codes to borrower language.",
        "Values are in reported units (usually thousands USD); check unit_ref column.",
        "Large file (~938k rows) — data sheet shows sample rows only.",
    ])
    rows += _connections([
        ("texas_mdrm_loan_taxonomy.csv", "Maps MDRM codes to Lenni loan product categories"),
        ("texas_loan_products_mdrm_catalog.csv", "Full catalog of possible MDRM codes"),
        ("lenni_icp_prospect_list.csv", "Pre-aggregated loan mix for ICP banks"),
    ])
    return rows


def _eda_loan_catalog(path: Path, df: pd.DataFrame, meta: dict) -> list:
    cat = _load_full_csv("texas_loan_products_mdrm_catalog.csv")
    in_tx = (cat["in_texas_data"].astype(str).str.lower() == "yes").sum()
    by_cat = cat.groupby("mdrm_category").size().reset_index(name="mdrm_codes")
    tx_only = cat[cat["in_texas_data"].astype(str).str.lower() == "yes"]
    tx_cat = tx_only["mdrm_category"].value_counts().reset_index()
    tx_cat.columns = ["mdrm_category", "codes_in_texas_data"]

    rows = _header(
        path, meta,
        "Master catalog of ~24k MDRM regulatory line items with flags for Texas Call Report appearance.",
        "The universe of measurable loan types regulators allow. Only ~1,611 codes appear in Texas data — those are what you can actually use to score banks today.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Total MDRM codes cataloged", f"{len(cat):,}"),
        ("Codes seen in Texas filings (in_texas_data=yes)", in_tx),
        ("Texas-usable share", f"{100*in_tx/len(cat):.1f}%"),
        ("", ""),
    ]
    rows += _section("All catalog codes by category")
    rows.append(("__table__", by_cat))
    rows += _section("Texas-observed codes by category")
    rows.append(("__table__", tx_cat))
    rows += _decision_guide([
        ("Why so many codes but few in Texas?", "National catalog includes credit unions, holding companies, and schedules Texas community banks don't file."),
        ("Which codes matter for CRE?", "Cross-reference in_texas_data=yes with texas_mdrm_loan_taxonomy.csv borrower categories."),
    ])
    rows += _connections([
        ("texas_loans_labeled.csv", "Actual values for Texas-observed codes"),
        ("texas_mdrm_loan_taxonomy.csv", "Borrower-friendly labels on top of MDRM codes"),
    ])
    return rows


def _eda_taxonomy_csv(path: Path, df: pd.DataFrame, meta: dict) -> list:
    tax = _load_full_csv("texas_mdrm_loan_taxonomy.csv")
    borrower_cats = [
        "Multifamily (5+ units)", "Investor CRE (income property)", "Owner-Occupied CRE",
        "Commercial Construction", "Commercial & Industrial (C&I)", "Agricultural & Farmland",
    ]
    br = tax[tax["Loan Product Category"].isin(borrower_cats)]
    agg = br.groupby("Loan Product Category").agg(
        regulatory_line_items=("Regulatory Line Item Code", "count"),
        median_TX_banks_reporting=("Number of Texas Banks Reporting", "median"),
        median_nonzero_balances=("Texas Observations with Non-Zero Balance", "median"),
        in_borrower_site_catalog=("Listed in Borrower Product Catalog", lambda s: int((s == "Yes").sum())),
    ).reset_index()

    cre = tax[tax["Loan Product Category"] == "Investor CRE (income property)"]
    cre_sub = (
        cre.groupby("Loan Product Subcategory", dropna=False)["Number of Texas Banks Reporting"]
        .max()
        .sort_values(ascending=False)
        .head(8)
        .reset_index()
    )
    cre_sub.columns = ["CRE sub-type", "Max TX banks reporting"]

    rows = _header(
        path, meta,
        "Lenni loan product taxonomy — maps FFIEC MDRM codes to borrower-friendly categories (multifamily, investor CRE, C&I, etc.).",
        "The most important reference for borrowers: translates regulatory jargon into 'does this bank do my kind of loan?' with Texas coverage stats per product line.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Regulatory line items mapped", len(tax)),
        ("Borrower-facing product categories", len(tax["Loan Product Category"].dropna().unique())),
        ("Listed on borrower site catalog", int((tax["Listed in Borrower Product Catalog"] == "Yes").sum())),
        ("", ""),
    ]
    rows += _section("Texas coverage by borrower product category")
    rows.append(("__table__", agg))
    rows += _section("Investor CRE — sub-types with widest Texas bank coverage")
    rows.append(("__table__", cre_sub))
    rows += _decision_guide([
        ("Multifamily vs 1–4 family?", "1–4 Family Residential has most line items but different borrower profile; multifamily (5+) is Lenni CRE focus."),
        ("What does 'Number of Texas Banks Reporting' mean?", "How many Texas banks file a non-blank value for that line — higher = more common product on Texas balance sheets."),
        ("Non-zero balance count?", "How often banks report an actual outstanding balance — stronger signal of active lending vs. zero placeholder."),
    ])
    rows += _caveats([
        "Portfolio share ≠ underwriting appetite for your specific deal.",
        "Regulatory categories don't capture policy (LTV, recourse, minimum loan size).",
        "Only 10 lines flagged 'Listed in Borrower Product Catalog' at line-item level — site uses rolled-up categories.",
    ])
    rows += _connections([
        ("texas_mdrm_loan_taxonomy.xlsx", "Same data plus Borrower View plain-English sheet"),
        ("texas_loans_labeled.csv", "Dollar values per bank for each MDRM code"),
        ("borrower_site loan product pages", "Content generated from taxonomy + rankings"),
    ])
    return rows


def _eda_taxonomy_xlsx(path: Path, df: pd.DataFrame, meta: dict) -> list:
    bv = pd.read_excel(ROOT / path.name, sheet_name="Borrower View")
    readme = pd.read_excel(ROOT / path.name, sheet_name="Read Me")

    rows = _header(
        path, meta,
        "Excel workbook packaging the loan taxonomy for borrowers — includes 'Borrower View' plain-English product summaries.",
        "Designed for non-bankers: each row explains a loan category in plain English, who it's for, and how many Texas banks report it.",
    )
    rows += _section("Workbook sheets")
    rows.append(("__table__", readme.rename(columns={"Topic": "Sheet / topic", "Detail": "Description"})))
    rows += _section("Borrower View — product guide (full table)")
    rows.append(("__table__", bv))
    rows += _decision_guide([
        ("Which sheet should I read first?", "Borrower View — 10 product rows with 'Who This Is For' and Lenni site links."),
        ("How is this different from the CSV?", "Same Loan Taxonomy Data plus glossary and data dictionary tabs for analysts."),
    ])
    rows += _connections([
        ("texas_mdrm_loan_taxonomy.csv", "Machine-readable same taxonomy"),
        ("borrower_site/", "Learn More on Lenni links point to generated HTML guides"),
    ])
    return rows


def _eda_ubpr_reference(path: Path, df: pd.DataFrame, meta: dict) -> list:
    lp = pd.read_excel(ROOT / path.name, sheet_name="Loan Products")
    tmpl = pd.read_excel(ROOT / path.name, sheet_name="Template Library")
    by_ubpr = lp["UBPR Category"].value_counts().reset_index()
    by_ubpr.columns = ["UBPR Category", "Loan product rows"]

    rows = _header(
        path, meta,
        "Lenni internal UBPR-aligned loan type reference — maps Uniform Bank Performance Report categories to FDIC Call Report fields.",
        "Helps borrowers understand the industry-standard loan hierarchy (construction, CRE, C&I, ag) and which regulatory fields underpin each product on the site.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Loan product rows", len(lp)),
        ("UBPR categories", lp["UBPR Category"].nunique()),
        ("Underwriting templates planned", len(tmpl)),
        ("Workbook sheets", "About, Build Math, Template Library, Loan Products, FDIC Fields, Pitfalls"),
        ("", ""),
    ]
    rows += _section("Loan products by UBPR category")
    rows.append(("__table__", by_ubpr))
    rows += _section("Template library (build sequence)")
    rows.append(("__table__", tmpl.head(15)))
    rows += _decision_guide([
        ("I'm a multifamily borrower — where in UBPR?", "Loans secured by real estate → multifamily schedules; cross-walk to taxonomy Multifamily (5+ units)."),
        ("Owner-occupied vs investor?", "UBPR and taxonomy both split these — critical for matching (different underwriters at the bank)."),
    ])
    rows += _connections([
        ("texas_mdrm_loan_taxonomy.csv", "Production taxonomy used on live site"),
        ("ONLY_TEXAS_SINCE_2025/content/loan_products.yaml", "27 sub-type content pages on borrower site"),
    ])
    return rows


def _eda_all_financial_reports(path: Path, df: pd.DataFrame, meta: dict) -> list:
    rows = _header(
        path, meta,
        "FFIEC/FDIC API reference workbook — URLs and variable names for pulling financial report fields programmatically.",
        "Not a borrower-facing dataset. Useful for analysts building fresh extracts; borrowers should use texas_loans_labeled.csv and bank profile pages instead.",
    )
    rows += _section("Dataset overview")
    rows += [
        ("Combined non-empty sheets", meta.get("xlsx_sheets_with_data", [])),
        ("Purpose", "API endpoint templates for Total Assets, loan schedules, demographics, ratios"),
        ("", ""),
    ]
    rows += _decision_guide([
        ("Should a borrower open this file?", "No — use texas_mdrm_loan_taxonomy.xlsx 'Borrower View' or the live Lenni borrower site."),
        ("When is this useful?", "When regenerating Texas extracts or validating MDRM field coverage."),
    ])
    rows += _connections([
        ("texas_filings.csv", "Downloaded filings that feed the pipeline"),
        ("texas_loans_labeled.csv", "Parsed output borrowers actually consume"),
    ])
    return rows


def _eda_asset_band_counts(path: Path, df: pd.DataFrame, meta: dict) -> list:
    ab = df if not df.empty else pd.read_csv(path)
    total = ab["count"].sum()
    ab = ab.copy()
    ab["pct_of_banks"] = (100 * ab["count"] / total).round(1).astype(str) + "%"

    rows = _header(
        path, meta,
        "Distribution of Texas banks by total asset size band (latest analysis snapshot).",
        "Borrowers and banks both care about scale: a $50M bank vs $1.5B bank have different minimum loan sizes and CRE appetite. Lenni targets $500M–$2B.",
    )
    rows += _section("Texas banks by asset band")
    rows.append(("__table__", ab))
    rows += _decision_guide([
        ("Where is Lenni's ICP?", "$500M–$1B (68) + $1–2B (37) = 105 banks — matches lenni_market_segments.csv."),
        ("I'm seeking a $8M CRE loan — who fits?", "Banks in $250M+ bands more commonly originate commercial-sized credits; verify with loan mix."),
    ])
    rows += _connections([
        ("summary_statistics_latest.csv", "Loan portfolio stats within these bands"),
        ("lenni_icp_prospect_list.csv", "Named banks in $500M–$2B with CRE/C&I ratios"),
    ])
    return rows


def _eda_icp_prospect_list(path: Path, df: pd.DataFrame, meta: dict) -> list:
    icp = df if not df.empty else pd.read_csv(path)
    icp = icp.copy()
    icp["total_assets_M"] = icp["total_assets"] / 1e6
    icp["cre_pct"] = (100 * icp["cre_to_loans"]).round(1)

    summary = pd.DataFrame([
        {"metric": "Banks in list", "value": len(icp)},
        {"metric": "Median total assets", "value": f"${icp['total_assets'].median()/1e6:,.0f}M"},
        {"metric": "Median loan-to-asset ratio", "value": f"{icp['loan_to_asset_ratio'].median():.0%}"},
        {"metric": "Median CRE % of loans", "value": f"{icp['cre_to_loans'].median():.0%}"},
        {"metric": "Median C&I % of loans", "value": f"{icp['ci_to_loans'].median():.0%}"},
    ])

    top_cre = icp.nlargest(10, "cre_to_loans")[
        ["name", "city", "total_assets_M", "cre_pct", "loan_to_asset_ratio"]
    ].round(2)

    top_ci = icp.nlargest(10, "ci_to_loans")[
        ["name", "city", "total_assets_M", "ci_to_loans", "loan_to_asset_ratio"]
    ].round(2)
    top_ci["ci_pct"] = (100 * top_ci["ci_to_loans"]).round(1)
    top_ci = top_ci.drop(columns=["ci_to_loans"])

    rows = _header(
        path, meta,
        "Ranked list of 105 Lenni ICP Texas banks ($500M–$2B) with computed loan mix — CRE proxy, C&I, loan-to-asset.",
        "Actionable shortlist for borrowers: banks in Lenni's sweet spot with measurable portfolio tilt toward CRE or C&I.",
    )
    rows += _section("Portfolio summary (ICP banks)")
    rows.append(("__table__", summary))
    rows += _section("Top 10 ICP banks by CRE concentration (% of total loans)")
    rows.append(("__table__", top_cre))
    rows += _section("Top 10 ICP banks by C&I concentration (% of total loans)")
    rows.append(("__table__", top_ci))
    rows += _decision_guide([
        ("I'm buying an industrial building — start where?", "Sort by cre_to_loans and filter cities near your asset; confirm Investor CRE lines in taxonomy."),
        ("I need a working capital line?", "Prioritize high ci_to_loans banks — see top C&I table above."),
        ("Does high CRE % mean they'll approve my deal?", "No — it means CRE is a large share of what they already lend; still verify policy with a lender."),
    ])
    rows += _caveats([
        "cre_proxy_total is a regulatory aggregate, not exact 'investor CRE' from taxonomy.",
        "Snapshot from latest Call Report period in pipeline — ask bank for current appetite.",
    ])
    rows += _connections([
        ("asset_band_counts.csv", "How many banks fall in each size bucket"),
        ("texas_loans_labeled.csv", "Underlying line-item detail per bank"),
    ])
    return rows


def _eda_market_segments(path: Path, df: pd.DataFrame, meta: dict) -> list:
    seg = df if not df.empty else pd.read_csv(path)
    total = seg["Banks_latest"].sum()
    seg = seg.copy()
    seg["pct"] = (100 * seg["Banks_latest"] / total).round(1).astype(str) + "%"

    rows = _header(
        path, meta,
        "Texas bank counts segmented by asset size relative to Lenni ICP ($500M–$2B).",
        "Quick market sizing: how many Texas banks are in Lenni's target range vs. smaller or larger institutions.",
    )
    rows += _section("Market segments")
    rows.append(("__table__", seg))
    rows += _decision_guide([
        ("How many banks does Lenni focus on?", "105 in ICP ($500M–$2B) — about 30% of Texas banks with asset data."),
        ("Should borrowers avoid banks >$2B?", "Not necessarily — they may have CRE desks but less community-bank relationship model."),
    ])
    rows += _connections([
        ("asset_band_counts.csv", "Detailed band breakdown"),
        ("lenni_icp_prospect_list.csv", "Named ICP banks"),
    ])
    return rows


def _eda_summary_statistics(path: Path, df: pd.DataFrame, meta: dict) -> list:
    stats = df if not df.empty else pd.read_csv(path)
    rows = _header(
        path, meta,
        "Summary statistics (mean, median, min, max) for Texas bank loan portfolios — latest reporting period.",
        "Benchmark your target bank: is their loan book larger or smaller than peer medians? How CRE-heavy vs typical?",
    )
    rows += _section("Distribution of key metrics (Texas banks with data)")
    rows.append(("__table__", stats))
    rows += _decision_guide([
        ("Median loan-to-asset is ~62% — what does that mean?", "Typical Texas bank lends about three-fifths of its balance sheet; higher ratios = more lending-intensive."),
        ("Median CRE proxy ~$116M vs mean ~$426M?", "A few large banks skew the mean; compare your bank to median for 'typical community bank' context."),
    ])
    rows += _connections([
        ("lenni_icp_prospect_list.csv", "Per-bank values behind these aggregates"),
        ("texas_loans_labeled.csv", "Line-item source data"),
    ])
    return rows


def _eda_generic(path: Path, df: pd.DataFrame, meta: dict) -> list:
    rows = _header(path, meta, "Project data file.", "See column profile below.")
    if not df.empty:
        profile = []
        for col in df.columns:
            s = df[col]
            profile.append({
                "column": col,
                "dtype": str(s.dtype),
                "null_pct": round(100 * s.isna().mean(), 2),
                "unique": int(s.nunique(dropna=True)),
            })
        rows += _section("Column profile")
        rows.append(("__table__", pd.DataFrame(profile)))
    return rows
