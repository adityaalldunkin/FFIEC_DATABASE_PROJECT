#!/usr/bin/env python3
"""
Generate Lenni Borrower Website Guide PDF — comprehensive, human-readable.

  MPLCONFIGDIR=/tmp/mplcache python ONLY_TEXAS_SINCE_2025/build_borrower_website_guide.py

Output: ONLY_TEXAS_SINCE_2025/analysis/Lenni_Borrower_Website_Guide.pdf
"""

from __future__ import annotations

import json
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import yaml
from matplotlib.backends.backend_pdf import PdfPages

from guide_content import all_sections

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SITE = REPO / "borrower_site"
ANALYSIS = ROOT / "analysis"
CONTENT = ROOT / "content"
OUT_PDF = ANALYSIS / "Lenni_Borrower_Website_Guide.pdf"
LIVE = "http://lenni-borrower.s3-website.us-east-2.amazonaws.com"

NAVY = "#0E1B2A"
SAGE = "#1f9d76"
MUTED = "#5b6b7b"
BODY = "#1c2e42"
CHARS = 1650  # smaller chunks = more pages, easier reading


def load_context() -> dict:
    stats, period, insights = {}, "12/31/2025", []
    mi = SITE / "data" / "market_insights.json"
    if mi.is_file():
        data = json.loads(mi.read_text(encoding="utf-8"))
        stats = data.get("stats", {})
        period = data.get("period", period)
        insights = data.get("insights", [])

    scenarios = []
    sp = CONTENT / "borrower_scenarios.yaml"
    if sp.is_file():
        scenarios = yaml.safe_load(sp.read_text(encoding="utf-8")).get("scenarios", [])

    parents = []
    pp = CONTENT / "loan_products.yaml"
    if pp.is_file():
        parents = yaml.safe_load(pp.read_text(encoding="utf-8")).get("parents", [])

    n_urls = 470
    sm = SITE / "sitemap.xml"
    if sm.is_file():
        n_urls = sm.read_text(encoding="utf-8").count("<url>")

    def fmt_m(v):
        v = float(v or 0)
        return f"${v/1000:.1f}B" if v >= 1000 else f"${v:.0f}M"

    return {
        "live": LIVE,
        "period": period,
        "build_date": datetime.now().strftime("%B %d, %Y"),
        "n_banks": stats.get("bank_count", 351),
        "n_icp": stats.get("icp_count", 105),
        "n_urls": n_urls,
        "n_objects": 478,
        "med_assets": fmt_m(stats.get("median_assets_m", 437)),
        "med_loans": fmt_m(stats.get("median_loans_m", 256)),
        "med_lta": stats.get("median_lta", 62),
        "portfolio_style": stats.get("portfolio_style_count", 129),
        "insights": insights,
        "scenarios": scenarios,
        "parents": parents,
    }


def wrap_paragraph(para: str, width: int = 86) -> str:
    para = para.strip()
    if not para:
        return ""
    if para.startswith("  ") or para.startswith("•") or para.startswith("☐"):
        return textwrap.fill(para, width=width, subsequent_indent="    ")
    if para.startswith("{"):
        return para  # JSON blocks — don't wrap
    return textwrap.fill(para, width=width)


def wrap_body(body: str) -> str:
    lines = []
    for para in body.strip().split("\n"):
        if not para.strip():
            lines.append("")
        else:
            lines.append(wrap_paragraph(para))
    return "\n".join(lines)


def split_pages(title: str, body: str) -> list[tuple[str, str]]:
    wrapped = wrap_body(body)
    pages: list[tuple[str, str]] = []
    current = ""
    for para in wrapped.split("\n\n"):
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= CHARS:
            current = candidate
        else:
            if current:
                pages.append((title if not pages else f"{title} (continued)", current))
            if len(para) <= CHARS:
                current = para
            else:
                words = para.split()
                chunk = ""
                for w in words:
                    test = f"{chunk} {w}".strip()
                    if len(test) > CHARS and chunk:
                        pages.append((title if not pages else f"{title} (continued)", chunk))
                        chunk = w
                    else:
                        chunk = test
                current = chunk
    if current:
        pages.append((title if not pages else f"{title} (continued)", current))
    return pages or [(title, body)]


def cover_page(pdf: PdfPages, ctx: dict) -> None:
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    fig.text(0.5, 0.70, "Lenni Borrower Website", ha="center", fontsize=28, fontweight="bold", color=NAVY)
    fig.text(0.5, 0.62, "Complete Guide", ha="center", fontsize=18, color=SAGE)
    fig.text(
        0.5, 0.52,
        "Every page, feature, and deployment setting —\nwritten for borrowers, teammates, and developers",
        ha="center", fontsize=11, color=MUTED, linespacing=1.6,
    )
    fig.text(0.5, 0.38, f"{ctx['n_banks']} Texas banks  ·  {ctx['n_urls']} pages  ·  {ctx['n_objects']} files on AWS", ha="center", fontsize=11, color=BODY)
    fig.text(0.5, 0.32, f"FFIEC data period: {ctx['period']}", ha="center", fontsize=10, color=MUTED)
    fig.text(0.5, 0.24, ctx["live"], ha="center", fontsize=9, color=SAGE)
    fig.text(0.5, 0.14, f"Generated {ctx['build_date']}", ha="center", fontsize=9, color=MUTED)
    fig.text(0.5, 0.08, "Includes: site walkthrough · loan guides · insights · scenarios · AWS deployment", ha="center", fontsize=8, color=MUTED)
    plt.axis("off")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def toc_page(pdf: PdfPages, section_titles: list[str], page_map: list[int]) -> None:
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    fig.text(0.07, 0.94, "Table of Contents", fontsize=16, fontweight="bold", color=NAVY)
    y = 0.88
    for i, (title, pnum) in enumerate(zip(section_titles, page_map)):
        if y < 0.06:
            break
        short = title if len(title) < 72 else title[:69] + "..."
        fig.text(0.07, y, short, fontsize=8.5, color=BODY)
        fig.text(0.93, y, str(pnum), fontsize=8.5, ha="right", color=MUTED)
        y -= 0.022
    plt.axis("off")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def content_page(pdf: PdfPages, title: str, body: str, page_num: int) -> None:
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor("white")
    # Section title bar
    fig.add_axes([0, 0.91, 1, 0.09])
    ax_bar = fig.axes[-1]
    ax_bar.set_facecolor("#f0ede5")
    ax_bar.set_xlim(0, 1)
    ax_bar.set_ylim(0, 1)
    ax_bar.axis("off")
    ax_bar.text(0.05, 0.5, title, fontsize=11, fontweight="bold", va="center", color=NAVY)
    # Body
    fig.text(0.07, 0.86, body, fontsize=9, va="top", family="sans-serif", color=BODY, linespacing=1.45)
    # Footer
    fig.text(0.5, 0.035, f"Lenni Borrower Website Guide  ·  Page {page_num}", ha="center", fontsize=7.5, color=MUTED)
    plt.axis("off")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ctx = load_context()
    raw_sections = all_sections(ctx)

    # Expand all sections into page chunks
    expanded: list[tuple[str, str]] = []
    section_start_pages: list[int] = []
    page_num = 3  # after cover + toc

    for title, body in raw_sections:
        section_start_pages.append(page_num)
        for pt, pb in split_pages(title, body):
            expanded.append((pt, pb))
            page_num += 1

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    section_titles = [t for t, _ in raw_sections]

    with PdfPages(OUT_PDF) as pdf:
        cover_page(pdf, ctx)
        toc_page(pdf, section_titles, section_start_pages)
        p = 3
        for title, body in expanded:
            content_page(pdf, title, body, p)
            p += 1

    print(f"Wrote {OUT_PDF}")
    print(f"  Sections: {len(raw_sections)}")
    print(f"  Pages: {p - 1}")
    print(f"  Live site: {LIVE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
