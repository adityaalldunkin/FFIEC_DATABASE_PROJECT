# Texas banks only (2025+)

Separate pull for **Texas (`TX`)** Call Report filings with reporting periods ending in **2025 or later**.

## Run

From project root (uses `../.env` credentials):

```bash
cd /Users/adityarajiv/Documents/ffiec-cdr
source .venv/bin/activate
python ONLY_TEXAS_SINCE_2025/pull_texas_since_2025.py
```

Test with 5 downloads:

```bash
python ONLY_TEXAS_SINCE_2025/pull_texas_since_2025.py --max 5
```

## Outputs

| Path | Description |
|------|-------------|
| `exports/texas_institutions.csv` | TX banks per quarter (from panel) |
| `exports/texas_filings.csv` | Each downloaded filing |
| `exports/texas_xbrl_facts.csv` | Parsed XBRL line items |
| `archive/call/<period>/` | Raw XBRL/PDF files |
| `data/progress.json` | Resume state (re-run skips completed) |

Upload the CSV files to Google Sheets like the main `exports/` folder.

## Note

Respects the same FFIEC rate limit (~1.5s between API calls). Full TX × all 2025+ quarters may take hours. Re-run the script to resume.
