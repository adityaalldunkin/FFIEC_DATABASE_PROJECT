"""Phase 5: search helpers over SQLite."""

from __future__ import annotations

import sqlite3
from typing import Any


def search_institutions(
    conn: sqlite3.Connection,
    q: str = "",
    *,
    state: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM institutions WHERE 1=1"
    params: list[Any] = []
    if q:
        sql += " AND (name LIKE ? OR CAST(id_rssd AS TEXT) LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if state:
        sql += " AND state = ?"
        params.append(state.upper())
    sql += " ORDER BY name LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def search_filings(
    conn: sqlite3.Connection,
    *,
    id_rssd: int | None = None,
    period: str | None = None,
    data_series: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = """
        SELECT f.*, i.name AS institution_name, i.state, i.city
        FROM filings f
        LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
        WHERE 1=1
    """
    params: list[Any] = []
    if id_rssd is not None:
        sql += " AND f.id_rssd = ?"
        params.append(id_rssd)
    if period:
        sql += " AND f.reporting_period = ?"
        params.append(period)
    if data_series:
        sql += " AND f.data_series = ?"
        params.append(data_series)
    sql += " ORDER BY f.retrieved_at DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_filing_detail(conn: sqlite3.Connection, filing_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT f.*, i.name AS institution_name, i.state, i.city
        FROM filings f
        LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
        WHERE f.id = ?
        """,
        (filing_id,),
    ).fetchone()
    if not row:
        return None
    detail = dict(row)
    facts = conn.execute(
        "SELECT concept, context_ref, unit_ref, value_text, value_num FROM xbrl_facts WHERE filing_id = ? LIMIT 500",
        (filing_id,),
    ).fetchall()
    detail["facts"] = [dict(f) for f in facts]
    detail["facts_total"] = conn.execute(
        "SELECT COUNT(*) AS c FROM xbrl_facts WHERE filing_id = ?", (filing_id,)
    ).fetchone()["c"]
    return detail


def search_facts_by_concept(
    conn: sqlite3.Connection,
    concept_substring: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT xf.concept, xf.value_text, xf.value_num, xf.context_ref,
               f.id_rssd, f.reporting_period, f.id AS filing_id, i.name
        FROM xbrl_facts xf
        JOIN filings f ON f.id = xf.filing_id
        LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
        WHERE xf.concept LIKE ?
        ORDER BY f.reporting_period DESC
        LIMIT ?
        """,
        (f"%{concept_substring}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def compare_periods(
    conn: sqlite3.Connection,
    id_rssd: int,
    concept_substring: str,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT f.reporting_period, xf.concept, xf.value_num, xf.value_text
        FROM xbrl_facts xf
        JOIN filings f ON f.id = xf.filing_id
        WHERE f.id_rssd = ? AND xf.concept LIKE ? AND xf.value_num IS NOT NULL
        ORDER BY f.reporting_period
        """,
        (id_rssd, f"%{concept_substring}%"),
    ).fetchall()
    return [dict(r) for r in rows]


def latest_updates(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT f.id, f.id_rssd, f.reporting_period, f.retrieved_at, f.facsimile_format,
               i.name
        FROM filings f
        LEFT JOIN institutions i ON i.id_rssd = f.id_rssd
        ORDER BY f.retrieved_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
