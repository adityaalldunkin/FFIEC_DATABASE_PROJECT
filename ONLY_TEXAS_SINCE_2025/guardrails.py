"""Financial-domain guardrails for borrower chat."""

from __future__ import annotations

import re
from typing import Any

DISCLAIMER = (
    "Portfolio data from public FFIEC Call Reports — not an offer, rate quote, or approval. "
    "Every bank sets its own credit policy."
)

RATE_APPROVAL_PATTERNS = [
    r"\b(what(?:'s| is) (?:the|my) rate)\b",
    r"\b(will i (?:get|be) approved)\b",
    r"\b(guarantee(?:d)? (?:approval|funding|loan))\b",
    r"\b(approve my loan)\b",
    r"\b(interest rate)\b",
    r"\b(can you lend me)\b",
]

INPUT_BLOCK_PATTERNS = [
    r"\bignore (?:all )?previous instructions\b",
    r"\bsystem prompt\b",
    r"\bjailbreak\b",
]

MUST_NOT_CLAIM = [
    r"\b\d+\.?\d*%\s*(?:interest|apr|rate)\b",
    r"\b(you (?:will|are) (?:approved|denied))\b",
    r"\bguaranteed approval\b",
]


def check_input(text: str) -> dict[str, Any]:
    lower = text.lower()
    flags = []
    for pat in INPUT_BLOCK_PATTERNS:
        if re.search(pat, lower, re.I):
            flags.append("prompt_injection")
    for pat in RATE_APPROVAL_PATTERNS:
        if re.search(pat, lower, re.I):
            flags.append("rate_or_approval_request")
    return {"safe": len(flags) == 0, "flags": flags}


def sanitize_output(text: str, *, add_disclaimer: bool = False) -> str:
    """Strip dangerous claims from assistant output."""
    out = text
    for pat in MUST_NOT_CLAIM:
        out = re.sub(pat, "[consult a banker for terms]", out, flags=re.I)
    if add_disclaimer and DISCLAIMER not in out:
        out = f"{out.rstrip()}\n\n_{DISCLAIMER}_"
    return out


def response_for_flag(flag: str) -> str:
    if flag == "rate_or_approval_request":
        return (
            "I can't quote rates or tell you if you'll be approved — only a banker can do that "
            "after reviewing your full file. What I *can* do is help you identify the right loan "
            "type, which Texas banks actively lend in that category, and what to prepare before "
            "your first call. Want to keep going on your deal?"
        )
    if flag == "prompt_injection":
        return (
            "I'm here to help with your Texas loan search. Tell me about the property or "
            "business you're trying to finance."
        )
    return "How can I help with your loan search today?"
