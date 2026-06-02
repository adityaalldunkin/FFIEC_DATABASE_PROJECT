"""Download all available Call Report XBRL filings (resumable)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ffiec_cdr.archive import save_raw_filing
from ffiec_cdr.client import FFIECClient
from ffiec_cdr.config import ROOT, ensure_dirs
from ffiec_cdr.db import (
    connect,
    filing_exists,
    init_db,
    insert_filing,
    insert_facts,
    set_checkpoint,
    upsert_institution,
    utc_now,
)
from ffiec_cdr.parser import parse_xbrl

logger = logging.getLogger(__name__)

PROGRESS_FILE = ROOT / "data" / "backfill_progress.json"
FILERS_SINCE = "01/01/2000"


def _load_progress() -> dict[str, Any]:
    if PROGRESS_FILE.is_file():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {
        "completed_periods": [],
        "last_period": None,
        "stats": {},
        "period_filer_totals": {},
        "periods_total": 0,
        "started_at": None,
    }


def _save_progress(state: dict[str, Any]) -> None:
    ensure_dirs()
    PROGRESS_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _already_have_filing(conn, id_rssd: int, period: str, fmt: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM filings
        WHERE id_rssd = ? AND reporting_period = ? AND facsimile_format = ?
        LIMIT 1
        """,
        (id_rssd, period, fmt),
    ).fetchone()
    return row is not None


def run_backfill(
    client: FFIECClient,
    *,
    facsimile_format: str = "XBRL",
    data_series: str = "Call",
    max_downloads: int | None = None,
    skip_completed_periods: bool = True,
) -> dict[str, Any]:
    """
    For every reporting period, download every institution that has filed.
    Skips filings already in the database. Resumes across runs.
    """
    init_db()
    state = _load_progress()
    completed_periods = set(state.get("completed_periods", []))
    if not state.get("started_at"):
        state["started_at"] = utc_now()
    period_filer_totals: dict[str, int] = dict(state.get("period_filer_totals") or {})

    stats: dict[str, Any] = {
        "periods_total": 0,
        "periods_done": 0,
        "filings_downloaded": 0,
        "filings_skipped": 0,
        "facts_inserted": 0,
        "errors": [],
    }

    periods = client.retrieve_reporting_periods(data_series=data_series)
    stats["periods_total"] = len(periods)
    state["periods_total"] = len(periods)
    _save_progress(state)
    logger.info("Backfill: %s reporting periods", len(periods))

    with connect() as conn:
        for period in periods:
            if skip_completed_periods and period in completed_periods:
                logger.info("Skipping completed period %s", period)
                stats["periods_done"] += 1
                continue

            state["last_period"] = period
            _save_progress(state)
            logger.info("Period %s — loading panel …", period)

            try:
                panel = client.retrieve_panel_of_reporters(period, data_series=data_series)
                for inst in panel:
                    upsert_institution(conn, inst)
            except Exception as exc:
                stats["errors"].append(f"panel {period}: {exc}")
                logger.exception("Panel failed for %s", period)
                continue

            try:
                rssd_list = client.retrieve_filers_since_date(
                    period, FILERS_SINCE, data_series=data_series
                )
            except Exception as exc:
                stats["errors"].append(f"filers {period}: {exc}")
                logger.exception("Filers list failed for %s", period)
                continue

            period_filer_totals[period] = len(rssd_list)
            state["period_filer_totals"] = period_filer_totals
            _save_progress(state)
            logger.info("Period %s — %s filers to process", period, len(rssd_list))

            period_downloaded = 0
            period_skipped = 0
            for rssd in rssd_list:
                if max_downloads is not None and stats["filings_downloaded"] >= max_downloads:
                    logger.info("Stopping: max_downloads=%s reached", max_downloads)
                    _save_progress(state)
                    return stats

                if _already_have_filing(conn, int(rssd), period, facsimile_format):
                    stats["filings_skipped"] += 1
                    period_skipped += 1
                    continue

                params = {
                    "dataSeries": data_series,
                    "reportingPeriodEndDate": period,
                    "fiIdType": "ID_RSSD",
                    "fiId": str(rssd),
                    "facsimileFormat": facsimile_format,
                }
                try:
                    content = client.retrieve_facsimile(
                        period,
                        rssd,
                        fi_id_type="ID_RSSD",
                        facsimile_format=facsimile_format,
                        data_series=data_series,
                    )
                except Exception as exc:
                    stats["errors"].append(f"{rssd}/{period}: {exc}")
                    continue

                archived = save_raw_filing(
                    content,
                    source_endpoint="RetrieveFacsimile",
                    request_params=params,
                    data_series=data_series,
                )

                if filing_exists(conn, archived.sha256):
                    stats["filings_skipped"] += 1
                    period_skipped += 1
                    continue

                filing_id = insert_filing(
                    conn,
                    id_rssd=int(rssd),
                    data_series=data_series,
                    reporting_period=period,
                    facsimile_format=facsimile_format,
                    source_endpoint="RetrieveFacsimile",
                    request_params=params,
                    file_path=str(archived.file_path),
                    sha256=archived.sha256,
                    file_size=archived.file_size,
                )
                if filing_id and facsimile_format.upper() == "XBRL":
                    facts = parse_xbrl(content)
                    if facts:
                        insert_facts(conn, filing_id, facts)
                        stats["facts_inserted"] += len(facts)

                stats["filings_downloaded"] += 1
                period_downloaded += 1
                if stats["filings_downloaded"] % 25 == 0:
                    logger.info(
                        "Progress: %s downloaded, %s skipped (period %s: %s/%s)",
                        stats["filings_downloaded"],
                        stats["filings_skipped"],
                        period,
                        period_downloaded + period_skipped,
                        len(rssd_list),
                    )
                    state["stats"] = stats
                    state["current_period_progress"] = {
                        "period": period,
                        "done": period_downloaded + period_skipped,
                        "total": len(rssd_list),
                    }
                    _save_progress(state)

            set_checkpoint(conn, data_series, period, FILERS_SINCE)
            completed_periods.add(period)
            state["completed_periods"] = sorted(completed_periods, key=_period_sort_key)
            stats["periods_done"] += 1
            state["stats"] = stats
            _save_progress(state)
            logger.info("Finished period %s", period)

    state["stats"] = stats
    state["last_period"] = None
    _save_progress(state)
    return stats


def _period_sort_key(period: str) -> tuple:
    try:
        parts = period.split("/")
        return (int(parts[2]), int(parts[0]), int(parts[1]))
    except (IndexError, ValueError):
        return (0, 0, 0)
