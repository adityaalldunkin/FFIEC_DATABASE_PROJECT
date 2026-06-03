#!/usr/bin/env python3
"""
Enrich texas_xbrl_facts with Federal Reserve MDRM labels → loan CSV exports.

Requires: ONLY_TEXAS_SINCE_2025/data/mdrm/MDRM_CSV.csv
  (from https://www.federalreserve.gov/apps/mdrm/pdf/MDRM.zip)

  python extract_texas_loans.py
  python extract_texas_loans.py --summary
  python extract_texas_loans.py --catalog   # MDRM loan dictionary only
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from mdrm_loader import LOAN_KEYWORDS, load_mdrm_lookup

ROOT = Path(__file__).resolve().parent
FACTS = ROOT / "exports" / "texas_xbrl_facts.csv"
OUT = ROOT / "exports" / "texas_loans_labeled.csv"
OUT_SUMMARY = ROOT / "exports" / "texas_loans_summary.csv"
OUT_CATALOG = ROOT / "exports" / "texas_loan_products_mdrm_catalog.csv"

# Core Schedule RC-C / loan totals for --summary
SUMMARY_CODES = frozenset(
    {
        "RCON2122", "RCFD2122", "RCON2145", "RCON2130", "RCON1400", "RCON1403",
        "RCON1420", "RCON1460", "RCON1480", "RCON1545", "RCON1583", "RCON1590",
        "RCON1754", "RCON1797", "RCON5367", "RCON5368", "RCON5369",
        "RCONF158", "RCONF159", "RCONF160", "RCONF161", "RCONF162", "RCONF163",
    }
)

LOAN_PREFIXES = (
    "RCON14", "RCON15", "RCON16", "RCON17", "RCON21",
    "RCONF1", "RCONF2", "RCONHK", "RCONJ4", "RCONLL", "RCONA5", "RCONB5",
    "RCFD14", "RCFD15", "RCFD16", "RCFD21", "RCFDHK", "RCFDJ4", "RCFDLL",
)


def local_concept(full: str) -> str:
    return full.rsplit("}", 1)[-1] if "}" in full else full


def is_metadata_code(code: str) -> bool:
    return code in {
        "measure", "period", "xbrl", "entity", "identifier",
        "instant", "startDate", "endDate",
    }


def is_loan_row(code: str, lookup: dict) -> bool:
    if code in SUMMARY_CODES:
        return True
    info = lookup.get(code, {})
    if info.get("mdrm_category") in ("loan_or_lease", "schedule_rc_c"):
        return True
    if any(code.startswith(p) for p in LOAN_PREFIXES):
        return True
    return False


def write_catalog(lookup: dict, codes_in_data: set[str]) -> int:
    fieldnames = [
        "mdrm_code",
        "item_name",
        "mdrm_description",
        "mdrm_category",
        "reporting_form",
        "item_type",
        "in_texas_data",
    ]
    loan_codes = []
    for code in sorted(codes_in_data):
        if is_metadata_code(code):
            continue
        info = lookup.get(code, {})
        if is_loan_row(code, lookup) or info.get("mdrm_category") in (
            "loan_or_lease",
            "schedule_rc_c",
        ):
            loan_codes.append(code)
    # Also add CALL loan MDRM entries that match keywords (reference)
    for code, info in lookup.items():
        if info.get("mdrm_category") in ("loan_or_lease", "schedule_rc_c"):
            if code not in loan_codes:
                loan_codes.append(code)

    seen = set()
    with OUT_CATALOG.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for code in sorted(set(loan_codes)):
            if code in seen:
                continue
            seen.add(code)
            info = lookup.get(code, {})
            w.writerow(
                {
                    "mdrm_code": code,
                    "item_name": info.get("item_name", ""),
                    "mdrm_description": info.get("description", ""),
                    "mdrm_category": info.get("mdrm_category", ""),
                    "reporting_form": info.get("reporting_form", ""),
                    "item_type": info.get("item_type", ""),
                    "in_texas_data": "yes" if code in codes_in_data else "no",
                }
            )
    return len(seen)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--catalog", action="store_true", help="Only write MDRM catalog CSV")
    args = parser.parse_args()

    print("Loading Federal Reserve MDRM dictionary …")
    lookup = load_mdrm_lookup()

    if args.catalog:
        codes = set()
        if FACTS.is_file():
            with FACTS.open(encoding="utf-8", errors="replace") as fin:
                for row in csv.DictReader(fin):
                    codes.add(local_concept(row.get("concept", "")))
        n = write_catalog(lookup, codes)
        print(f"Wrote {n:,} loan/lease MDRM definitions → {OUT_CATALOG}")
        return 0

    if not FACTS.is_file():
        print(f"Missing {FACTS}")
        return 1

    out_path = OUT_SUMMARY if args.summary else OUT
    fieldnames = [
        "id_rssd",
        "institution_name",
        "reporting_period",
        "mdrm_code",
        "item_name",
        "line_description",
        "mdrm_description",
        "mdrm_category",
        "reporting_form",
        "item_type",
        "value_num",
        "value_text",
        "context_ref",
        "unit_ref",
    ]

    codes_seen: set[str] = set()
    n = 0
    with FACTS.open(encoding="utf-8", errors="replace") as fin, out_path.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            code = local_concept(row.get("concept", ""))
            if is_metadata_code(code):
                continue
            codes_seen.add(code)
            if args.summary:
                if code not in SUMMARY_CODES:
                    continue
            elif not is_loan_row(code, lookup):
                continue

            info = lookup.get(code, {})
            item_name = info.get("item_name", "")
            writer.writerow(
                {
                    "id_rssd": row["id_rssd"],
                    "institution_name": row["institution_name"],
                    "reporting_period": row["reporting_period"],
                    "mdrm_code": code,
                    "item_name": item_name,
                    "line_description": item_name or f"MDRM {code}",
                    "mdrm_description": info.get("description", ""),
                    "mdrm_category": info.get("mdrm_category", "loan_related_prefix"),
                    "reporting_form": info.get("reporting_form", ""),
                    "item_type": info.get("item_type", ""),
                    "value_num": row.get("value_num", ""),
                    "value_text": row.get("value_text", ""),
                    "context_ref": row.get("context_ref", ""),
                    "unit_ref": row.get("unit_ref", ""),
                }
            )
            n += 1

    cat_n = write_catalog(lookup, codes_seen)
    print(f"Wrote {n:,} rows → {out_path}")
    print(f"Wrote {cat_n:,} MDRM loan product definitions → {OUT_CATALOG}")
    if args.summary:
        print("Tip: omit --summary for full RC-C detail with MDRM labels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
