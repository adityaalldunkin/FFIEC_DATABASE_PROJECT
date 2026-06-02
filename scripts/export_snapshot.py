#!/usr/bin/env python3
"""
Create a point-in-time snapshot for analysis without touching the live DB.

Copies data/ffiec.db → exports/snapshots/ffiec_YYYYMMDD_HHMMSS.db
then writes CSVs from that copy so backfill can keep writing to the original.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.config import DB_PATH  # noqa: E402

SNAPSHOT_DIR = ROOT / "exports" / "snapshots"


def main() -> int:
    if not DB_PATH.is_file():
        print(f"No database at {DB_PATH}. Run backfill first.")
        return 1

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_db = SNAPSHOT_DIR / f"ffiec_{stamp}.db"
    snap_csv_dir = SNAPSHOT_DIR / f"csv_{stamp}"
    snap_csv_dir.mkdir(parents=True, exist_ok=True)

    # Consistent copy while WAL may be active
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(snap_db)
    src.backup(dst)
    src.close()
    dst.close()

    print(f"Snapshot DB: {snap_db}")

    import csv as csv_mod
    import re

    def write_query(path: Path, conn: sqlite3.Connection, sql: str, params=()) -> int:
        cur = conn.execute(sql, params)
        cols = [d[0] for d in cur.description]
        n = 0
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv_mod.writer(f)
            w.writerow(cols)
            while True:
                rows = cur.fetchmany(10_000)
                if not rows:
                    break
                w.writerows(rows)
                n += len(rows)
        return n

    with sqlite3.connect(snap_db) as conn:
        conn.row_factory = sqlite3.Row
        counts = {}
        counts["institutions"] = write_query(
            snap_csv_dir / "institutions.csv",
            conn,
            "SELECT * FROM institutions ORDER BY name",
        )
        counts["filings_summary"] = write_query(
            snap_csv_dir / "filings_summary.csv",
            conn,
            """
            SELECT f.id AS filing_id, f.id_rssd, i.name AS institution_name,
                   i.state, i.city, f.reporting_period, f.facsimile_format,
                   f.retrieved_at, f.file_size
            FROM filings f
            LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
            ORDER BY f.reporting_period DESC, i.name
            """,
        )
        periods = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT reporting_period FROM filings ORDER BY reporting_period DESC"
            )
        ]
        for period in periods:
            safe = re.sub(r"[^\w\-]", "_", period.replace("/", "-"))
            write_query(
                snap_csv_dir / f"xbrl_facts_{safe}.csv",
                conn,
                """
                SELECT xf.concept, xf.value_text, xf.value_num, f.id_rssd,
                       i.name AS institution_name, f.reporting_period
                FROM xbrl_facts xf
                JOIN filings f ON f.id = xf.filing_id
                LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
                WHERE f.reporting_period = ?
                """,
                (period,),
            )

    print(f"Snapshot CSVs: {snap_csv_dir}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print("\nUse these files in Google Sheets; backfill can continue on data/ffiec.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
