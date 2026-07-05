"""Load Texas bank portfolio data for deal matching."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SITE_BANKS = REPO / "borrower_site" / "data" / "banks.json"
EXPORTS_BANKS = ROOT / "exports" / "texas_bank_profiles_latest.csv"


@lru_cache(maxsize=1)
def load_banks() -> tuple[list[dict], str]:
    """Return (banks, reporting_period). Prefers built site JSON."""
    if SITE_BANKS.is_file():
        payload = json.loads(SITE_BANKS.read_text(encoding="utf-8"))
        banks = payload.get("banks") or payload
        period = payload.get("period", "") if isinstance(payload, dict) else ""
        if isinstance(banks, list) and banks:
            return banks, str(period)

    # Fallback: rebuild from site builder logic when JSON missing.
    from build_borrower_site import load_enriched_banks

    banks, period = load_enriched_banks()
    return banks, period
