#!/usr/bin/env python3
"""Smoke tests for match_deal engine."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from match_deal import match_deal, parse_listing_text


def test_land_hold():
    r = match_deal(
        "12.4 acre land lot near Brenham TX asking $849,000 — holding for investment",
        metro="College Station",
        use_llm=False,
    )
    assert r["listing_profile"]["parent_key"] == "con"
    assert len(r["loan_products"]) >= 1
    assert len(r["recommended_banks"]) >= 3
    assert r["roadmap"]["steps"]


def test_multifamily_bridge():
    r = match_deal(
        "40-unit apartment value-add bridge loan in Fort Worth $4.2M",
        use_llm=False,
    )
    assert r["listing_profile"]["parent_key"] == "mf"
    titles = [p["title"] for p in r["loan_products"]]
    assert any("bridge" in t.lower() or "value" in t.lower() or "acquisition" in t.lower() for t in titles)


def test_ci_line():
    r = match_deal("working capital line of credit for manufacturing business in Houston", use_llm=False)
    assert r["listing_profile"]["parent_key"] == "ci"


if __name__ == "__main__":
    test_land_hold()
    test_multifamily_bridge()
    test_ci_line()
    print("match_deal tests OK")
