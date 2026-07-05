#!/usr/bin/env python3
"""Tests for Lenni conversational loan advisory chat engine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Force rules-only for deterministic tests
os.environ["LENNI_LLM_PROVIDER"] = "rules"

from chat_engine import chat_turn, get_session, opening_message, reset_session  # noqa: E402
from chat_state import DealState  # noqa: E402
from guardrails import check_input  # noqa: E402
from knowledge_rag import retrieve  # noqa: E402


def test_opening_message():
    msg = opening_message()
    assert "Lenni" in msg
    assert "not a bank" in msg.lower() or "not a bank" in msg


def test_slot_extraction_land():
    state = DealState()
    state.update_slots({"parent_key": "con", "intent": "hold", "acres": 12.4})
    assert state.missing_slots()
    assert "city" in state.missing_slots() or "price_n" in state.missing_slots()


def test_multifamily_full_flow():
    sid = "test-mf-flow"
    reset_session(sid)

    r1 = chat_turn(
        "40-unit apartment value-add bridge in Fort Worth, $4.2 million",
        session_id=sid,
        reset=True,
    )
    assert r1["session_id"]
    assert r1["state"]["slots"].get("parent_key") == "mf"
    assert r1["state"]["slots"].get("units") == 40

    # Fill missing slots if needed
    if not r1["state"]["ready_for_match"]:
        r2 = chat_turn("Fort Worth, Texas. Closing in 60 days.", session_id=sid)
        assert r2["state"]["slots"].get("city") or r2["state"]["slots"].get("metro")

    state = get_session(sid)
    if state.ready_for_match():
        r3 = chat_turn("yes", session_id=sid)
        assert r3.get("package_ready") or "loan package" in r3["reply"].lower()
        assert r3.get("match_result")
        banks = r3["match_result"].get("recommended_banks") or []
        assert len(banks) >= 3
        primary = r3["match_result"].get("primary_product") or {}
        assert "bridge" in primary.get("title", "").lower() or "multifamily" in primary.get("parent_name", "").lower()


def test_ci_working_capital():
    sid = "test-ci"
    reset_session(sid)
    r = chat_turn(
        "working capital line of credit for manufacturing business in Houston, need $2M",
        session_id=sid,
        reset=True,
    )
    assert r["state"]["slots"].get("parent_key") == "ci"


def test_land_hold_brenham():
    sid = "test-land"
    reset_session(sid)
    r = chat_turn(
        "12.4 acre land lot near Brenham TX asking $849,000 — holding for investment",
        session_id=sid,
        reset=True,
    )
    assert r["state"]["slots"].get("parent_key") == "con"
    assert r["state"]["slots"].get("intent") == "hold"


def test_guardrail_rate_request():
    check = check_input("What interest rate will I get?")
    assert "rate_or_approval_request" in check["flags"]
    sid = "test-rate"
    reset_session(sid)
    r = chat_turn("What interest rate will I get on a $3M loan?", session_id=sid, reset=True)
    assert "can't quote rates" in r["reply"].lower() or "cannot" in r["reply"].lower() or "can't" in r["reply"].lower()


def test_rag_retrieval():
    chunks = retrieve("multifamily bridge value-add apartment", parent_key="mf")
    assert len(chunks) >= 1
    assert any("multifamily" in c["text"].lower() or "bridge" in c["text"].lower() for c in chunks)


def test_owner_occupied_waco():
    sid = "test-own"
    reset_session(sid)
    r = chat_turn(
        "I want to buy the building my manufacturing business operates out of in Waco for $3.1 million",
        session_id=sid,
        reset=True,
    )
    assert r["state"]["slots"].get("parent_key") in ("own", "inv", "ci")


def run_all():
    tests = [
        test_opening_message,
        test_slot_extraction_land,
        test_multifamily_full_flow,
        test_ci_working_capital,
        test_land_hold_brenham,
        test_guardrail_rate_request,
        test_rag_retrieval,
        test_owner_occupied_waco,
    ]
    passed = 0
    failed = []
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  OK  {t.__name__}")
        except Exception as exc:
            failed.append((t.__name__, exc))
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{passed}/{len(tests)} passed")
    if failed:
        for name, exc in failed:
            print(f"  - {name}: {exc}")
        raise SystemExit(1)
    print("All chat engine tests passed.")


if __name__ == "__main__":
    run_all()
