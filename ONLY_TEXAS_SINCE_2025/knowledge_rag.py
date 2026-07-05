"""Lightweight RAG over loan product YAML and borrower scenarios — no external deps."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _load_chunks() -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []

    products_path = ROOT / "content" / "loan_products.yaml"
    if products_path.is_file():
        data = yaml.safe_load(products_path.read_text(encoding="utf-8"))
        for parent in data.get("parents") or []:
            text = " ".join(filter(None, [
                parent.get("name", ""),
                parent.get("short", ""),
                parent.get("learn", ""),
                " ".join(parent.get("keywords") or []),
            ]))
            chunks.append({
                "id": f"parent:{parent.get('slug')}",
                "text": text,
                "tags": parent.get("key", ""),
            })
            for st in parent.get("subtypes") or []:
                st_text = " ".join(filter(None, [
                    st.get("title", ""),
                    st.get("one_liner", ""),
                    st.get("who_its_for", ""),
                    st.get("how_banks_underwrite", ""),
                    " ".join(st.get("keywords") or []),
                    " ".join(st.get("what_to_prepare") or []),
                ]))
                chunks.append({
                    "id": f"subtype:{parent.get('slug')}/{st.get('slug')}",
                    "text": st_text,
                    "tags": parent.get("key", ""),
                })

    scenarios_path = ROOT / "content" / "borrower_scenarios.yaml"
    if scenarios_path.is_file():
        data = yaml.safe_load(scenarios_path.read_text(encoding="utf-8"))
        for sc in data.get("scenarios") or []:
            text = " ".join(filter(None, [
                sc.get("title", ""),
                sc.get("summary", ""),
                sc.get("situation", ""),
                " ".join(sc.get("action_plan") or []),
                " ".join(sc.get("questions_to_ask") or []),
            ]))
            chunks.append({
                "id": f"scenario:{sc.get('slug')}",
                "text": text.replace("\n", " "),
                "tags": sc.get("loan_parent", ""),
            })

    return chunks


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def retrieve(query: str, *, top_k: int = 4, parent_key: str | None = None) -> list[dict[str, Any]]:
    """Hybrid-ish retrieval: BM25-style keyword overlap scoring."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    scored: list[tuple[float, dict]] = []
    for chunk in _load_chunks():
        c_tokens = _tokenize(chunk["text"])
        if not c_tokens:
            continue
        overlap = len(q_tokens & c_tokens)
        if overlap == 0:
            continue
        score = overlap / (len(q_tokens) ** 0.5)
        if parent_key and chunk.get("tags") == parent_key:
            score *= 1.5
        scored.append((score, chunk))

    scored.sort(key=lambda x: -x[0])
    return [
        {"id": c["id"], "text": c["text"][:400], "score": round(s, 3)}
        for s, c in scored[:top_k]
    ]


def format_context(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "No specific product context retrieved."
    return "\n".join(f"[{c['id']}] {c['text']}" for c in chunks)
