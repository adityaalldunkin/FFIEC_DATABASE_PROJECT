"""Bank website enrichment — load, merge, and HTML fragments for borrower site."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
ENRICHMENT_DIR = ROOT / "enrichment"
ENRICHMENT_JSON = ENRICHMENT_DIR / "bank_website_enrichment.json"


def load_enrichment_map() -> dict[int, dict[str, Any]]:
    if not ENRICHMENT_JSON.is_file():
        return {}
    data = json.loads(ENRICHMENT_JSON.read_text(encoding="utf-8"))
    out: dict[int, dict[str, Any]] = {}
    for item in data.get("banks", []):
        rssd = item.get("rssd")
        if rssd is not None:
            out[int(rssd)] = item
    return out


def merge_enrichment(bank: dict, enrichment: dict[str, Any] | None) -> dict:
    if not enrichment:
        return bank
    bank = dict(bank)
    bank["webEnrichment"] = enrichment
    return bank


def _esc(text) -> str:
    import html

    return html.escape(str(text) if text is not None else "")


def render_bank_enrichment_html(bank: dict, esc=_esc) -> str:
    """HTML block for website-sourced about, contact, FAQ (empty if none)."""
    en = bank.get("webEnrichment")
    if not en:
        return ""

    scraped = en.get("scraped_at", "")
    parts: list[str] = []

    about = (en.get("about_excerpt") or "").strip()
    if about:
        src = en.get("about_source_url") or bank.get("website") or ""
        parts.append(
            f'<section class="content-section"><h2 class="serif">About this bank</h2>'
            f'<p>{esc(about)}</p>'
            f'<p class="tiny muted">Excerpt from <a href="{esc(src)}" target="_blank" rel="noopener">'
            f'bank website</a> · captured {esc(scraped)}</p></section>'
        )

    phones = en.get("phones") or []
    emails = en.get("emails") or []
    hours = en.get("hours") or []
    if phones or emails or hours:
        rows = ""
        for p in phones[:5]:
            rows += (
                f'<tr><th>{esc(p.get("label", "Phone"))}</th>'
                f'<td><a href="tel:{esc(re.sub(r"[^0-9+]", "", p.get("number", "")))}">'
                f'{esc(p.get("number"))}</a>'
                f' <span class="tiny muted">(<a href="{esc(p.get("source_url", ""))}" target="_blank" rel="noopener">source</a>)</span></td></tr>'
            )
        for e in emails[:3]:
            rows += (
                f'<tr><th>{esc(e.get("label", "Email"))}</th>'
                f'<td><a href="mailto:{esc(e.get("address"))}">{esc(e.get("address"))}</a></td></tr>'
            )
        for h in hours[:3]:
            rows += f'<tr><th>{esc(h.get("label", "Hours"))}</th><td>{esc(h.get("text"))}</td></tr>'
        parts.append(
            f'<section class="content-section"><h2 class="serif">Contact &amp; hours</h2>'
            f'<table class="data-table">{rows}</table>'
            f'<p class="tiny muted">From bank website · captured {esc(scraped)}. Confirm with the bank before visiting.</p></section>'
        )

    links = en.get("links") or {}
    link_items = []
    for key, label in (
        ("commercial_banking", "Commercial / business banking"),
        ("contact", "Contact page"),
        ("faq", "FAQ"),
        ("apply_online", "Apply online"),
    ):
        url = links.get(key)
        if url:
            link_items.append(f'<li><a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a></li>')
    if link_items:
        parts.append(
            f'<section class="content-section"><h2 class="serif">On the bank&apos;s website</h2>'
            f'<ul class="fit-list">{"".join(link_items)}</ul></section>'
        )

    faqs = en.get("faqs") or []
    if faqs:
        faq_html = ""
        for f in faqs[:8]:
            q = f.get("question", "")
            a = f.get("answer_excerpt", "")
            src = f.get("source_url", "")
            faq_html += (
                f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p>"
                f'<p class="tiny muted"><a href="{esc(src)}" target="_blank" rel="noopener">'
                f"Read full answer on bank site</a> · {esc(f.get('captured_at', scraped))}</p></details>"
            )
        parts.append(
            f'<section class="content-section"><h2 class="serif">FAQ from the bank&apos;s website</h2>'
            f'<div class="faq">{faq_html}</div>'
            f'<p class="tiny muted">Short excerpts only — not financial advice. Rates and terms are set by the bank.</p></section>'
        )

    if not parts:
        return ""
    return "\n".join(parts)


def json_ld_for_bank(bank: dict) -> str:
    en = bank.get("webEnrichment") or {}
    phones = en.get("phones") or []
    tel = phones[0].get("number") if phones else None
    org: dict[str, Any] = {
        "@type": "BankOrCreditUnion",
        "name": bank.get("name"),
        "url": bank.get("website"),
        "address": {
            "@type": "PostalAddress",
            "addressLocality": bank.get("city"),
            "addressRegion": "TX",
            "postalCode": str(bank.get("zip") or ""),
            "streetAddress": bank.get("hqAddress"),
        },
    }
    if tel:
        org["telephone"] = tel
    graph: list[dict[str, Any]] = [{"@context": "https://schema.org", **org}]
    faqs = en.get("faqs") or []
    if len(faqs) >= 2:
        graph.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f["question"],
                    "acceptedAnswer": {"@type": "Answer", "text": f["answer_excerpt"]},
                }
                for f in faqs[:6]
            ],
        })
    if len(graph) == 1:
        return json.dumps(graph[0], separators=(",", ":"))
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, separators=(",", ":"))
