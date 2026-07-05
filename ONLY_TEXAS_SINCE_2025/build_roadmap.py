"""Build borrower roadmap from match results and loan product YAML."""

from __future__ import annotations

from typing import Any

from loan_product_loader import load_parents


def _fill_template(template: str, profile: dict, product: dict | None) -> str:
    text = template
    replacements = {
        "[city]": profile.get("city") or profile.get("metro") or "Texas",
        "[unit count]": str(profile.get("units") or "—"),
        "[X]": "—",
        "[goal]": profile.get("intent", "acquire").replace("_", " "),
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def build_roadmap(
    profile: Any,
    primary_product: dict[str, Any] | None,
    banks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge YAML guidance with ranked banks into an actionable roadmap."""
    pdict = profile if isinstance(profile, dict) else {
        "city": getattr(profile, "city", ""),
        "metro": getattr(profile, "metro", ""),
        "units": getattr(profile, "units", None),
        "intent": getattr(profile, "intent", "acquire"),
        "property_type": getattr(profile, "property_type", ""),
        "price": getattr(profile, "price", ""),
    }

    approach = {"opening": "", "questions": []}
    prepare: list[str] = []
    title = ""
    page_url = ""

    if primary_product:
        title = primary_product.get("title", "")
        page_url = primary_product.get("page_url", "")
        raw_approach = primary_product.get("how_to_approach") or {}
        opening = raw_approach.get("opening", "")
        if opening:
            approach["opening"] = _fill_template(opening, pdict, primary_product)
        approach["questions"] = list(raw_approach.get("questions") or [])
        prepare = list(primary_product.get("what_to_prepare") or [])

    steps = [
        {
            "step": 1,
            "title": "Confirm the loan product",
            "detail": f"Lenni mapped this to **{title}** based on your listing and intent. Read the product guide before calling banks.",
        },
        {
            "step": 2,
            "title": "Prepare your package",
            "detail": "Gather the documents lenders in this category typically ask for first — not last.",
        },
        {
            "step": 3,
            "title": "Shortlist banks",
            "detail": "Start with banks whose FFIEC portfolios show real activity in this loan category near your market.",
        },
        {
            "step": 4,
            "title": "Make the first call",
            "detail": "Lead with property facts and your plan. Ask process questions — not rate quotes on day one.",
        },
    ]

    if prepare:
        steps[1]["detail"] = "Priority documents: " + "; ".join(prepare[:4]) + ("…" if len(prepare) > 4 else "")

    bank_lines = []
    for i, b in enumerate(banks[:5], 1):
        bank_lines.append(
            f"{i}. **{b['name']}** ({b['city']}) — {b['portfolio_pct']}% portfolio share. {b.get('why', '')}"
        )

    return {
        "steps": steps,
        "how_to_approach": approach,
        "what_to_prepare": prepare,
        "product_title": title,
        "product_page_url": page_url,
        "bank_shortlist_summary": bank_lines,
        "first_call_tip": (
            "Community banks respond to prepared borrowers. Send a one-page deal summary "
            "with property facts, your plan, and liquidity — then ask what they need to issue terms."
        ),
    }
