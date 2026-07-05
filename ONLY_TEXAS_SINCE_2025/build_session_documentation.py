#!/usr/bin/env python3
"""
Generate PDF session documentation from session-notes_2026-06-14.md

  python ONLY_TEXAS_SINCE_2025/build_session_documentation.py
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / "session-notes_2026-06-14.md"
OUT = Path(__file__).resolve().parent / "analysis" / "Lenni_Session_Documentation_2026-06-14.pdf"

NAVY = "#0E1B2A"
SAGE = "#1f9d76"
MUTED = "#5b6b7b"


def parse_sections(md: str) -> list[tuple[str, str]]:
    """Split markdown into (title, body) by ## headings."""
    sections: list[tuple[str, str]] = []
    parts = re.split(r"\n(?=## )", md.strip())
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n", 1)
        title = lines[0].lstrip("#").strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if title.startswith("Session Notes"):
            continue  # cover uses custom title
        sections.append((title, body))
    return sections


def strip_md_tables_and_links(text: str) -> str:
    """Simplify markdown for plain-text PDF rendering."""
    out_lines = []
    for line in text.split("\n"):
        if line.strip().startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2:
                out_lines.append(f"  {cells[0]}: {cells[1]}")
            continue
        if line.strip().startswith("|") and "---" in line:
            continue
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        line = re.sub(r"\*([^*]+)\*", r"\1", line)
        if line.startswith("### "):
            line = "\n" + line[4:].upper() + "\n" + "-" * min(60, len(line))
        elif line.startswith("## "):
            line = "\n" + line[3:] + "\n"
        out_lines.append(line)
    return "\n".join(out_lines)


def wrap_body(body: str, width: int = 92) -> str:
    body = strip_md_tables_and_links(body)
    wrapped_lines = []
    for line in body.split("\n"):
        if not line.strip():
            wrapped_lines.append("")
        elif line.startswith("  ") or line.startswith("-"):
            wrapped_lines.append(textwrap.fill(line, width=width, subsequent_indent="    "))
        else:
            wrapped_lines.append(textwrap.fill(line, width=width))
    return "\n".join(wrapped_lines)


def cover_page(pdf: PdfPages) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor("white")
    fig.text(0.5, 0.62, "Lenni Borrower Platform", ha="center", fontsize=22, fontweight="bold", color=NAVY)
    fig.text(0.5, 0.54, "Session Documentation", ha="center", fontsize=16, color=SAGE)
    fig.text(
        0.5, 0.44,
        "Developments · Completed Tasks · Sub-Type Site Map · Chat Roadmap",
        ha="center", fontsize=11, color=MUTED,
    )
    fig.text(0.5, 0.32, "2026-06-14", ha="center", fontsize=12, color=MUTED)
    fig.text(
        0.5, 0.22,
        "FFIEC CDR / Texas Community Bank Index / lenni-borrower S3",
        ha="center", fontsize=10, color=MUTED,
    )
    fig.text(
        0.5, 0.08,
        "Companion: session-notes_2026-06-14.md",
        ha="center", fontsize=9, color=MUTED,
    )
    plt.axis("off")
    pdf.savefig(fig)
    plt.close(fig)


def content_pages(pdf: PdfPages, sections: list[tuple[str, str]]) -> None:
    for title, body in sections:
        wrapped = wrap_body(body)
        chunk_size = 3200
        chunks = [wrapped[i:i + chunk_size] for i in range(0, max(len(wrapped), 1), chunk_size)]
        if not chunks:
            chunks = [""]
        for i, chunk in enumerate(chunks):
            fig = plt.figure(figsize=(11, 8.5))
            fig.patch.set_facecolor("white")
            page_title = title if i == 0 else f"{title} (continued)"
            fig.text(0.05, 0.95, page_title, fontsize=13, fontweight="bold", va="top", color=NAVY)
            fig.text(0.05, 0.88, chunk, fontsize=8.2, va="top", family="sans-serif", color="#1c2e42")
            fig.text(0.95, 0.02, f"Lenni · {OUT.name}", ha="right", fontsize=7, color=MUTED)
            plt.axis("off")
            pdf.savefig(fig)
            plt.close(fig)


def main() -> int:
    if not NOTES.is_file():
        raise FileNotFoundError(f"Missing {NOTES}")
    md = NOTES.read_text(encoding="utf-8")
    sections = parse_sections(md)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUT) as pdf:
        cover_page(pdf)
        content_pages(pdf, sections)
    print(f"Wrote {OUT}")
    print(f"  Source: {NOTES}")
    print(f"  Sections: {len(sections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
