# FFIEC CDR Public Regulatory Data Platform

A Python platform that pulls **Call Report** and **UBPR** public filings from the [FFIEC Central Data Repository](https://cdr.ffiec.gov/public/) via the official **Public Web Service (PWS)** REST API, archives raw files, parses XBRL into searchable tables, syncs incrementally, and exposes a local search API.

The manual site [Manage Facsimiles](https://cdr.ffiec.gov/public/ManageFacsimiles.aspx) is the browser UI for the same data. This project automates retrieval through the API documented in [CDR-PDD-SIS-611](https://cdr.ffiec.gov/public/Files/SIS611_-_Retrieve_Public_Data_via_Web_Service.pdf).

---

## Table of contents

1. [What was built (all 7 phases)](#what-was-built-all-7-phases)
2. [Step-by-step: how each phase works](#step-by-step-how-each-phase-works)
3. [Project structure](#project-structure)
4. [Prerequisites and credentials](#prerequisites-and-credentials)
5. [Installation](#installation)
6. [Running the pipeline](#running-the-pipeline)
7. [REST API (your platform)](#rest-api-your-platform)
8. [Configuration](#configuration)
9. [Production notes and limits](#production-notes-and-limits)
10. [References](#references)

---

## What was built (all 7 phases)

| Phase | Goal | Status | Implementation |
|-------|------|--------|----------------|
| **1** | Prove end-to-end download | Done | `scripts/phase1_download.py` |
| **2** | Raw archive + provenance | Done | `src/ffiec_cdr/archive.py` → `archive/` + `.meta.json` |
| **3** | Parse XBRL → structured facts | Done | `src/ffiec_cdr/parser.py` → `xbrl_facts` table |
| **4** | Incremental sync + checkpoint | Done | `src/ffiec_cdr/sync.py`, `scripts/run_sync.py` |
| **5** | Search layer | Done | `src/ffiec_cdr/search.py` (SQLite queries) |
| **6** | Public API | Done | `src/ffiec_cdr/api.py`, `scripts/run_api.py` (FastAPI) |
| **7** | Production hardening | Done | Retries, rate limit, SHA-256 dedup, logging, idempotent inserts |

---

## Step-by-step: how each phase works

### Phase 1 — One successful download

**Purpose:** Confirm credentials and API connectivity.

**Steps the script runs:**

1. Load `FFIEC_USER_ID` and `FFIEC_TOKEN` from `.env`.
2. Call `RetrieveReportingPeriods` → list of quarter-end dates (newest first).
3. Call `RetrievePanelOfReporters` for the latest period → banks + `HasFiledForReportingPeriod`.
4. Pick the first institution that has filed.
5. Call `RetrieveFacsimile` (default **XBRL**).
6. Save via Phase 2 archive and record in SQLite (Phases 2–3).

**Run:**

```bash
source .venv/bin/activate
python scripts/phase1_download.py
```

**Success:** A file under `archive/call/<period>/` and rows in `data/ffiec.db`.

---

### Phase 2 — Raw archive

**Purpose:** Keep the source exactly as received, with full traceability.

**For every download, the platform stores:**

| Artifact | Location | Contents |
|----------|----------|----------|
| Raw file | `archive/call/<period>/<rssd>.xbrl` (or `.pdf`, `.txt`) | Exact API bytes |
| Metadata | Same path + `.meta.json` | Endpoint, request params, timestamp, SHA-256, size |

**Module:** `src/ffiec_cdr/archive.py`

**Database table:** `filings` — links institution, period, path, checksum, request JSON.

---

### Phase 3 — Parse into structured tables

**Purpose:** Turn XBRL filings into queryable facts while keeping the original file.

**Module:** `src/ffiec_cdr/parser.py`

**Process:**

1. Parse XML with `lxml` (inline XBRL and standard instance documents).
2. Extract elements with values and `contextRef` / `unitRef`.
3. Store in `xbrl_facts`: `concept`, `context_ref`, `unit_ref`, `value_text`, `value_num`.

**Note:** Full Call Report taxonomy mapping is domain-heavy; this implementation extracts **all discoverable facts** (up to 50,000 per filing) for search and comparison. You can extend the parser for specific MDRM line items later.

---

### Phase 4 — Sync engine

**Purpose:** Update regularly without re-downloading everything.

**Module:** `src/ffiec_cdr/sync.py`

**Operational loop:**

1. Load checkpoint from `sync_checkpoints` (per data series + period), or default `01/01/2000`.
2. Refresh institution rows from `RetrievePanelOfReporters`.
3. Call `RetrieveFilersSinceDate` with `lastUpdateDateTime` = checkpoint.
4. For each new RSSD (up to `FFIEC_MAX_DOWNLOADS_PER_RUN`):
   - Download facsimile → archive (Phase 2)
   - Skip if SHA-256 already in DB (idempotent)
   - Parse XBRL if new (Phase 3)
5. Advance checkpoint to current date.

**Run:**

```bash
python scripts/init_db.py          # once
python scripts/run_sync.py         # default: latest period, max 10 downloads
python scripts/run_sync.py --period "3/31/2025" --max-downloads 5
```

**Scheduling (production):** Use cron or APScheduler, e.g. daily:

```cron
0 6 * * * cd /path/to/ffiec-cdr && .venv/bin/python scripts/run_sync.py
```

---

### Phase 5 — Search layer

**Purpose:** Query institutions, filings, and financial concepts.

**Module:** `src/ffiec_cdr/search.py`

**Capabilities:**

- Search institutions by name, RSSD, state
- Search filings by period, RSSD, data series
- Search facts by concept substring (e.g. `Assets`, `RIAD`)
- Compare a concept across reporting periods for one bank
- List latest ingested filings

Backed by **SQLite** at `data/ffiec.db` (upgrade path: set `DATABASE_URL` for PostgreSQL in a future revision).

---

### Phase 6 — Your public API

**Purpose:** HTTP access for apps and LLM tools.

**Module:** `src/ffiec_cdr/api.py` (FastAPI)

**Start server:**

```bash
python scripts/run_api.py
# Open http://127.0.0.1:8000/docs for interactive Swagger UI
```

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `GET /institutions/search?q=&state=` | Find banks |
| `GET /filings/search?id_rssd=&period=` | List filings |
| `GET /filings/{id}` | Filing detail + sample facts |
| `GET /filings/{id}/download` | Download original archived file |
| `GET /facts/search?concept=` | Facts matching concept name |
| `GET /institutions/{id_rssd}/compare?concept=` | Metric across periods |
| `GET /updates/latest` | Recently ingested filings |

---

### Phase 7 — Production hardening

**Built into the client and sync path:**

| Feature | Where |
|---------|--------|
| **Retries** | `tenacity` on API GETs (3 attempts, exponential backoff) |
| **Rate limiting** | 1.5s delay between requests (`FFIEC_REQUEST_DELAY_SEC`) |
| **Hourly cap awareness** | Handles HTTP 429; sync respects `FFIEC_MAX_DOWNLOADS_PER_RUN` |
| **Logging** | `logging` in sync script and client |
| **Checksum validation** | SHA-256 on every file; stored in DB and metadata |
| **Idempotent re-runs** | `INSERT OR IGNORE` on `(rssd, period, format, sha256)` |
| **Version tracking** | `filings.version` column reserved; new SHA = new row |
| **Sync audit** | `sync_runs` table with counts and errors |

---

## Project structure

```
ffiec-cdr/
├── README.md                 # This file
├── requirements.txt
├── .env.example
├── .env                      # Your credentials (not in git)
├── archive/                  # Phase 2 raw files + .meta.json
│   └── call/<period>/
├── data/
│   └── ffiec.db              # SQLite: institutions, filings, facts, checkpoints
├── scripts/
│   ├── phase1_download.py    # Phase 1 smoke test
│   ├── init_db.py            # Create schema
│   ├── run_sync.py           # Phase 4 incremental sync
│   └── run_api.py            # Phase 6 API server
└── src/ffiec_cdr/
    ├── client.py             # All 7 FFIEC API methods
    ├── archive.py            # Phase 2
    ├── parser.py             # Phase 3
    ├── sync.py               # Phase 4
    ├── search.py             # Phase 5
    ├── api.py                # Phase 6
    ├── db.py                 # Schema + helpers
    └── config.py             # Paths and env defaults
```

---

## Prerequisites and credentials

1. Register at [FFIEC CDR](https://cdr.ffiec.gov/public/) → **Manage My Web Service Account**.
2. You receive **Username** and **Security Token** by email.
3. Copy `.env.example` → `.env`:

```env
FFIEC_USER_ID=your_username
FFIEC_TOKEN=eyJ...   # token only, no "Bearer" prefix
```

Renew the token at least every **90 days**. Inactive accounts are removed after ~1 year.

---

## Installation

```bash
cd ffiec-cdr
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit with your credentials
python scripts/init_db.py
```

---

## Pull all data + export CSV (Google Sheets)

**Full download** (101 quarters × thousands of banks — runs many hours; resumable):

```bash
# Runs in foreground (or use nohup ... & for background)
python scripts/backfill_all.py

# Watch progress
tail -f data/backfill.log
```

**Export to CSV** (after any downloads):

```bash
python scripts/export_csv.py
```

Files appear in `exports/`:

| File | Use in Google Sheets |
|------|----------------------|
| `filings_summary.csv` | **Start here** — one row per filing + bank name |
| `institutions.csv` | All banks |
| `filings.csv` | Filing metadata |
| `xbrl_facts_latest.csv` | Line items for the newest quarter only |
| `xbrl_facts/xbrl_facts_*.csv` | One file per quarter (import separately if large) |

Upload: Google Drive → New → File upload → Open with Google Sheets.

Re-run `export_csv.py` after backfill progresses to refresh CSVs.

---

## Monitor extraction (progress + ETA)

A small **monitor agent** reports how much is done, what is left, and estimated time remaining.

**One-shot status:**

```bash
python scripts/backfill_status.py
```

**Short one-liner** (good for scripts):

```bash
python scripts/backfill_status.py --short
# [RUNNING] 2.4% | 8,432/350,000 filings | quarters 2/101 | ETA 18d
```

**Start backfill + live updates every 60 seconds:**

```bash
python scripts/backfill_agent.py
```

Options:

| Command | What it does |
|---------|----------------|
| `python scripts/backfill_agent.py` | Starts backfill if stopped, prints full report every 60s |
| `python scripts/backfill_agent.py --interval 30` | Update every 30 seconds |
| `python scripts/backfill_agent.py --monitor-only` | Only watch; do not start backfill |
| `python scripts/backfill_agent.py --once` | Print once and exit |

Press `Ctrl+C` to stop the monitor; the backfill keeps running in the background.

Progress is stored in `data/backfill_progress.json`. Logs: `data/backfill.log`.

### Use data while backfill runs (do not disturb extraction)

| Safe | Avoid |
|------|--------|
| `python scripts/backfill_status.py` | Starting a **second** `backfill_all.py` |
| `python scripts/export_csv.py` | Deleting `data/ffiec.db` or `archive/` |
| `python scripts/export_snapshot.py` | Editing the database by hand |
| `python scripts/run_api.py` (read-only queries) | Moving/renaming files under `archive/` |
| Open CSVs from `exports/` in Google Sheets | Running `phase1_download.py` at the same time |

**Best practice for Google Sheets:** run a **snapshot** export (copies DB, then CSV) so Sheets never locks the live DB:

```bash
python scripts/export_snapshot.py
# Upload exports/snapshots/csv_YYYYMMDD_HHMMSS/*.csv
```

Re-run snapshot anytime for a fresher cut; backfill keeps writing to `data/ffiec.db`.

SQLite **WAL mode** is enabled so reads and the backfill writer can coexist.

---

## Running the pipeline

**Recommended order for a new setup:**

```bash
# 1. Prove API + archive + parse (one bank)
python scripts/phase1_download.py

# 2. Incremental sync (more banks, respects rate limit)
python scripts/run_sync.py --max-downloads 10

# 3. Search API
python scripts/run_api.py
```

**Example API calls after ingest:**

```bash
curl "http://127.0.0.1:8000/institutions/search?q=bank&limit=5"
curl "http://127.0.0.1:8000/filings/search?period=3/31/2025"
curl "http://127.0.0.1:8000/facts/search?concept=Assets&limit=10"
curl "http://127.0.0.1:8000/updates/latest"
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FFIEC_USER_ID` | — | PWS username |
| `FFIEC_TOKEN` | — | PWS bearer token |
| `FFIEC_FACSIMILE_FORMAT` | `XBRL` | `XBRL`, `PDF`, or `SDF` |
| `FFIEC_REQUEST_DELAY_SEC` | `1.5` | Delay between API calls |
| `FFIEC_MAX_DOWNLOADS_PER_RUN` | `10` | Cap per sync run (avoid hourly 2500 limit) |

---

## Production notes and limits

- FFIEC allows ~**2500 downloads per hour** — keep `FFIEC_REQUEST_DELAY_SEC=1.5` for bulk jobs.
- Use **`RetrieveFilersSinceDate`** (implemented) for incremental updates, not full re-downloads.
- **`RetrieveFilersSubmissionDateTime`** is implemented in the client for submission timestamps.
- UBPR: use `client.retrieve_ubpr_reporting_periods()` and `retrieve_ubpr_xbrl_facsimile()`; extend `run_sync.py` similarly for UBPR series.
- For large production deployments: move `data/ffiec.db` to PostgreSQL, store `archive/` on S3, run sync on Airflow, add monitoring on `sync_runs.errors`.

---

## References

- [PWS help](https://cdr.ffiec.gov/public/HelpFiles/PWSInfo.htm)
- [SIS611 API specification (PDF)](https://cdr.ffiec.gov/public/Files/SIS611_-_Retrieve_Public_Data_via_Web_Service.pdf)
- [Manage Facsimiles (manual UI)](https://cdr.ffiec.gov/public/ManageFacsimiles.aspx)
- API base URL: `https://ffieccdr.azure-api.us/public/`
