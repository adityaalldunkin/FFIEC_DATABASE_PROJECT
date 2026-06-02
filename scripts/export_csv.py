#!/usr/bin/env python3
"""
Export SQLite data to CSV files for Google Sheets.

Outputs in exports/:
  institutions.csv       — all banks
  filings.csv            — one row per downloaded filing
  filings_summary.csv    — filings + institution (best for Sheets overview)
  xbrl_facts/            — facts split by reporting period (large tables)
  xbrl_facts_latest.csv  — facts for most recent period only (single file)
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.config import DB_PATH, ROOT as PROJECT_ROOT  # noqa: E402

EXPORT_DIR = PROJECT_ROOT / "exports"
FACTS_DIR = EXPORT_DIR / "xbrl_facts"

# Google Sheets: keep single CSV under ~50MB when possible; split by period if larger
MAX_ROWS_PER_FACTS_FILE = 500_000


def _safe_name(period: str) -> str:
    return re.sub(r"[^\w\-]", "_", period.replace("/", "-"))


def _write_query(path: Path, conn: sqlite3.Connection, sql: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        while True:
            rows = cur.fetchmany(10_000)
            if not rows:
                break
            writer.writerows(rows)
            count += len(rows)
    return count


def export_all(db_path: Path | None = None) -> dict[str, int | str]:
    db = db_path or DB_PATH
    if not db.is_file():
        raise SystemExit(f"Database not found: {db}. Run backfill or phase1 first.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    FACTS_DIR.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int | str] = {}

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row

        counts["institutions"] = _write_query(
            EXPORT_DIR / "institutions.csv",
            conn,
            "SELECT id_rssd, name, state, city, filing_type, updated_at FROM institutions ORDER BY name",
        )

        counts["filings"] = _write_query(
            EXPORT_DIR / "filings.csv",
            conn,
            """
            SELECT id, id_rssd, data_series, reporting_period, facsimile_format,
                   retrieved_at, file_path, sha256, file_size
            FROM filings ORDER BY reporting_period DESC, id_rssd
            """,
        )

        counts["filings_summary"] = _write_query(
            EXPORT_DIR / "filings_summary.csv",
            conn,
            """
            SELECT
                f.id AS filing_id,
                f.id_rssd,
                i.name AS institution_name,
                i.state,
                i.city,
                f.reporting_period,
                f.facsimile_format,
                f.retrieved_at,
                f.file_size,
                f.sha256
            FROM filings f
            LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
            ORDER BY f.reporting_period DESC, i.name
            """,
        )

        periods = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT reporting_period FROM filings ORDER BY reporting_period DESC"
            ).fetchall()
        ]

        facts_total = 0
        for period in periods:
            safe = _safe_name(period)
            out = FACTS_DIR / f"xbrl_facts_{safe}.csv"
            out.parent.mkdir(parents=True, exist_ok=True)
            cur = conn.execute(
                """
                SELECT
                    xf.id,
                    f.id AS filing_id,
                    f.id_rssd,
                    i.name AS institution_name,
                    f.reporting_period,
                    xf.concept,
                    xf.context_ref,
                    xf.unit_ref,
                    xf.value_text,
                    xf.value_num
                FROM xbrl_facts xf
                JOIN filings f ON f.id = xf.filing_id
                LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
                WHERE f.reporting_period = ?
                ORDER BY f.id_rssd, xf.concept
                """,
                (period,),
            )
            cols = [d[0] for d in cur.description]
            n = 0
            with out.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                while True:
                    rows = cur.fetchmany(10_000)
                    if not rows:
                        break
                    writer.writerows(rows)
                    n += len(rows)
            facts_total += n
            counts[f"facts_{safe}"] = n

        counts["xbrl_facts_total_rows"] = facts_total

        if periods:
            latest = periods[0]
            latest_safe = _safe_name(latest)
            src = FACTS_DIR / f"xbrl_facts_{latest_safe}.csv"
            dest = EXPORT_DIR / "xbrl_facts_latest.csv"
            if src.is_file():
                dest.write_bytes(src.read_bytes())
                counts["xbrl_facts_latest"] = f"{latest} ({src.stat().st_size // 1024} KB)"

    readme = EXPORT_DIR / "README.txt"
    readme.write_text(
        """FFIEC CSV exports for Google Sheets
====================================

Upload these files to Google Drive → Open with Google Sheets:

1. filings_summary.csv   — Start here (one row per filing + bank name)
2. institutions.csv      — All banks in the database
3. filings.csv           — Filing metadata
4. xbrl_facts/           — Detailed line items, one CSV per quarter
5. xbrl_facts_latest.csv — Most recent quarter only (smaller file)

Note: Full historical facts can be very large. Import one xbrl_facts_*.csv at a time.

Re-run after more data is downloaded:
  python scripts/export_csv.py
""",
        encoding="utf-8",
    )
    counts["export_dir"] = str(EXPORT_DIR)
    return counts


if __name__ == "__main__":
    result = export_all()
    print("Exported to", result.pop("export_dir"))
    for k, v in sorted(result.items()):
        print(f"  {k}: {v}")
