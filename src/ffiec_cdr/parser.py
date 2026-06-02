"""Phase 3: parse XBRL facsimiles into normalized fact rows."""

from __future__ import annotations

import re
from typing import Any

from lxml import etree

# Inline XBRL and standard XBRL namespaces seen in Call/UBPR filings
NS = {
    "xbrli": "http://www.xbrl.org/2003/instance",
    "ix": "http://www.xbrl.org/2013/inlineXBRL",
    "link": "http://www.xbrl.org/2003/linkbase",
    "xbrldi": "http://xbrl.org/2006/xbrldi",
}

SKIP_TAGS = frozenset(
    {
        "context",
        "unit",
        "schemaRef",
        "linkbaseRef",
        "roleRef",
        "arcroleRef",
    }
)


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _parse_numeric(text: str) -> float | None:
    cleaned = text.replace(",", "").strip()
    if not cleaned or cleaned in ("-", "—"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_xbrl(content: bytes) -> list[dict[str, Any]]:
    """
    Extract fact-like elements from an XBRL instance (including inline XBRL).

    Returns rows: concept, context_ref, unit_ref, value_text, value_num.
    """
    parser = etree.XMLParser(recover=True, huge_tree=True)
    try:
        root = etree.fromstring(content, parser=parser)
    except etree.XMLSyntaxError:
        return []

    facts: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()

    for elem in root.iter():
        name = _local_name(elem.tag)
        if name in SKIP_TAGS:
            continue

        # Inline facts
        context_ref = elem.get("contextRef") or elem.get("contextref")
        unit_ref = elem.get("unitRef") or elem.get("unitref")
        if context_ref is None and elem.getparent() is not None:
            parent = elem.getparent()
            context_ref = parent.get("contextRef") or parent.get("contextref")

        text = (elem.text or "").strip()
        if not text and len(elem) == 0:
            continue
        if not text:
            text = "".join(elem.itertext()).strip()
        if not text:
            continue

        concept = name
        if elem.nsmap:
            for prefix, uri in elem.nsmap.items():
                if uri and elem.tag.startswith("{"):
                    concept = elem.tag
                    break

        key = (concept, context_ref, text[:80])
        if key in seen:
            continue
        seen.add(key)

        value_num = _parse_numeric(text)
        facts.append(
            {
                "concept": concept,
                "context_ref": context_ref,
                "unit_ref": unit_ref,
                "value_text": text[:2000],
                "value_num": value_num,
            }
        )

    # Cap per filing to keep DB reasonable on first sync
    max_facts = 50_000
    return facts[:max_facts]


def extract_institution_hints(content: bytes) -> dict[str, Any]:
    """Best-effort DEI / entity hints from XBRL text."""
    text = content.decode("utf-8", errors="ignore")
    hints: dict[str, Any] = {}
    for pattern, key in [
        (r"<dei:EntityRegistrantName[^>]*>([^<]+)", "name"),
        (r"EntityRegistrantName[^>]*>([^<]+)", "name"),
        (r"<dei:EntityCentralIndexKey[^>]*>([^<]+)", "cik"),
    ]:
        m = re.search(pattern, text, re.I)
        if m:
            hints[key] = m.group(1).strip()
    return hints
