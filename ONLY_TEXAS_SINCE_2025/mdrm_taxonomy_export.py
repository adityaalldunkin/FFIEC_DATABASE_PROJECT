"""Plain-English column labels and data dictionary for the loan taxonomy export."""

from __future__ import annotations

import csv
from pathlib import Path

from loan_product_loader import load_parents

# Lean public export: one fact per column, no duplicates derivable from other fields.
PLAIN_HEADERS: dict[str, str] = {
    "mdrm_code": "Regulatory Line Item Code",
    "office_scope": "Reporting Office Scope",
    "loan_type": "Loan Product Category",
    "sub_type": "Loan Product Subcategory",
    "what_this_line_measures": "What This Line Measures",
    "collateral_class": "Collateral or Security Type",
    "item_name": "Official Line Item Title",
    "mdrm_description": "Official Line Item Definition",
    "schedule_location": "Regulatory Schedule Location",
    "line_item_value_type": "Line Item Value Type",
    "bank_size_form_type": "Bank Size Form Type",
    "analysis_column_name": "Analysis Dataset Column Name",
    "in_product_catalog": "Listed in Borrower Product Catalog",
    "appears_in_texas_filings": "Appears in Texas Bank Filings",
    "texas_banks_reporting": "Number of Texas Banks Reporting",
    "texas_nonzero_balances": "Texas Observations with Non-Zero Balance",
    "federal_reserve_dictionary_link": "Federal Reserve Dictionary Link",
}

EXPORT_FIELD_ORDER: list[str] = list(PLAIN_HEADERS.keys())

REPORTING_DIMENSION_LABELS = {
    "product_balance": "Outstanding loan balance by product type",
    "portfolio_total": "Total loans or portfolio-level aggregate",
    "maturity_repricing": "Loan maturity or interest-rate repricing bucket",
    "credit_quality": "Past-due, nonaccrual, or troubled loan status",
    "credit_loss_flow": "Charge-offs, recoveries, or provision for loan losses",
    "income_statement": "Interest income or income-statement loan amount",
    "count": "Number of loans (count, not dollars)",
    "memorandum": "Supplemental memorandum or supporting detail",
}

YES_NO = {"yes": "Yes", "no": "No", "": ""}

# Regulatory title keywords that are not headline loan balances (skip for borrower view).
_SKIP_TITLE_KEYWORDS = ("NONACCRUAL", "PAST DUE", "PAST-DUE", "CHARGE-OFF", "NUMBER OF", "PROVISION")

# When YAML MDRM codes point at non-balance lines, use these headline codes instead.
BORROWER_PRIMARY_BY_KEY: dict[str, str] = {
    "res": "RCON1403",
    "inv": "RCONF161",
    "con": "RCONF159",
}

# Extra headline rows not tied to a single YAML parent.
BORROWER_EXTRA_PRODUCTS: list[dict[str, str | list[str]]] = [
    {
        "codes": ["RCON2122", "RCFD2122"],
        "loan_type": "Total bank lending",
        "plain_english": (
            "The bank's entire loan and lease portfolio — all product types combined."
        ),
        "who_its_for": (
            "Anyone comparing overall bank size before drilling into a specific niche."
        ),
        "slug": "",
    },
    {
        "codes": ["RCON1545"],
        "loan_type": "Consumer — credit cards",
        "plain_english": "Credit card balances the bank holds on its books.",
        "who_its_for": "Retail and consumer lending (not typical commercial real estate borrowers).",
        "slug": "",
    },
    {
        "codes": ["RCON1583"],
        "loan_type": "Consumer — other loans",
        "plain_english": "Other consumer installment loans excluding credit cards.",
        "who_its_for": "Personal and household borrowing outside of mortgage portfolios.",
        "slug": "",
    },
    {
        "codes": ["RCON1754"],
        "loan_type": "Lease financing",
        "plain_english": "Equipment and property leases the bank finances and keeps on balance sheet.",
        "who_its_for": "Businesses financing equipment or assets through bank-held leases.",
        "slug": "",
    },
]

BORROWER_HEADERS: dict[str, str] = {
    "loan_type": "Loan Product Category",
    "plain_english": "In Plain English",
    "who_its_for": "Who This Is For",
    "regulatory_code": "Regulatory Line Item Code (Reference)",
    "available_texas": "Available from Texas Banks",
    "texas_banks_active": "Texas Banks Reporting This Category",
    "learn_more": "Learn More on Lenni",
}

BORROWER_FIELD_ORDER: list[str] = list(BORROWER_HEADERS.keys())


def humanize_yes_no(value: str) -> str:
    return YES_NO.get((value or "").strip().lower(), value)


def humanize_snake_case(value: str) -> str:
    if not value:
        return ""
    return value.replace("_", " ").title()


def clean_description(text: str) -> str:
    return (text or "").replace("&#x0D;", " ").replace("\r", " ").strip()


def _title_is_headline_balance(item_name: str) -> bool:
    upper = (item_name or "").upper()
    return not any(k in upper for k in _SKIP_TITLE_KEYWORDS)


def _resolve_internal(
    parent_key: str,
    codes: list[str],
    by_code: dict[str, dict[str, str]],
) -> dict[str, str] | None:
    forced = BORROWER_PRIMARY_BY_KEY.get(parent_key)
    if forced and forced in by_code:
        return by_code[forced]
    return _pick_best_internal(codes, by_code)


def _pick_best_internal(codes: list[str], by_code: dict[str, dict[str, str]]) -> dict[str, str] | None:
    best: dict[str, str] | None = None
    best_score = -1
    for code in codes:
        row = by_code.get(code)
        if not row or not _title_is_headline_balance(row.get("item_name", "")):
            continue
        try:
            score = int(row.get("texas_nonzero_obs") or 0)
        except (TypeError, ValueError):
            score = 0
        if score > best_score:
            best_score = score
            best = row
    return best


def build_borrower_rows(internal_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Curated one-row-per-product view for borrowers (no regulatory jargon columns)."""
    by_code = {r["mdrm_code"]: r for r in internal_rows}
    seen_codes: set[str] = set()
    out: list[dict[str, str]] = []

    for parent in load_parents():
        internal = _resolve_internal(
            parent["key"],
            list(parent.get("mdrm") or []),
            by_code,
        )
        if not internal:
            continue
        code = internal["mdrm_code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        slug = parent.get("slug", "")
        out.append(
            {
                "loan_type": parent["name"],
                "plain_english": parent.get("short", ""),
                "who_its_for": parent.get("cat", ""),
                "regulatory_code": code,
                "available_texas": humanize_yes_no(internal.get("in_texas_data", "")),
                "texas_banks_active": internal.get("texas_bank_count", ""),
                "learn_more": f"loan-types/{slug}.html" if slug else "",
            }
        )

    for extra in BORROWER_EXTRA_PRODUCTS:
        codes = list(extra["codes"])  # type: ignore[arg-type]
        internal = _pick_best_internal(codes, by_code)
        if not internal:
            continue
        code = internal["mdrm_code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        slug = str(extra.get("slug") or "")
        out.append(
            {
                "loan_type": str(extra["loan_type"]),
                "plain_english": str(extra["plain_english"]),
                "who_its_for": str(extra["who_its_for"]),
                "regulatory_code": code,
                "available_texas": humanize_yes_no(internal.get("in_texas_data", "")),
                "texas_banks_active": internal.get("texas_bank_count", ""),
                "learn_more": f"loan-types/{slug}.html" if slug else "",
            }
        )

    out.sort(key=lambda r: r["loan_type"])
    return out


def to_public_row(internal: dict[str, str]) -> dict[str, str]:
    """Map internal row keys to lean plain-English export columns."""
    dimension = internal.get("reporting_dimension", "")
    metric = internal.get("metric_column", "")
    form = internal.get("ffiec_form_size", "") or internal.get("reporting_form_primary", "")

    return {
        "mdrm_code": internal.get("mdrm_code", ""),
        "office_scope": internal.get("office_scope", ""),
        "loan_type": internal.get("loan_type", ""),
        "sub_type": internal.get("sub_type", ""),
        "what_this_line_measures": REPORTING_DIMENSION_LABELS.get(dimension, dimension),
        "collateral_class": internal.get("collateral_class", ""),
        "item_name": internal.get("item_name", ""),
        "mdrm_description": clean_description(internal.get("mdrm_description", "")),
        "schedule_location": internal.get("schedule", ""),
        "line_item_value_type": internal.get("item_type_label") or internal.get("item_type", ""),
        "bank_size_form_type": form if form else internal.get("reporting_form", ""),
        "analysis_column_name": humanize_snake_case(metric) if metric else "",
        "in_product_catalog": humanize_yes_no(internal.get("explicit_taxonomy_mapping", "")),
        "appears_in_texas_filings": humanize_yes_no(internal.get("in_texas_data", "")),
        "texas_banks_reporting": internal.get("texas_bank_count", ""),
        "texas_nonzero_balances": internal.get("texas_nonzero_obs", ""),
        "federal_reserve_dictionary_link": internal.get("mdrm_lookup_url", ""),
    }


def public_headers() -> list[str]:
    return [PLAIN_HEADERS[key] for key in EXPORT_FIELD_ORDER]


def write_public_csv(path: Path, rows: list[dict[str, str]]) -> None:
    headers = public_headers()
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for internal in rows:
            public = to_public_row(internal)
            writer.writerow({PLAIN_HEADERS[k]: public[k] for k in EXPORT_FIELD_ORDER})


def write_workbook(path: Path, rows: list[dict[str, str]]) -> None:
    import pandas as pd

    public_rows = [to_public_row(r) for r in rows]
    data_df = pd.DataFrame(public_rows, columns=EXPORT_FIELD_ORDER)
    data_df.columns = public_headers()

    dict_df = pd.DataFrame(DATA_DICTIONARY)
    dict_df = dict_df.rename(
        columns={
            "column_header": "Column Header",
            "data_type": "Data Type",
            "example": "Example",
            "description": "Description",
            "how_to_use": "How to Use This Field",
        }
    )

    glossary_df = pd.DataFrame(GLOSSARY_ROWS)
    glossary_df = glossary_df.rename(columns={"term": "Term", "definition": "Definition"})

    borrower_rows = build_borrower_rows(rows)
    borrower_df = pd.DataFrame(borrower_rows, columns=BORROWER_FIELD_ORDER)
    borrower_df.columns = [BORROWER_HEADERS[k] for k in BORROWER_FIELD_ORDER]

    borrower_dict_df = pd.DataFrame(BORROWER_DATA_DICTIONARY)
    borrower_dict_df = borrower_dict_df.rename(
        columns={
            "column_header": "Column Header",
            "data_type": "Data Type",
            "example": "Example",
            "description": "Description",
            "how_to_use": "How to Use This Field",
        }
    )

    intro = pd.DataFrame(
        [
            {
                "Topic": "About this workbook",
                "Detail": (
                    "This file maps bank Call Report line items to Lenni loan product categories. "
                    "'Borrower View' is the best starting point if you are not a data analyst. "
                    "'Loan Taxonomy Data' is the full technical reference (17 columns). "
                    "Each sheet has its own data dictionary."
                ),
            },
            {
                "Topic": "Start here (borrowers and sales)",
                "Detail": (
                    f"Open 'Borrower View' ({len(borrower_rows)} rows) — one row per loan product "
                    "with plain-English descriptions. Use 'Borrower Data Dictionary' to understand "
                    "those columns. Find specific Texas banks in separate bank profile files, not here."
                ),
            },
            {
                "Topic": "Row filter",
                "Detail": (
                    f"Only rows with a Loan Product Category are included ({len(rows):,} lines). "
                    "Lines without a product mapping were removed."
                ),
            },
            {
                "Topic": "Dollar amounts",
                "Detail": (
                    "Call Report financial amounts are reported in thousands of United States "
                    "dollars. This applies to all rows where Line Item Value Type is "
                    "'Financial / reported amount'."
                ),
            },
            {
                "Topic": "Columns removed to reduce redundancy",
                "Detail": (
                    "Reporting prefix and line number (embedded in Regulatory Line Item Code); "
                    "duplicate marketing summaries per product category; schedule part columns "
                    "(merged into Regulatory Schedule Location); duplicate reporting-form columns; "
                    "Included in Bank Analysis Summary (use Analysis Dataset Column Name instead); "
                    "Total Texas Filing Observations (use Non-Zero Balance count); effective dates, "
                    "confidentiality flags, and dollar-unit labels (see Federal Reserve Dictionary Link)."
                ),
            },
        ]
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        intro.to_excel(writer, sheet_name="Read Me", index=False)
        borrower_df.to_excel(writer, sheet_name="Borrower View", index=False)
        borrower_dict_df.to_excel(writer, sheet_name="Borrower Data Dictionary", index=False)
        data_df.to_excel(writer, sheet_name="Loan Taxonomy Data", index=False)
        dict_df.to_excel(writer, sheet_name="Data Dictionary", index=False)
        glossary_df.to_excel(writer, sheet_name="Term Glossary", index=False)

        for sheet in writer.sheets.values():
            for column in sheet.columns:
                max_len = 0
                col_letter = column[0].column_letter
                for cell in column:
                    if cell.value:
                        max_len = max(max_len, min(len(str(cell.value)), 80))
                sheet.column_dimensions[col_letter].width = max(12, max_len + 2)


DATA_DICTIONARY: list[dict[str, str]] = [
    {
        "column_header": "Regulatory Line Item Code",
        "data_type": "Text",
        "example": "RCON1460",
        "description": (
            "Unique eight-character identifier for this Call Report line. The first four "
            "characters are the reporting series (for example RCON for domestic offices of "
            "larger banks, RCFD for community-bank series). The remainder is the line number."
        ),
        "how_to_use": "Primary key. Use to join bank filing data and to open the Federal Reserve dictionary link.",
    },
    {
        "column_header": "Reporting Office Scope",
        "data_type": "Text",
        "example": "Domestic offices (FFIEC 031 larger banks)",
        "description": (
            "Whose balances this line covers—typically domestic United States offices versus "
            "the consolidated domestic series used by many community banks."
        ),
        "how_to_use": "Do not mix RCON and RCFD balances without checking they refer to the same bank and scope.",
    },
    {
        "column_header": "Loan Product Category",
        "data_type": "Text",
        "example": "Multifamily (5+ units)",
        "description": (
            "Lenni borrower-facing product family this line maps to: Multifamily, Investor "
            "Commercial Real Estate, Construction, Commercial and Industrial, and so on."
        ),
        "how_to_use": "Group and filter rows by lending product focus.",
    },
    {
        "column_header": "Loan Product Subcategory",
        "data_type": "Text (often empty)",
        "example": "Apartment acquisition loan",
        "description": (
            "More specific borrower product when keyword matching found one (bridge, refinance, "
            "working capital, and so on). Empty when the line is a regulatory split (maturity, "
            "past-due status) rather than a product."
        ),
        "how_to_use": "Optional detail; blank is normal for most technical lines.",
    },
    {
        "column_header": "What This Line Measures",
        "data_type": "Text",
        "example": "Outstanding loan balance by product type",
        "description": (
            "Purpose of the line: product balance, portfolio total, maturity bucket, credit "
            "quality, loan count, income-statement amount, or memorandum detail."
        ),
        "how_to_use": (
            "Critical for analysis. Use 'Outstanding loan balance by product type' for loan-mix "
            "charts; exclude maturity and credit-quality rows from mix totals."
        ),
    },
    {
        "column_header": "Collateral or Security Type",
        "data_type": "Text (often empty)",
        "example": "Multifamily (5+ units)",
        "description": "Simplified collateral label inferred from the official title and definition.",
        "how_to_use": "Secondary grouping when product category is broad.",
    },
    {
        "column_header": "Official Line Item Title",
        "data_type": "Text",
        "example": "REAL ESTATE LOANS SECURED BY MULTI-FAMILY (5 OR MORE) RESIDENTIAL PROPERTIES",
        "description": "Short regulatory title exactly as defined by the Federal Reserve.",
        "how_to_use": "Search by regulatory wording.",
    },
    {
        "column_header": "Official Line Item Definition",
        "data_type": "Long text (often empty)",
        "example": "Includes all permanent nonfarm residential loans secured by...",
        "description": "Full Call Report instructions for what to include in this line.",
        "how_to_use": "Read when you need precise inclusion rules.",
    },
    {
        "column_header": "Regulatory Schedule Location",
        "data_type": "Text (often empty)",
        "example": "Schedule RC-C Part I item 1.a",
        "description": "Where the line appears on the Call Report form, when parseable from the definition.",
        "how_to_use": "Locate the line on official schedule PDFs.",
    },
    {
        "column_header": "Line Item Value Type",
        "data_type": "Text",
        "example": "Financial / reported amount",
        "description": (
            "Kind of value filed: reported dollar amount, derived amount, loan count, rate, "
            "or percentage. Dollar amounts use thousands of United States dollars."
        ),
        "how_to_use": "Never sum count rows with dollar rows.",
    },
    {
        "column_header": "Bank Size Form Type",
        "data_type": "Text",
        "example": "FFIEC 031 (larger banks)",
        "description": "Which Call Report form this line primarily applies to (larger bank Form 031 or community Form 041).",
        "how_to_use": "Segment analysis by institution size.",
    },
    {
        "column_header": "Analysis Dataset Column Name",
        "data_type": "Text (empty unless core metric)",
        "example": "Multifamily Re Loans",
        "description": (
            "If this is one of roughly twenty headline metrics in the Texas bank analysis "
            "datasets, the column name used there. Empty for all other lines."
        ),
        "how_to_use": "Join to bank profile or exploratory analysis exports when populated.",
    },
    {
        "column_header": "Listed in Borrower Product Catalog",
        "data_type": "Yes / No",
        "example": "Yes",
        "description": "Whether this code is explicitly tied to a product on the Lenni borrower website (ten core codes).",
        "how_to_use": "Filter to Yes for the strongest product mappings.",
    },
    {
        "column_header": "Appears in Texas Bank Filings",
        "data_type": "Yes / No",
        "example": "Yes",
        "description": "Whether this line appears at least once in the Texas Call Report extract (2025 onward).",
        "how_to_use": "Filter to Yes for Texas-only work.",
    },
    {
        "column_header": "Number of Texas Banks Reporting",
        "data_type": "Integer (empty if not in Texas data)",
        "example": "377",
        "description": "Distinct Texas banks that reported this line at least once.",
        "how_to_use": "See how common the line is across the Texas panel.",
    },
    {
        "column_header": "Texas Observations with Non-Zero Balance",
        "data_type": "Integer (empty if not in Texas data)",
        "example": "722",
        "description": (
            "Bank-quarter filings where this line had a non-zero value. More meaningful than "
            "total observations because many lines are filed as zero when a bank does not use that product."
        ),
        "how_to_use": "Estimate how actively Texas banks use this line.",
    },
    {
        "column_header": "Federal Reserve Dictionary Link",
        "data_type": "URL",
        "example": "https://www.federalreserve.gov/apps/mdrm/data-dictionary?mdrm=RCON1460",
        "description": (
            "Link to the authoritative definition, effective dates, confidentiality, and "
            "Uniform Bank Performance Report cross-references."
        ),
        "how_to_use": "Open for full regulatory detail not duplicated in this file.",
    },
]


BORROWER_DATA_DICTIONARY: list[dict[str, str]] = [
    {
        "column_header": "Loan Product Category",
        "data_type": "Text",
        "example": "Multifamily (5+ units)",
        "description": (
            "The type of lending you care about as a borrower — apartments, construction, "
            "business loans, and so on. This is Lenni's product name, not government form language."
        ),
        "how_to_use": "Pick the row that matches what you are trying to finance.",
    },
    {
        "column_header": "In Plain English",
        "data_type": "Text",
        "example": "Acquisition, refinance, and bridge financing for apartment buildings of five or more units.",
        "description": (
            "A short, jargon-free summary of what this lending category means. "
            "This replaces the confusing 'Official Line Item Title' from the full taxonomy sheet."
        ),
        "how_to_use": "Read this first to confirm you are looking at the right product type.",
    },
    {
        "column_header": "Who This Is For",
        "data_type": "Text",
        "example": "Apartment & multifamily lending",
        "description": (
            "The business context or borrower segment — for example business-occupied property, "
            "income-producing real estate, or agricultural borrowers."
        ),
        "how_to_use": "Decide whether this category fits your situation before contacting banks.",
    },
    {
        "column_header": "Regulatory Line Item Code (Reference)",
        "data_type": "Text",
        "example": "RCON1460",
        "description": (
            "The government's internal code for this loan category on bank quarterly filings. "
            "You do not need to memorize it — analysts use it to pull dollar amounts from Call Reports."
        ),
        "how_to_use": (
            "Optional. Mention only if speaking with a banker or analyst about filing data. "
            "Borrowers normally ignore this column."
        ),
    },
    {
        "column_header": "Available from Texas Banks",
        "data_type": "Yes / No",
        "example": "Yes",
        "description": (
            "Whether any Texas bank in our dataset reports this product category on their "
            "Call Report (2025 onward)."
        ),
        "how_to_use": (
            "If No, Texas filing data may not track this niche — it does not mean no bank lends "
            "in that category."
        ),
    },
    {
        "column_header": "Texas Banks Reporting This Category",
        "data_type": "Number (may be empty)",
        "example": "377",
        "description": (
            "How many distinct Texas banks reported this product category on a Call Report "
            "at least once in our dataset (2025 onward)."
        ),
        "how_to_use": (
            "Higher numbers mean more Texas banks file data for this niche. To see which banks "
            "and their dollar amounts, use the Texas bank profile export (separate file)."
        ),
    },
    {
        "column_header": "Learn More on Lenni",
        "data_type": "Link path",
        "example": "loan-types/multifamily.html",
        "description": (
            "Relative path to the Lenni borrower website guide for this product — sub-types, "
            "what to prepare, and how to approach banks."
        ),
        "how_to_use": "Open on the Lenni borrower site for detailed product guidance.",
    },
]


GLOSSARY_ROWS: list[dict[str, str]] = [
    {
        "term": "Call Report",
        "definition": (
            "The quarterly financial report that insured banks file with regulators. In this "
            "project the data come from the FFIEC Central Data Repository."
        ),
    },
    {
        "term": "FFIEC",
        "definition": (
            "Federal Financial Institutions Examination Council. The council coordinates "
            "regulatory reporting forms among bank agencies."
        ),
    },
    {
        "term": "FFIEC Form 031",
        "definition": "Full quarterly Call Report used by larger banks.",
    },
    {
        "term": "FFIEC Form 041",
        "definition": "Reduced quarterly Call Report used by many community banks.",
    },
    {
        "term": "Schedule RC-C",
        "definition": (
            "The Loans and Leases section of the Call Report. It lists loan balances by "
            "category (real estate, commercial and industrial, consumer, and so on)."
        ),
    },
    {
        "term": "Micro Data Reference Manual (MDRM)",
        "definition": (
            "The Federal Reserve master dictionary of every reportable line item. Each item "
            "has an eight-character code."
        ),
    },
    {
        "term": "Regulatory Line Item Code",
        "definition": (
            "Same as MDRM code—for example RCON1460. Used to link filings to definitions."
        ),
    },
    {
        "term": "Domestic offices",
        "definition": (
            "Branches and offices located in the United States, as opposed to foreign offices."
        ),
    },
    {
        "term": "RSSD ID (not in this file)",
        "definition": (
            "Federal Reserve unique bank identifier used in filing data. Join filing values "
            "to this dictionary using Regulatory Line Item Code plus bank and quarter keys."
        ),
    },
]
