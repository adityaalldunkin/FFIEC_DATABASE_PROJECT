"""Extended EDA documentation: insights catalog, abbreviations, data provenance."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent


def _section(title: str) -> list[tuple[str, object]]:
    return [(title, ""), ("", "")]


def _insights_table(items: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(items)


def _abbr_table(items: list[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(items, columns=["Abbreviation", "Full term", "Plain English"])


# ---------------------------------------------------------------------------
# Per-file insights catalogs and abbreviation glossaries
# ---------------------------------------------------------------------------

FILE_INSIGHTS: dict[str, list[dict]] = {}
FILE_ABBREVIATIONS: dict[str, list[tuple[str, str, str]]] = {}


def _register(filename: str, insights: list[dict], abbrs: list[tuple[str, str, str]]) -> None:
    FILE_INSIGHTS[filename] = insights
    FILE_ABBREVIATIONS[filename] = abbrs


_register(
    "institutions_definitions.csv",
    [
        {"#": 1, "Insight": "Decode any column in institutions.csv", "What you learn": "Exact regulatory meaning of CERT, ASSET, BKCLASS, CB, WEBADDR, etc.", "How to generate": "Look up Variable Name in this file; read Variable Definition for coded values.", "Borrower decision": "Understand what you are comparing before ranking banks."},
        {"#": 2, "Insight": "Community bank identification", "What you learn": "Which field (CB) flags FDIC community-bank research program members.", "How to generate": "Find CB definition; then filter institutions.csv CB=1.", "Borrower decision": "Prioritize relationship-oriented community lenders vs. nationals."},
        {"#": 3, "Insight": "Charter / regulator mapping", "What you learn": "BKCLASS codes (N, NM, SM, SB, SI, SL) and who supervises the bank.", "How to generate": "Read BKCLASS definition block; join to live BKCLASS values.", "Borrower decision": "Low risk context only — does not predict loan approval."},
        {"#": 4, "Insight": "Geographic field selection", "What you learn": "Difference between CITY, COUNTY, CBSA, ZIP, STALP.", "How to generate": "Compare definitions for CBSA vs COUNTY; pick field matching your search radius.", "Borrower decision": "Find banks headquartered or reporting in your metro."},
        {"#": 5, "Insight": "Asset size interpretation", "What you learn": "ASSET is total balance-sheet size in thousands of dollars.", "How to generate": "Read ASSET definition; divide institutions.csv ASSET by 1,000 for millions.", "Borrower decision": "Filter banks large enough for your loan amount ($500M–$2B = Lenni ICP)."},
        {"#": 6, "Insight": "Open vs closed institutions", "What you learn": "ACTIVE=1 means open and FDIC-insured.", "How to generate": "Read ACTIVE definition; always filter ACTIVE=1 for shortlists.", "Borrower decision": "Avoid dead ends — do not contact closed banks."},
        {"#": 7, "Insight": "Website / contact fields", "What you learn": "WEBADDR is primary URL from latest Call Report.", "How to generate": "Look up WEBADDR, OFFICES, NAME definitions.", "Borrower decision": "Navigate to bank site to find commercial lending contact."},
        {"#": 8, "Insight": "Merger history codes", "What you learn": "CHANGEC1–CHANGEC15 document structural events.", "How to generate": "Cross-reference with events_definitions.csv for code meanings.", "Borrower decision": "Due diligence if bank recently merged or rebranded."},
    ],
    [
        ("CERT", "FDIC Certificate Number", "Unique ID for each insured bank — use to join files and find bank pages."),
        ("FDIC", "Federal Deposit Insurance Corporation", "U.S. agency that insures deposits and maintains bank data."),
        ("FFIEC", "Federal Financial Institutions Examination Council", "Council of regulators; runs the Call Report system."),
        ("CDR", "Central Data Repository", "FFIEC system storing Call Reports and UBPR data."),
        ("BKCLASS", "Bank Class", "Short code for charter type and primary federal regulator."),
        ("CB", "Community Bank flag", "1 = bank is in FDIC community bank research program."),
        ("CBSA", "Core Based Statistical Area", "Census metro/micro area name and code."),
        ("STALP", "State abbreviation", "Two-letter state code (TX = Texas)."),
        ("ASSET", "Total assets", "Sum of everything the bank owns — size proxy (in thousands USD)."),
        ("DEP", "Total deposits", "Customer deposits held by the bank."),
        ("ROA", "Return on assets", "Profitability ratio — earnings divided by assets."),
        ("ROE", "Return on equity", "Profitability ratio — earnings divided by equity."),
        ("WEBADDR", "Website address", "Bank's primary public website URL."),
        ("REGAGNT", "Primary regulator", "OCC, FDIC, or Federal Reserve."),
        ("RSSD / FED_RSSD", "Federal Reserve ID", "Numeric ID used in FFIEC filings (join to texas_institutions)."),
    ],
)

_register(
    "events_definitions.csv",
    [
        {"#": 1, "Insight": "Merger / acquisition timeline", "What you learn": "Whether a bank was acquired or renamed recently.", "How to generate": "Map institutions.csv CHANGEC* values to definitions here.", "Borrower decision": "Ask if your relationship manager or credit policy changed post-merger."},
        {"#": 2, "Insight": "Failure / closure events", "What you learn": "Historical failure codes for inactive institutions.", "How to generate": "Filter events with 'fail' or 'close' in Variable Label.", "Borrower decision": "Confirm bank is ACTIVE=1 before outreach."},
        {"#": 3, "Insight": "Acquiring bank identification", "What you learn": "ACQ_CERT links to surviving institution after merger.", "How to generate": "Look up ACQ_CERT definition; join to CERT in institutions.csv.", "Borrower decision": "Follow the surviving entity if your contact bank merged."},
        {"#": 4, "Insight": "Charter change tracking", "What you learn": "When a bank changed charter agent or regulator.", "How to generate": "Read CHARTAGENT and related event field definitions.", "Borrower decision": "Rarely affects borrower; useful for analysts only."},
    ],
    [
        ("CHANGEC", "Change Code", "FDIC code for structural events (merger, failure, charter change)."),
        ("ACQ_CERT", "Acquiring FDIC Certificate", "CERT number of bank that acquired another institution."),
        ("CHARTAGENT", "Chartering Agency", "State or federal body that granted the bank's charter."),
        ("OCC", "Office of the Comptroller of the Currency", "Regulator for national banks."),
        ("OTS", "Office of Thrift Supervision", "Former thrift regulator (merged into OCC/FDIC in 2011)."),
    ],
)

_register(
    "institutions.csv",
    [
        {"#": 1, "Insight": "Texas active bank count", "What you learn": "How many TX banks are open today (~349 active).", "How to generate": "Filter STALP='TX' AND ACTIVE=1; count rows.", "Borrower decision": "Size of the Texas community bank universe."},
        {"#": 2, "Insight": "Asset band distribution", "What you learn": "How many banks fall in <$100M, $100–250M, … >$5B.", "How to generate": "ASSET/1000 → millions; use bins; compare to asset_band_counts.csv.", "Borrower decision": "Target banks big enough for your deal size."},
        {"#": 3, "Insight": "ICP shortlist ($500M–$2B)", "What you learn": "~109 active TX banks in Lenni target range.", "How to generate": "Filter ACTIVE=1, STALP=TX, ASSET between 500,000 and 2,000,000 (thousands).", "Borrower decision": "Start with banks sized for relationship CRE lending."},
        {"#": 4, "Insight": "City concentration map", "What you learn": "Which Texas cities have the most bank HQs.", "How to generate": "Group by CITY; count CERT; top cities: Houston, Dallas, San Antonio.", "Borrower decision": "Find local lenders near your property or business."},
        {"#": 5, "Insight": "Community bank share", "What you learn": "% of active TX banks with CB=1.", "How to generate": "Count CB=1 / total active TX.", "Borrower decision": "Focus on community lenders if you want relationship banking."},
        {"#": 6, "Insight": "Website coverage", "What you learn": "How many banks have WEBADDR populated (~344/349).", "How to generate": "Count non-null WEBADDR on active TX rows.", "Borrower decision": "Direct path to bank website and contact pages."},
        {"#": 7, "Insight": "Charter mix", "What you learn": "NM (state non-member) vs N (national) vs SM (state member) counts.", "How to generate": "value_counts on BKCLASS for active TX.", "Borrower decision": "Informational — does not determine loan product fit."},
        {"#": 8, "Insight": "Branch count proxy", "What you learn": "OFFICES field = number of offices reported.", "How to generate": "Sort by OFFICES descending; validate with locations.csv.", "Borrower decision": "Multi-branch banks may have wider geographic lending."},
        {"#": 9, "Insight": "Profitability snapshot", "What you learn": "ROA/ROE distribution across Texas banks.", "How to generate": "Describe ROA, ROE numerically; exclude outliers.", "Borrower decision": "Secondary signal — healthy bank vs distressed (not loan appetite)."},
        {"#": 10, "Insight": "Join key to FFIEC data", "What you learn": "FED_RSSD links to texas_institutions.id_rssd.", "How to generate": "Merge on FED_RSSD = id_rssd after numeric cast.", "Borrower decision": "Connect FDIC profile to Call Report loan data."},
    ],
    [
        ("CERT", "FDIC Certificate Number", "Primary bank ID in FDIC/BankFind data."),
        ("STALP", "State", "TX = Texas."),
        ("ACTIVE", "Institution status", "1 = open and insured; 0 = closed."),
        ("ASSET", "Total assets (thousands USD)", "Divide by 1,000 for millions."),
        ("BKCLASS", "Bank class", "N, NM, SM, etc. — charter and regulator type."),
        ("CB", "Community bank", "1 = FDIC community bank program member."),
        ("CBSA", "Metro area name", "Census statistical area for HQ."),
        ("WEBADDR", "Website", "Public URL for the bank."),
        ("OFFICES", "Office count", "Branches + HQ reported to FDIC."),
        ("FED_RSSD", "Federal Reserve RSSD ID", "Join key to FFIEC Texas extract."),
        ("DEP", "Deposits (thousands USD)", "Total customer deposits."),
        ("ROA / ROE", "Return on assets / equity", "Profitability ratios from regulatory reports."),
    ],
)

_register(
    "locations.csv",
    [
        {"#": 1, "Insight": "Texas branch footprint per bank", "What you learn": "How many offices a bank has in Texas (~6,403 branch records).", "How to generate": "Filter STALP='TX'; group by CERT; count rows.", "Borrower decision": "Confirm the bank actually operates near your deal."},
        {"#": 2, "Insight": "City-level branch density", "What you learn": "Houston (~606), Dallas (~374), San Antonio (~269) lead branch counts.", "How to generate": "Count branches per CITY in TX.", "Borrower decision": "Pick lenders with physical presence in your market."},
        {"#": 3, "Insight": "Headquarters vs branch", "What you learn": "MAINOFF=1 marks HQ; other rows are branches.", "How to generate": "Filter MAINOFF=1 for HQ address; MAINOFF=0 for branches.", "Borrower decision": "Commercial lending may be at HQ even if branch is nearer."},
        {"#": 4, "Insight": "County / metro coverage", "What you learn": "Whether bank has offices in your county or CBSA.", "How to generate": "Filter COUNTY or CBSA fields for your market.", "Borrower decision": "Rural deals need banks with rural branches."},
        {"#": 5, "Insight": "Unique Texas cities served", "What you learn": "~836 cities have at least one branch.", "How to generate": "Count distinct CITY where STALP=TX.", "Borrower decision": "Breadth of geographic coverage."},
        {"#": 6, "Insight": "Crosswalk to institutions", "What you learn": "CERT links branch rows to bank name and assets.", "How to generate": "Join locations.CERT = institutions.CERT.", "Borrower decision": "Full profile: size (institutions) + footprint (locations)."},
    ],
    [
        ("CERT", "FDIC Certificate Number", "Links branch to parent bank."),
        ("MAINOFF", "Main office flag", "1 = headquarters; 0 = branch."),
        ("STALP", "State", "TX for Texas branches."),
        ("CBSA", "Core Based Statistical Area", "Metro/micro area for the branch."),
        ("COUNTY", "County name", "County where branch is located."),
        ("SERVTYPE", "Service type", "Branch services offered (deposits, etc.)."),
        ("UNINUM", "FDIC unique number", "Branch-level identifier."),
        ("ESTYMD", "Establishment date", "When the office opened."),
    ],
)

_register(
    "locations_definitions.csv",
    [
        {"#": 1, "Insight": "Branch field decoder", "What you learn": "Meaning of every column in locations.csv.", "How to generate": "Match NAME column here to locations.csv headers.", "Borrower decision": "Understand branch data before geographic filtering."},
        {"#": 2, "Insight": "Main office identification", "What you learn": "How FDIC defines headquarters vs branch.", "How to generate": "Read MAINOFF / OFFTYPE definitions.", "Borrower decision": "Contact commercial lending at HQ when unsure."},
    ],
    [
        ("MAINOFF", "Main office", "Flag: 1 = headquarters location."),
        ("OFFTYPE", "Office type", "Classification of banking office."),
        ("NAME", "Field code", "Column name used in locations.csv."),
        ("TITLE", "Short label", "Human-readable field name."),
        ("DEFINITION", "Full definition", "Regulatory explanation of the field."),
    ],
)

_register(
    "sod_variables_definitions.csv",
    [
        {"#": 1, "Insight": "Deposit market structure", "What you learn": "How FDIC classifies branch deposit services.", "How to generate": "Read DEFINITIONS column for deposit-related variables.", "Borrower decision": "Secondary — useful if you also want a deposit relationship."},
        {"#": 2, "Insight": "Branch vs institution variables", "What you learn": "Which fields apply at branch vs holding company level.", "How to generate": "Read BRANCH INSTITUTION HOLDING CO column.", "Borrower decision": "Analyst-level; not required for loan matching."},
    ],
    [
        ("SOD", "Summary of Deposits", "Annual FDIC survey of branch-level deposits."),
        ("COL REF", "Column reference", "Internal column code in SOD files."),
        ("ACTION", "Action code", "How the variable is used in SOD reporting."),
    ],
)

_register(
    "texas_filings.csv",
    [
        {"#": 1, "Insight": "Filing freshness", "What you learn": "Which quarters are downloaded (Q1 2025 through Q1 2026).", "How to generate": "value_counts on reporting_period.", "Borrower decision": "Use latest period for current portfolio data."},
        {"#": 2, "Insight": "Texas bank filing universe", "What you learn": "~377 unique banks across all periods.", "How to generate": "nunique(id_rssd).", "Borrower decision": "Complete Texas Call Report coverage for downloaded periods."},
        {"#": 3, "Insight": "Data integrity check", "What you learn": "SHA-256 hash per file proves unchanged download.", "How to generate": "Compare sha256 across re-downloads.", "Borrower decision": "Analyst use — confirms data not corrupted."},
        {"#": 4, "Insight": "XBRL format confirmation", "What you learn": "All filings are XBRL (machine-readable).", "How to generate": "facsimile_format value_counts.", "Borrower decision": "Enables automated loan line extraction."},
        {"#": 5, "Insight": "Archive path traceability", "What you learn": "Exact .xbrl file on disk for audit.", "How to generate": "Read file_path column.", "Borrower decision": "Source document if you need to verify a number."},
        {"#": 6, "Insight": "Filing size distribution", "What you learn": "Typical XBRL file 50KB–500KB.", "How to generate": "Describe file_size_bytes.", "Borrower decision": "Spot incomplete downloads (unusually small files)."},
    ],
    [
        ("RSSD / id_rssd", "Federal Reserve ID", "Unique institution ID in FFIEC system."),
        ("XBRL", "eXtensible Business Reporting Language", "Machine-readable financial reporting format."),
        ("FFIEC", "Federal Financial Institutions Examination Council", "Publisher of Call Reports."),
        ("SHA-256", "Secure hash", "Fingerprint of file contents for integrity."),
        ("facsimile", "Regulatory filing copy", "Official submitted Call Report file."),
        ("PWS", "Public Web Service", "FFIEC REST API used to download filings."),
    ],
)

_register(
    "texas_institutions.csv",
    [
        {"#": 1, "Insight": "Quarterly Texas bank roster", "What you learn": "Every TX bank on FFIEC panel per quarter (1,825 rows = 5 quarters).", "How to generate": "Count rows; group by reporting_period.", "Borrower decision": "Official list of who must file Call Reports."},
        {"#": 2, "Insight": "Filing completion status", "What you learn": "has_filed=True means FFIEC received the report.", "How to generate": "Filter has_filed; compare to texas_filings.csv.", "Borrower decision": "Only filed banks have loan data in labeled extract."},
        {"#": 3, "Insight": "Call Report form type", "What you learn": "filing_type 051 = FFIEC 031 (larger), 041 = smaller bank form.", "How to generate": "value_counts on filing_type.", "Borrower decision": "Form type affects which loan lines appear."},
        {"#": 4, "Insight": "City-based bank list", "What you learn": "HQ city per bank per quarter.", "How to generate": "Sort by city; dedupe on latest period.", "Borrower decision": "Geographic shortlist starting point."},
        {"#": 5, "Insight": "Panel size trends", "What you learn": "Texas panel ~352–377 banks per quarter.", "How to generate": "Count per reporting_period.", "Borrower decision": "Understand mergers/new charters over time."},
    ],
    [
        ("id_rssd", "RSSD ID", "Federal Reserve unique institution identifier."),
        ("filing_type", "Call Report form", "051 = FFIEC 031; 041 = FFIEC 041 (smaller banks)."),
        ("has_filed", "Filing status", "True if bank submitted for that quarter."),
        ("reporting_period", "Quarter end date", "MM/DD/YYYY — e.g. 6/30/2025 = Q2 2025."),
        ("FFIEC 031", "Call Report (large)", "Full call report for banks above size threshold."),
        ("FFIEC 041", "Call Report (community)", "Reduced call report for smaller banks."),
    ],
)

_register(
    "texas_loans_labeled.csv",
    [
        {"#": 1, "Insight": "Bank loan portfolio by product line", "What you learn": "Dollar balance per MDRM code per bank per quarter.", "How to generate": "Filter id_rssd + reporting_period; sum value_num by mdrm_code.", "Borrower decision": "Rank banks by exposure to your loan type."},
        {"#": 2, "Insight": "Multifamily lender ranking", "What you learn": "Banks with highest RCON1460 (multifamily) balances.", "How to generate": "Filter mdrm_code=RCON1460; sort value_num desc.", "Borrower decision": "Shortlist apartment lenders in Texas."},
        {"#": 3, "Insight": "CRE / C&I concentration", "What you learn": "Owner-occupied vs investor CRE vs C&I splits.", "How to generate": "Sum RCONF160, RCONF161, RCON1766, etc. per bank.", "Borrower decision": "Match bank specialization to your deal type."},
        {"#": 4, "Insight": "Construction lending activity", "What you learn": "Ground-up and land development balances (RCONF158, RCONF159).", "How to generate": "Filter construction MDRM codes; non-zero value_num.", "Borrower decision": "Find banks active in commercial construction."},
        {"#": 5, "Insight": "Ag / farmland lenders", "What you learn": "RCON1420, RCON1590 balances by bank.", "How to generate": "Filter ag-related codes; rank by value.", "Borrower decision": "Ranch and farmland borrower matching."},
        {"#": 6, "Insight": "Portfolio share calculation", "What you learn": "% of total loans in a category.", "How to generate": "Category balance / RCON2122 total loans per bank.", "Borrower decision": "Prefer banks where your product is a meaningful share."},
        {"#": 7, "Insight": "Time trend for one bank", "What you learn": "How a bank's CRE portfolio changed across 5 quarters.", "How to generate": "Filter one id_rssd; plot value_num by period.", "Borrower decision": "Growing CRE book may mean active lending."},
        {"#": 8, "Insight": "Non-zero vs zero reporting", "What you learn": "Bank reports line but balance may be zero.", "How to generate": "Filter value_num > 0 vs = 0 for a code.", "Borrower decision": "Non-zero = stronger signal of active lending."},
        {"#": 9, "Insight": "Form type coverage", "What you learn": "FFIEC 031 vs 041 banks report different line sets.", "How to generate": "Group by reporting_form; compare mdrm_code sets.", "Borrower decision": "Ensure you compare banks on same form lines."},
        {"#": 10, "Insight": "Plain-English labels", "What you learn": "item_name and mdrm_description from Fed dictionary.", "How to generate": "Read item_name column — no need to memorize RCON codes.", "Borrower decision": "Understand what each number represents."},
    ],
    [
        ("MDRM", "Micro Data Reference Manual", "Federal Reserve dictionary of Call Report line codes."),
        ("RCON", "Domestic office line code", "Dollar amounts for domestic offices (most large banks)."),
        ("RCFD", "Consolidated domestic code", "Variant often used by FFIEC 041 community banks."),
        ("RCONF", "Schedule RC-C extension", "Detailed loan category lines on Schedule RC-C."),
        ("RC-C", "Call Report Schedule C", "Loans and leases section of the Call Report."),
        ("XBRL", "Reporting format", "How values were originally filed electronically."),
        ("value_num", "Numeric amount", "Usually in thousands of U.S. dollars."),
        ("context_ref", "XBRL period tag", "Which quarter / instant vs average the value applies to."),
        ("id_rssd", "Institution ID", "Join to texas_institutions and texas_filings."),
        ("mdrm_code", "Line item code", "e.g. RCON2122 = total loans and leases."),
        ("mdrm_category", "Lenni grouping", "loan_or_lease, schedule_rc_c, or other."),
    ],
)

_register(
    "texas_loan_products_mdrm_catalog.csv",
    [
        {"#": 1, "Insight": "Texas-usable code list", "What you learn": "Only ~1,611 of 24,015 codes appear in Texas data.", "How to generate": "Filter in_texas_data='yes'; count rows.", "Borrower decision": "Focus analysis on codes actually reported by TX banks."},
        {"#": 2, "Insight": "Full loan code encyclopedia", "What you learn": "Official Fed name + definition for every loan-related MDRM line.", "How to generate": "Search mdrm_code or keyword in mdrm_description.", "Borrower decision": "Translate regulatory jargon into plain English."},
        {"#": 3, "Insight": "Form applicability", "What you learn": "Which Call Report form uses each code (031, 041, etc.).", "How to generate": "Group by reporting_form.", "Borrower decision": "Know if a code applies to community vs large banks."},
        {"#": 4, "Insight": "Category coverage map", "What you learn": "loan_or_lease vs schedule_rc_c volume in catalog.", "How to generate": "value_counts mdrm_category.", "Borrower decision": "Navigate to the right section of the loan schedules."},
        {"#": 5, "Insight": "Build custom product filters", "What you learn": "Create a list of MDRM codes for 'my product'.", "How to generate": "Filter descriptions for keywords; flag in_texas_data.", "Borrower decision": "Custom bank matching beyond Lenni taxonomy."},
    ],
    [
        ("MDRM", "Micro Data Reference Manual", "Fed master list of regulatory line items."),
        ("in_texas_data", "Texas observation flag", "yes = at least one Texas bank reported this code."),
        ("item_type", "Line item type", "F = financial amount; D = derived; R = rate."),
        ("reporting_form", "FFIEC form", "Which regulatory form includes this line."),
        ("RC-C", "Schedule RC-C", "Primary loan and lease schedule on Call Report."),
    ],
)

_register(
    "texas_mdrm_loan_taxonomy.csv",
    [
        {"#": 1, "Insight": "Borrower product category mapping", "What you learn": "Each MDRM line mapped to Multifamily, Investor CRE, C&I, etc.", "How to generate": "Group by Loan Product Category; count line items.", "Borrower decision": "Speak in product terms, not regulatory codes."},
        {"#": 2, "Insight": "Texas bank coverage per product", "What you learn": "Number of Texas Banks Reporting per category.", "How to generate": "Read Number of Texas Banks Reporting column; sort desc.", "Borrower decision": "How common each product is across Texas banks."},
        {"#": 3, "Insight": "Active lending signal", "What you learn": "Texas Observations with Non-Zero Balance.", "How to generate": "Compare reporting count vs non-zero count.", "Borrower decision": "Non-zero = banks with actual outstanding loans in that line."},
        {"#": 4, "Insight": "CRE sub-type breakdown", "What you learn": "Industrial, office, retail within Investor CRE.", "How to generate": "Filter Investor CRE; group by Loan Product Subcategory.", "Borrower decision": "Match industrial borrower to industrial-heavy lenders."},
        {"#": 5, "Insight": "Collateral type classification", "What you learn": "What secures each line (real estate, farmland, etc.).", "How to generate": "Read Collateral or Security Type column.", "Borrower decision": "Align your collateral with bank's reported categories."},
        {"#": 6, "Insight": "Borrower site catalog flag", "What you learn": "Which lines appear on Lenni borrower product pages.", "How to generate": "Filter Listed in Borrower Product Catalog = Yes.", "Borrower decision": "Lines tied to live borrower_site content."},
        {"#": 7, "Insight": "Regulatory dictionary deep link", "What you learn": "Federal Reserve MDRM page per code.", "How to generate": "Open Federal Reserve Dictionary Link column.", "Borrower decision": "Verify official definition for diligence."},
        {"#": 8, "Insight": "Construction vs permanent CRE", "What you learn": "Separate Commercial Construction from Investor CRE lines.", "How to generate": "Compare category counts and median bank reporting.", "Borrower decision": "Ground-up borrowers need construction-active banks."},
    ],
    [
        ("MDRM", "Micro Data Reference Manual", "Source of regulatory line item codes."),
        ("RC-C", "Schedule RC-C", "Call Report loans and leases schedule."),
        ("CRE", "Commercial real estate", "Non-residential property loans."),
        ("C&I", "Commercial and industrial", "Business operating and equipment loans."),
        ("ICP", "Ideal customer profile", "Lenni target: $500M–$2B Texas community banks."),
        ("FFIEC 031/041", "Call Report forms", "Large bank vs community bank report templates."),
        ("Collateral", "Security for loan", "Asset pledged — real estate, equipment, etc."),
    ],
)

_register(
    "texas_mdrm_loan_taxonomy.xlsx",
    [
        {"#": 1, "Insight": "Plain-English product guide", "What you learn": "10-row Borrower View: category, who it's for, Lenni link.", "How to generate": "Open Borrower View sheet.", "Borrower decision": "Fastest on-ramp for non-bankers."},
        {"#": 2, "Insight": "Field-by-field data dictionary", "What you learn": "How to use each column in Loan Taxonomy Data.", "How to generate": "Read Borrower Data Dictionary + Data Dictionary sheets.", "Borrower decision": "Self-serve without asking an analyst."},
        {"#": 3, "Insight": "Glossary of lending terms", "What you learn": "Definitions of MDRM, RC-C, nonaccrual, etc.", "How to generate": "Open Term Glossary sheet.", "Borrower decision": "Learn vocabulary before calling banks."},
        {"#": 4, "Insight": "Texas availability per category", "What you learn": "Texas Banks Reporting This Category in Borrower View.", "How to generate": "Sort Borrower View by reporting column.", "Borrower decision": "Pick categories with broad Texas lender coverage."},
    ],
    [
        ("Borrower View", "Summary sheet", "Plain-English loan categories for borrowers."),
        ("MDRM", "Micro Data Reference Manual", "Regulatory code system behind the data."),
        ("RCON/RCFD", "Line code prefixes", "Domestic vs consolidated reporting variants."),
        ("Lenni", "Borrower-lender platform", "Texas community bank loan matching product."),
    ],
)

_register(
    "26.05.18.All.Loan.Types.UBPR.Reference.xlsx",
    [
        {"#": 1, "Insight": "UBPR loan hierarchy", "What you learn": "Industry-standard loan type tree (real estate, C&I, consumer, ag).", "How to generate": "Read Loan Products sheet; group by UBPR Category.", "Borrower decision": "Map your deal to standard banking categories."},
        {"#": 2, "Insight": "FDIC field crosswalk", "What you learn": "Primary FDIC Field for each loan product row.", "How to generate": "Match Primary FDIC Field to mdrm_code in labeled file.", "Borrower decision": "Bridge UBPR language to Texas extract codes."},
        {"#": 3, "Insight": "Owner-occupied flag", "What you learn": "Which products are owner-occupied vs investor.", "How to generate": "Filter Owner-Occupied? column on Loan Products.", "Borrower decision": "Critical split for CRE borrowers."},
        {"#": 4, "Insight": "Underwriting template roadmap", "What you learn": "Which MD templates Lenni plans to build.", "How to generate": "Read Template Library sheet.", "Borrower decision": "Future — structured intake per loan type."},
        {"#": 5, "Insight": "Common pitfalls", "What you learn": "Analyst notes on misclassification risks.", "How to generate": "Read Pitfalls sheet.", "Borrower decision": "Avoid comparing incompatible product types."},
    ],
    [
        ("UBPR", "Uniform Bank Performance Report", "FFIEC peer comparison report (ratios, aggregates)."),
        ("FDIC Field", "Call Report line code", "MDRM code such as LNRECONS, RCONF160."),
        ("Owner-occupied", "O/O CRE", "Borrower occupies the commercial property."),
        ("Investor", "Non-owner-occupied", "Property held for rental income."),
        ("C&I", "Commercial & industrial", "Business loans not secured by real estate."),
    ],
)

_register(
    "All Financial Reports.xlsx",
    [
        {"#": 1, "Insight": "FFIEC API field index", "What you learn": "URLs to pull any Call Report field via FDIC API.", "How to generate": "Browse Assets & Liabilities and Income sheets.", "Borrower decision": "Analyst tool — not for direct borrower use."},
        {"#": 2, "Insight": "Variable definition lookup", "What you learn": "API variable names with definitions.", "How to generate": "Search Variable column on Reference sheets.", "Borrower decision": "Rebuild custom extracts if needed."},
        {"#": 3, "Insight": "Report type navigation", "What you learn": "How fields group into Assets, Income, Demographics, Ratios.", "How to generate": "Read Report Type column per sheet.", "Borrower decision": "Understand scope of available regulatory fields."},
    ],
    [
        ("API", "Application programming interface", "Programmatic access to FDIC/FFIEC data."),
        ("UBPR", "Uniform Bank Performance Report", "Peer ratio report — separate from Call Report."),
        ("RCON", "Call Report line prefix", "Domestic office financial line item."),
        ("REPDTE", "Report date", "Quarter end date for the filing."),
    ],
)

_register(
    "asset_band_counts.csv",
    [
        {"#": 1, "Insight": "Texas bank size histogram", "What you learn": "Count of banks in each asset bucket.", "How to generate": "Read asset_band and count columns directly.", "Borrower decision": "See how many lenders exist at your target size."},
        {"#": 2, "Insight": "ICP band validation", "What you learn": "$500M–$1B (68) + $1–2B (37) = 105 ICP banks.", "How to generate": "Sum counts for $500M–$1B and $1–2B rows.", "Borrower decision": "Confirms Lenni market segment sizing."},
        {"#": 3, "Insight": "Small bank availability", "What you learn": "43 banks under $100M — may not do large CRE.", "How to generate": "Read <$100M row.", "Borrower decision": "Set minimum bank size for your loan amount."},
    ],
    [
        ("ICP", "Ideal customer profile", "Lenni target banks: $500M–$2B assets."),
        ("asset_band", "Size bucket", "Total assets grouped into ranges."),
        ("M", "Millions", "Millions of U.S. dollars."),
    ],
)

_register(
    "lenni_icp_prospect_list.csv",
    [
        {"#": 1, "Insight": "Ready-made ICP shortlist", "What you learn": "105 banks in $500M–$2B with loan metrics.", "How to generate": "Use file directly — sorted by total_assets.", "Borrower decision": "Start here for Lenni-aligned bank list."},
        {"#": 2, "Insight": "CRE-heavy lender ranking", "What you learn": "cre_to_loans ratio — top: Security State Bank Pearsall (~87%).", "How to generate": "Sort cre_to_loans descending.", "Borrower decision": "CRE borrowers prioritize high cre_to_loans."},
        {"#": 3, "Insight": "C&I-heavy lender ranking", "What you learn": "ci_to_loans identifies business lending focus.", "How to generate": "Sort ci_to_loans descending.", "Borrower decision": "Working capital borrowers use C&I tilt."},
        {"#": 4, "Insight": "Loan-to-asset leverage", "What you learn": "How much of balance sheet is loans (median ~63%).", "How to generate": "Describe loan_to_asset_ratio.", "Borrower decision": "Higher ratio = more lending-intensive bank."},
        {"#": 5, "Insight": "City + size combined filter", "What you learn": "Bank name, city, assets in one table.", "How to generate": "Filter city contains your market; filter assets.", "Borrower decision": "Geographic + size shortlist in one step."},
        {"#": 6, "Insight": "CRE proxy dollar amounts", "What you learn": "cre_proxy_total in dollars for scale comparison.", "How to generate": "Sort cre_proxy_total desc.", "Borrower decision": "Larger CRE book may handle larger deals."},
    ],
    [
        ("ICP", "Ideal customer profile", "$500M–$2B Texas community banks."),
        ("CRE", "Commercial real estate", "Non-owner-occupied and owner-occupied property loans."),
        ("C&I", "Commercial & industrial", "Business operating lines and term loans."),
        ("cre_to_loans", "CRE % of loans", "cre_proxy_total divided by total_loans_gross."),
        ("ci_to_loans", "C&I % of loans", "ci_loans divided by total_loans_gross."),
        ("loan_to_asset_ratio", "Loans / assets", "How lending-intensive the bank is."),
        ("id_rssd", "RSSD ID", "Join to texas_loans_labeled and texas_institutions."),
    ],
)

_register(
    "lenni_market_segments.csv",
    [
        {"#": 1, "Insight": "Market sizing by segment", "What you learn": "105 ICP, 197 below $500M, 52 above $2B.", "How to generate": "Read Segment and Banks_latest columns.", "Borrower decision": "Understand where Lenni focuses vs total market."},
        {"#": 2, "Insight": "ICP share of Texas banks", "What you learn": "~30% of banks with asset data are ICP.", "How to generate": "105 / sum(Banks_latest).", "Borrower decision": "ICP is a deliberate slice, not all Texas banks."},
        {"#": 3, "Insight": "Missing data awareness", "What you learn": "6 banks lack asset data in latest period.", "How to generate": "Read Missing asset data row.", "Borrower decision": "Exclude or manually research these banks."},
    ],
    [
        ("ICP", "Ideal customer profile", "$500M–$2B asset band."),
        ("TAM", "Total addressable market", "All Texas banks in analysis."),
        ("Banks_latest", "Bank count", "Number of banks in segment (latest quarter)."),
    ],
)

_register(
    "summary_statistics_latest.csv",
    [
        {"#": 1, "Insight": "Peer benchmark — total assets", "What you learn": "Median ~$433M; mean ~$1.4B (skewed by large banks).", "How to generate": "Read 50% and mean rows for total_assets.", "Borrower decision": "Is your target bank bigger or smaller than typical?"},
        {"#": 2, "Insight": "Peer benchmark — loan book size", "What you learn": "Median gross loans ~$251M.", "How to generate": "Read total_loans_gross 50% row.", "Borrower decision": "Bank big enough for your requested loan size?"},
        {"#": 3, "Insight": "Typical CRE proxy scale", "What you learn": "Median CRE proxy ~$116M.", "How to generate": "Read cre_proxy_total 50% row.", "Borrower decision": "Compare bank CRE book to your deal size."},
        {"#": 4, "Insight": "Typical C&I scale", "What you learn": "Median C&I loans ~$27M.", "How to generate": "Read ci_loans 50% row.", "Borrower decision": "Business borrowers benchmark against median."},
        {"#": 5, "Insight": "Loan-to-asset norm", "What you learn": "Median ~62% of assets are loans.", "How to generate": "Read loan_to_asset_ratio 50% (=0.62).", "Borrower decision": "Typical community bank lending intensity."},
        {"#": 6, "Insight": "Outlier detection", "What you learn": "Max assets ~$53B — large regionals skew averages.", "How to generate": "Compare mean vs 50% vs max.", "Borrower decision": "Use median for 'typical' community bank."},
    ],
    [
        ("50%", "Median", "Middle value — half of banks above, half below."),
        ("mean", "Average", "Skewed upward by largest banks."),
        ("CRE proxy", "CRE aggregate", "Regulatory sum approximating commercial real estate."),
        ("C&I", "Commercial & industrial", "Business lending lines."),
    ],
)


def append_file_documentation(rows: list[tuple[str, object]], filename: str) -> list[tuple[str, object]]:
    """Add insights catalog and abbreviations sections to an EDA sheet."""
    if filename in FILE_INSIGHTS:
        rows += _section(
            "Detailed insights catalog — everything you can learn from this file"
        )
        rows.append(("__table__", _insights_table(FILE_INSIGHTS[filename])))
        rows.append(("", ""))

    if filename in FILE_ABBREVIATIONS:
        rows += _section("Abbreviations and terms used in this file")
        rows.append(("__table__", _abbr_table(FILE_ABBREVIATIONS[filename])))
        rows.append(("", ""))

    return rows


def build_provenance_rows() -> list[tuple[str, object]]:
    """Very detailed documentation of how all original data was pulled."""
    rows: list[tuple[str, object]] = [
        ("Title", "How all original data in this workbook was pulled"),
        ("Document purpose", "Step-by-step provenance for every CSV/XLSX file analyzed in this workbook. Written for borrowers, analysts, and auditors who need to trust where numbers came from."),
        ("Last updated", pd.Timestamp.now().strftime("%Y-%m-%d")),
        ("", ""),
    ]

    rows += _section("Executive summary — three data pipelines")
    rows += [
        ("Pipeline 1 — FFIEC Texas Call Reports (2025+)", "Official FFIEC Central Data Repository Public Web Service (REST API). Downloads XBRL Call Reports for every Texas bank that filed each quarter since 2025. Produces texas_institutions, texas_filings, texas_xbrl_facts, then texas_loans_labeled and catalog via Federal Reserve MDRM dictionary."),
        ("Pipeline 2 — FDIC BankFind enrichment", "FDIC public institution and branch files (institutions.csv, locations.csv) plus their definition files. Adds websites, HQ addresses, branch footprints, community bank flags, and CERT-based joins to the borrower site."),
        ("Pipeline 3 — Lenni analysis & taxonomy builds", "Python scripts join extracts, compute loan mix, build taxonomy (texas_mdrm_loan_taxonomy), ICP prospect lists, and summary statistics for borrower decision-making."),
        ("", ""),
    ]

    rows += _section("Source systems and APIs")
    rows.append(("__table__", pd.DataFrame([
        {"System": "FFIEC CDR PWS", "URL": "https://ffieccdr.azure-api.us/public/", "Auth": "UserID + Bearer token (.env)", "Used for": "Call Report periods, panel, XBRL facsimiles"},
        {"System": "Federal Reserve MDRM", "URL": "https://www.federalreserve.gov/apps/mdrm/", "Auth": "None (public ZIP)", "Used for": "Labeling RCON/RCFD codes with English names"},
        {"System": "FDIC BankFind", "URL": "https://banks.data.fdic.gov/", "Auth": "Public download", "Used for": "institutions.csv, locations.csv, definition files"},
        {"System": "FFIEC/FDIC Financial Reports API", "URL": "https://api.fdic.gov/banks/financials", "Auth": "Documented in All Financial Reports.xlsx", "Used for": "Optional field pulls (reference workbook)"},
    ])))
    rows.append(("", ""))

    rows += _section("Phase A — Texas Call Report download (FFIEC API)")
    rows.append(("__table__", pd.DataFrame([
        {"Step": 0, "Action": "Authenticate", "Detail": "Load FFIEC_USER_ID and FFIEC_TOKEN from repo .env. Send as API headers on every request."},
        {"Step": 1, "Action": "List reporting periods", "Detail": "API: RetrieveReportingPeriods (data_series=Call). Keep periods with year >= 2025 → 5 quarters: 3/31/2025, 6/30/2025, 9/30/2025, 12/31/2025, 3/31/2026."},
        {"Step": 2, "Action": "Get Texas bank panel", "Detail": "API: RetrievePanelOfReporters per period. Filter State == 'TX'. Write every row to texas_institutions.csv (1,825 rows = 365 banks × 5 quarters)."},
        {"Step": 3, "Action": "Download XBRL facsimiles", "Detail": "For each bank with HasFiledForReportingPeriod=True, API: RetrieveFacsimile (format=XBRL). Rate limit ~1.5s between calls (~2,400/hour)."},
        {"Step": 4, "Action": "Archive raw filings", "Detail": "Save bytes to ONLY_TEXAS_SINCE_2025/archive/call/<period>/<rssd>.xbrl plus .meta.json (SHA-256, timestamp)."},
        {"Step": 5, "Action": "Write filing manifest", "Detail": "Each download → row in texas_filings.csv (id_rssd, period, path, sha256, size, retrieved_at)."},
        {"Step": 6, "Action": "Parse XBRL to facts", "Detail": "ffiec_cdr.parser.parse_xbrl() extracts every numeric/text fact → texas_xbrl_facts.csv (~2.19M rows)."},
        {"Step": 7, "Action": "Resume support", "Detail": "data/progress.json stores completed period|rssd pairs; re-run skips finished downloads."},
        {"Step": 8, "Action": "Script", "Detail": "python ONLY_TEXAS_SINCE_2025/pull_texas_since_2025.py"},
    ])))
    rows.append(("", ""))

    rows += _section("Phase B — MDRM labeling (loan product names)")
    rows.append(("__table__", pd.DataFrame([
        {"Step": 1, "Action": "Download Fed MDRM dictionary", "Detail": "https://www.federalreserve.gov/apps/mdrm/pdf/MDRM.zip → data/mdrm/MDRM_CSV.csv (~91 MB)."},
        {"Step": 2, "Action": "Build code lookup", "Detail": "mdrm_loader.py maps each code (e.g. RCON2122) to item_name, description, category, reporting_form."},
        {"Step": 3, "Action": "Filter loan-related facts", "Detail": "From texas_xbrl_facts: keep RC-C prefixes (RCON14*, RCONF1*, RCON21*, etc.) and MDRM categories loan_or_lease / schedule_rc_c."},
        {"Step": 4, "Action": "Export labeled loans", "Detail": "texas_loans_labeled.csv (~938k rows) — full detail. texas_loans_summary.csv (~31k) — main category totals only."},
        {"Step": 5, "Action": "Export catalog", "Detail": "texas_loan_products_mdrm_catalog.csv (~24k codes) with in_texas_data=yes/no flag."},
        {"Step": 6, "Action": "Script", "Detail": "python ONLY_TEXAS_SINCE_2025/extract_texas_loans.py [--summary | --catalog]"},
    ])))
    rows.append(("", ""))

    rows += _section("Phase C — Lenni taxonomy & borrower mapping")
    rows.append(("__table__", pd.DataFrame([
        {"Step": 1, "Action": "Inputs", "Detail": "texas_loan_products_mdrm_catalog.csv + MDRM_CSV.csv + content/loan_products.yaml + texas_loans_labeled.csv (for TX frequency stats)."},
        {"Step": 2, "Action": "Map codes to borrower categories", "Detail": "Assign each MDRM line to Multifamily, Investor CRE, C&I, Ag, Construction, etc. using keyword rules and YAML taxonomy."},
        {"Step": 3, "Action": "Compute Texas coverage stats", "Detail": "Number of Texas Banks Reporting and Non-Zero Balance counts per line."},
        {"Step": 4, "Action": "Outputs", "Detail": "texas_mdrm_loan_taxonomy.csv + texas_mdrm_loan_taxonomy.xlsx (Borrower View, glossary, data dictionary sheets)."},
        {"Step": 5, "Action": "Script", "Detail": "python ONLY_TEXAS_SINCE_2025/build_mdrm_taxonomy_dataset.py"},
    ])))
    rows.append(("", ""))

    rows += _section("Phase D — FDIC institution & branch enrichment")
    rows.append(("__table__", pd.DataFrame([
        {"Step": 1, "Action": "institutions.csv", "Detail": "FDIC BankFind / institutions bulk file — all U.S. banks with CERT, ASSET, CITY, WEBADDR, CB, BKCLASS, ACTIVE, etc. (~27,835 rows)."},
        {"Step": 2, "Action": "locations.csv", "Detail": "FDIC branch/office file — every U.S. branch with CERT, CITY, COUNTY, MAINOFF (~78k rows)."},
        {"Step": 3, "Action": "Definition files", "Detail": "institutions_definitions.csv, locations_definitions.csv, events_definitions.csv, sod_variables_definitions.csv — FDIC field dictionaries."},
        {"Step": 4, "Action": "Join to borrower site", "Detail": "build_borrower_site.py joins FDIC CERT to Texas loan profiles for 351 bank pages."},
    ])))
    rows.append(("", ""))

    rows += _section("Phase E — Lenni EDA analysis outputs")
    rows.append(("__table__", pd.DataFrame([
        {"Step": 1, "Action": "Master join", "Detail": "build_lenni_eda_report.py joins texas_institutions + texas_filings + texas_loans_summary + texas_xbrl_facts on id_rssd + reporting_period."},
        {"Step": 2, "Action": "ICP filter", "Detail": "Flag banks with total_assets $500M–$2B (RCON2170) as Lenni ICP."},
        {"Step": 3, "Action": "Loan mix metrics", "Detail": "Compute cre_to_loans, ci_to_loans, loan_to_asset_ratio from RCON2122, RCON1766, CRE proxy lines."},
        {"Step": 4, "Action": "Outputs", "Detail": "analysis/lenni_icp_prospect_list.csv (105 banks), asset_band_counts.csv, lenni_market_segments.csv, summary_statistics_latest.csv."},
        {"Step": 5, "Action": "Script", "Detail": "python ONLY_TEXAS_SINCE_2025/build_lenni_eda_report.py"},
    ])))
    rows.append(("", ""))

    rows += _section("Phase F — Reference workbooks (manual / internal)")
    rows += [
        ("26.05.18.All.Loan.Types.UBPR.Reference.xlsx", "Internal Lenni document mapping UBPR loan categories to FDIC fields and underwriting template build sequence. Not downloaded from API — authored for product planning."),
        ("All Financial Reports.xlsx", "Reference index of FDIC financial reports API URLs and variable definitions. Used by analysts to craft API queries, not auto-generated by pipeline."),
        ("", ""),
    ]

    rows += _section("File lineage — each workbook file traced to source")
    rows.append(("__table__", pd.DataFrame([
        {"File": "institutions_definitions.csv", "Source": "FDIC BankFind", "Pull method": "Bulk definitions download", "Pipeline script": "Manual / FDIC export"},
        {"File": "events_definitions.csv", "Source": "FDIC BankFind", "Pull method": "Bulk definitions download", "Pipeline script": "Manual / FDIC export"},
        {"File": "institutions.csv", "Source": "FDIC BankFind", "Pull method": "Institutions bulk CSV", "Pipeline script": "Manual / FDIC export"},
        {"File": "locations.csv", "Source": "FDIC BankFind", "Pull method": "Locations bulk CSV", "Pipeline script": "Manual / FDIC export"},
        {"File": "locations_definitions.csv", "Source": "FDIC BankFind", "Pull method": "Definitions file", "Pipeline script": "Manual / FDIC export"},
        {"File": "sod_variables_definitions.csv", "Source": "FDIC SOD", "Pull method": "Summary of Deposits variable defs", "Pipeline script": "Manual / FDIC export"},
        {"File": "texas_institutions.csv", "Source": "FFIEC PWS", "Pull method": "RetrievePanelOfReporters + TX filter", "Pipeline script": "pull_texas_since_2025.py"},
        {"File": "texas_filings.csv", "Source": "FFIEC PWS", "Pull method": "RetrieveFacsimile metadata", "Pipeline script": "pull_texas_since_2025.py"},
        {"File": "texas_loans_labeled.csv", "Source": "FFIEC XBRL + Fed MDRM", "Pull method": "Parse XBRL then label with MDRM", "Pipeline script": "pull_texas_since_2025.py → extract_texas_loans.py"},
        {"File": "texas_loan_products_mdrm_catalog.csv", "Source": "Fed MDRM + TX facts", "Pull method": "MDRM.zip + loan code filter", "Pipeline script": "extract_texas_loans.py --catalog"},
        {"File": "texas_mdrm_loan_taxonomy.csv", "Source": "Catalog + YAML + TX stats", "Pull method": "Taxonomy mapping build", "Pipeline script": "build_mdrm_taxonomy_dataset.py"},
        {"File": "texas_mdrm_loan_taxonomy.xlsx", "Source": "Same as taxonomy CSV", "Pull method": "Excel packaging with Borrower View", "Pipeline script": "build_mdrm_taxonomy_dataset.py"},
        {"File": "asset_band_counts.csv", "Source": "Derived", "Pull method": "Aggregate total_assets into bands", "Pipeline script": "build_lenni_eda_report.py"},
        {"File": "lenni_icp_prospect_list.csv", "Source": "Derived", "Pull method": "ICP filter + loan mix ranking", "Pipeline script": "build_lenni_eda_report.py"},
        {"File": "lenni_market_segments.csv", "Source": "Derived", "Pull method": "Segment counts by asset size", "Pipeline script": "build_lenni_eda_report.py"},
        {"File": "summary_statistics_latest.csv", "Source": "Derived", "Pull method": "describe() on latest quarter metrics", "Pipeline script": "build_lenni_eda_report.py"},
        {"File": "26.05.18.All.Loan.Types.UBPR.Reference.xlsx", "Source": "Internal Lenni", "Pull method": "Authored reference", "Pipeline script": "N/A — manual"},
        {"File": "All Financial Reports.xlsx", "Source": "FFIEC/FDIC API docs", "Pull method": "Authored API index", "Pipeline script": "N/A — manual"},
    ])))
    rows.append(("", ""))

    rows += _section("Credentials, environment, and rerun commands")
    rows += [
        (".env variables", "FFIEC_USER_ID and FFIEC_TOKEN — register at https://cdr.ffiec.gov/public/"),
        ("Python environment", "Repo .venv with pandas, openpyxl, requests, python-dotenv"),
        ("Full Texas re-pull", "cd ONLY_TEXAS_SINCE_2025 && python pull_texas_since_2025.py"),
        ("Re-label loans only", "python ONLY_TEXAS_SINCE_2025/extract_texas_loans.py"),
        ("Rebuild from archive", "python ONLY_TEXAS_SINCE_2025/rebuild_csv_from_archive.py"),
        ("Rebuild taxonomy", "python ONLY_TEXAS_SINCE_2025/build_mdrm_taxonomy_dataset.py"),
        ("Rebuild ICP analysis", "python ONLY_TEXAS_SINCE_2025/build_lenni_eda_report.py"),
        ("Rebuild this workbook", "python build_eda_workbook.py"),
        ("", ""),
    ]

    rows += _section("Important limitations (all pipelines)")
    rows += [
        ("•", "Call Report data is aggregated — no individual loan or borrower names."),
        ("•", "Dollar amounts are typically in thousands on the Call Report."),
        ("•", "Portfolio balance ≠ current underwriting appetite for your specific deal."),
        ("•", "FFIEC XBRL concepts do not contain the word 'loan' — always use MDRM codes."),
        ("•", "Texas extract covers 2025+ quarters only in ONLY_TEXAS_SINCE_2025 pipeline."),
        ("•", "FDIC institutions.csv is a national snapshot; filter STALP=TX and ACTIVE=1 for Texas."),
        ("", ""),
    ]

    rows += _section("Abbreviations used in this provenance document")
    rows.append(("__table__", _abbr_table([
        ("FFIEC", "Federal Financial Institutions Examination Council", "Regulatory council that oversees Call Reports."),
        ("CDR", "Central Data Repository", "FFIEC system storing Call Reports."),
        ("PWS", "Public Web Service", "REST API for downloading public regulatory data."),
        ("XBRL", "eXtensible Business Reporting Language", "Machine-readable format of Call Report filings."),
        ("MDRM", "Micro Data Reference Manual", "Federal Reserve dictionary of line item codes."),
        ("RCON / RCFD", "Call Report line prefixes", "Domestic office vs consolidated domestic variants."),
        ("RC-C", "Schedule RC-C", "Loans and leases section of Call Report."),
        ("RSSD / id_rssd", "Federal Reserve ID", "Institution identifier in FFIEC data."),
        ("CERT", "FDIC Certificate Number", "Institution identifier in FDIC BankFind data."),
        ("FDIC", "Federal Deposit Insurance Corporation", "Deposit insurer and bank data publisher."),
        ("UBPR", "Uniform Bank Performance Report", "Peer ratio report (separate from Call Report)."),
        ("ICP", "Ideal customer profile", "Lenni target: Texas community banks $500M–$2B."),
        ("SOD", "Summary of Deposits", "Annual FDIC branch deposit survey."),
        ("SHA-256", "Secure hash algorithm", "File integrity fingerprint."),
    ])))

    return rows
