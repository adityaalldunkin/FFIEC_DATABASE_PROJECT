# Data Dictionary — Texas Call Reports (2025+)

This document describes every column in the three CSV files produced by `ONLY_TEXAS_SINCE_2025/`. It applies **only** to this Texas subset, not the national `ffiec-cdr` database.

**Source system:** [FFIEC Central Data Repository (CDR)](https://cdr.ffiec.gov/public/) Public Web Service (PWS), Call Report data series.

**Geographic filter:** `State = TX` (Texas).

**Time filter:** Reporting period end date in calendar year **2025 or later** (includes quarters ending in 2025 and 2026, e.g. `3/31/2026`).

---

## File overview

| File | Grain | Typical row count (full run) | Primary use |
|------|-------|------------------------------|-------------|
| `texas_institutions.csv` | One row per **bank × reporting period** (panel) | ~1,800 | Who must file; filed or not |
| `texas_filings.csv` | One row per **downloaded filing** | ~3,600 | Filing inventory & file locations |
| `texas_xbrl_facts.csv` | One row per **XBRL fact** (line item) | ~1M+ | Financial values & concepts |

**Join keys:** `id_rssd` + `reporting_period` link all three files.

---

## 1. `texas_institutions.csv`

### Purpose

Lists every **Texas institution on the FFIEC Panel of Reporters** for each included reporting period. This comes from the API method `RetrievePanelOfReporters`, not from the XBRL file itself.

A bank appears **once per quarter** even if you did not download its facsimile.

### Columns

| Column | Data type | Required | Description |
|--------|-----------|----------|-------------|
| **id_rssd** | Integer | Yes | **RSSD ID** — Federal Reserve’s unique identifier for the institution. Stable across time. Use as primary key with `reporting_period`. Example: `480228`. |
| **name** | Text | Yes | Legal or reporting name from FFIEC panel (may include trailing spaces in raw API; trimmed in script). Example: `JPMORGAN CHASE BANK, NATIONAL ASSOCIATION`. |
| **state** | Text (2 chars) | Yes | State code from panel. Always **`TX`** for this dataset (filter applied in extraction). |
| **city** | Text | Yes | City from panel address. May have trailing spaces. Example: `DALLAS`. |
| **filing_type** | Text / numeric | Yes | FFIEC **Call Report form type** code (e.g. `051` = commercial bank FFIEC 031, `041` = smaller bank FFIEC 041). Defines which report template the bank files. |
| **reporting_period** | Text | Yes | Quarter **end date** in `MM/DD/YYYY` format. Example: `6/30/2025` = Q2 2025. |
| **has_filed** | Boolean | Yes | **`True`** if FFIEC marks the institution as having submitted for this period; **`False`** if expected but not yet filed. Only `True` rows are downloaded into `texas_filings.csv`. |

### Example row

```csv
id_rssd,name,state,city,filing_type,reporting_period,has_filed
488653,"NATIONAL BANK OF ANDREWS, THE",TX,ANDREWS,051,3/31/2026,True
```

### Notes

- **Not all panel rows have a filing download** — use `has_filed` before expecting rows in `texas_filings.csv`.
- The same `id_rssd` appears on **multiple rows** (one per `reporting_period`).
- Institution count per quarter varies (~352–372 Texas banks in recent panels).

---

## 2. `texas_filings.csv`

### Purpose

One row for each **Call Report facsimile** successfully downloaded from `RetrieveFacsimile` (default format **XBRL**). This is your filing manifest: what was retrieved, when, where stored, and integrity hash.

### Columns

| Column | Data type | Required | Description |
|--------|-----------|----------|-------------|
| **id_rssd** | Integer | Yes | Institution RSSD ID. Join to `texas_institutions.id_rssd`. |
| **institution_name** | Text | Yes | Bank name at time of download (from panel). |
| **state** | Text | Yes | Always **`TX`** for this extract. |
| **city** | Text | Optional | City from panel; may be empty if rebuilt from archive only. |
| **reporting_period** | Text | Yes | Quarter end date `MM/DD/YYYY`. |
| **facsimile_format** | Text | Yes | Format requested from FFIEC: **`XBRL`** (default), or `PDF`, `SDF` if you used `--format`. |
| **retrieved_at** | ISO 8601 datetime (UTC) | Yes | When this run downloaded the file. Example: `2026-06-03T03:30:48.174808+00:00`. Same timestamp may appear on many rows from one batch. |
| **file_path** | Text (absolute path) | Yes | Location of raw file on disk under `ONLY_TEXAS_SINCE_2025/archive/call/<period>/`. Example: `.../archive/call/9-30-2025/623052.xbrl`. |
| **sha256** | Text (64 hex chars) | Yes | SHA-256 hash of raw file bytes for integrity and deduplication. |
| **file_size_bytes** | Integer | Yes | Size of downloaded file in bytes. Typical XBRL Call Report: ~50KB–500KB. |

### Example row

```csv
id_rssd,institution_name,state,city,reporting_period,facsimile_format,retrieved_at,file_path,sha256,file_size_bytes
623052,"LAMESA NATIONAL BANK, THE",TX,LAMESA,9/30/2025,XBRL,2026-06-03T03:30:48+00:00,.../623052.xbrl,e706acc1...,59080
```

### Cardinality

- At most **one XBRL row per (`id_rssd`, `reporting_period`)** per successful download.
- Full Texas 2025+ run: on the order of **~3,500–3,700** filings across five quarters (only banks with `has_filed=True`).

### Important: CSV vs archive

If you **stopped and restarted** `pull_texas_since_2025.py`, the CSV may list only filings from the **last run** (the script opens CSVs with write mode). The **archive** folder is complete. Rebuild CSVs with:

```bash
python ONLY_TEXAS_SINCE_2025/rebuild_csv_from_archive.py
```

---

## 3. `texas_xbrl_facts.csv`

### Purpose

**Normalized fact table** extracted from each XBRL instance document. Each row is one reported value (or text disclosure) with its XBRL concept and context.

This is the largest file and is the basis for financial analysis in Excel / Google Sheets / databases.

### Columns

| Column | Data type | Required | Description |
|--------|-----------|----------|-------------|
| **id_rssd** | Integer | Yes | Institution RSSD ID. |
| **institution_name** | Text | Yes | Bank name (denormalized for convenience). |
| **reporting_period** | Text | Yes | Quarter end `MM/DD/YYYY`. |
| **concept** | Text | Yes | XBRL element identifier. Often a local name (e.g. `RCFD2170`) or full QName in braces, e.g. `{http://www.fdic.gov/xbrl/us-gaap/...}Assets`. Maps to Call Report line items via FFIEC taxonomy. |
| **context_ref** | Text | Optional | XBRL **context** id (e.g. `c-1`, `I2025Q3`). Defines period, entity, and scenario (instant vs duration). Required to interpret `value_num` correctly when multiple contexts exist. |
| **unit_ref** | Text | Optional | XBRL **unit** id (e.g. `UUSD`, `UShares`). Indicates currency, shares, pure number, etc. |
| **value_text** | Text | Optional | Fact value as string (up to 2,000 characters). Used for text blocks and numeric values before parsing. |
| **value_num** | Float | Optional | Numeric parsing of `value_text` (commas stripped). **`NULL`/empty** if value is non-numeric or text-only disclosure. |

### Example rows

```csv
id_rssd,institution_name,reporting_period,concept,context_ref,unit_ref,value_text,value_num
623052,LAMESA NATIONAL BANK,9/30/2025,RCFD2170,c-5,UUSD,1250000,1250000.0
623052,LAMESA NATIONAL BANK,9/30/2025,dei:EntityRegistrantName,c-1,,LAMESA NATIONAL BANK,
```

### How facts are produced

1. Download XBRL XML from FFIEC.
2. Parse with `lxml` (`ffiec_cdr.parser.parse_xbrl`).
3. Walk XML tree; capture elements with non-empty text and optional `contextRef` / `unitRef`.
4. Deduplicate identical (`concept`, `context_ref`, value prefix) tuples within a filing.
5. Cap at **50,000 facts per filing** (safety limit).

### Typical volume

- **~800–1,200 facts per bank per quarter** (varies by size and form type).
- Full Texas extract: **~1–1.5 million rows**.

### Analysis tips

| Task | Suggestion |
|------|------------|
| Find total assets | Filter `concept` containing `Assets` or known MDRM (e.g. `RCFD2170` for many banks). |
| Compare quarters | Filter same `id_rssd`, different `reporting_period`. |
| Sheets performance | Filter one `reporting_period` or one `id_rssd` at a time; full file is very large. |
| Correct period | Use `context_ref` with FFIEC taxonomy docs on [CDR taxonomy page](https://cdr.ffiec.gov/public/). |

### Limitations

- Not every concept is mapped to a human-readable line name in this CSV — you see **technical XBRL names**.
- Facts include **metadata/dei** (entity name, CIK) mixed with **financial** facts.
- **Restated/amended** filings may appear as a new download with a new `sha256` if FFIEC republishes.

---

## Reporting periods in this extract

| `reporting_period` | Quarter | Calendar year |
|--------------------|---------|-----------------|
| `3/31/2025` | Q1 | 2025 |
| `6/30/2025` | Q2 | 2025 |
| `9/30/2025` | Q3 | 2025 |
| `12/31/2025` | Q4 | 2025 |
| `3/31/2026` | Q1 | 2026 |

---

## Entity-relationship (logical)

```text
texas_institutions (id_rssd, reporting_period)
        │
        │  has_filed = True
        ▼
texas_filings (id_rssd, reporting_period) ──► archive/.../id_rssd.xbrl
        │
        │  1 : many
        ▼
texas_xbrl_facts (id_rssd, reporting_period, concept, context_ref)
```

---

## Data quality & provenance

| Item | Detail |
|------|--------|
| **Authority** | FFIEC CDR public distribution (regulatory filing). |
| **API spec** | [CDR-PDD-SIS-611](https://cdr.ffiec.gov/public/Files/SIS611_-_Retrieve_Public_Data_via_Web_Service.pdf) |
| **Authentication** | PWS `UserID` + Bearer token (`../.env`) |
| **Rate limit** | ~2,500 requests/hour; script uses ~1.5s delay between calls |
| **Integrity** | `sha256` on each file; `progress.json` tracks completed (`period\|rssd`) pairs |

---

## Related files (not CSV)

| Path | Description |
|------|-------------|
| `archive/call/<period>/<rssd>.xbrl` | Raw regulatory filing |
| `archive/call/<period>/<rssd>.xbrl.meta.json` | `id_rssd`, `period`, `format`, `sha256`, `retrieved_at` |
| `data/progress.json` | Resume checkpoint list |
| `data/pull.log` | Extraction log |

---

*Generated for project `ONLY_TEXAS_SINCE_2025`. For questions about Call Report line codes, refer to FFIEC Call Report instruction books and XBRL taxonomy for the reporting period.*
