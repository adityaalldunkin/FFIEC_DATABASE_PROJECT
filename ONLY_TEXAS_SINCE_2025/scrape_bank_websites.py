#!/usr/bin/env python3
"""
Fetch public bank website snippets for Lenni borrower profiles.

  python scrape_bank_websites.py              # all TX banks with FDIC website
  python scrape_bank_websites.py --icp-only   # Lenni ICP segment only
  python scrape_bank_websites.py --limit 20   # smoke test

Writes: enrichment/bank_website_enrichment.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from lxml import html as lhtml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
EXPORTS = ROOT / "exports"
OUT = ROOT / "enrichment" / "bank_website_enrichment.json"

LINK_KEYWORDS = (
    "business", "commercial", "faq", "contact", "lending", "loan", "apply", "about",
)
PHONE_RE = re.compile(
    r"(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}"
)
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "LenniBorrowerResearch/1.0 (+https://lenni-borrower.s3-website.us-east-2.amazonaws.com; regulatory research)",
    "Accept": "text/html,application/xhtml+xml",
})


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url or url.lower() in ("nan", "none"):
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def fetch(url: str, timeout: int = 12) -> str | None:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code >= 400 or not r.text:
            return None
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return None
        return r.text
    except requests.RequestException:
        return None


def extract_json_ld_faqs(doc: lhtml.HtmlElement) -> list[dict]:
    faqs: list[dict] = []
    for script in doc.xpath('//script[@type="application/ld+json"]/text()'):
        try:
            data = json.loads(script)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "FAQPage":
                for ent in item.get("mainEntity") or []:
                    if not isinstance(ent, dict):
                        continue
                    q = ent.get("name") or ""
                    ans = ent.get("acceptedAnswer") or {}
                    a = ans.get("text") if isinstance(ans, dict) else str(ans)
                    if q and a:
                        faqs.append({"question": q.strip(), "answer_excerpt": str(a).strip()[:500]})
            if item.get("@type") == "Question":
                q = item.get("name") or ""
                ans = item.get("acceptedAnswer") or {}
                a = ans.get("text") if isinstance(ans, dict) else ""
                if q and a:
                    faqs.append({"question": q.strip(), "answer_excerpt": str(a).strip()[:500]})
    return faqs[:8]


def extract_phones(doc: lhtml.HtmlElement, base_url: str) -> list[dict]:
    seen: set[str] = set()
    phones: list[dict] = []
    for el in doc.xpath("//a[starts-with(@href,'tel:')]"):
        num = unescape(el.get("href", "").replace("tel:", "").strip())
        num = re.sub(r"\s+", " ", num)
        if num and num not in seen:
            seen.add(num)
            label = unescape("".join(el.itertext())).strip() or "Phone"
            phones.append({"label": label[:60], "number": num, "source_url": base_url})
    if not phones:
        text = unescape(" ".join(doc.xpath("//body//text()")))
        for m in PHONE_RE.findall(text):
            if m not in seen and len(m) >= 10:
                seen.add(m)
                phones.append({"label": "Phone", "number": m, "source_url": base_url})
                if len(phones) >= 3:
                    break
    return phones[:5]


def extract_emails(doc: lhtml.HtmlElement, base_url: str) -> list[dict]:
    emails: list[dict] = []
    seen: set[str] = set()
    for el in doc.xpath("//a[starts-with(@href,'mailto:')]"):
        addr = el.get("href", "").replace("mailto:", "").split("?")[0].strip()
        if addr and "@" in addr and addr.lower() not in seen:
            seen.add(addr.lower())
            label = unescape("".join(el.itertext())).strip() or "Email"
            emails.append({"label": label[:60], "address": addr, "source_url": base_url})
    return emails[:3]


def extract_hours(doc: lhtml.HtmlElement) -> list[dict]:
    hours: list[dict] = []
    for el in doc.xpath("//*[contains(translate(@class,'HOURS','hours'),'hour') or contains(@id,'hour')]"):
        text = " ".join(unescape(t).strip() for t in el.xpath(".//text()") if t.strip())
        if 8 < len(text) < 200 and re.search(r"\d", text):
            hours.append({"label": "Hours", "text": text[:180]})
            break
    return hours[:2]


def discover_links(doc: lhtml.HtmlElement, base_url: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for el in doc.xpath("//a[@href]"):
        href = el.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        if urlparse(full).netloc != urlparse(base_url).netloc:
            continue
        path = urlparse(full).path.lower()
        text = unescape("".join(el.itertext())).lower()
        combined = path + " " + text
        if "commercial" in combined or "business-bank" in combined or "business/" in path:
            links.setdefault("commercial_banking", full)
        if "contact" in combined:
            links.setdefault("contact", full)
        if "faq" in combined or "frequently" in combined:
            links.setdefault("faq", full)
        if "apply" in combined or "application" in combined:
            links.setdefault("apply_online", full)
    return links


def extract_about(doc: lhtml.HtmlElement) -> str:
    meta = doc.xpath("//meta[@name='description']/@content")
    if meta:
        return unescape(meta[0].strip())[:400]
    for xp in ("//main//p", "//article//p", "//div[contains(@class,'about')]//p"):
        for p in doc.xpath(xp):
            text = " ".join(unescape(t).strip() for t in p.xpath(".//text()") if t.strip())
            if 80 < len(text) < 600:
                return text[:400]
    return ""


def scrape_one(row: dict) -> dict | None:
    website = normalize_url(str(row.get("WEBADDR") or ""))
    if not website:
        return None
    rssd = int(row["id_rssd"])
    name = str(row.get("name") or row.get("NAME") or "").strip()
    today = date.today().isoformat()

    home_html = fetch(website)
    if not home_html:
        return None

    doc = lhtml.fromstring(home_html)
    base = website
    about = extract_about(doc)
    phones = extract_phones(doc, base)
    emails = extract_emails(doc, base)
    hours = extract_hours(doc)
    links = discover_links(doc, base)
    faqs = extract_json_ld_faqs(doc)
    source_pages = [{"url": base, "title": "Homepage", "fetched_at": today}]

    # One subpage fetch: best candidate FAQ or commercial link
    sub_url = links.get("faq") or links.get("commercial_banking") or links.get("contact")
    if sub_url and sub_url != base:
        sub_html = fetch(sub_url)
        if sub_html:
            sub_doc = lhtml.fromstring(sub_html)
            source_pages.append({"url": sub_url, "title": "Subpage", "fetched_at": today})
            faqs = faqs or extract_json_ld_faqs(sub_doc)
            if not phones:
                phones = extract_phones(sub_doc, sub_url)
            if not emails:
                emails = extract_emails(sub_doc, sub_url)
            if not hours:
                hours = extract_hours(sub_doc)
            links.update(discover_links(sub_doc, sub_url))

    for f in faqs:
        f["source_url"] = links.get("faq") or sub_url or base
        f["captured_at"] = today

    if not any([about, phones, emails, faqs, links]):
        return None

    return {
        "rssd": rssd,
        "slug": f"{rssd}-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:80]}",
        "name": name,
        "website": website,
        "scraped_at": today,
        "about_excerpt": about,
        "about_source_url": base,
        "phones": phones,
        "emails": emails,
        "hours": hours,
        "faqs": faqs,
        "links": links,
        "source_pages": source_pages,
        "extraction_method": "requests+lxml",
        "review_status": "auto",
    }


def load_bank_rows(icp_only: bool, limit: int | None) -> list[dict]:
    profiles = pd.read_csv(EXPORTS / "texas_bank_profiles_latest.csv", dtype={"id_rssd": int})
    fdic = pd.read_csv(REPO / "institutions.csv", low_memory=False)
    fdic_tx = fdic[(fdic["STALP"] == "TX") & (fdic["ACTIVE"] == 1)].copy()
    fdic_tx["FED_RSSD"] = pd.to_numeric(fdic_tx["FED_RSSD"], errors="coerce")
    merged = profiles.merge(fdic_tx, left_on="id_rssd", right_on="FED_RSSD", how="left")
    merged = merged[merged["WEBADDR"].notna() & (merged["WEBADDR"].astype(str).str.len() > 4)]
    if icp_only:
        merged = merged[merged["icp_fit"] == "ICP ($500M–$2B)"]
    merged = merged.sort_values("total_assets", ascending=False)
    if limit:
        merged = merged.head(limit)
    return merged.to_dict("records")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--icp-only", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    rows = load_bank_rows(args.icp_only, args.limit)
    print(f"Scraping {len(rows)} banks with websites…")

    results: list[dict] = []
    failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(scrape_one, r): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            row = futures[fut]
            try:
                rec = fut.result()
                if rec:
                    results.append(rec)
                else:
                    failed += 1
            except Exception:
                failed += 1
            if i % 25 == 0:
                print(f"  …{i}/{len(rows)} processed ({len(results)} enriched)")
            time.sleep(0.15)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": date.today().isoformat(),
        "bank_count": len(results),
        "banks": sorted(results, key=lambda x: x["rssd"]),
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} — {len(results)} banks enriched, {failed} empty/failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
