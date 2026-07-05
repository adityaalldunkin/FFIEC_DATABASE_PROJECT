"""
Listing → loan product + bank recommendation engine.

v0: keyword rules from loan_products.yaml + FFIEC bank ranker.
v1: optional OpenAI JSON extraction when OPENAI_API_KEY is set.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from bank_loader import load_banks
from build_borrower_website import MAJOR_METROS, metro_for
from loan_mix import MIX_LABELS, mix_score
from loan_product_loader import load_parents, subtype_keyword_index

DISCLAIMER = (
    "Portfolio data from public FFIEC Call Reports — not an offer, rate quote, or approval. "
    "Every bank sets its own credit policy."
)

METRO_ALIASES: dict[str, str] = {
    "dallas": "Dallas–Fort Worth",
    "fort worth": "Dallas–Fort Worth",
    "dfw": "Dallas–Fort Worth",
    "plano": "Dallas–Fort Worth",
    "houston": "Houston",
    "austin": "Austin",
    "san antonio": "San Antonio",
    "midland": "Midland–Odessa",
    "odessa": "Midland–Odessa",
    "corpus christi": "Corpus Christi",
    "waco": "Waco",
    "lubbock": "Lubbock",
    "amarillo": "Amarillo",
    "bryan": "College Station",
    "college station": "College Station",
    "brenham": "College Station",
    "tyler": "East Texas",
    "beaumont": "East Texas",
    "mcallen": "Rio Grande Valley",
    "brownsville": "Rio Grande Valley",
    "el paso": "El Paso",
}

INTENT_PATTERNS: list[tuple[str, str]] = [
    (r"\b(value.?add|renovat|rehab|reposition)\b", "value_add"),
    (r"\b(bridge|transitional|lease.?up)\b", "bridge"),
    (r"\b(refinanc|refi|cash.?out)\b", "refinance"),
    (r"\b(build|construct|ground.?up|vertical)\b", "build"),
    (r"\b(develop|entitle|subdivid|a&d|land dev)\b", "develop"),
    (r"\b(hold|holding|investment|raw land)\b", "hold"),
    (r"\b(owner.?occup|my business|operate out of)\b", "owner_occupy"),
    (r"\b(acquir|purchase|buy)\b", "acquire"),
]

PROPERTY_PATTERNS: list[tuple[str, str, str]] = [
    (r"\b(multifamily|apartment|units?|duplex|fourplex|5\+)\b", "mf", "Multifamily"),
    (r"\b(retail|strip|office|industrial|warehouse|cre|nnn|cap rate|noi)\b", "inv", "Investor CRE"),
    (r"\b(owner.?occup|my\s+\w+\s+business|my business|operate?s?\s+out of|business operates)\b", "own", "Owner-occupied CRE"),
    (r"\b(construction|ground.?up|build|develop|lot loan|land dev)\b", "con", "Construction / land"),
    (r"\b(working capital|equipment|line of credit|sba|business loan|c&i)\b", "ci", "C&I / Business"),
    (r"\b(farmland|ag |ranch|farm |timber)\b", "oth", "Ag & farmland"),
    (r"\b(land|lot|acre|raw|unimproved)\b", "con", "Land / lot"),
    (r"\b(single family|1-4|home loan|residential(?! construction))\b", "res", "1–4 Residential"),
]


@dataclass
class ListingProfile:
    raw_input: str
    title: str = ""
    short: str = ""
    property_type: str = ""
    parent_key: str = "con"
    price: str = ""
    price_n: float = 0.0
    metro: str = "Other Texas"
    city: str = ""
    county: str = ""
    units: int | None = None
    acres: float | None = None
    intent: str = "acquire"
    facts: list[list[str]] = field(default_factory=list)
    summary: str = ""


def _money(n: float) -> str:
    return f"${n:,.0f}"


def _parse_price(text: str) -> tuple[str, float]:
    patterns = [
        (r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:k|K)\b", 1_000),
        (r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:m|M|million)\b", 1_000_000),
        (r"\b([\d,]+(?:\.\d+)?)\s*(?:million)\b", 1_000_000),
        (r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:m|M)\b", 1_000_000),
        (r"\$\s*([\d,]+(?:\.\d+)?)", 1),
        (r"\b([\d,]+)\s*(?:k|K)\b", 1_000),
        (r"\b([\d.]+)\s*(?:m|M)\b", 1_000_000),
    ]
    for pat, mult in patterns:
        m = re.search(pat, text, re.I)
        if not m:
            continue
        raw = m.group(1).replace(",", "")
        val = float(raw) * mult
        return _money(val), val
    return "", 0.0


def _parse_units(text: str) -> int | None:
    m = re.search(r"\b(\d{1,4})\s*[- ]?(?:unit|units|apt|apartment)\b", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})\s*plex\b", text, re.I)
    if m:
        n = int(m.group(1))
        return n if n >= 2 else None
    return None


def _parse_acres(text: str) -> float | None:
    m = re.search(r"\b([\d.]+)\s*(?:ac|acre|acres)\b", text, re.I)
    return float(m.group(1)) if m else None


def _parse_city(text: str) -> str:
    m = re.search(
        r"\b(?:in|near|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,?\s*(?:TX|Texas)?\b",
        text,
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,\s*(?:TX|Texas)\b", text)
    if m:
        return m.group(1).strip()
    lower = text.lower()
    for alias in sorted(METRO_ALIASES, key=len, reverse=True):
        if alias in lower:
            return alias.title()
    return ""


def _parse_metro(text: str, city: str = "") -> str:
    lower = text.lower()
    for alias, metro in sorted(METRO_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in lower:
            return metro
    for metro in MAJOR_METROS:
        if metro.lower().split()[0] in lower:
            return metro
    if city:
        return metro_for(city.upper())
    return "Other Texas"


def _parse_intent(text: str) -> str:
    lower = text.lower()
    for pat, intent in INTENT_PATTERNS:
        if re.search(pat, lower):
            return intent
    return "acquire"


def _detect_parent_key(text: str) -> tuple[str, str]:
    lower = text.lower()
    best_key, best_label, best_score = "con", "Land / lot", 0
    for pat, key, label in PROPERTY_PATTERNS:
        if re.search(pat, lower):
            score = 2
            if key == "own":
                score = 4
            if key == "con" and re.search(r"\b(land|lot|acre|raw)\b", lower):
                score = 3
            if score > best_score:
                best_key, best_label, best_score = key, label, score
    return best_key, best_label


def parse_listing_text(text: str, metro_hint: str | None = None) -> ListingProfile:
    text = (text or "").strip()
    price, price_n = _parse_price(text)
    units = _parse_units(text)
    acres = _parse_acres(text)
    city = _parse_city(text)
    metro = metro_hint or _parse_metro(text, city)
    intent = _parse_intent(text)
    parent_key, prop_type = _detect_parent_key(text)

    if units and parent_key not in ("mf",):
        parent_key, prop_type = "mf", "Multifamily"
    if acres and parent_key == "con" and not units:
        prop_type = "Land / lot"

    short = city or metro.split("–")[0].strip() if metro else "Texas"
    if acres:
        title = f"{acres:g} acres · {short}, TX"
    elif units:
        title = f"{units}-unit · {short}, TX"
    else:
        title = f"{prop_type} · {short}, TX"
    if price:
        title = f"{title} · {price}"

    facts: list[list[str]] = []
    if prop_type:
        facts.append(["Listed as", prop_type + (f" · {units} units" if units else "") + (f" · {acres:g} acres" if acres else "")])
    if price:
        facts.append(["Asking price", price])
    if city:
        facts.append(["Location", f"{city}, TX ({metro})"])
    facts.append(["Intent", intent.replace("_", " ").title()])

    summaries = {
        "hold": "This reads as unimproved or hold land. The right loan depends on whether you're holding, developing, or building.",
        "develop": "This reads as a development play. Banks will want to see entitlements, budget, and an exit.",
        "build": "This reads as a construction project. Expect equity in first and a clear takeout plan.",
        "value_add": "This reads as value-add territory — occupancy and business plan drive the loan type.",
        "bridge": "This reads as transitional — short-term financing until stabilization or sale.",
        "refinance": "This reads as a refinance — in-place cash flow and equity position matter most.",
        "owner_occupy": "This reads as owner-occupied — your business cash flow is central to underwriting.",
        "acquire": "The right loan depends on what you're doing with the property — hold, operate, develop, or build.",
    }
    summary = summaries.get(intent, summaries["acquire"])

    return ListingProfile(
        raw_input=text,
        title=title,
        short=short,
        property_type=prop_type,
        parent_key=parent_key,
        price=price,
        price_n=price_n,
        metro=metro,
        city=city,
        county="",
        units=units,
        acres=acres,
        intent=intent,
        facts=facts,
        summary=summary,
    )


def _parent_lookup() -> dict[str, dict[str, Any]]:
    return {p["key"]: p for p in load_parents()}


def _score_subtype(text: str, parent: dict, subtype: dict) -> float:
    lower = text.lower()
    score = 0.0
    for kw in subtype.get("keywords") or []:
        if kw.lower() in lower:
            score += 3.0
    title = (subtype.get("title") or "").lower()
    for word in title.split():
        if len(word) > 4 and word in lower:
            score += 1.0
    intent = _parse_intent(text)
    slug = subtype.get("slug", "")
    intent_map = {
        "bridge": {"bridge", "value-add-rehab", "value-add"},
        "refinance": {"refinance", "permanent-takeout"},
        "value_add": {"bridge", "value-add-rehab", "value-add"},
        "build": {"ground-up", "major-rehab"},
        "develop": {"land-development", "lot-loans"},
        "hold": {"lot-loans", "land-development"},
        "owner_occupy": {"purchase", "sba-504-paired"},
        "acquire": {"acquisition", "purchase", "farmland-purchase"},
    }
    if slug in intent_map.get(intent, set()):
        score += 4.0
    if parent.get("key") == "mf" and "acquisition" in slug and intent == "acquire":
        score += 2.0
    if parent.get("key") == "con" and "land" in slug and re.search(r"\b(land|lot|acre|raw)\b", lower):
        score += 3.0
    return score


def match_loan_products(
    text: str,
    profile: ListingProfile | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    profile = profile or parse_listing_text(text)
    parents = load_parents()
    scored: list[tuple[float, dict, dict]] = []

    for parent in parents:
        if parent["key"] != profile.parent_key and profile.parent_key not in ("oth",):
            # Allow ag parent for oth
            if not (profile.parent_key == "oth" and parent["key"] == "ag-farmland"):
                if parent["key"] not in (profile.parent_key,):
                    continue
        if profile.parent_key == "oth" and parent["slug"] != "ag-farmland":
            continue
        for st in parent.get("subtypes") or []:
            s = _score_subtype(text, parent, st)
            if s > 0:
                scored.append((s, parent, st))

    if not scored:
        # Fallback: first subtype of detected parent
        for parent in parents:
            if parent["key"] == profile.parent_key or (
                profile.parent_key == "oth" and parent["slug"] == "ag-farmland"
            ):
                for st in parent.get("subtypes") or []:
                    scored.append((1.0, parent, st))
                break

    scored.sort(key=lambda x: -x[0])
    results = []
    reasons = {
        "hold": "You're buying and holding for now",
        "develop": "You'll add infrastructure and develop",
        "build": "You're building on it soon",
        "value_add": "You plan to renovate and raise income",
        "bridge": "Short-term financing fits your transition plan",
        "refinance": "You want to replace or pull equity from existing debt",
        "owner_occupy": "Your own business will occupy the property",
        "acquire": "Purchase financing for this property type",
    }
    reason = reasons.get(profile.intent, reasons["acquire"])

    for score, parent, st in scored[:limit]:
        conf = min(0.95, 0.45 + score * 0.08)
        results.append({
            "parent_slug": parent["slug"],
            "parent_key": parent["key"],
            "parent_name": parent["name"],
            "subtype_slug": st["slug"],
            "title": st["title"],
            "one_liner": st.get("one_liner", ""),
            "reason": reason,
            "confidence": round(conf, 2),
            "page_url": f"loan-types/{parent['slug']}/{st['slug']}.html",
            "who_its_for": st.get("who_its_for", ""),
            "how_to_approach": st.get("how_to_approach") or {},
            "what_to_prepare": st.get("what_to_prepare") or [],
        })
    return results


def banks_near_metro(banks: list[dict], metro: str) -> list[dict]:
    if not metro:
        return banks
    near = [b for b in banks if b.get("metro") == metro or metro in (b.get("markets") or [])]
    return near if len(near) >= 5 else banks


def rank_banks(
    product_key: str,
    banks: list[dict],
    metro: str | None = None,
    limit: int = 8,
    min_pct: int = 3,
) -> list[dict]:
    pool = banks_near_metro(banks, metro or "")
    ranked = sorted(pool, key=lambda b: -mix_score(b.get("mix") or {}, product_key))
    out = []
    for b in ranked:
        pct = mix_score(b.get("mix") or {}, product_key)
        if pct < min_pct and out:
            continue
        label = MIX_LABELS.get(product_key, product_key)
        if product_key == "oth":
            label = "farmland / ag production"
        out.append({
            "id": b["id"],
            "name": b["name"],
            "city": b.get("city", ""),
            "metro": b.get("metro", ""),
            "assets_m": b.get("assets"),
            "portfolio_pct": pct,
            "icp": bool(b.get("icp")),
            "why": f"{pct}% of loan book in {label.lower()} — active in this category per FFIEC filings.",
            "page_url": b.get("pageUrl") or f"banks/{b['id']}.html",
            "website": b.get("website"),
        })
        if len(out) >= limit:
            break
    if len(out) < 5:
        extra = sorted(banks, key=lambda b: -mix_score(b.get("mix") or {}, product_key))
        seen = {x["id"] for x in out}
        for b in extra:
            if b["id"] in seen:
                continue
            pct = mix_score(b.get("mix") or {}, product_key)
            out.append({
                "id": b["id"],
                "name": b["name"],
                "city": b.get("city", ""),
                "metro": b.get("metro", ""),
                "assets_m": b.get("assets"),
                "portfolio_pct": pct,
                "icp": bool(b.get("icp")),
                "why": f"{pct}% of loan book in {MIX_LABELS.get(product_key, product_key).lower()}.",
                "page_url": b.get("pageUrl") or f"banks/{b['id']}.html",
                "website": b.get("website"),
            })
            if len(out) >= limit:
                break
    return out


def _llm_enrich(text: str, profile: ListingProfile) -> ListingProfile | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import urllib.request

        prompt = f"""Extract structured listing data from this borrower input. Return JSON only.
Fields: property_type, parent_key (one of mf,inv,own,con,ci,res,oth), city, metro, price_n (number), units (int or null), acres (float or null), intent (hold|develop|build|value_add|bridge|refinance|owner_occupy|acquire), summary (one sentence).

Input: {text[:2000]}"""

        body = json.dumps({
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": "You extract Texas real estate listing fields for loan matching. JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        content = json.loads(data["choices"][0]["message"]["content"])
        if content.get("parent_key"):
            profile.parent_key = content["parent_key"]
        if content.get("property_type"):
            profile.property_type = content["property_type"]
        if content.get("city"):
            profile.city = content["city"]
        if content.get("metro"):
            profile.metro = content["metro"]
        if content.get("price_n"):
            profile.price_n = float(content["price_n"])
            profile.price = _money(profile.price_n)
        if content.get("units") is not None:
            profile.units = int(content["units"]) if content["units"] else None
        if content.get("acres") is not None:
            profile.acres = float(content["acres"]) if content["acres"] else None
        if content.get("intent"):
            profile.intent = content["intent"]
        if content.get("summary"):
            profile.summary = content["summary"]
        return profile
    except Exception:
        return None


def profile_to_dict(p: ListingProfile) -> dict[str, Any]:
    return {
        "title": p.title,
        "short": p.short,
        "property_type": p.property_type,
        "parent_key": p.parent_key,
        "price": p.price,
        "price_n": p.price_n,
        "metro": p.metro,
        "city": p.city,
        "county": p.county,
        "units": p.units,
        "acres": p.acres,
        "intent": p.intent,
        "facts": p.facts,
        "summary": p.summary,
        "raw_input": p.raw_input,
    }


def match_deal(
    text: str,
    metro: str | None = None,
    use_llm: bool = True,
    bank_limit: int = 8,
) -> dict[str, Any]:
    """Main entry: listing text → profile, loan products, banks."""
    from build_roadmap import build_roadmap

    profile = parse_listing_text(text, metro_hint=metro)
    if use_llm:
        enriched = _llm_enrich(text, profile)
        if enriched:
            profile = enriched

    products = match_loan_products(text, profile)
    primary = products[0] if products else None
    product_key = primary["parent_key"] if primary else profile.parent_key

    banks, period = load_banks()
    recommended = rank_banks(product_key, banks, metro=profile.metro, limit=bank_limit)

    roadmap = build_roadmap(profile, primary, recommended)

    return {
        "listing_profile": profile_to_dict(profile),
        "loan_products": products,
        "primary_product": primary,
        "recommended_banks": recommended,
        "roadmap": roadmap,
        "data_period": period,
        "engine": "llm+rules" if use_llm and os.environ.get("OPENAI_API_KEY") else "rules",
        "disclaimer": DISCLAIMER,
    }
