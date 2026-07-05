# Lenni / FFIEC CDR — Master Session Log (June 7 – June 24, 2026)

**Project:** `/Users/adityarajiv/Documents/ffiec-cdr`  
**Live borrower site:** http://lenni-borrower.s3-website.us-east-2.amazonaws.com/  
**S3 bucket:** `lenni-borrower` (AWS `us-east-2`)  
**Companion PDFs:**  
- [Lenni_Borrower_Website_Guide.pdf](ONLY_TEXAS_SINCE_2025/analysis/Lenni_Borrower_Website_Guide.pdf) — comprehensive layman's guide (~90 pages) including AWS deployment settings  
- [Lenni_Texas_EDA_Comprehensive_Guide.pdf](ONLY_TEXAS_SINCE_2025/analysis/Lenni_Texas_EDA_Comprehensive_Guide.pdf) — data & EDA methodology  
- [Lenni_Session_Documentation_2026-06-14.pdf](ONLY_TEXAS_SINCE_2025/analysis/Lenni_Session_Documentation_2026-06-14.pdf) — June 14 session snapshot  

**Prior session note files (archived detail):**
- [session-notes_2026-06-07.md](session-notes_2026-06-07.md)
- [session-notes_2026-06-14.md](session-notes_2026-06-14.md)
- [session-notes_2026-06-18.md](session-notes_2026-06-18.md)
- [session-notes_2026-06-22-deal-matcher.md](session-notes_2026-06-22-deal-matcher.md)

---

## Executive summary (current state — June 24, 2026)

Over two weeks we built a **full Texas FFIEC regulatory data pipeline**, ran **exhaustive exploratory analysis (EDA)** on bank loan portfolios, and shipped a **production static borrower website** with **478 S3 objects** and **470 sitemap URLs.

The site helps Texas commercial borrowers find community banks that **actually specialize** in their loan type — ranked by real FFIEC Call Report portfolio data, not bank marketing copy. It includes:

| Asset | Count |
|-------|------:|
| Bank profile pages | 351 |
| City landing pages | 40 |
| Loan type parent hubs | 7 |
| Loan sub-type guides | 27 |
| Borrower insight pages | 12 |
| Borrower scenario stories | 12 |
| Market / ICP pages | 6+ (paginated ICP directory) |
| Guide pages | 6 (glossary, FAQ, methodology, playbook, checklist) |
| Machine-readable JSON feeds | 4 (`banks`, `loan_products`, `glossary`, `market_insights`) |
| SEO / LLM files | `sitemap.xml`, `robots.txt`, `llms.txt`, `llms-full.txt` |

**Deploy command:**
```bash
python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
```

---

## Master timeline

| Date | Session | What happened |
|------|---------|---------------|
| **2026-06-07** | FFIEC pipeline | Built 7-phase FFIEC PWS platform; Texas-only extract (2025+); MDRM loan labeling; joined tables; 25-chart Lenni EDA PDF |
| **2026-06-14** | Borrower site v1 | Multi-page static site (351 banks, 40 cities); 27 loan sub-type guides from YAML; S3 deploy (435 objects); glossary fix; git large-file fix |
| **2026-06-18** | Bank enrichment | Scraped 344 bank websites; 255 profiles enriched with phones, about text, links; JSON-LD schema on bank pages; S3 redeploy |
| **2026-06-22** | Deal matcher | `match_deal.py` engine; FastAPI `/api/match`; workspace UI (Land/Loan/My info); local keyword fallback in browser |
| **2026-06-24** | Content expansion | 12 EDA insights, 12 scenario stories, market pages, borrower playbook; SEO (OG tags, robots.txt); 478 S3 objects deployed |

---

## Part 1 — FFIEC data pipeline (June 7)

### What was built

A Python platform that downloads, parses, and exports **FFIEC Central Data Repository (CDR) Public Web Service** Call Report data.

| Phase | Goal | Key location |
|-------|------|--------------|
| 1–7 | Download → archive → parse XBRL → sync → search → API → hardening | `src/ffiec_cdr/`, `scripts/` |
| Texas extract | TX banks only, Q1 2025 → Q1 2026 | `ONLY_TEXAS_SINCE_2025/` |
| Loan labeling | Federal Reserve MDRM dictionary | `mdrm_loader.py`, `texas_loan_products_mdrm_catalog.csv` |
| EDA | 25 analyses + comprehensive PDF guide | `build_lenni_eda_report.py`, `build_comprehensive_eda_guide.py` |

### Texas data scale

| File | Rows | Purpose |
|------|------|---------|
| `texas_institutions.csv` | 1,825 | Bank metadata per quarter |
| `texas_filings.csv` | 1,825 | Filing paths |
| `texas_xbrl_facts.csv` | 2,186,590 | All parsed XBRL facts |
| `texas_loans_summary.csv` | 31,396 | Loan line items (start here) |
| `texas_loans_labeled.csv` | 937,816 | Full RC-C detail (805 MB, gitignored) |
| `texas_bank_profiles_latest.csv` | 360 | Latest quarter snapshot + ICP flag |
| `texas_master_joined.csv` | 1,825 | Master join per bank × quarter |

### Key insight: why `"loan"` filter fails

Call Report line items use **MDRM codes** (e.g. `RCON2122` = total loans, `RCON1460` = multifamily). Plain-text search for `"loan"` returns zero rows. Documented in `LOAN_EXTRACTION_GUIDE.md`.

### Borrower-facing EDA workbook

`build_texas_loans_summary_borrower_eda.py` produces `texas_loans_summary_borrower_eda.xlsx` with:
- 19 EDA sections (borrower lens)
- 12 documented insights (I-01 through I-12)
- Data provenance and abbreviations sheets

### Lenni business context

From `lenni_contenxt.txt`:
- **ICP:** Texas community banks, **$500M–$2B assets** (105 banks in latest panel)
- **Buyer:** Chief Lending Officer / SVP Lending
- **Product:** Convey by Lenni — borrower–lender hub
- **Sales:** One bank per market; portfolio / CRE focus

---

## Part 2 — Borrower static site v1 (June 14)

### Architecture

```
FFIEC profiles + FDIC institutions/locations + loan_products.yaml
        ↓
build_borrower_site.py  (orchestrator)
        ↓ imports render_html() from build_borrower_website.py
        ↓
borrower_site/  →  aws s3 sync  →  S3 static website
```

### Generator scripts

| Script | Role |
|--------|------|
| `build_borrower_site.py` | Full multi-page site: banks, cities, loan guides, JSON, sitemap |
| `build_borrower_website.py` | Interactive SPA template (`index.html`) |
| `loan_product_loader.py` | Reads `content/loan_products.yaml` |
| `loan_mix.py` | Maps FFIEC lines → 11 display categories |

### Loan product taxonomy (27 sub-types)

Single source of truth: `ONLY_TEXAS_SINCE_2025/content/loan_products.yaml`

| Parent category | Sub-types |
|-----------------|-----------|
| Multifamily (5+ units) | acquisition, refinance, bridge, value-add-rehab, permanent-takeout |
| Investor CRE | office, retail, industrial, mixed-use, nnn |
| Owner-occupied CRE | purchase, refinance, sba-504-paired |
| Commercial construction | ground-up, major-rehab, land-development, lot-loans |
| C&I / Business | working-capital-line, equipment, acquisition-finance, abl |
| 1–4 Family residential | portfolio-rental, investor-flip, second-lien |
| Ag & Farmland | farmland-purchase, operating-line, ranch |

Each sub-type page includes: who it's for, underwriting notes, prep checklist, approach script, ranked bank table, FAQ.

### Specialist ranking rule

**≥8%** of a bank's total loans (RCON2122) in a category = specialist. Used site-wide for bank rankings on loan type pages.

### Bug fixes (June 14)

| Issue | Fix |
|-------|-----|
| Empty glossary on live site | `load_glossary()` filter: `in_texas_data == "yes"` |
| GitHub push rejected (805 MB) | `texas_loans_labeled.csv` gitignored |

---

## Part 3 — Bank website enrichment (June 18)

### Goal

Scrape bank websites for contact info and content; merge into profile pages for SEO and borrower utility.

### New files

| File | Purpose |
|------|---------|
| `bank_enrichment.py` | Load JSON, merge records, render HTML + JSON-LD |
| `scrape_bank_websites.py` | Fetch sites, extract contacts/FAQ/links |
| `enrichment/bank_website_enrichment.json` | 257 banks scraped |

### Scrape results

| Metric | Count |
|--------|------:|
| Banks with FDIC website | 344 |
| Successfully enriched | 257 |
| Published on site | 255 |
| With phone numbers | 208 |

### Bank page additions

When enrichment exists:
1. About this bank (meta description excerpt)
2. Contact & hours (phones, emails)
3. On the bank's website (commercial, contact, FAQ links)
4. FAQ from bank website (when JSON-LD FAQ exists)
5. `BankOrCreditUnion` + optional `FAQPage` schema.org JSON-LD

**Refresh enrichment:**
```bash
python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py
python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
```

---

## Part 4 — Deal matcher (June 22)

### Goal

Borrower pastes a listing or describes a deal → system returns loan product match, ranked banks, and preparation roadmap.

### Architecture

```
User text → index.html → LenniMatch.matchDeal()
                              ↓
                    POST /api/match (if API running)
                              ↓
                    match_deal.py + loan_products.yaml + banks.json
                              ↓
                    Workspace UI (Land / Loan / My info tabs)
```

### New files

| File | Purpose |
|------|---------|
| `match_deal.py` | Parse listing, match products, rank banks, build roadmap |
| `build_roadmap.py` | 4-step prep/approach roadmap from YAML |
| `bank_loader.py` | Load `banks.json` |
| `api/main.py` | FastAPI service |
| `run_match_api.py` | Local dev on port 8000 |
| `static/match-client.js` | API client + local keyword fallback |
| `static/workspace.js` | Borrower workspace UI |
| `test_match_deal.py` | Smoke tests |

### Run locally

```bash
python ONLY_TEXAS_SINCE_2025/run_match_api.py
# API at http://127.0.0.1:8000
# Site uses local fallback when API unavailable
```

### Status

- **Backend:** Built and tested locally
- **Frontend:** Wired into `index.html` workspace
- **Production API:** Not deployed to cloud yet (defaults to `127.0.0.1:8000`)

---

## Part 5 — Content expansion & SEO (June 24)

### Goal

Populate the borrower site with exhaustive EDA-backed content for borrowers, search engines, and LLM crawlers.

### New files

| File | Purpose |
|------|---------|
| `borrower_content_engine.py` | Market stats, insight pages, scenario pages, playbook |
| `content/borrower_scenarios.yaml` | 12 borrower deal stories |

### New site sections

| Section | URLs | Content |
|---------|------|---------|
| **Texas Market** | `market/texas-overview.html`, `product-availability.html`, `asset-bands.html`, `icp-banks.html` (+ paginated pages) | Live stats from 351 banks |
| **Insights** | `insights/index.html` + `i-01` … `i-12` | 12 EDA insights with borrower actions |
| **Scenarios** | `scenarios/index.html` + 12 story pages | Dallas multifamily, Houston industrial, Austin C&I, etc. |
| **Playbook** | `guides/borrower-playbook.html`, `outreach-checklist.html` | Step-by-step outreach guide |

### 12 documented insights (I-01 → I-12)

| ID | Theme | Borrower takeaway |
|----|-------|-------------------|
| I-01 | Product choice breadth | C&I/CRE = widest pools; shop broadly vs target specialists |
| I-02 | Market structure | Consumer most concentrated; CRE/C&I fragmented |
| I-03 | Deal size fit | Compare your loan size to bank median exposure |
| I-04 | Specialist targeting | ≥8% portfolio share = specialist |
| I-05 | Bank size fit | Prefer portfolio-style community banks |
| I-06 | ICP opportunity | 105 banks in $500M–$2B band |
| I-07 | Geography | HQ city ≠ branch footprint |
| I-08 | Market momentum | Ask if lender's book in your sector grew |
| I-09 | Lender diligence | Elevated past-due ratios warrant questions |
| I-10 | Bank archetypes | Filter consumer-heavy banks |
| I-11 | Cross-sell | CRE specialists often overlap C&I |
| I-12 | Outreach planning | 10–15 banks for C&I/CRE; ~19 multifamily deep specialists |

### 12 borrower scenarios

| Slug | Story |
|------|-------|
| `dallas-multifamily-bridge` | 48-unit value-add apartment bridge |
| `houston-industrial-refinance` | 120K SF warehouse refi |
| `austin-working-capital-line` | SaaS company $2M revolver |
| `waco-owner-occupied-purchase` | Manufacturer buys HQ building |
| `amarillo-farmland-expansion` | Panhandle farmland + operating line |
| `san-antonio-restaurant-acquisition` | Multi-unit restaurant buy |
| `el-paso-retail-strip-refinance` | Neighborhood strip center |
| `midland-ground-up-industrial` | Spec industrial construction |
| `tyler-medical-office-owner-occupied` | Physician group buys clinic |
| `dallas-cre-ci-bundle` | Warehouse + operating line bundle |
| `corpus-christi-hotel-refinance` | Beachfront hotel refi |
| `lubbock-equipment-fleet-finance` | Contractor equipment fleet |

### SEO enhancements

- Open Graph + Twitter Card meta tags on all pages
- `robots.txt` with sitemap pointer
- Expanded `llms.txt` + `llms-full.txt` (all 351 bank URLs)
- `data/market_insights.json` for LLM/API consumption
- JSON-LD `Article` schema on insight and market pages
- Updated navigation: Texas Market, Insights, Stories, Playbook

### Deploy (June 24)

```bash
python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
# Result: 478 S3 objects, 470 sitemap URLs
```

---

## Part 6 — Site map (live URLs)

### Entry points

| Page | URL |
|------|-----|
| Home (interactive) | http://lenni-borrower.s3-website.us-east-2.amazonaws.com/ |
| Texas market overview | …/market/texas-overview.html |
| Product availability | …/market/product-availability.html |
| ICP bank directory | …/market/icp-banks.html |
| Insights hub | …/insights/index.html |
| Scenario stories | …/scenarios/index.html |
| Borrower playbook | …/guides/borrower-playbook.html |
| Glossary | …/guides/glossary.html |
| FAQ | …/guides/faq.html |
| Methodology | …/guides/methodology.html |
| Sitemap | …/sitemap.xml |
| LLM index | …/llms.txt |

### Loan type hubs

- …/loan-types/multifamily.html
- …/loan-types/investor-cre.html
- …/loan-types/owner-occupied-cre.html
- …/loan-types/commercial-construction.html
- …/loan-types/ci-business.html
- …/loan-types/residential-14.html
- …/loan-types/ag-farmland.html

(Sub-type URLs: `loan-types/{parent}/{subtype}.html`)

### Data files (machine-readable)

| File | Contents |
|------|----------|
| `data/banks.json` | 351 enriched bank records with portfolio mix |
| `data/loan_products.json` | Full loan taxonomy from YAML |
| `data/glossary.json` | MDRM term definitions |
| `data/market_insights.json` | Market stats + insight summaries |
| `data/bank_website_enrichment.json` | Scraped website data |

---

## Part 7 — Key commands reference

### Regenerate all data & site

```bash
cd /Users/adityarajiv/Documents/ffiec-cdr
source .venv/bin/activate

# Loan extracts & EDA
python ONLY_TEXAS_SINCE_2025/extract_texas_loans.py --summary
python ONLY_TEXAS_SINCE_2025/build_lenni_eda_report.py
python ONLY_TEXAS_SINCE_2025/build_texas_loans_summary_borrower_eda.py

# Build & deploy site
python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete

# Generate documentation PDFs
python ONLY_TEXAS_SINCE_2025/build_borrower_website_guide.py
python ONLY_TEXAS_SINCE_2025/build_session_documentation.py
```

### Deal matcher API (local)

```bash
python ONLY_TEXAS_SINCE_2025/run_match_api.py
curl -X POST http://127.0.0.1:8000/api/match \
  -H 'Content-Type: application/json' \
  -d '{"text":"40-unit apartment bridge Dallas $4M","use_llm":false}'
```

### Refresh bank website enrichment

```bash
python ONLY_TEXAS_SINCE_2025/scrape_bank_websites.py
python ONLY_TEXAS_SINCE_2025/build_borrower_site.py
aws s3 sync borrower_site/ s3://lenni-borrower/ --region us-east-2 --delete
```

---

## Part 8 — Completed vs open work

### Done

- [x] FFIEC Texas data pipeline (5 quarters, 360 banks)
- [x] MDRM loan labeling and taxonomy
- [x] Lenni EDA (25 analyses + comprehensive PDF guide)
- [x] Borrower EDA workbook (12 insights)
- [x] Multi-page static borrower site (351 banks, 40 cities)
- [x] 27 loan sub-type content guides
- [x] Bank website enrichment (255 banks)
- [x] Deal matcher backend + local API + workspace UI
- [x] Content expansion (insights, scenarios, market, playbook)
- [x] SEO (sitemap, robots.txt, llms.txt, OG tags, JSON-LD)
- [x] S3 production deploy (478 objects)
- [x] Layman's website guide PDF

### Partial / in progress

| Item | Status |
|------|--------|
| Deal matcher API in production | Local only; needs cloud deploy |
| HTTPS / CloudFront | Still HTTP S3 website endpoint |
| Monday.com chat integration | Documented; not wired |
| AI terminal on site | Keyword stub; no full roadmap yet |
| SME editorial review of copy | Pending CLO review |

### Not started

- Automated CI/CD deploy pipeline
- `sync_monday_exports.py` for call recordings
- Online loan application status field research (267/360 banks — separate from FFIEC)

---

## Part 9 — File index (most important paths)

```
ffiec-cdr/
├── session.md                          ← this file
├── borrower_site/                      ← generated static site (deploy to S3)
├── institutions.csv, locations.csv     ← FDIC data (repo root)
├── texas_loan_products_mdrm_catalog.csv
├── session-notes_2026-06-*.md          ← per-session archives
└── ONLY_TEXAS_SINCE_2025/
    ├── build_borrower_site.py          ← main site builder
    ├── build_borrower_website.py       ← interactive index.html
    ├── borrower_content_engine.py      ← insights, scenarios, market pages
    ├── match_deal.py                   ← deal matching engine
    ├── bank_enrichment.py              ← website scrape merge
    ├── scrape_bank_websites.py
    ├── loan_mix.py                     ← portfolio category logic
    ├── loan_product_loader.py
    ├── content/
    │   ├── loan_products.yaml          ← loan guide editorial source
    │   └── borrower_scenarios.yaml     ← 12 scenario stories
    ├── exports/                        ← FFIEC CSV outputs (gitignored large files)
    ├── enrichment/bank_website_enrichment.json
    ├── static/match-client.js, workspace.js
    └── analysis/
        ├── Lenni_Borrower_Website_Guide.pdf
        ├── Lenni_Texas_EDA_Comprehensive_Guide.pdf
        ├── texas_loans_summary_borrower_eda.xlsx
        └── lenni_icp_prospect_list.csv
```

---

## Part 10 — Live site statistics (June 24, 2026 deploy)

| Metric | Value |
|--------|------:|
| S3 objects | 478 |
| Sitemap URLs | 470 |
| Texas banks tracked | 351 |
| ICP banks ($500M–$2B) | 105 |
| Portfolio-style commercial lenders | 129 |
| Banks with website enrichment | 255 |
| Reporting period | 12/31/2025 |
| Median bank assets | $437M |
| Median gross loans | $256M |
| Median loans/assets | 62% |

---

*Last updated: 2026-06-24*
