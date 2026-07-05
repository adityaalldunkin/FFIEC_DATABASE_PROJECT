#!/usr/bin/env python3
"""
Build a unified MDRM loan taxonomy export (mapped rows only).

Outputs:
  - texas_mdrm_loan_taxonomy.csv   (plain-English column headers)
  - texas_mdrm_loan_taxonomy.xlsx  (data + data dictionary + glossary sheets)

Combines:
  - texas_loan_products_mdrm_catalog.csv
  - Federal Reserve MDRM_CSV.csv (schedule, dates, item type, confidentiality)
  - content/loan_products.yaml (Lenni loan type / subtype taxonomy)
  - texas_loans_labeled.csv (Texas filing frequency stats, when present)

Usage:
  python ONLY_TEXAS_SINCE_2025/build_mdrm_taxonomy_dataset.py
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from loan_product_loader import load_parents
from mdrm_taxonomy_export import write_public_csv, write_workbook

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CATALOG = REPO / "texas_loan_products_mdrm_catalog.csv"
MDRM_CSV = ROOT / "data" / "mdrm" / "MDRM_CSV.csv"
LABELED = REPO / "texas_loans_labeled.csv"
OUT_REPO = REPO / "texas_mdrm_loan_taxonomy.csv"
OUT_XLSX = REPO / "texas_mdrm_loan_taxonomy.xlsx"
OUT_EXPORTS = ROOT / "exports" / "texas_mdrm_loan_taxonomy.csv"
OUT_XLSX_EXPORTS = ROOT / "exports" / "texas_mdrm_loan_taxonomy.xlsx"

CALL_FORMS = (
    "FFIEC 031",
    "FFIEC 041",
    "FFIEC 002",
    "FFIEC 032",
    "FFIEC 033",
    "FFIEC 034",
)

ITEM_TYPE_LABELS = {
    "F": "Financial / reported amount",
    "D": "Derived",
    "J": "Projected",
    "R": "Rate (decimal)",
    "P": "Percentage",
    "S": "Structure / institution attribute",
    "E": "Examination / supervision",
}

OFFICE_SCOPE = {
    "RCON": "Domestic offices (FFIEC 031 larger banks)",
    "RCFD": "Consolidated / domestic offices (often FFIEC 041 community banks)",
    "RCONF": "Schedule RC-C extension — domestic offices",
    "RCONHK": "Schedule RC-C memoranda — domestic offices",
    "RCONJ4": "Schedule RC-C extension detail — domestic offices",
    "RCONA5": "Schedule RC-C extension — domestic offices",
    "RCONB5": "Schedule RC-C supplemental — domestic offices",
    "RCONLL": "Lease financing lines — domestic offices",
    "RCONS4": "FFIEC 051 supplemental — domestic offices",
    "RCONB5": "FFIEC 051 consumer lines",
    "RIAD": "Income statement (Schedule RI)",
    "RIAA": "Income statement average",
}

METRIC_BY_CODE = {
    "RCON2122": "total_loans_gross",
    "RCFD2122": "total_loans_gross",
    "RCON2145": "total_loans_net",
    "RCON2130": "allowance_loan_losses",
    "RCON1420": "farmland_loans",
    "RCON1460": "multifamily_re_loans",
    "RCONF158": "residential_construction",
    "RCONF159": "other_construction_ld",
    "RCONF160": "owner_occupied_nonfarm_re",
    "RCONF161": "other_nonfarm_nonres_re",
    "RCONF162": "commercial_re_loans",
    "RCON1545": "credit_card_plans",
    "RCON1583": "other_consumer_loans",
    "RCON1754": "lease_financing",
    "RCON5367": "past_due_30_89",
    "RCON5368": "past_due_90_plus",
    "RCON1403": "residential_1_4_family",
    "RCON1590": "ag_production_loans",
    "RCONS439": "residential_mortgage_exposures",
    "RCONB562": "consumer_other_051",
    "RCONB539": "consumer_revolving_051",
    "RCON2170": "total_assets",
    "RCON1766": "ci_loans",
}

EXTRA_LOAN_TYPE = {
    "RCON2122": ("Portfolio totals", "total", "portfolio-totals"),
    "RCFD2122": ("Portfolio totals", "total", "portfolio-totals"),
    "RCON2145": ("Portfolio totals", "total", "portfolio-totals"),
    "RCON2130": ("Portfolio totals", "total", "allowance"),
    "RCON1400": ("1–4 Family Residential", "res", "residential-14"),
    "RCON1480": ("Investor CRE (income property)", "inv", "investor-cre"),
    "RCON1545": ("Consumer lending", "cons", "consumer"),
    "RCON1583": ("Consumer lending", "cons", "consumer"),
    "RCONB562": ("Consumer lending", "cons", "consumer"),
    "RCONB539": ("Consumer lending", "cons", "consumer"),
    "RCON1754": ("Lease financing", "lease", "lease-financing"),
    "RCON5367": ("Credit quality", "quality", "credit-quality"),
    "RCON5368": ("Credit quality", "quality", "credit-quality"),
    "RCON5369": ("Credit quality", "quality", "credit-quality"),
    "RCON1797": ("1–4 Family Residential", "res", "residential-14"),
    "RCON2170": ("Balance sheet", "bs", "balance-sheet"),
}

SCHEDULE_RE = re.compile(
    r"Schedule\s+(RC-[A-Z0-9]+)(?:\s+Part\s+([IVXLC\d.]+))?(?:[^;]*?item\s+([\w.()]+))?",
    re.IGNORECASE,
)
UBPR_RE = re.compile(r"FDIC's Data Element name is\s+([A-Z0-9_-]+)", re.IGNORECASE)
DATE_FORMATS = ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y")


def parse_dt(text: str) -> datetime | None:
    text = (text or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""


def load_mdrm_metadata() -> dict[str, dict[str, str]]:
    """Best current Call Report row per mdrm_code from MDRM_CSV.csv."""
    if not MDRM_CSV.is_file():
        return {}

    best: dict[str, dict[str, str]] = {}
    with MDRM_CSV.open(encoding="utf-8", errors="replace") as f:
        first = f.readline()
        if first.strip().upper() != "PUBLIC":
            f.seek(0)
        for row in csv.DictReader(f):
            mnem = (row.get("Mnemonic") or "").strip()
            code = (row.get("Item Code") or "").strip()
            if not mnem or not code:
                continue
            mdrm_id = f"{mnem}{code}"
            form = (row.get("Reporting Form") or "").strip()
            end = parse_dt(row.get("End Date") or "")
            is_call = any(cf in form for cf in CALL_FORMS)

            score = 0
            if is_call:
                score += 100
            if end and end.year >= 9999:
                score += 50
            elif end and end.year >= 2020:
                score += 20
            if "FFIEC 031" in form or "FFIEC 041" in form:
                score += 10

            entry = {
                "mnemonic": mnem,
                "item_code": code,
                "mdrm_start_date": fmt_date(parse_dt(row.get("Start Date") or "")),
                "mdrm_end_date": fmt_date(end),
                "confidentiality": (row.get("Confidentiality") or "").strip(),
                "item_type_code": (row.get("ItemType") or "").strip(),
                "reporting_form_primary": form,
                "mdrm_description_full": (row.get("Description") or "").replace("\n", " ").strip(),
            }
            prev = best.get(mdrm_id)
            if prev is None or score > int(prev.get("_score", 0)):
                entry["_score"] = str(score)
                best[mdrm_id] = entry

    for entry in best.values():
        entry.pop("_score", None)
    return best


def load_texas_usage() -> dict[str, dict[str, int]]:
    """Bank/observation counts per mdrm_code from labeled Texas loan facts."""
    if not LABELED.is_file():
        return {}

    stats: dict[str, dict] = {}
    with LABELED.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = row["mdrm_code"].strip()
            if code not in stats:
                stats[code] = {"texas_banks": set(), "texas_observations": 0, "texas_nonzero_obs": 0}
            bucket = stats[code]
            bucket["texas_banks"].add(row["id_rssd"])
            bucket["texas_observations"] += 1
            try:
                val = float(row["value_num"] or 0)
            except (TypeError, ValueError):
                val = 0.0
            if val != 0:
                bucket["texas_nonzero_obs"] += 1

    out: dict[str, dict[str, int]] = {}
    for code, bucket in stats.items():
        out[code] = {
            "texas_bank_count": len(bucket["texas_banks"]),
            "texas_observations": bucket["texas_observations"],
            "texas_nonzero_obs": bucket["texas_nonzero_obs"],
        }
    return out


def build_code_to_parent() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for parent in load_parents():
        for code in parent.get("mdrm") or []:
            out.setdefault(code, parent)
    return out


def explicit_yaml_codes() -> set[str]:
    codes: set[str] = set()
    for parent in load_parents():
        codes.update(parent.get("mdrm") or [])
    return codes


def infer_parent(
    code: str,
    item_name: str,
    description: str,
    parents: list[dict],
    code_to_parent: dict[str, dict],
) -> dict | None:
    if code in code_to_parent:
        return code_to_parent[code]

    if not (code.startswith("RCON") or code.startswith("RCFD")):
        return None

    text = f"{item_name} {description}".lower()

    prefix_rules: list[tuple[str, str]] = [
        ("RCONF158", "con"),
        ("RCONF159", "con"),
        ("RCONF160", "own"),
        ("RCONF161", "inv"),
        ("RCONF162", "inv"),
        ("RCONF163", "inv"),
        ("RCON1460", "mf"),
        ("RCON1766", "ci"),
        ("RCON1763", "ci"),
        ("RCON1420", "oth"),
        ("RCON1590", "oth"),
        ("RCON1403", "res"),
        ("RCON1400", "res"),
        ("RCON1480", "inv"),
    ]
    parent_by_key = {p["key"]: p for p in parents}
    for prefix, key in prefix_rules:
        if code.startswith(prefix) or code == prefix:
            return parent_by_key.get(key)

    if code.startswith("RCON14") or code.startswith("RCFD14"):
        if any(k in text for k in ("multifamily", "5 or more", "5+", "apartment")):
            return parent_by_key.get("mf")
        if any(k in text for k in ("farmland", "farm land")):
            return parent_by_key.get("oth")
        return parent_by_key.get("res")

    if code.startswith("RCON17") or code.startswith("RCFD17"):
        if "lease" not in text:
            return parent_by_key.get("ci")

    if code.startswith("RCONF1") or code.startswith("RCONF2"):
        if any(k in text for k in ("construction", "land development", "land loan")):
            return parent_by_key.get("con")
        if any(k in text for k in ("owner occupied", "owner-occupied")):
            return parent_by_key.get("own")
        if any(k in text for k in ("commercial real estate", "nonfarm nonresidential", "income")):
            return parent_by_key.get("inv")

    best_parent: dict | None = None
    best_score = 0
    for parent in parents:
        score = 0
        for kw in parent.get("keywords") or []:
            if kw.lower() in text:
                score += max(3, len(kw))
        for bit in parent["name"].lower().replace("–", "-").split():
            if len(bit) > 3 and bit in text:
                score += 2
        if score > best_score:
            best_score = score
            best_parent = parent
    return best_parent if best_score >= 4 else None


def best_subtype(parent: dict, item_name: str, description: str) -> dict | None:
    text = f"{item_name} {description}".lower()
    best: dict | None = None
    best_score = 0
    for st in parent.get("subtypes") or []:
        score = sum(max(3, len(kw)) for kw in (st.get("keywords") or []) if kw.lower() in text)
        if score > best_score:
            best_score = score
            best = st
    return best if best_score >= 3 else None


def parse_schedule_fields(description: str) -> dict[str, str]:
    m = SCHEDULE_RE.search(description or "")
    if not m:
        return {"schedule_code": "", "schedule_part": "", "schedule_item": "", "schedule": ""}
    code, part, item = m.group(1), (m.group(2) or "").strip(), (m.group(3) or "").strip()
    schedule = f"Schedule {code}"
    if part:
        schedule += f" Part {part}"
    if item:
        schedule += f" item {item}"
    return {
        "schedule_code": code,
        "schedule_part": part,
        "schedule_item": item,
        "schedule": schedule,
    }


def office_scope_label(code: str) -> str:
    for prefix, label in OFFICE_SCOPE.items():
        if code.startswith(prefix):
            return label
    if code.startswith("RCON"):
        return OFFICE_SCOPE["RCON"]
    if code.startswith("RCFD"):
        return OFFICE_SCOPE["RCFD"]
    return ""


def mdrm_family(code: str) -> str:
    if code.startswith("RCONF"):
        return "RCONF"
    if code.startswith("RCON"):
        return "RCON"
    if code.startswith("RCFD"):
        return "RCFD"
    return "other"


def reporting_dimension(code: str, item_name: str, description: str) -> str:
    text = f"{item_name} {description}".upper()
    if "NUMBER OF" in text or text.startswith("COUNT"):
        return "count"
    if any(k in text for k in ("PAST DUE", "NONACCRUAL", "PAST-DUE")):
        return "credit_quality"
    if any(k in text for k in ("CHARGE-OFF", "CHARGE OFF", "RECOVERY", "PROVISION")):
        return "credit_loss_flow"
    if any(k in text for k in ("INTEREST INCOME", "INTEREST AND FEE", "RI-")):
        return "income_statement"
    if any(k in text for k in ("REMAINING MATURITY", "REPRICING", "NEXT REPRICING")):
        return "maturity_repricing"
    if any(k in text for k in ("MEMORANDUM", "HK", "JJ")):
        return "memorandum"
    if code in METRIC_BY_CODE or any(k in text for k in ("TOTAL LOANS", "NET LOANS", "ALLOWANCE")):
        return "portfolio_total"
    if code.startswith("RIAD") or code.startswith("RIAA"):
        return "income_statement"
    return "product_balance"


def collateral_class(item_name: str, description: str) -> str:
    text = f"{item_name} {description}".lower()
    rules = [
        ("multifamily", "Multifamily (5+ units)"),
        ("1-4 family", "1–4 family residential"),
        ("1–4 family", "1–4 family residential"),
        ("farmland", "Farmland"),
        ("agricult", "Agricultural production"),
        ("owner occupied", "Owner-occupied nonfarm CRE"),
        ("owner-occupied", "Owner-occupied nonfarm CRE"),
        ("nonfarm nonresidential", "Nonfarm nonresidential CRE"),
        ("commercial and industrial", "Commercial & industrial"),
        ("commercial & industrial", "Commercial & industrial"),
        ("credit card", "Credit card"),
        ("consumer", "Consumer"),
        ("construction", "Construction / land development"),
        ("lease", "Lease financing"),
        ("real estate", "Real estate (unspecified)"),
    ]
    for needle, label in rules:
        if needle in text:
            return label
    return ""


def ffiec_form_size(reporting_form: str) -> str:
    form = reporting_form or ""
    if re.search(r"FFIEC\s+0?31\b", form):
        return "FFIEC 031 (larger banks)"
    if re.search(r"FFIEC\s+0?41\b", form):
        return "FFIEC 041 (community banks)"
    if re.search(r"FFIEC\s+0?51\b", form):
        return "FFIEC 051 (supplemental)"
    return form


def loan_type_fields(code: str, parent: dict | None) -> dict[str, str]:
    if parent:
        return {
            "loan_type": parent["name"],
            "loan_type_key": parent["key"],
            "loan_type_slug": parent["slug"],
            "loan_type_category": parent.get("cat", ""),
            "loan_type_short": parent.get("short", ""),
            "loan_type_lines": parent.get("lines", ""),
        }
    extra = EXTRA_LOAN_TYPE.get(code)
    if extra:
        name, key, slug = extra
        return {
            "loan_type": name,
            "loan_type_key": key,
            "loan_type_slug": slug,
            "loan_type_category": "",
            "loan_type_short": "",
            "loan_type_lines": "",
        }
    return {
        "loan_type": "",
        "loan_type_key": "",
        "loan_type_slug": "",
        "loan_type_category": "",
        "loan_type_short": "",
        "loan_type_lines": "",
    }


def main() -> int:
    if not CATALOG.is_file():
        print(f"Missing catalog: {CATALOG}")
        print("Run: python ONLY_TEXAS_SINCE_2025/extract_texas_loans.py --catalog")
        return 1

    print("Loading MDRM metadata …")
    mdrm_meta = load_mdrm_metadata()
    print("Loading Texas usage stats …")
    texas_usage = load_texas_usage()

    parents = load_parents()
    code_to_parent = build_code_to_parent()
    yaml_explicit = explicit_yaml_codes()

    rows: list[dict[str, str]] = []
    skipped = 0

    with CATALOG.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = row["mdrm_code"].strip()
            item_name = row.get("item_name", "").strip()
            catalog_desc = row.get("mdrm_description", "").strip()
            meta = mdrm_meta.get(code, {})
            description = meta.get("mdrm_description_full") or catalog_desc

            parent = infer_parent(code, item_name, description, parents, code_to_parent)
            lt = loan_type_fields(code, parent)
            if not lt["loan_type"]:
                skipped += 1
                continue

            subtype = best_subtype(parent, item_name, description) if parent else None
            metric = METRIC_BY_CODE.get(code, "")
            sched = parse_schedule_fields(description)
            item_type_code = meta.get("item_type_code") or row.get("item_type", "")
            reporting_form = row.get("reporting_form", "") or meta.get("reporting_form_primary", "")
            usage = texas_usage.get(code, {})
            ubpr = UBPR_RE.search(description)
            in_texas = row.get("in_texas_data", "").lower() == "yes" or bool(usage)

            rows.append(
                {
                    "mdrm_code": code,
                    "mnemonic": meta.get("mnemonic", code[:4] if len(code) >= 4 else ""),
                    "item_code": meta.get("item_code", code[4:] if len(code) > 4 else ""),
                    "mdrm_family": mdrm_family(code),
                    "office_scope": office_scope_label(code),
                    **lt,
                    "sub_type": (subtype or {}).get("title", ""),
                    "sub_type_slug": (subtype or {}).get("slug", ""),
                    "sub_sub_type": metric or (subtype or {}).get("slug", ""),
                    "metric_column": metric,
                    "in_eda_summary": "yes" if metric else "no",
                    "explicit_taxonomy_mapping": "yes" if code in yaml_explicit else "no",
                    "item_name": item_name,
                    "line_description": item_name,
                    "mdrm_description": description[:1200],
                    "sub_type_one_liner": (subtype or {}).get("one_liner", ""),
                    "collateral_class": collateral_class(item_name, description),
                    "reporting_dimension": reporting_dimension(code, item_name, description),
                    **sched,
                    "mdrm_category": row.get("mdrm_category", ""),
                    "reporting_form": reporting_form,
                    "reporting_form_primary": meta.get("reporting_form_primary", reporting_form),
                    "ffiec_form_size": ffiec_form_size(reporting_form),
                    "item_type": item_type_code,
                    "item_type_code": item_type_code,
                    "item_type_label": ITEM_TYPE_LABELS.get(item_type_code, ""),
                    "confidentiality": meta.get("confidentiality", ""),
                    "mdrm_start_date": meta.get("mdrm_start_date", ""),
                    "mdrm_end_date": meta.get("mdrm_end_date", ""),
                    "ubpr_element": ubpr.group(1) if ubpr else "",
                    "value_units": "USD thousands" if item_type_code == "F" else "",
                    "in_texas_data": "yes" if in_texas else "no",
                    "texas_bank_count": str(usage.get("texas_bank_count", "")),
                    "texas_observations": str(usage.get("texas_observations", "")),
                    "texas_nonzero_obs": str(usage.get("texas_nonzero_obs", "")),
                    "mdrm_lookup_url": f"https://www.federalreserve.gov/apps/mdrm/data-dictionary?mdrm={code}",
                }
            )

    rows.sort(key=lambda r: (r["loan_type"], r["mdrm_code"]))

    for out_path in (OUT_REPO, OUT_EXPORTS):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_public_csv(out_path, rows)

    for out_path in (OUT_XLSX, OUT_XLSX_EXPORTS):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        write_workbook(out_path, rows)

    in_tx = sum(1 for r in rows if r["in_texas_data"] == "yes")
    print(f"Wrote {len(rows):,} mapped rows → {OUT_REPO}")
    print(f"Workbook (data + dictionary) → {OUT_XLSX}")
    print(f"Also → {OUT_EXPORTS}")
    print(f"Also → {OUT_XLSX_EXPORTS}")
    print(f"  Skipped (no loan_type): {skipped:,}")
    print(f"  In Texas data:          {in_tx:,}")
    print(f"  In EDA summary:         {sum(1 for r in rows if r['in_eda_summary']=='yes'):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
