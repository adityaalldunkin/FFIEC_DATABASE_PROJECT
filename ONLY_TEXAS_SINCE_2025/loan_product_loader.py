"""Load loan product taxonomy from content/loan_products.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
CONTENT_PATH = ROOT / "content" / "loan_products.yaml"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    if not CONTENT_PATH.is_file():
        raise FileNotFoundError(f"Missing loan product catalog: {CONTENT_PATH}")
    with CONTENT_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "parents" not in data:
        raise ValueError("loan_products.yaml must define a top-level 'parents' list")
    return data


def load_parents() -> list[dict[str, Any]]:
    return load_catalog()["parents"]


def parent_as_legacy(parent: dict[str, Any]) -> dict[str, Any]:
    """Shape compatible with legacy LOAN_TYPES entries."""
    faq = parent.get("faq") or []
    return {
        "slug": parent["slug"],
        "key": parent["key"],
        "name": parent["name"],
        "cat": parent.get("cat", ""),
        "short": parent.get("short", ""),
        "learn": parent.get("learn", ""),
        "lines": parent.get("lines", ""),
        "faq": [(item["q"], item["a"]) if isinstance(item, dict) else item for item in faq],
        "subtypes": parent.get("subtypes") or [],
    }


def legacy_loan_types() -> list[dict[str, Any]]:
    return [parent_as_legacy(p) for p in load_parents()]


def products_for_js() -> list[dict[str, Any]]:
    items = []
    for parent in load_parents():
        subtypes = []
        for st in parent.get("subtypes") or []:
            subtypes.append({
                "slug": st["slug"],
                "title": st["title"],
                "one_liner": st.get("one_liner", ""),
                "pageUrl": f"loan-types/{parent['slug']}/{st['slug']}.html",
                "keywords": st.get("keywords") or [],
            })
        items.append({
            "slug": parent["slug"],
            "key": parent["key"],
            "name": parent["name"],
            "cat": parent.get("cat", ""),
            "short": parent.get("short", ""),
            "learn": parent.get("learn", ""),
            "lines": parent.get("lines", ""),
            "pageUrl": f"loan-types/{parent['slug']}.html",
            "subtypes": subtypes,
        })
    return items


def loan_products_json() -> dict[str, Any]:
    parents = []
    for parent in load_parents():
        entry = {
            "slug": parent["slug"],
            "key": parent["key"],
            "name": parent["name"],
            "cat": parent.get("cat", ""),
            "short": parent.get("short", ""),
            "learn": parent.get("learn", ""),
            "lines": parent.get("lines", ""),
            "mdrm": parent.get("mdrm") or [],
            "pageUrl": f"loan-types/{parent['slug']}.html",
            "subtypes": [],
        }
        for st in parent.get("subtypes") or []:
            entry["subtypes"].append({
                "slug": st["slug"],
                "title": st["title"],
                "one_liner": st.get("one_liner", ""),
                "keywords": st.get("keywords") or [],
                "pageUrl": f"loan-types/{parent['slug']}/{st['slug']}.html",
                "who_its_for": st.get("who_its_for", ""),
                "how_banks_underwrite": st.get("how_banks_underwrite", ""),
                "what_to_prepare": st.get("what_to_prepare") or [],
                "how_to_approach": st.get("how_to_approach") or {},
                "faq": st.get("faq") or [],
                "related_subtypes": st.get("related_subtypes") or [],
                "not_this_product": st.get("not_this_product", ""),
            })
        parents.append(entry)
    return {"parents": parents}


def all_subtype_pages() -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return (parent, subtype) pairs for static page generation."""
    pages = []
    for parent in load_parents():
        for st in parent.get("subtypes") or []:
            pages.append((parent, st))
    return pages


def subtype_keyword_index() -> list[dict[str, str]]:
    """Flat index for AI routing: keyword → parent key + optional subtype slug."""
    index = []
    for parent in load_parents():
        for kw in parent.get("keywords") or []:
            index.append({"keyword": kw.lower(), "parent_key": parent["key"], "subtype": ""})
        for st in parent.get("subtypes") or []:
            for kw in st.get("keywords") or []:
                index.append({
                    "keyword": kw.lower(),
                    "parent_key": parent["key"],
                    "subtype": st["slug"],
                    "parent_slug": parent["slug"],
                })
    return index
