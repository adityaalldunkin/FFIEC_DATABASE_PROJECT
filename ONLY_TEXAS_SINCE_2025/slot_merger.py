"""Merge slot extractions from multiple extractors; detect disagreements."""

from __future__ import annotations

from typing import Any

CRITICAL_SLOTS = frozenset({"parent_key", "intent"})


def _normalize_val(key: str, val: Any) -> Any:
    if val is None or val == "":
        return None
    if key in ("units", "occupancy_pct"):
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    if key in ("price_n", "acres"):
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
    return val


def merge_extractions(
    turn_slots: dict[str, Any],
    context_slots: dict[str, Any],
    *,
    current_slots: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Merge turn-focused (current message) and context-focused (full log) extractions.

    Policy:
    - Turn slots win when present (borrower correction in latest message).
    - Context fills gaps only.
    - Record disagreements on critical fields when both sources disagree.
    """
    current_slots = current_slots or {}
    merged: dict[str, Any] = dict(current_slots)
    disagreements: list[dict[str, Any]] = []

    all_keys = set(turn_slots) | set(context_slots) | set(current_slots)
    for key in all_keys:
        turn_val = _normalize_val(key, turn_slots.get(key))
        ctx_val = _normalize_val(key, context_slots.get(key))

        if turn_val is not None and ctx_val is not None and turn_val != ctx_val:
            disagreements.append({
                "field": key,
                "turn_value": turn_val,
                "context_value": ctx_val,
                "resolved_to": turn_val,
                "critical": key in CRITICAL_SLOTS,
            })
            merged[key] = turn_val  # latest message wins
        elif turn_val is not None:
            merged[key] = turn_val
        elif ctx_val is not None:
            merged[key] = ctx_val

    critical_disagreements = [d for d in disagreements if d["critical"]]
    return {
        "merged": {k: v for k, v in merged.items() if v is not None},
        "disagreements": disagreements,
        "needs_clarification": len(critical_disagreements) > 0,
        "clarification_fields": [d["field"] for d in critical_disagreements],
    }


def clarification_question(fields: list[str]) -> str:
    if "parent_key" in fields:
        return (
            "I want to make sure I have the property type right — "
            "is this apartments/multifamily, investor CRE, land, owner-occupied, or a business loan?"
        )
    if "intent" in fields:
        return (
            "Just to confirm your plan — are you buying, building, refinancing, "
            "holding land, or doing a value-add/bridge deal?"
        )
    return "Can you clarify the property type and what you plan to do with it?"
