#!/usr/bin/env python3
"""
Compare slot extraction: baseline (single-pass) vs task-based routing (dual extract + merge).

Runs 28 golden eval cases from eval/task_routing_eval_cases.yaml.
Outputs eval/routing_comparison_report.md and eval/routing_comparison_results.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("LENNI_LLM_PROVIDER", "rules")

from chat_state import DealState  # noqa: E402
from llm_client import extract_slots_detailed, task_routing_enabled  # noqa: E402
from match_deal import match_deal  # noqa: E402

EVAL_CASES = ROOT / "eval" / "task_routing_eval_cases.yaml"
REPORT_MD = ROOT / "eval" / "routing_comparison_report.md"
RESULTS_JSON = ROOT / "eval" / "routing_comparison_results.json"

CRITICAL_FIELDS = ("parent_key", "intent")
SCORE_FIELDS = ("parent_key", "intent", "city", "metro", "units", "acres", "price_n")


def load_cases() -> list[dict[str, Any]]:
    data = yaml.safe_load(EVAL_CASES.read_text(encoding="utf-8"))
    return data.get("cases") or []


def _norm_city(val: Any) -> str:
    if not val:
        return ""
    return str(val).strip().lower()


def _field_match(expected: Any, actual: Any, field: str) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    if field == "city":
        return _norm_city(expected) in _norm_city(actual) or _norm_city(actual) in _norm_city(expected)
    if field == "price_n":
        exp, act = float(expected), float(actual)
        if exp == 0:
            return act == 0
        return abs(exp - act) / exp < 0.02
    if field in ("units", "acres"):
        return float(expected) == float(actual)
    return str(expected).lower() == str(actual).lower()


def run_case(case: dict, *, routing: bool) -> dict[str, Any]:
    os.environ["LENNI_TASK_ROUTING"] = "true" if routing else "false"
    state = DealState()
    last_extraction = None
    turn_results = []

    for i, msg in enumerate(case["turns"]):
        state.append_message("user", msg)
        extraction = extract_slots_detailed(msg, state.slots, state.conversation_log)
        state.update_slots(extraction.updates)
        last_extraction = extraction
        turn_results.append({
            "turn": i + 1,
            "message": msg,
            "slots_after": dict(state.slots),
            "disagreements": extraction.disagreements,
            "needs_clarification": extraction.needs_clarification,
            "latency_ms": extraction.latency_ms,
        })

    expected = case.get("expected") or {}
    field_results = {}
    for field in SCORE_FIELDS:
        if field not in expected:
            continue
        field_results[field] = {
            "expected": expected[field],
            "actual": state.slots.get(field),
            "match": _field_match(expected[field], state.slots.get(field), field),
        }

    critical_hits = sum(
        1 for f in CRITICAL_FIELDS
        if f in expected and field_results.get(f, {}).get("match")
    )
    critical_total = sum(1 for f in CRITICAL_FIELDS if f in expected)
    scored = [field_results[f]["match"] for f in field_results]
    all_hits = sum(1 for m in scored if m)
    all_total = len(scored)

    # Product match via match_deal
    product_title = ""
    match_ok = None
    if state.ready_for_match() or (state.slots.get("parent_key") and state.slots.get("price_n")):
        try:
            mr = match_deal(state.to_profile_text(), metro=state.slots.get("metro"), use_llm=False)
            product_title = (mr.get("primary_product") or {}).get("title", "")
            exp_pk = expected.get("parent_key")
            if exp_pk == "mf" and product_title:
                match_ok = "multifamily" in product_title.lower() or "apartment" in product_title.lower()
            elif exp_pk == "ci" and product_title:
                match_ok = any(w in product_title.lower() for w in ("capital", "business", "c&i", "line", "sba", "equipment"))
            elif exp_pk == "con" and product_title:
                match_ok = any(w in product_title.lower() for w in ("land", "lot", "construction", "development"))
            elif exp_pk == "own" and product_title:
                match_ok = "owner" in product_title.lower() or "occupied" in product_title.lower()
            elif exp_pk == "inv" and product_title:
                match_ok = any(w in product_title.lower() for w in ("investor", "industrial", "retail", "office", "nnn", "refinance", "commercial"))
            elif exp_pk == "oth" and product_title:
                match_ok = any(w in product_title.lower() for w in ("farm", "ag", "land", "farmland"))
            elif exp_pk == "res" and product_title:
                match_ok = "residential" in product_title.lower() or "1" in product_title
            else:
                match_ok = bool(product_title)
        except Exception as exc:
            product_title = f"ERROR: {exc}"
            match_ok = False

    return {
        "id": case["id"],
        "description": case["description"],
        "routing": routing,
        "multi_turn": len(case["turns"]) > 1,
        "final_slots": dict(state.slots),
        "field_results": field_results,
        "critical_accuracy": critical_hits / critical_total if critical_total else 1.0,
        "field_accuracy": all_hits / all_total if all_total else 1.0,
        "critical_hits": critical_hits,
        "critical_total": critical_total,
        "field_hits": all_hits,
        "field_total": all_total,
        "product_title": product_title,
        "product_match_ok": match_ok,
        "turn_results": turn_results,
        "total_disagreements": sum(len(t["disagreements"]) for t in turn_results),
        "clarifications_triggered": sum(1 for t in turn_results if t["needs_clarification"]),
        "total_latency_ms": sum(t["latency_ms"] for t in turn_results),
        "last_extraction": {
            "routing_enabled": last_extraction.routing_enabled if last_extraction else False,
            "provider": last_extraction.provider if last_extraction else "",
            "turn_provider": last_extraction.turn_provider if last_extraction else "",
            "context_provider": last_extraction.context_provider if last_extraction else "",
        } if last_extraction else {},
    }


def run_suite(routing: bool) -> list[dict]:
    label = "task_routing" if routing else "baseline_single"
    print(f"\n{'='*60}\nRunning suite: {label}\n{'='*60}")
    results = []
    for case in load_cases():
        r = run_case(case, routing=routing)
        status = "PASS" if r["field_accuracy"] == 1.0 else "PARTIAL" if r["critical_accuracy"] == 1.0 else "FAIL"
        print(f"  {r['id']} [{status}] critical={r['critical_hits']}/{r['critical_total']} fields={r['field_hits']}/{r['field_total']} — {r['description'][:50]}")
        results.append(r)
    return results


def compare(baseline: list[dict], routing: list[dict]) -> dict[str, Any]:
    by_id_b = {r["id"]: r for r in baseline}
    by_id_r = {r["id"]: r for r in routing}
    diffs = []
    routing_wins = []
    baseline_wins = []
    ties = []

    for cid in by_id_b:
        b, r = by_id_b[cid], by_id_r[cid]
        b_score = (b["critical_hits"], b["field_hits"])
        r_score = (r["critical_hits"], r["field_hits"])
        entry = {
            "id": cid,
            "description": b["description"],
            "multi_turn": b["multi_turn"],
            "baseline_critical": b["critical_hits"],
            "routing_critical": r["critical_hits"],
            "baseline_fields": b["field_hits"],
            "routing_fields": r["field_hits"],
            "baseline_slots": b["final_slots"],
            "routing_slots": r["final_slots"],
            "routing_disagreements": r["total_disagreements"],
            "routing_clarifications": r["clarifications_triggered"],
        }
        diffs.append(entry)
        if r_score > b_score:
            routing_wins.append(cid)
        elif b_score > r_score:
            baseline_wins.append(cid)
        else:
            ties.append(cid)

    def agg(results: list[dict]) -> dict:
        n = len(results)
        return {
            "cases": n,
            "critical_accuracy_pct": round(100 * sum(r["critical_hits"] for r in results) / max(1, sum(r["critical_total"] for r in results)), 1),
            "field_accuracy_pct": round(100 * sum(r["field_hits"] for r in results) / max(1, sum(r["field_total"] for r in results)), 1),
            "product_match_pct": round(100 * sum(1 for r in results if r.get("product_match_ok")) / max(1, n), 1),
            "avg_latency_ms": round(sum(r["total_latency_ms"] for r in results) / max(1, n), 2),
            "perfect_cases": sum(1 for r in results if r["field_accuracy"] == 1.0),
            "critical_failures": [r["id"] for r in results if r["critical_accuracy"] < 1.0],
        }

    return {
        "baseline": agg(baseline),
        "routing": agg(routing),
        "routing_wins": routing_wins,
        "baseline_wins": baseline_wins,
        "ties": ties,
        "per_case": diffs,
    }


def write_report(comparison: dict, baseline: list, routing: list) -> None:
    b, r = comparison["baseline"], comparison["routing"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    provider = os.environ.get("LENNI_LLM_PROVIDER", "rules")

    lines = [
        "# Task-Based Model Routing — Evaluation Report",
        "",
        f"**Generated:** {now}  ",
        f"**LLM provider:** `{provider}` (rules = deterministic parser; Ollama models when configured)  ",
        f"**Cases:** {b['cases']} golden examples from `eval/task_routing_eval_cases.yaml`",
        "",
        "---",
        "",
        "## Executive summary",
        "",
        "| Metric | Baseline (single-pass) | Task routing (dual extract + merge) | Delta |",
        "|--------|------------------------|-------------------------------------|-------|",
        f"| Critical field accuracy (parent_key, intent) | {b['critical_accuracy_pct']}% | {r['critical_accuracy_pct']}% | {r['critical_accuracy_pct'] - b['critical_accuracy_pct']:+.1f}pp |",
        f"| All scored field accuracy | {b['field_accuracy_pct']}% | {r['field_accuracy_pct']}% | {r['field_accuracy_pct'] - b['field_accuracy_pct']:+.1f}pp |",
        f"| Product match (match_deal) | {b['product_match_pct']}% | {r['product_match_pct']}% | {r['product_match_pct'] - b['product_match_pct']:+.1f}pp |",
        f"| Perfect cases (all fields) | {b['perfect_cases']}/{b['cases']} | {r['perfect_cases']}/{r['cases']} | {r['perfect_cases'] - b['perfect_cases']:+d} |",
        f"| Avg latency per case | {b['avg_latency_ms']} ms | {r['avg_latency_ms']} ms | {r['avg_latency_ms'] - b['avg_latency_ms']:+.2f} ms |",
        "",
        f"**Routing won on {len(comparison['routing_wins'])} cases** · "
        f"Baseline won on {len(comparison['baseline_wins'])} · "
        f"Tied on {len(comparison['ties'])}",
        "",
        "---",
        "",
        "## What each mode does",
        "",
        "### Baseline (`LENNI_TASK_ROUTING=false`)",
        "- Single extraction pass on **full conversation + current message**",
        "- One model (or rules parser) for both slot extraction and chat",
        "- No disagreement detection",
        "",
        "### Task routing (`LENNI_TASK_ROUTING=true`)",
        "- **Turn extractor:** current message only (corrections win)",
        "- **Context extractor:** full conversation log (fills gaps)",
        "- **Merge policy:** turn wins on conflict; flags critical disagreements",
        "- **Separate chat model** (`LENNI_OLLAMA_MODEL_CHAT`) when using Ollama",
        "- **Separate extract models** (`EXTRACT` + `EXTRACT_ALT`) when using Ollama",
        "",
        "---",
        "",
        "## Cases where routing won",
        "",
    ]

    if comparison["routing_wins"]:
        for cid in comparison["routing_wins"]:
            d = next(x for x in comparison["per_case"] if x["id"] == cid)
            lines.append(f"- **{cid}** — {d['description']}")
            lines.append(f"  - Baseline fields: {d['baseline_fields']} → Routing fields: {d['routing_fields']}")
    else:
        lines.append("_None in this run._")

    lines.extend(["", "## Cases where baseline won", ""])
    if comparison["baseline_wins"]:
        for cid in comparison["baseline_wins"]:
            d = next(x for x in comparison["per_case"] if x["id"] == cid)
            lines.append(f"- **{cid}** — {d['description']}")
    else:
        lines.append("_None in this run._")

    lines.extend(["", "---", "", "## Per-case detail", ""])
    for d in comparison["per_case"]:
        br = next(x for x in baseline if x["id"] == d["id"])
        rr = next(x for x in routing if x["id"] == d["id"])
        lines.append(f"### {d['id']}: {d['description']}")
        lines.append("")
        lines.append(f"| | Baseline | Task routing |")
        lines.append(f"|--|----------|--------------|")
        lines.append(f"| Critical fields | {d['baseline_critical']} | {d['routing_critical']} |")
        lines.append(f"| All fields | {d['baseline_fields']} | {d['routing_fields']} |")
        lines.append(f"| Product | {br.get('product_title', '')[:60]} | {rr.get('product_title', '')[:60]} |")
        if d["multi_turn"]:
            lines.append(f"| Disagreements flagged | — | {d['routing_disagreements']} |")
            lines.append(f"| Clarifications | — | {d['routing_clarifications']} |")
        lines.append("")
        mismatches = []
        for field, fr in br["field_results"].items():
            rr_fr = rr["field_results"].get(field, {})
            if fr.get("match") != rr_fr.get("match") or fr.get("actual") != rr_fr.get("actual"):
                mismatches.append(
                    f"- `{field}`: baseline={fr.get('actual')} ({'✓' if fr.get('match') else '✗'}) · "
                    f"routing={rr_fr.get('actual')} ({'✓' if rr_fr.get('match') else '✗'}) · "
                    f"expected={fr.get('expected')}"
                )
        if mismatches:
            lines.append("**Field differences:**")
            lines.extend(mismatches)
        else:
            lines.append("_Identical slot outcomes._")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Critical failures (baseline)",
        "",
        ", ".join(comparison["baseline"]["critical_failures"]) or "_None_",
        "",
        "## Critical failures (routing)",
        "",
        ", ".join(comparison["routing"]["critical_failures"]) or "_None_",
        "",
        "---",
        "",
        "## Re-run instructions",
        "",
        "```bash",
        "cd ONLY_TEXAS_SINCE_2025",
        "LENNI_LLM_PROVIDER=rules python eval_routing_comparison.py",
        "",
        "# With Ollama task routing:",
        "LENNI_LLM_PROVIDER=ollama \\",
        "LENNI_OLLAMA_MODEL_CHAT=llama3.3:70b \\",
        "LENNI_OLLAMA_MODEL_EXTRACT=qwen2.5:14b \\",
        "LENNI_OLLAMA_MODEL_EXTRACT_ALT=deepseek-r1:14b \\",
        "python eval_routing_comparison.py",
        "```",
        "",
    ])

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    t0 = time.perf_counter()
    print("Lenni task routing comparison eval")
    print(f"Provider: {os.environ.get('LENNI_LLM_PROVIDER', 'rules')}")
    print(f"Cases: {len(load_cases())}")

    baseline = run_suite(routing=False)
    routing = run_suite(routing=True)
    comparison = compare(baseline, routing)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": os.environ.get("LENNI_LLM_PROVIDER", "rules"),
        "comparison": comparison,
        "baseline_results": baseline,
        "routing_results": routing,
        "elapsed_sec": round(time.perf_counter() - t0, 2),
    }
    RESULTS_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    write_report(comparison, baseline, routing)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"  Baseline:  critical={comparison['baseline']['critical_accuracy_pct']}%  fields={comparison['baseline']['field_accuracy_pct']}%  perfect={comparison['baseline']['perfect_cases']}")
    print(f"  Routing:   critical={comparison['routing']['critical_accuracy_pct']}%  fields={comparison['routing']['field_accuracy_pct']}%  perfect={comparison['routing']['perfect_cases']}")
    print(f"  Routing wins: {len(comparison['routing_wins'])}  Baseline wins: {len(comparison['baseline_wins'])}  Ties: {len(comparison['ties'])}")
    print(f"\nReport: {REPORT_MD}")
    print(f"JSON:   {RESULTS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
