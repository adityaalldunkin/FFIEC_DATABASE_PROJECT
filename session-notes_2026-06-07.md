# Session Notes — FFIEC CDR / Texas Bank Data Pipeline

**Date:** 2026-06-07  
**Project:** `/Users/adityarajiv/Documents/ffiec-cdr`  
**Prior chat transcript:** [FFIEC Texas data pipeline](8af0bd34-6b61-48af-a676-fd72bbeccc7f)  
**Status at end of session:** Lenni EDA work complete; several outputs uncommitted to git

---

## Executive summary

This session built a full **FFIEC Central Data Repository (CDR) Public Web Service** pipeline in Python, pulled national Call Report data (backfill in progress at various points), created a **Texas-only extract (2025+)** with **Federal Reserve MDRM loan labeling**, and delivered **joined tables plus a 25-analysis Lenni-aligned EDA PDF** for sales / Texas Community Bank Index work.

---

## Session timeline (user requests → outcomes)

| # | Request | Outcome |
|---|---------|---------|
| 1 | Build public regulatory data platform from FFIEC PWS API (7 phases) | Full Python platform scaffolded in `ffiec-cdr/` |
| 2 | What credentials are needed? | PWS `UserID` + `Bearer` token in `.env` |
| 3 | Configure credentials & verify Phase 1 | `.env` created; Phase 1 download verified; User-Agent fix for Azure 403 |
| 4 | Can't see files in Cursor sidebar | Guided to `Cmd+Shift+E`, open `ffiec-cdr` folder |
| 5 | Status: what's done vs left? | Phase 1 done; Phases 2–7 not yet built at that point |
| 6 | Complete all phases + detailed README | Phases 1–7 implemented; root `README.md` written |
| 7 | Pull all data into CSV for Google Sheets | `backfill_all.py` + `export_csv.py`; full pull takes days |
| 8 | How to know if extraction is still running? | `backfill.log`, `pgrep`, `backfill_progress.json` |
| 9 | Agent to report progress / ETA | `backfill_status.py`, `backfill_agent.py` |
| 10 | Run all commands on agent side | Test batch (+5 filings); full backfill must run in local Terminal |
| 11 | Access data during long extraction without disturbing it | WAL mode + `export_snapshot.py`; one writer, many readers |
| 12 | Current bottleneck (brief) | API rate limit (~2,500/hr) + sequential downloads |
| 13 | How to open Terminal in Cursor | `Ctrl+` ` (backtick) or View → Terminal |
| 14 | Create `ONLY_TEXAS_SINCE_2025/` — TX banks from 2025+ | `pull_texas_since_2025.py`; 1,825 filings across 5 quarters |
| 15 | ETA for Texas pull | ~1.5s per file; resumable via `progress.json` |
| 16 | Update README + detailed data dictionary for Texas folder | `README.md`, `DATA_DICTIONARY.md`, Mermaid diagrams |
| 17 | Where are the CSV files? | `ONLY_TEXAS_SINCE_2025/exports/` |
| 18 | Not committed on GitHub | Large CSVs gitignored; SharePoint used for teammate access |
| 19 | Upload CSVs to SharePoint; link in README | SharePoint folder linked in README |
| 20 | Did we use all API calls for Texas? | 3 of 7 PWS methods — minimum for complete Call Report XBRL pull |
| 21 | Briefly explain extracted data | Institutions, filings, XBRL facts, MDRM-labeled loans |
| 22 | Where to get loan product/type info? | Schedule RC-C / MDRM codes (RCON*, not plain "loan" text) |
| 23 | Why only 3 APIs? | Other 4 are for UBPR, incremental sync, or alternate facsimile formats |
| 24 | Help extract loan types from `texas_xbrl_facts.csv` | `extract_texas_loans.py`, `LOAN_EXTRACTION_GUIDE.md` |
| 25 | Enrich with Federal Reserve MDRM dictionary | `mdrm_loader.py`, `download_mdrm.py`; labeled loan CSVs |
| 26 | Update `ONLY_TEXAS_SINCE_2025/README.md` with latest | Comprehensive README with metrics, diagrams, changelog |
| 27 | **Boss request:** joined tables + exhaustive EDA PDF (Lenni context) | `build_lenni_eda_report.py`; master joined CSV + 25-chart PDF |

---

## Part 1 — Core FFIEC platform (Phases 1–7)

### What was built

| Phase | Goal | Key files |
|-------|------|-----------|
| 1 | Prove end-to-end download | `scripts/phase1_download.py` |
| 2 | Raw archive + provenance | `src/ffiec_cdr/archive.py` → `archive/` + `.meta.json` |
| 3 | Parse XBRL → structured facts | `src/ffiec_cdr/parser.py` → `xbrl_facts` in SQLite |
| 4 | Incremental sync + checkpoint | `src/ffiec_cdr/sync.py`, `scripts/run_sync.py` |
| 5 | Search layer | `src/ffiec_cdr/search.py` |
| 6 | Public API | `src/ffiec_cdr/api.py`, `scripts/run_api.py` (FastAPI) |
| 7 | Production hardening | Retries, rate limit, SHA-256 dedup, idempotent inserts |

### Credentials

- Stored in `.env` (gitignored): `FFIEC_USER_ID`, `FFIEC_TOKEN`
- PWS account registered; token must be renewed every ~90 days
- **Security note:** Token was pasted in chat during setup — consider regenerating in [Manage My Web Service Account](https://cdr.ffiec.gov/public/)

### National data pull & monitoring

| Script | Purpose |
|--------|---------|
| `scripts/backfill_all.py` | Resumable full historical backfill (~101 quarters) |
| `scripts/export_csv.py` | SQLite → CSV in `exports/` |
| `scripts/export_snapshot.py` | Point-in-time copy for safe reads during backfill |
| `scripts/backfill_status.py` | Progress, ETA, running/stopped status |
| `scripts/backfill_agent.py` | Start backfill + periodic status updates |
| `scripts/start_extraction.sh` | Persistent launcher for local Terminal |

**Bottleneck:** FFIEC ~2,500 downloads/hour; ~1.5s spacing per request → multi-day full national pull.

**Safe concurrent access:** One writer (`backfill_all.py`); readers use snapshots or read-only queries.

---

## Part 2 — Texas-only extract (`ONLY_TEXAS_SINCE_2025/`)

### Scope

- **State:** Texas only (`State = TX` on Panel of Reporters)
- **Periods:** 2025 Q1 through 2026 Q1 (5 quarters)
- **Format:** Call Report XBRL facsimiles via FFIEC PWS

### Results

| Metric | Value |
|--------|--------|
| Reporting periods | 5 |
| Texas institutions (panel rows) | 1,825 |
| XBRL filings downloaded | 1,825 (100% of `has_filed=True`) |
| Parsed XBRL fact rows | 2,186,590 |
| Loan summary rows (MDRM-labeled) | 31,396 |
| Full loan/RC-C rows (MDRM-labeled) | 937,816 |
| MDRM loan product definitions (catalog) | 24,015 codes |

### By quarter

| Reporting period | TX banks | XBRL downloaded |
|------------------|----------|-----------------|
| 3/31/2025 | 377 | 377 |
| 6/30/2025 | 372 | 372 |
| 9/30/2025 | 364 | 364 |
| 12/31/2025 | 360 | 360 |
| 3/31/2026 | 352 | 352 |
| **Total** | **1,825** | **1,825** |

### FFIEC APIs used (3 of 7)

1. `RetrieveReportingPeriods`
2. `RetrievePanelOfReporters` (filtered to TX)
3. `RetrieveFacsimile` (XBRL)

The other four PWS methods support UBPR, incremental sync, or alternate formats — not required for a complete Texas Call Report pull.

### Key scripts

| Script | Purpose |
|--------|---------|
| `pull_texas_since_2025.py` | Download + parse Texas XBRL (resumable) |
| `extract_texas_loans.py` | Filter loan/RC-C lines; attach MDRM labels |
| `scripts/download_mdrm.py` | Fetch Federal Reserve MDRM dictionary |
| `mdrm_loader.py` | MDRM lookup module |
| `rebuild_csv_from_archive.py` | Rebuild exports from raw archive |
| `build_lenni_eda_report.py` | Join tables + generate EDA PDF |

### Core export files

| File | Rows | Notes |
|------|------|-------|
| `exports/texas_institutions.csv` | 1,825 | Bank metadata per quarter |
| `exports/texas_filings.csv` | 1,825 | Filing paths, SHA-256 |
| `exports/texas_xbrl_facts.csv` | 2,186,590 | All parsed facts (~208 MB) |
| `exports/texas_loans_summary.csv` | 31,396 | **Start here for Sheets** |
| `exports/texas_loans_labeled.csv` | 937,816 | Full RC-C detail |
| `exports/texas_loan_products_mdrm_catalog.csv` | 24,015 | Code book |

### MDRM labeling

- Source: [Federal Reserve MDRM](https://www.federalreserve.gov/apps/mdrm/) (`MDRM_CSV.csv`)
- Key codes: `RCON2122` (total loans), `RCON1480` (C&I), `RCON1545` (cards), `RCON1420` (farmland), etc.
- Values typically in **thousands of dollars** on Call Reports

### Teammate access

- **SharePoint:** [Texas FFIEC CSV files](https://cedarframe-my.sharepoint.com/:f:/g/personal/aditya_alldunkin_com/IgCVLkzsCMRsQqXAsv7Ql-A5AW2lhgQIsUy0pHp0Kv9Vkm4?e=jGFMZX)
- Large CSVs are **gitignored**; GitHub stores code/docs only
- Zip for upload: `texas_csv_exports_2025_plus.zip`

### Documentation

- `ONLY_TEXAS_SINCE_2025/README.md` — full pipeline, diagrams, troubleshooting
- `ONLY_TEXAS_SINCE_2025/DATA_DICTIONARY.md` — column-level CSV reference
- `ONLY_TEXAS_SINCE_2025/LOAN_EXTRACTION_GUIDE.md` — loan code guide
- `ONLY_TEXAS_SINCE_2025/UPLOAD_TO_SHAREPOINT.md` — upload instructions

---

## Part 3 — Lenni joined tables & EDA (final task)

### Lenni context reference

Analysis aligned with `lenni_contenxt.txt`:

- **ICP:** Texas community banks, **$500M–$2B assets**
- **Primary buyer:** Chief Lending Officer (CLO) / SVP of Lending
- **Product:** Convey by Lenni — white-labeled borrower–lender hub (digital handshake)
- **Sales model:** One bank per market; portfolio / CRE lending focus

### Joined tables (`exports/`)

| Table | Rows | Purpose |
|-------|------|---------|
| `texas_master_joined.csv` | 1,825 | Master: institution + filing + wide loan/balance-sheet metrics per bank × quarter |
| `texas_bank_profiles_latest.csv` | 360 | Latest quarter snapshot with `icp_fit` flag |
| `texas_loans_joined_long.csv` | 31,396 | Long loan lines + institution fields |

**Join keys:** `id_rssd` + `reporting_period`

### EDA outputs (`analysis/`)

| Output | Description |
|--------|-------------|
| `Lenni_Texas_Bank_EDA_Report.pdf` | **25 analyses** with charts + narrative |
| `lenni_icp_prospect_list.csv` | 105 ICP banks ranked by loan portfolio |
| `lenni_market_segments.csv` | TAM by asset segment |
| `summary_statistics_latest.csv` | Descriptive stats |
| `asset_band_counts.csv` | Asset distribution counts |
| `01_asset_distribution.png` | Sample chart from report |

### Key finding

Of **360 Texas community banks** filing in Q1 2026, **105** (29%) fall in Lenni's **$500M–$2B** ICP band. Most show commercial/portfolio lending (CRE + C&I) rather than retail mortgage focus.

**Limitation:** FFIEC data does not include online loan application presence (Lenni's "267/360 have no online app" stat comes from separate research, not this extract).

---

## Regenerate commands

```bash
cd /Users/adityarajiv/Documents/ffiec-cdr
source .venv/bin/activate

# National backfill + status
python scripts/backfill_all.py
python scripts/backfill_status.py

# Export CSVs
python scripts/export_csv.py
python scripts/export_snapshot.py   # safe snapshot during backfill

# Texas pull (if needed)
python ONLY_TEXAS_SINCE_2025/pull_texas_since_2025.py

# MDRM + loan extracts
python ONLY_TEXAS_SINCE_2025/scripts/download_mdrm.py
python ONLY_TEXAS_SINCE_2025/extract_texas_loans.py --summary

# Lenni joined tables + PDF report
python ONLY_TEXAS_SINCE_2025/build_lenni_eda_report.py
```

---

## Where the session left off

**Completed:**

- Full 7-phase FFIEC platform
- Texas 2025+ extract (1,825 filings, MDRM-labeled loans)
- Joined master tables
- Lenni-aligned EDA PDF (25 analyses)
- Detailed README + data dictionary for Texas folder
- SharePoint link for teammate CSV access

**Suggested next steps (not done in session):**

- Upload PDF + `texas_master_joined.csv` to SharePoint for teammates
- Git commit/push of new scripts and docs (CSVs remain gitignored)
- Continue national `backfill_all.py` in local Terminal if full US history is still needed

---

## Uncommitted local work (git status snapshot)

| Path | Notes |
|------|-------|
| `ONLY_TEXAS_SINCE_2025/build_lenni_eda_report.py` | New — EDA report generator |
| `ONLY_TEXAS_SINCE_2025/analysis/*` | PDF, charts, prospect lists |
| `ONLY_TEXAS_SINCE_2025/README.md` | Updated with Lenni EDA section |
| `requirements.txt` | Added pandas, matplotlib, numpy |
| `lenni_contenxt.txt` | Lenni brand/market reference (untracked) |
| `.mplconfig/fontlist-v390.json` | Matplotlib cache (typically not committed) |

---

## Project structure (high level)

```
ffiec-cdr/
├── README.md                          # Full 7-phase platform docs
├── lenni_contenxt.txt                 # Lenni ICP / brand context
├── session-notes_2026-06-07.md        # This file
├── src/ffiec_cdr/                     # Core library (client, parser, sync, API)
├── scripts/                           # National backfill, export, status agents
├── data/ffiec.db                      # National SQLite DB
├── exports/                           # National CSV exports
├── archive/                           # Raw national XBRL
└── ONLY_TEXAS_SINCE_2025/
    ├── pull_texas_since_2025.py
    ├── extract_texas_loans.py
    ├── build_lenni_eda_report.py
    ├── README.md
    ├── DATA_DICTIONARY.md
    ├── exports/                       # Texas CSVs + joined tables
    ├── analysis/                      # Lenni EDA PDF + supporting CSVs
    └── archive/call/                  # Raw Texas XBRL by quarter
```

---

## References

- [FFIEC CDR Public Data Distribution](https://cdr.ffiec.gov/public/)
- [Manage Facsimiles (manual UI)](https://cdr.ffiec.gov/public/ManageFacsimiles.aspx)
- [PWS API spec (SIS611)](https://cdr.ffiec.gov/public/Files/SIS611_-_Retrieve_Public_Data_via_Web_Service.pdf)
- [Federal Reserve MDRM dictionary](https://www.federalreserve.gov/apps/mdrm/)
