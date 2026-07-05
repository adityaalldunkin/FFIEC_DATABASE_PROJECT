# Session Notes — Lenni Borrower Site, Sub-Types, S3 Deploy & Chat Roadmap

**Date:** 2026-06-14  
**Project:** `/Users/adityarajiv/Documents/ffiec-cdr`  
**Live site:** http://lenni-borrower.s3-website.us-east-2.amazonaws.com/  
**S3 bucket:** `lenni-borrower` (us-east-2)  
**Prior session notes:** [session-notes_2026-06-07.md](session-notes_2026-06-07.md)  
**PDF companion:** [ONLY_TEXAS_SINCE_2025/analysis/Lenni_Session_Documentation_2026-06-14.pdf](ONLY_TEXAS_SINCE_2025/analysis/Lenni_Session_Documentation_2026-06-14.pdf)

---

## Executive summary

This session span covers **project status review**, **where loan product sub-types live on the live site**, and a **full implementation plan for a borrower chat interface** powered by Monday.com data and call recordings. It also documents **S3 deployment success** (435 objects), **AWS CLI setup**, and **GitHub push fixes** (excluding 805 MB `texas_loans_labeled.csv`).

---

## 1. Developments so far — what has been built

### 1.1 Texas FFIEC data pipeline (foundation)

- Texas-only Call Report extract under `ONLY_TEXAS_SINCE_2025/`
- Bank profiles CSV with loan mix, ICP flags, portfolio percentages
- MDRM catalog: `texas_loan_products_mdrm_catalog.csv`
- FDIC enrichment: `institutions.csv`, `locations.csv` (websites, branches, HQ)
- EDA outputs: PDF reports, prospect lists, market segment CSVs
- 50-page comprehensive EDA guide PDF

### 1.2 Borrower-facing static site (`borrower_site/`)

| Asset | Count / detail |
|-------|----------------|
| Total S3 objects | **435** (synced 2026-06-14) |
| Bank profile pages | 351 |
| City landing pages | 40 |
| Parent loan-type hubs | 7 |
| Loan product **sub-type** guides | **27** (new) |
| Interactive index | Bank finder, loan browser, calculator, AI terminal stub |
| Guides | glossary, FAQ, methodology |
| SEO / LLM | `sitemap.xml`, `llms.txt`, `styles.css` |

**Generator:** `python ONLY_TEXAS_SINCE_2025/build_borrower_site.py`  
**Deploy:** `aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete`

### 1.3 Loan product sub-types (main content task — COMPLETED)

| Component | Path |
|-----------|------|
| Single source of truth | `ONLY_TEXAS_SINCE_2025/content/loan_products.yaml` |
| Loader module | `ONLY_TEXAS_SINCE_2025/loan_product_loader.py` |
| Site builder | `ONLY_TEXAS_SINCE_2025/build_borrower_site.py` |
| Interactive app data | `build_borrower_website.py` — `PRODUCTS` from YAML (no duplicate strings) |
| JSON for integrations | `borrower_site/data/loan_products.json` |

Each sub-type page includes:

- Who it's for
- How community banks underwrite it
- What to prepare before calling a bank
- How to approach a bank (opening script + questions)
- Texas banks ranked by FFIEC portfolio share (auto-generated)
- FAQ, related sub-types, disclaimers

**Parent categories and sub-type counts:**

| Parent | Sub-types |
|--------|-----------|
| Multifamily | acquisition, refinance, bridge, value-add-rehab, permanent-takeout (5) |
| Investor CRE | office, retail, industrial, mixed-use, nnn (5) |
| Owner-occupied CRE | purchase, refinance, sba-504-paired (3) |
| Commercial construction | ground-up, major-rehab, land-development, lot-loans (4) |
| C&I / Business | working-capital-line, equipment, acquisition-finance, abl (4) |
| 1–4 Family | portfolio-rental, investor-flip, second-lien (3) |
| Ag & Farmland | farmland-purchase, operating-line, ranch (3) |

### 1.4 Bug fixes completed

| Issue | Fix |
|-------|-----|
| Empty glossary on live site | `load_glossary()` filter: `in_texas_data == "yes"` (not boolean `True`) |
| GitHub push rejected (805 MB file) | `texas_loans_labeled.csv` added to `.gitignore`; removed from git index; recommitted as `f54237e` |

### 1.5 DevOps completed

- AWS CLI installed and configured (`us-east-2`)
- IAM policy for `lenni-borrower` bucket (ListBucket, Get/Put/DeleteObject)
- Successful S3 sync verified: 435 objects, sub-type folders present, `loan_products.json` in `data/`

---

## 2. Tasks completed vs open

### [DONE] Completed

1. Texas FFIEC + FDIC data pipeline and EDA
2. Multi-page borrower static site (351 banks, cities, guides)
3. Loan product taxonomy YAML + 27 sub-type content pages
4. Site builder refactor (single source of truth)
5. Glossary fix
6. Git repo push (large file excluded)
7. S3 production deploy

### [PARTIAL] Partially done

| Item | Status |
|------|--------|
| Monday.com integration | Documented (MCP + API); not wired to repo |
| AI terminal on site | Stub exists; no roadmap output |
| Deal matching | Keywords in YAML for routing; no `match_deal()` API |
| HTTPS / CloudFront | Still HTTP S3 website endpoint |

### [TODO] Not started

1. Chat interface with Monday data + recordings → application roadmap
2. Listing → loan type + bank recommendation model (full)
3. Monday MCP connected in Cursor for live board access
4. `sync_monday_exports.py`
5. SME editorial review of sub-type copy (Doak / CLO)
6. Automated CI deploy script

---

## 3. Where to find loan sub-types on the website

### 3.1 Parent hub pages

URL pattern: `/loan-types/{parent}.html`

| Category | URL |
|----------|-----|
| Multifamily | http://lenni-borrower.s3-website.us-east-2.amazonaws.com/loan-types/multifamily.html |
| Investor CRE | …/loan-types/investor-cre.html |
| Owner-occupied CRE | …/loan-types/owner-occupied-cre.html |
| Commercial construction | …/loan-types/commercial-construction.html |
| C&I / Business | …/loan-types/ci-business.html |
| 1–4 Family | …/loan-types/residential-14.html |
| Ag & Farmland | …/loan-types/ag-farmland.html |

Each hub has a **“Loan product sub-types”** section with clickable cards.

### 3.2 Sub-type guide pages

URL pattern: `/loan-types/{parent}/{subtype}.html`

Examples:

- Multifamily bridge: …/loan-types/multifamily/bridge.html
- SBA 504: …/loan-types/owner-occupied-cre/sba-504-paired.html
- Working capital LOC: …/loan-types/ci-business/working-capital-line.html

### 3.3 Interactive home page

1. Open home → **Loan Types**
2. Category cards show sub-type count and **Full guide →**
3. Open a loan type → **Learn** tab → sub-type chip links
4. Search bar (e.g. “apartment bridge Dallas”) can route to sub-type static page

### 3.4 In the repo (source)

| What | Path |
|------|------|
| Edit content | `ONLY_TEXAS_SINCE_2025/content/loan_products.yaml` |
| Generated HTML | `borrower_site/loan-types/{parent}/{subtype}.html` |
| JSON | `borrower_site/data/loan_products.json` |

---

## 4. Chat interface task — implementation plan

**Goal:** Borrower describes deal in plain English → receives a **roadmap** (loan type, prep steps, banks, how to approach), grounded in Monday.com data and call recordings.

### 4.1 Target output schema

```json
{
  "deal_summary": "48-unit apartment bridge in Dallas, ~$4M",
  "loan_product": { "parent": "multifamily", "subtype": "bridge" },
  "roadmap": [
    { "step": 1, "title": "Clarify hold period & exit", "detail": "..." },
    { "step": 2, "title": "Prepare rent roll + T-12", "detail": "..." },
    { "step": 3, "title": "Shortlist banks", "detail": "..." },
    { "step": 4, "title": "First call script", "detail": "..." }
  ],
  "recommended_banks": [{ "name": "...", "why": "14% multifamily portfolio" }],
  "disclaimer": "Portfolio data only — not an offer or approval."
}
```

### 4.2 Architecture

```
Monday.com + recordings + loan_products.yaml + FFIEC banks.json
    → knowledge_base/ (JSON + transcript chunks)
    → match_deal() + build_roadmap()
    → Chat API (Lambda or FastAPI)
    → Enhanced AI terminal /chat on borrower site
```

**Rules:**

- Banks: **only** from FFIEC `banks.json` (never hallucinated)
- Journey copy: Monday + recordings + YAML
- Never quote rates or approval odds
- Bank is the hero; Lenni is the guide

### 4.3 Phase 1 — Monday data (2–3 days)

1. Connect **Monday MCP** in Cursor (OAuth)
2. Map boards: Loan Products, Underwriting, Loan Application Form, Lenders, Bridge/Hard Money
3. Export to `ONLY_TEXAS_SINCE_2025/knowledge_base/monday_*.json`
4. Later: `sync_monday_exports.py` for automation

### 4.4 Phase 2 — Recordings (3–5 days)

1. Collect sales / education recordings
2. Transcribe (Whisper, Otter, Descript)
3. Chunk with metadata → `recordings_chunks.jsonl`
4. Extract `journey_playbooks.json` per sub-type (stages, actions, scripts)

### 4.5 Phase 3 — `match_deal.py` (1 week)

- Input: property type, units, intent, location, amount, free text
- v0: rules + keywords from `loan_products.yaml`
- v1: LLM with JSON schema
- Bank ranker: portfolio %, ICP, metro (reuse existing logic)

### 4.6 Phase 4 — `build_roadmap.py` (3–5 days)

Merge playbook stages + YAML `what_to_prepare` / `how_to_approach` + top banks.

### 4.7 Phase 5 — Chat UI (1–2 weeks)

- v0: Upgrade existing `#terminal` on `index.html`
- v1: Dedicated `/chat` page
- Backend: Lambda + API Gateway (fits S3 static site)

### 4.8 Phase 6 — RAG (optional, after v0)

Embed recording chunks; retrieve by sub-type + stage; pass to LLM as context only.

### 4.9 Recommended 6-week schedule

| Week | Deliverable |
|------|-------------|
| 1 | Monday export JSON |
| 2 | `journey_playbooks.json` from 5–10 recordings |
| 3 | `match_deal.py` + test cases |
| 4 | `build_roadmap()` |
| 5 | Chat API |
| 6 | UI on live site + deploy |

### 4.10 Next coding steps in this repo

1. `ONLY_TEXAS_SINCE_2025/match_deal.py`
2. `ONLY_TEXAS_SINCE_2025/knowledge_base/journey_playbooks.json` (3 pilots)
3. `ONLY_TEXAS_SINCE_2025/build_roadmap.py`
4. Wire AI terminal to roadmap logic

**Pilot journeys:** multifamily bridge, owner-occupied purchase, C&I working capital.

---

## 5. S3 deploy reference

```bash
cd /Users/adityarajiv/Documents/ffiec-cdr
source .venv/bin/activate
python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
```

**Verified 2026-06-14:**

- 435 objects in bucket
- `loan-types/multifamily/bridge.html` and siblings present
- `data/loan_products.json`, `glossary.json`, `banks.json` present

---

## 6. Git / data hygiene

**Do not commit to GitHub:**

- `texas_loans_labeled.csv` (805 MB)
- `ONLY_TEXAS_SINCE_2025/exports/` large extracts (gitignored)

**Commit message reference:** `f54237e` — Lenni borrower site, sub-types, tooling (large CSV excluded)

---

## 7. Key file index

| Purpose | Path |
|---------|------|
| Loan content (edit here) | `ONLY_TEXAS_SINCE_2025/content/loan_products.yaml` |
| Regenerate site | `ONLY_TEXAS_SINCE_2025/build_borrower_site.py` |
| Static output | `borrower_site/` |
| Lenni context | `lenni_contenxt.txt` |
| Session notes (prior) | `session-notes_2026-06-07.md` |
| This session | `session-notes_2026-06-14.md` |

---

## 8. One-line project status

**Done:** Live Texas bank finder on S3 with 351 banks, 7 loan categories, 27 sub-type guides, FFIEC/FDIC data, glossary, repeatable build/deploy pipeline.

**Next:** Monday sync, `match_deal()` + roadmap builder, full chat interface, production HTTPS.

---

*Generated 2026-06-14 for Lenni / ALL Dunkin FFIEC CDR project.*
