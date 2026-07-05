"""Unified LLM client with optional task-based model routing."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from slot_merger import clarification_question, merge_extractions

SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "parent_key": {"type": "string", "enum": ["mf", "inv", "own", "con", "ci", "res", "oth"]},
        "intent": {
            "type": "string",
            "enum": [
                "hold", "develop", "build", "value_add", "bridge",
                "refinance", "owner_occupy", "acquire",
            ],
        },
        "city": {"type": "string"},
        "metro": {"type": "string"},
        "price_n": {"type": "number"},
        "units": {"type": "integer"},
        "acres": {"type": "number"},
        "occupancy_pct": {"type": "integer"},
        "timeline": {"type": "string"},
        "sponsor_experience": {"type": "string"},
        "property_type": {"type": "string"},
        "summary": {"type": "string"},
    },
}


@dataclass
class ExtractionResult:
    updates: dict[str, Any]
    provider: str
    routing_enabled: bool = False
    turn_provider: str = ""
    context_provider: str = ""
    turn_slots: dict[str, Any] = field(default_factory=dict)
    context_slots: dict[str, Any] = field(default_factory=dict)
    disagreements: list[dict[str, Any]] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_fields: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    chat_model: str = ""
    extract_model: str = ""
    extract_alt_model: str = ""


def task_routing_enabled() -> bool:
    val = os.environ.get("LENNI_TASK_ROUTING", "true").lower()
    return val in ("1", "true", "yes", "on")


def llm_provider() -> str:
    if os.environ.get("LENNI_LLM_PROVIDER", "").lower() == "rules":
        return "rules"
    if os.environ.get("LENNI_LLM_PROVIDER", "").lower() == "openai":
        if os.environ.get("OPENAI_API_KEY", "").strip():
            return "openai"
    if os.environ.get("LENNI_LLM_PROVIDER", "").lower() == "ollama":
        return "ollama"
    if os.environ.get("OLLAMA_HOST") or os.environ.get("LENNI_OLLAMA_MODEL"):
        return "ollama"
    if _ollama_reachable():
        return "ollama"
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return "openai"
    return "rules"


def _ollama_reachable() -> bool:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def ollama_model() -> str:
    return os.environ.get(
        "LENNI_OLLAMA_MODEL",
        os.environ.get("OLLAMA_MODEL", "qwen2.5:14b"),
    )


def model_for_task(task: str) -> str:
    """Task-specific model selection: chat | extract | extract_alt | critic."""
    env_map = {
        "chat": "LENNI_OLLAMA_MODEL_CHAT",
        "extract": "LENNI_OLLAMA_MODEL_EXTRACT",
        "extract_alt": "LENNI_OLLAMA_MODEL_EXTRACT_ALT",
        "critic": "LENNI_OLLAMA_MODEL_CRITIC",
    }
    specific = os.environ.get(env_map.get(task, ""), "").strip()
    if specific:
        return specific
    defaults = {
        "chat": ollama_model(),
        "extract": os.environ.get("LENNI_OLLAMA_MODEL_EXTRACT", "qwen2.5:14b"),
        "extract_alt": os.environ.get("LENNI_OLLAMA_MODEL_EXTRACT_ALT", "llama3.2:3b"),
        "critic": ollama_model(),
    }
    return defaults.get(task, ollama_model())


def openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 60) -> dict:
    body = json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def chat_completion(
    messages: list[dict[str, str]],
    *,
    json_mode: bool = False,
    temperature: float = 0.3,
    model: str | None = None,
    task: str = "chat",
) -> tuple[str, str]:
    provider = llm_provider()
    if provider == "ollama":
        m = model or model_for_task(task)
        content = _ollama_chat(messages, model=m, json_mode=json_mode, temperature=temperature)
        return content, f"ollama:{m}"
    if provider == "openai":
        content = _openai_chat(messages, json_mode=json_mode, temperature=temperature)
        return content, f"openai:{openai_model()}"
    return "", "rules"


def _ollama_chat(
    messages: list[dict[str, str]],
    *,
    model: str,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"
    data = _http_post_json(f"{host.rstrip('/')}/api/chat", payload, timeout=120)
    return data.get("message", {}).get("content", "")


def _openai_chat(
    messages: list[dict[str, str]],
    *,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    payload: dict[str, Any] = {
        "model": openai_model(),
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _http_post_json(
        "https://api.openai.com/v1/chat/completions",
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    return data["choices"][0]["message"]["content"]


def _profile_to_slots(text: str) -> dict[str, Any]:
    from match_deal import parse_listing_text

    profile = parse_listing_text(text.strip())
    return {
        k: v
        for k, v in {
            "parent_key": profile.parent_key,
            "intent": profile.intent,
            "city": profile.city,
            "metro": profile.metro,
            "price_n": profile.price_n or None,
            "units": profile.units,
            "acres": profile.acres,
            "property_type": profile.property_type,
            "summary": profile.summary,
        }.items()
        if v is not None and v != "" and v != 0
    }


def _filter_turn_slots(turn_text: str, slots: dict[str, Any]) -> dict[str, Any]:
    """
    For task routing: only apply turn extractions backed by signals in the current message.
    Prevents sparse follow-up turns ('$1.5M revolver') from resetting parent_key to defaults.
    """
    import re

    lower = turn_text.lower()
    out: dict[str, Any] = {}

    for k in ("price_n", "units", "acres", "occupancy_pct", "city", "metro", "timeline", "sponsor_experience"):
        if slots.get(k) is not None:
            out[k] = slots[k]

    intent_signals = (
        "refinanc", "refi", "cash out", "cash-out", "bridge", "value-add", "value add",
        "hold", "holding", "develop", "build", "construct", "owner-occup", "owner occup",
        "operate out of", "acqui", "purchase", "buy", "buying",
    )
    if slots.get("intent") and any(s in lower for s in intent_signals):
        out["intent"] = slots["intent"]

    pk = slots.get("parent_key")
    pk_signals = {
        "mf": r"\b(multifamily|apartment|units?|plex|duplex|fourplex)\b",
        "inv": r"\b(retail|office|industrial|warehouse|investor|cre|nnn|cap rate|noi|strip)\b",
        "own": r"\b(owner.?occup|operate?s?\s+out of|my\s+\w+\s+business|my business)\b",
        "con": r"\b(construction|ground.?up|build|develop|land|lot|acre|raw|unimproved|vertical)\b",
        "ci": r"\b(working capital|line of credit|sba|business loan|c&i|equipment|revolver|saas|manufacturing)\b",
        "res": r"\b(single family|1-4|home loan|duplex|triplex|fourplex|residential)\b",
        "oth": r"\b(farmland|farm |ranch|ag |timber|cotton)\b",
    }
    if pk and pk in pk_signals and re.search(pk_signals[pk], lower):
        out["parent_key"] = pk
        if slots.get("property_type"):
            out["property_type"] = slots["property_type"]
    if slots.get("summary") and (out.get("parent_key") or out.get("intent")):
        out["summary"] = slots["summary"]

    return out


def _llm_extract_json(text: str, current_slots: dict[str, Any], *, model: str | None = None) -> dict[str, Any]:
    system = (
        "You extract Texas commercial real estate deal fields for loan matching. "
        "Return JSON only with fields you can infer. "
        "parent_key: mf|inv|own|con|ci|res|oth. "
        "intent: hold|develop|build|value_add|bridge|refinance|owner_occupy|acquire. "
        "Only include fields explicitly stated or clearly implied."
    )
    user = json.dumps({"current_slots": current_slots, "text": text[:2000]})
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    raw, _ = chat_completion(messages, json_mode=True, temperature=0.1, model=model, task="extract")
    parsed = json.loads(raw) if raw else {}
    allowed = set(SLOT_SCHEMA["properties"].keys())
    return {k: v for k, v in parsed.items() if k in allowed and v not in (None, "", "null")}


def _extract_baseline(
    user_message: str,
    current_slots: dict[str, Any],
    conversation_log: str,
) -> tuple[dict[str, Any], str]:
    """Single-model / single-pass extraction (legacy behavior)."""
    provider = llm_provider()
    full_text = f"{conversation_log} {user_message}".strip()
    if provider == "rules":
        return _profile_to_slots(full_text), "rules"
    try:
        return _llm_extract_json(full_text, current_slots, model=ollama_model()), f"ollama:{ollama_model()}"
    except Exception:
        return _profile_to_slots(full_text), "rules"


def _extract_routed(
    user_message: str,
    current_slots: dict[str, Any],
    conversation_log: str,
) -> ExtractionResult:
    """Task routing: turn-focused + context-focused extractors, then merge."""
    t0 = time.perf_counter()
    provider = llm_provider()
    chat_m = model_for_task("chat")
    extract_m = model_for_task("extract")
    extract_alt_m = model_for_task("extract_alt")

    turn_text = user_message.strip()
    context_text = conversation_log.strip()

    if provider == "rules":
        raw_turn = _profile_to_slots(turn_text) if turn_text else {}
        turn_slots = _filter_turn_slots(turn_text, raw_turn) if turn_text else {}
        context_slots = _profile_to_slots(context_text) if context_text else {}
        turn_prov = "rules:turn" if turn_text else "rules:empty"
        context_prov = "rules:context" if context_text else "rules:empty"
    else:
        try:
            turn_slots = _llm_extract_json(turn_text, current_slots, model=extract_m) if turn_text else {}
            turn_prov = f"ollama:{extract_m}"
        except Exception:
            turn_slots = _profile_to_slots(turn_text)
            turn_prov = "rules:fallback"

        try:
            # Second extractor uses alternate model when available (ensemble)
            alt_model = extract_alt_m if extract_alt_m != extract_m else extract_m
            if context_text:
                context_slots = _llm_extract_json(context_text, current_slots, model=alt_model)
                context_prov = f"ollama:{alt_model}"
            else:
                context_slots = {}
                context_prov = "empty"
        except Exception:
            context_slots = _profile_to_slots(context_text) if context_text else {}
            context_prov = "rules:fallback"

    merge = merge_extractions(turn_slots, context_slots, current_slots=current_slots)
    elapsed = (time.perf_counter() - t0) * 1000

    return ExtractionResult(
        updates=merge["merged"],
        provider=f"routing:{turn_prov}+{context_prov}",
        routing_enabled=True,
        turn_provider=turn_prov,
        context_provider=context_prov,
        turn_slots=turn_slots,
        context_slots=context_slots,
        disagreements=merge["disagreements"],
        needs_clarification=merge["needs_clarification"],
        clarification_fields=merge["clarification_fields"],
        latency_ms=round(elapsed, 2),
        chat_model=chat_m,
        extract_model=extract_m,
        extract_alt_model=extract_alt_m,
    )


def extract_slots_detailed(
    user_message: str,
    current_slots: dict[str, Any],
    conversation_log: str = "",
) -> ExtractionResult:
    t0 = time.perf_counter()
    if task_routing_enabled():
        return _extract_routed(user_message, current_slots, conversation_log)

    updates, prov = _extract_baseline(user_message, current_slots, conversation_log)
    elapsed = (time.perf_counter() - t0) * 1000
    return ExtractionResult(
        updates=updates,
        provider=prov,
        routing_enabled=False,
        latency_ms=round(elapsed, 2),
        chat_model=ollama_model() if llm_provider() == "ollama" else llm_provider(),
        extract_model=ollama_model() if llm_provider() == "ollama" else llm_provider(),
    )


def extract_slots(
    user_message: str,
    current_slots: dict[str, Any],
    conversation_log: str = "",
) -> tuple[dict[str, Any], str]:
    result = extract_slots_detailed(user_message, current_slots, conversation_log)
    return result.updates, result.provider


def generate_reply(
    user_message: str,
    state_summary: str,
    next_question: str | None,
    rag_context: str,
    *,
    phase: str = "discover",
    needs_clarification: bool = False,
    clarification_fields: list[str] | None = None,
) -> tuple[str, str]:
    provider = llm_provider()
    if needs_clarification and clarification_fields:
        q = clarification_question(clarification_fields)
        if provider == "rules":
            return f"I want to double-check before we go further.\n\n{q}", "rules:clarify"
        # LLM wraps clarification naturally below

    if provider == "rules":
        if needs_clarification and clarification_fields:
            return f"I want to double-check before we go further.\n\n{clarification_question(clarification_fields)}", "rules:clarify"
        return _rules_reply(user_message, state_summary, next_question, phase), "rules"

    chat_model = model_for_task("chat")
    clarify_note = ""
    if needs_clarification and clarification_fields:
        clarify_note = f"\nIMPORTANT: Ask a clarifying question about: {', '.join(clarification_fields)}"

    system = f"""You are Lenni, a Texas community bank loan guide for borrowers.
You are NOT a bank and cannot approve loans or quote rates.
Be plainspoken, warm, and concise (2-4 sentences).
Ask at most ONE follow-up question per turn.
Never invent bank names or loan terms — banks come from data later.
Phase: {phase}{clarify_note}

Reference knowledge (cite concepts, do not invent facts):
{rag_context[:2000]}
"""
    user_parts = [f"Deal so far:\n{state_summary}"]
    if next_question and phase == "discover" and not needs_clarification:
        user_parts.append(f"Ask something like: {next_question}")
    user_parts.append(f"Borrower said: {user_message}")
    user_parts.append("Reply as Lenni. End with one clear question if still gathering info.")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]
    try:
        raw, used = chat_completion(messages, json_mode=False, temperature=0.4, model=chat_model, task="chat")
        if raw.strip():
            return raw.strip(), used
    except Exception:
        pass
    return _rules_reply(user_message, state_summary, next_question, phase), "rules"


def _rules_reply(
    user_message: str,
    state_summary: str,
    next_question: str | None,
    phase: str,
) -> str:
    if phase == "package":
        return (
            "I've put together your loan package below — product match, bank shortlist, "
            "documents to prepare, and how to open the first conversation. "
            "Remember: portfolio data from public filings, not an offer or approval."
        )
    if phase == "confirm":
        return (
            f"Here's what I have so far:\n\n{state_summary}\n\n"
            "Does this look right? Reply **yes** to see your loan package and bank shortlist, "
            "or tell me what to change."
        )
    intro = (
        "I'm Lenni — I help Texas borrowers figure out the right loan type, "
        "which community banks to talk to, and how to show up prepared. "
        "I'm not a bank and can't quote rates or approve anything."
    )
    if not state_summary.strip():
        return f"{intro}\n\n{next_question or 'What are you trying to finance?'}"
    ack = "Got it — that helps."
    if next_question:
        return f"{ack}\n\n{next_question}"
    return f"{ack}\n\nDoes this look right? Reply **yes** to build your loan package."
