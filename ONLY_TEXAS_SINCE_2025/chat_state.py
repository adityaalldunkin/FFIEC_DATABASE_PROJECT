"""Deal state and slot tracking for conversational loan intake."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

VALID_PARENT_KEYS = frozenset({"mf", "inv", "own", "con", "ci", "res", "oth"})
VALID_INTENTS = frozenset({
    "hold", "develop", "build", "value_add", "bridge",
    "refinance", "owner_occupy", "acquire",
})

SLOT_LABELS = {
    "intent": "what you plan to do (buy, build, refinance, hold land, etc.)",
    "parent_key": "property type (apartments, CRE, land, business loan, etc.)",
    "city": "city in Texas",
    "metro": "metro area",
    "price_n": "purchase price or loan amount",
    "units": "number of units (for apartments)",
    "acres": "acreage (for land)",
    "occupancy_pct": "current occupancy",
    "timeline": "when you need to close",
    "sponsor_experience": "your experience with deals like this",
}

# Priority order for discovery questions
SLOT_PRIORITY = [
    "intent",
    "parent_key",
    "city",
    "metro",
    "price_n",
    "units",
    "acres",
    "occupancy_pct",
    "timeline",
    "sponsor_experience",
]

QUESTION_TEMPLATES: dict[str, str] = {
    "intent": "What are you trying to do — buy, build on it, refinance, or hold the property for now?",
    "parent_key": "What kind of property is this — apartments, retail/office/industrial, raw land, your own business building, or a business line of credit?",
    "city": "What city in Texas is the property in?",
    "metro": "Which metro area is closest — Dallas–Fort Worth, Houston, Austin, San Antonio, or another?",
    "price_n": "What's the purchase price or loan amount you're targeting?",
    "units": "How many units does the property have?",
    "acres": "How many acres is the parcel?",
    "occupancy_pct": "What's the current occupancy (if it's an income property)?",
    "timeline": "When are you hoping to close?",
    "sponsor_experience": "Have you done a commercial or investment deal like this before?",
}


@dataclass
class DealState:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: str = "discover"  # discover | confirm | package
    slots: dict[str, Any] = field(default_factory=dict)
    messages: list[dict[str, str]] = field(default_factory=list)
    conversation_log: str = ""
    match_result: dict[str, Any] | None = None
    confirmed: bool = False

    def append_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        if role == "user":
            self.conversation_log = (self.conversation_log + " " + content).strip()

    def update_slots(self, updates: dict[str, Any]) -> None:
        for key, val in updates.items():
            if val is None or val == "" or val == "null":
                continue
            if key == "parent_key" and val not in VALID_PARENT_KEYS:
                continue
            if key == "intent" and val not in VALID_INTENTS:
                continue
            if key in ("units", "occupancy_pct") and val is not None:
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    continue
            if key in ("price_n", "acres") and val is not None:
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
            self.slots[key] = val

    def missing_slots(self) -> list[str]:
        missing: list[str] = []
        if not self.slots.get("intent"):
            missing.append("intent")
        if not self.slots.get("parent_key"):
            missing.append("parent_key")
        if not self.slots.get("city") and not self.slots.get("metro"):
            missing.append("city")
        pk = self.slots.get("parent_key")
        if pk == "mf" and not self.slots.get("units"):
            missing.append("units")
        if pk == "con" and not self.slots.get("acres") and not self.slots.get("price_n"):
            missing.append("acres")
        if not self.slots.get("price_n"):
            missing.append("price_n")
        return missing

    def ready_for_match(self) -> bool:
        if not self.slots.get("intent") or not self.slots.get("parent_key"):
            return False
        if not self.slots.get("city") and not self.slots.get("metro"):
            return False
        if not self.slots.get("price_n"):
            return False
        pk = self.slots.get("parent_key")
        if pk == "mf" and not self.slots.get("units"):
            return False
        return True

    def next_question_slot(self) -> str | None:
        for slot in SLOT_PRIORITY:
            if slot in self.missing_slots():
                return slot
        return None

    def next_question(self) -> str | None:
        slot = self.next_question_slot()
        return QUESTION_TEMPLATES.get(slot or "", None) if slot else None

    def to_profile_text(self) -> str:
        """Assemble narrative for match_deal."""
        parts = [self.conversation_log]
        s = self.slots
        if s.get("parent_key") == "mf" and s.get("units"):
            parts.append(f"{s['units']}-unit apartment")
        if s.get("acres"):
            parts.append(f"{s['acres']} acres")
        if s.get("city"):
            parts.append(f"in {s['city']}, TX")
        if s.get("metro"):
            parts.append(f"({s['metro']} metro)")
        if s.get("price_n"):
            parts.append(f"${s['price_n']:,.0f}")
        if s.get("intent"):
            parts.append(s["intent"].replace("_", " "))
        if s.get("occupancy_pct"):
            parts.append(f"{s['occupancy_pct']}% occupancy")
        return " ".join(p for p in parts if p).strip()

    def summary_for_confirm(self) -> str:
        lines = []
        pk = self.slots.get("parent_key", "")
        labels = {
            "mf": "Multifamily", "inv": "Investor CRE", "own": "Owner-occupied CRE",
            "con": "Construction / land", "ci": "C&I / Business", "res": "1–4 Residential",
            "oth": "Ag / farmland",
        }
        if pk:
            lines.append(f"**Property type:** {labels.get(pk, pk)}")
        if self.slots.get("intent"):
            lines.append(f"**Your plan:** {self.slots['intent'].replace('_', ' ').title()}")
        if self.slots.get("city"):
            lines.append(f"**Location:** {self.slots['city']}, TX")
        if self.slots.get("metro"):
            lines.append(f"**Metro:** {self.slots['metro']}")
        if self.slots.get("price_n"):
            lines.append(f"**Amount:** ${self.slots['price_n']:,.0f}")
        if self.slots.get("units"):
            lines.append(f"**Units:** {self.slots['units']}")
        if self.slots.get("acres"):
            lines.append(f"**Acres:** {self.slots['acres']}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "phase": self.phase,
            "slots": self.slots,
            "missing_slots": self.missing_slots(),
            "ready_for_match": self.ready_for_match(),
            "messages": self.messages,
            "match_result": self.match_result,
            "confirmed": self.confirmed,
        }
