"""SQLite persistence for archive metadata, filings, facts, and sync state."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterator

from ffiec_cdr.config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS institutions (
    id_rssd INTEGER PRIMARY KEY,
    name TEXT,
    state TEXT,
    city TEXT,
    filing_type TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS filings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_rssd INTEGER NOT NULL,
    data_series TEXT NOT NULL,
    reporting_period TEXT NOT NULL,
    facsimile_format TEXT NOT NULL,
    source_endpoint TEXT NOT NULL,
    request_params TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    file_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(id_rssd, data_series, reporting_period, facsimile_format, sha256),
    FOREIGN KEY (id_rssd) REFERENCES institutions(id_rssd)
);

CREATE TABLE IF NOT EXISTS xbrl_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id INTEGER NOT NULL,
    concept TEXT NOT NULL,
    context_ref TEXT,
    unit_ref TEXT,
    value_text TEXT,
    value_num REAL,
    FOREIGN KEY (filing_id) REFERENCES filings(id)
);

CREATE INDEX IF NOT EXISTS idx_filings_period ON filings(reporting_period);
CREATE INDEX IF NOT EXISTS idx_filings_rssd ON filings(id_rssd);
CREATE INDEX IF NOT EXISTS idx_facts_filing ON xbrl_facts(filing_id);
CREATE INDEX IF NOT EXISTS idx_facts_concept ON xbrl_facts(concept);
CREATE INDEX IF NOT EXISTS idx_institutions_name ON institutions(name);

CREATE TABLE IF NOT EXISTS sync_checkpoints (
    data_series TEXT NOT NULL,
    reporting_period TEXT NOT NULL,
    last_update_datetime TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (data_series, reporting_period)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    periods_processed INTEGER DEFAULT 0,
    filings_downloaded INTEGER DEFAULT 0,
    filings_skipped INTEGER DEFAULT 0,
    errors TEXT
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    ensure_dirs()
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Allow readers (export, API, Sheets) while backfill writes.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_institution(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO institutions (id_rssd, name, state, city, filing_type, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_rssd) DO UPDATE SET
            name=excluded.name,
            state=excluded.state,
            city=excluded.city,
            filing_type=excluded.filing_type,
            updated_at=excluded.updated_at
        """,
        (
            row.get("ID_RSSD"),
            (row.get("Name") or "").strip(),
            row.get("State"),
            row.get("City"),
            str(row.get("FilingType", "")),
            utc_now(),
        ),
    )


def insert_filing(
    conn: sqlite3.Connection,
    *,
    id_rssd: int,
    data_series: str,
    reporting_period: str,
    facsimile_format: str,
    source_endpoint: str,
    request_params: dict[str, Any],
    file_path: str,
    sha256: str,
    file_size: int,
) -> int | None:
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO filings (
            id_rssd, data_series, reporting_period, facsimile_format,
            source_endpoint, request_params, retrieved_at, file_path, sha256, file_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            id_rssd,
            data_series,
            reporting_period,
            facsimile_format,
            source_endpoint,
            json.dumps(request_params),
            utc_now(),
            file_path,
            sha256,
            file_size,
        ),
    )
    if cur.rowcount == 0:
        return None
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def filing_exists(conn: sqlite3.Connection, sha256: str) -> bool:
    row = conn.execute("SELECT 1 FROM filings WHERE sha256 = ?", (sha256,)).fetchone()
    return row is not None


def insert_facts(conn: sqlite3.Connection, filing_id: int, facts: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO xbrl_facts (filing_id, concept, context_ref, unit_ref, value_text, value_num)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                filing_id,
                f["concept"],
                f.get("context_ref"),
                f.get("unit_ref"),
                f.get("value_text"),
                f.get("value_num"),
            )
            for f in facts
        ],
    )


def get_checkpoint(conn: sqlite3.Connection, data_series: str, period: str) -> str | None:
    row = conn.execute(
        "SELECT last_update_datetime FROM sync_checkpoints WHERE data_series=? AND reporting_period=?",
        (data_series, period),
    ).fetchone()
    return row["last_update_datetime"] if row else None


def set_checkpoint(conn: sqlite3.Connection, data_series: str, period: str, dt: str) -> None:
    conn.execute(
        """
        INSERT INTO sync_checkpoints (data_series, reporting_period, last_update_datetime, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(data_series, reporting_period) DO UPDATE SET
            last_update_datetime=excluded.last_update_datetime,
            updated_at=excluded.updated_at
        """,
        (data_series, period, dt, utc_now()),
    )
