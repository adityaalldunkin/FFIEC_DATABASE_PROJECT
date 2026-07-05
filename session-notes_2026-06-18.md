# Session Notes — Bank Website Enrichment + S3 Deploy

**Date:** 2026-06-18  
**Project:** `/Users/adityarajiv/Documents/ffiec-cdr`  
**Live site:** http://lenni-borrower.s3-website.us-east-2.amazonaws.com/  
**Prior session:** [session-notes_2026-06-14.md](session-notes_2026-06-14.md)

---

## Executive summary

Implemented **automated bank website enrichment** (about text, phones, emails, hours, deep links, FAQ excerpts) and merged it into **351 bank profile pages**. Scraped **344 Texas banks** with FDIC websites; **257** returned usable data; **255** matched and published on the live site. Deployed to **S3** (`lenni-borrower`, `us-east-2`) via `aws s3 sync --delete`.

---

## Manager task addressed

> Scrape bank website FAQ/details; place in bank details section; include date, website link, contact info; optimize for SEO and LLM discoverability.

**Approach:** Separate enrichment layer (JSON) → merge at build time → static HTML with attribution, `schema.org` JSON-LD, and outbound links. Excerpts only — not full page copies.

---

## Code changes

### New files

| File | Purpose |
|------|---------|
| `ONLY_TEXAS_SINCE_2025/bank_enrichment.py` | Load JSON, merge into bank records, render HTML + JSON-LD |
| `ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py` | Fetch bank sites (requests + lxml), extract contacts/FAQ/links |
| `ONLY_TEXAS_SINCE_2025/enrichment/bank_website_enrichment.json` | Scraped data (257 banks) |
| `borrower_site/data/bank_website_enrichment.json` | Copy shipped with static site |

### Modified files

| File | Change |
|------|--------|
| `ONLY_TEXAS_SINCE_2025/build_borrower_site.py` | Merge enrichment; new bank page sections; copy enrichment JSON to `data/` |

---

## Scraper behavior (efficient design)

- **Input:** FDIC `WEBADDR` from `institutions.csv` joined to Texas bank profiles
- **Fetch:** Homepage + one subpage (FAQ, commercial, or contact link if found)
- **Extract:** `meta description`, `tel:` / `mailto:`, JSON-LD FAQPage, link discovery, hours heuristics
- **Concurrency:** 8 workers, ~54s for 344 banks
- **Output:** One JSON file keyed by `rssd` — no raw HTML in git

### Scrape results (2026-06-18)

| Metric | Count |
|--------|------:|
| Banks with FDIC website | 344 |
| Successfully enriched | 257 |
| Published on site (RSSD match) | 255 |
| Failed / empty | 87 |
| With phone numbers | 208 |
| With email addresses | 44 |
| With JSON-LD FAQ | 2 |

*FAQ count is low because most community bank sites lack FAQ schema; phones and about text are the main win.*

---

## Bank profile page — new sections

When enrichment exists, each `banks/{rssd}-{slug}.html` page now includes:

1. **About this bank** — meta description excerpt + link + capture date  
2. **Contact & hours** — phones, emails, hours (with source links)  
3. **On the bank's website** — commercial banking, contact, FAQ, apply links  
4. **FAQ from the bank's website** — when JSON-LD FAQ exists (accordion + “read full answer” link)  
5. **`application/ld+json`** — `BankOrCreditUnion` + optional `FAQPage` schema  

**Example (live):**  
http://lenni-borrower.s3-website.us-east-2.amazonaws.com/banks/682563-frost-bank.html

Attribution footer on enriched blocks:

> Excerpt from bank website · captured YYYY-MM-DD

---

## Deploy

```bash
python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py    # refresh enrichment
python ONLY_TEXAS_SINCE_2025/build_borrower_site.py   # rebuild site
aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
```

**Deployed:** 2026-06-18 — full `borrower_site/` sync completed successfully.

### CLI options

```bash
python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py --icp-only   # 105 ICP banks only
python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py --limit 20    # smoke test
python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py --workers 8
```

---

## Data schema (`bank_website_enrichment.json`)

```json
{
  "rssd": 682563,
  "website": "https://www.frostbank.com",
  "scraped_at": "2026-06-18",
  "about_excerpt": "...",
  "about_source_url": "https://...",
  "phones": [{ "label": "Phone", "number": "...", "source_url": "..." }],
  "emails": [{ "label": "Email", "address": "...", "source_url": "..." }],
  "hours": [{ "label": "Hours", "text": "..." }],
  "faqs": [{ "question": "...", "answer_excerpt": "...", "source_url": "...", "captured_at": "..." }],
  "links": { "commercial_banking": "...", "contact": "...", "faq": "...", "apply_online": "..." },
  "review_status": "auto"
}
```

---

## SEO / LLM improvements

- Unique **about** text per bank (from bank meta description)  
- **Structured data** (`BankOrCreditUnion`, `FAQPage` where available)  
- **Outbound canonical links** to bank commercial/contact/FAQ pages  
- **Capture dates** on all excerpts (freshness signal)  
- Enrichment JSON at `data/bank_website_enrichment.json` for future chat/RAG  

---

## Legal / quality notes

- Short excerpts only; full answers linked on bank site  
- `review_status: auto` — recommend human QA for ICP 105 before sales use  
- Respect rate limits; User-Agent identifies Lenni research  
- 87 banks failed (no website, SSL errors, or empty pages) — FFIEC/FDIC data still shown  

---

## Recommended next steps

1. **Monday Lenders board** — merge banker contacts (not on public websites)  
2. **HTML FAQ parsing** — improve FAQ extraction beyond JSON-LD (currently 2 banks)  
3. **Human review queue** — `review_status: approved` for ICP segment  
4. **Monthly re-scrape** — cron + `scraped_at` stale flag after 90 days  
5. **Monday MCP** — sync Loan Products into chat roadmap (separate task)  

---

## File index

| Purpose | Path |
|---------|------|
| Run scraper | `ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py` |
| Enrichment data | `ONLY_TEXAS_SINCE_2025/enrichment/bank_website_enrichment.json` |
| Render helpers | `ONLY_TEXAS_SINCE_2025/bank_enrichment.py` |
| Rebuild site | `ONLY_TEXAS_SINCE_2025/build_borrower_site.py` |
| Static output | `borrower_site/` |

---

*Generated 2026-06-18 · Lenni borrower platform / FFIEC CDR project.*
