"""Load Federal Reserve MDRM_CSV.csv and build mnemonic lookup."""

from __future__ import annotations

import csv
from pathlib import Path

MDRM_CSV = Path(__file__).resolve().parent / "data" / "mdrm" / "MDRM_CSV.csv"
MDRM_ZIP_URL = "https://www.federalreserve.gov/apps/mdrm/pdf/MDRM.zip"

CALL_FORMS = (
    "FFIEC 031",
    "FFIEC 041",
    "FFIEC 002",
    "FFIEC 032",
    "FFIEC 033",
    "FFIEC 034",
)

LOAN_KEYWORDS = (
    "loan",
    "lease",
    "lending",
    "mortgage",
    "past due",
    "nonaccrual",
    "real estate",
    "consumer",
    "credit card",
    "commercial",
    "agricult",
    "construction",
    "revolving",
    "farmland",
    "multifamily",
    "financing receivable",
    "schedule rc-c",
    "rc-c",
)


def _clean(text: str) -> str:
    return text.replace("&#x0D;", " ").replace("\r", " ").replace("\n", " ").strip()


def load_mdrm_lookup(
    path: Path | None = None,
    *,
    call_only: bool = False,
) -> dict[str, dict[str, str]]:
    """
    Returns dict keyed by MDRM id (e.g. RCON2122) with item_name, description,
    reporting_form, item_type, mdrm_category.
    """
    csv_path = path or MDRM_CSV
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"MDRM file missing: {csv_path}. Download from {MDRM_ZIP_URL}"
        )

    lookup: dict[str, dict[str, str]] = {}

    with csv_path.open(encoding="utf-8", errors="replace") as f:
        first = f.readline()
        if first.strip().upper() != "PUBLIC":
            f.seek(0)
        reader = csv.DictReader(f)
        for row in reader:
            mnem = (row.get("Mnemonic") or "").strip()
            code = (row.get("Item Code") or "").strip()
            if not mnem or not code:
                continue
            mdrm_id = f"{mnem}{code}"
            form = (row.get("Reporting Form") or "").strip()
            is_call = any(cf in form for cf in CALL_FORMS)
            if call_only and not is_call:
                continue

            name = _clean(row.get("Item Name") or "")
            desc = _clean(row.get("Description") or "")
            item_type = (row.get("ItemType") or "").strip()
            text = (name + " " + desc).lower()
            category = "other"
            if any(k in text for k in LOAN_KEYWORDS):
                category = "loan_or_lease"
            if "schedule rc-c" in text or "rc-c" in name.lower():
                category = "schedule_rc_c"

            entry = {
                "item_name": name,
                "description": desc[:800],
                "reporting_form": form,
                "item_type": item_type,
                "mdrm_category": category,
            }
            prev = lookup.get(mdrm_id)
            if prev is None or (is_call and "FFIEC" not in prev.get("reporting_form", "")):
                lookup[mdrm_id] = entry

    return lookup


def enrich_code(lookup: dict[str, dict[str, str]], mdrm_code: str) -> dict[str, str]:
    """Return MDRM fields for a code, with fallbacks."""
    base = lookup.get(mdrm_code, {})
    return {
        "mdrm_code": mdrm_code,
        "item_name": base.get("item_name", ""),
        "line_description": base.get("item_name") or f"Unknown MDRM code {mdrm_code}",
        "mdrm_description": base.get("description", ""),
        "reporting_form": base.get("reporting_form", ""),
        "item_type": base.get("item_type", ""),
        "mdrm_category": base.get("mdrm_category", "other"),
    }
