"""Conversational loan advisory orchestrator — LLM dialogue + deterministic match_deal."""

from __future__ import annotations

import re
from typing import Any

from chat_state import DealState
from guardrails import DISCLAIMER, check_input, response_for_flag, sanitize_output
from knowledge_rag import format_context, retrieve
from llm_client import extract_slots_detailed, generate_reply, llm_provider, task_routing_enabled
from match_deal import match_deal

# In-memory sessions (swap for Redis/DB in production)
_SESSIONS: dict[str, DealState] = {}


def get_session(session_id: str | None = None) -> DealState:
    if session_id and session_id in _SESSIONS:
        return _SESSIONS[session_id]
    state = DealState()
    _SESSIONS[state.session_id] = state
    return state


def reset_session(session_id: str) -> DealState:
    if session_id in _SESSIONS:
        del _SESSIONS[session_id]
    state = DealState(session_id=session_id)
    _SESSIONS[session_id] = state
    return state


def _is_confirmation(text: str) -> bool:
    t = text.strip().lower()
    return t in {"yes", "y", "correct", "looks good", "that's right", "confirm", "ok", "okay", "yep", "yeah"}


def _run_match(state: DealState) -> dict[str, Any]:
    text = state.to_profile_text()
    metro = state.slots.get("metro")
    result = match_deal(text, metro=metro, use_llm=False, bank_limit=8)
    state.match_result = result
    state.phase = "package"
    return result


def _format_package_reply(state: DealState, match: dict[str, Any]) -> str:
    primary = match.get("primary_product") or {}
    banks = match.get("recommended_banks") or []
    roadmap = match.get("roadmap") or {}
    approach = roadmap.get("how_to_approach") or {}

    lines = [
        "## Your loan package",
        "",
        f"**Recommended product:** {primary.get('title', 'See options below')}",
        f"_{primary.get('one_liner', '')}_",
        "",
        "**Why this fits:** " + (primary.get("reason") or "Based on your property type and plan."),
        "",
        "### Banks to start with (from FFIEC portfolio data)",
    ]
    for i, b in enumerate(banks[:5], 1):
        lines.append(f"{i}. **{b['name']}** ({b['city']}) — {b['portfolio_pct']}% portfolio in this category")

    prep = primary.get("what_to_prepare") or roadmap.get("what_to_prepare") or []
    if prep:
        lines.extend(["", "### Documents to prepare first"])
        for doc in prep[:6]:
            lines.append(f"- {doc}")

    opening = approach.get("opening") or roadmap.get("first_call_tip") or ""
    if opening:
        lines.extend(["", "### How to open the first call", f"> {opening}"])

    questions = approach.get("questions") or []
    if questions:
        lines.extend(["", "### Questions to ask the banker"])
        for q in questions[:4]:
            lines.append(f"- {q}")

    steps = roadmap.get("steps") or []
    if steps:
        lines.extend(["", "### Next steps"])
        for s in steps:
            lines.append(f"{s.get('step', '')}. **{s.get('title', '')}** — {s.get('detail', '')}")

    lines.extend(["", f"_{DISCLAIMER}_"])
    return "\n".join(lines)


def _extraction_meta(extraction) -> dict:
    return {
        "routing_enabled": extraction.routing_enabled,
        "provider": extraction.provider,
        "turn_provider": extraction.turn_provider,
        "context_provider": extraction.context_provider,
        "disagreements": extraction.disagreements,
        "needs_clarification": extraction.needs_clarification,
        "latency_ms": extraction.latency_ms,
        "extract_model": extraction.extract_model,
        "extract_alt_model": extraction.extract_alt_model,
        "chat_model": extraction.chat_model,
    }


def chat_turn(
    message: str,
    session_id: str | None = None,
    *,
    reset: bool = False,
) -> dict[str, Any]:
    """Process one borrower message; return assistant reply + state."""
    if reset and session_id:
        state = reset_session(session_id)
    else:
        state = get_session(session_id)

    user_msg = (message or "").strip()
    if not user_msg:
        return {
            "session_id": state.session_id,
            "reply": "Tell me about the property or business you're trying to finance.",
            "state": state.to_dict(),
            "provider": llm_provider(),
        }

    # Guardrails — input
    inp_check = check_input(user_msg)
    if not inp_check["safe"] and "prompt_injection" in inp_check["flags"]:
        reply = response_for_flag("prompt_injection")
        state.append_message("user", user_msg)
        state.append_message("assistant", reply)
        return {
            "session_id": state.session_id,
            "reply": reply,
            "state": state.to_dict(),
            "provider": llm_provider(),
            "flags": inp_check["flags"],
        }

    state.append_message("user", user_msg)

    # Rate/approval requests — answer with boundary, still extract slots
    if "rate_or_approval_request" in inp_check.get("flags", []):
        boundary = response_for_flag("rate_or_approval_request")
        extraction = extract_slots_detailed(user_msg, state.slots, state.conversation_log)
        state.update_slots(extraction.updates)
        state.append_message("assistant", boundary)
        return {
            "session_id": state.session_id,
            "reply": boundary,
            "state": state.to_dict(),
            "provider": extraction.provider,
            "flags": inp_check["flags"],
            "extraction": _extraction_meta(extraction),
        }

    # Confirmation → run match
    if state.phase == "confirm" and _is_confirmation(user_msg):
        match = _run_match(state)
        reply = _format_package_reply(state, match)
        state.append_message("assistant", reply)
        return {
            "session_id": state.session_id,
            "reply": reply,
            "state": state.to_dict(),
            "provider": "match_deal",
            "match_result": match,
            "package_ready": True,
        }

    # Extract slots from message
    extraction = extract_slots_detailed(user_msg, state.slots, state.conversation_log)
    state.update_slots(extraction.updates)

    # RAG context
    rag_query = f"{state.conversation_log} {user_msg}"
    chunks = retrieve(rag_query, parent_key=state.slots.get("parent_key"))
    rag_ctx = format_context(chunks)

    # Clarification when routed extractors disagree on critical fields
    if extraction.needs_clarification and state.phase == "discover":
        summary = state.summary_for_confirm()
        reply, reply_provider = generate_reply(
            user_msg,
            summary,
            state.next_question(),
            rag_ctx,
            phase="discover",
            needs_clarification=True,
            clarification_fields=extraction.clarification_fields,
        )
        reply = sanitize_output(reply)
        state.append_message("assistant", reply)
        return {
            "session_id": state.session_id,
            "reply": reply,
            "state": state.to_dict(),
            "provider": reply_provider,
            "extraction": _extraction_meta(extraction),
            "needs_clarification": True,
            "missing_slots": state.missing_slots(),
        }

    # Phase transitions
    if state.ready_for_match() and state.phase == "discover":
        state.phase = "confirm"
        summary = state.summary_for_confirm()
        reply, reply_provider = generate_reply(
            user_msg, summary, None, rag_ctx, phase="confirm",
        )
        if reply_provider == "rules":
            reply = (
                f"Here's what I have:\n\n{summary}\n\n"
                "Does this look right? Reply **yes** to build your loan package and bank shortlist."
            )
        reply = sanitize_output(reply)
        state.append_message("assistant", reply)
        return {
            "session_id": state.session_id,
            "reply": reply,
            "state": state.to_dict(),
            "provider": reply_provider,
            "rag_chunks": [c["id"] for c in chunks],
            "ready_for_confirm": True,
            "extraction": _extraction_meta(extraction),
        }

    if state.phase == "package" and state.match_result:
        # Follow-up after package — answer from match result + RAG
        reply = _post_package_reply(user_msg, state, rag_ctx)
        state.append_message("assistant", reply)
        return {
            "session_id": state.session_id,
            "reply": reply,
            "state": state.to_dict(),
            "provider": llm_provider(),
            "match_result": state.match_result,
        }

    # Discovery — ask next question
    next_q = state.next_question()
    summary = state.summary_for_confirm()
    reply, reply_provider = generate_reply(
        user_msg,
        summary,
        next_q,
        rag_ctx,
        phase="discover",
    )
    reply = sanitize_output(reply)
    state.append_message("assistant", reply)

    return {
        "session_id": state.session_id,
        "reply": reply,
        "state": state.to_dict(),
        "provider": reply_provider,
        "task_routing": task_routing_enabled(),
        "extraction": _extraction_meta(extraction),
        "rag_chunks": [c["id"] for c in chunks],
        "missing_slots": state.missing_slots(),
    }


def _post_package_reply(user_msg: str, state: DealState, rag_ctx: str) -> str:
    lower = user_msg.lower()
    match = state.match_result or {}
    banks = match.get("recommended_banks") or []
    primary = match.get("primary_product") or {}

    if re.search(r"\b(email|write|send)\b", lower):
        b = banks[0] if banks else {}
        opening = (primary.get("how_to_approach") or {}).get("opening", "")
        return sanitize_output(
            f"Here's a draft opener for **{b.get('name', 'the bank')}**:\n\n"
            f"> {opening or 'We are seeking financing for a Texas commercial property and would like to discuss your appetite for this type of loan.'}\n\n"
            "Attach a one-page deal summary with property facts, your plan, and liquidity. "
            f"_{DISCLAIMER}_",
            add_disclaimer=False,
        )
    if re.search(r"\b(which bank|why.*bank|first bank)\b", lower):
        if banks:
            b = banks[0]
            return sanitize_output(
                f"Start with **{b['name']}** ({b['city']}) — {b.get('why', '')} "
                "That doesn't mean they'll approve your deal; it means their public filings show real activity in this category.",
            )
        return "I don't have bank recommendations in this session — try starting a new conversation."

    reply, _ = generate_reply(user_msg, state.summary_for_confirm(), None, rag_ctx, phase="package")
    return sanitize_output(reply)


def opening_message() -> str:
    return (
        "Hi — I'm **Lenni**, your guide to Texas community bank lending.\n\n"
        "I'll ask a few questions about your deal, then put together:\n"
        "- The loan product type that fits\n"
        "- Banks whose portfolios show activity in that category\n"
        "- What to prepare and how to open the first call\n\n"
        "I'm not a bank — I can't quote rates or approve loans.\n\n"
        "**What are you trying to finance?** (property type, location, and what you plan to do with it)"
    )
