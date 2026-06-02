"""Phase 4: incremental sync with checkpoints, rate limiting, and idempotent downloads."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ffiec_cdr.archive import save_raw_filing
from ffiec_cdr.client import FFIECClient
from ffiec_cdr.config import MAX_DOWNLOADS_PER_RUN
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

DEFAULT_SINCE = "01/01/2000"


def _default_checkpoint() -> str:
    return DEFAULT_SINCE


def run_sync(
    client: FFIECClient,
    *,
    periods: list[str] | None = None,
    facsimile_format: str = "XBRL",
    max_downloads: int = MAX_DOWNLOADS_PER_RUN,
    data_series: str = "Call",
) -> dict[str, Any]:
    """
    Incremental sync for Call data:
      1. Resolve reporting periods (latest only if not specified)
      2. For each period, get filers since last checkpoint
      3. Download, archive, parse, and record new filings
    """
    init_db()
    stats: dict[str, Any] = {
        "filings_downloaded": 0,
        "filings_skipped": 0,
        "facts_inserted": 0,
        "errors": [],
    }

    if periods is None:
        periods = client.retrieve_reporting_periods(data_series=data_series)[:1]

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sync_runs (started_at, status) VALUES (?, 'running')
            """,
            (utc_now(),),
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for period in periods:
            try:
                panel = client.retrieve_panel_of_reporters(period, data_series=data_series)
                for inst in panel:
                    upsert_institution(conn, inst)
            except Exception as exc:
                stats["errors"].append(f"panel {period}: {exc}")
                logger.exception("Panel fetch failed for %s", period)

            checkpoint = (
                conn.execute(
                    "SELECT last_update_datetime FROM sync_checkpoints WHERE data_series=? AND reporting_period=?",
                    (data_series, period),
                ).fetchone()
            )
            since = checkpoint["last_update_datetime"] if checkpoint else _default_checkpoint()

            try:
                rssd_list = client.retrieve_filers_since_date(
                    period, since, data_series=data_series
                )
            except Exception as exc:
                stats["errors"].append(f"filers {period}: {exc}")
                continue

            if not rssd_list:
                logger.info("No new filers for %s since %s", period, since)
                set_checkpoint(conn, data_series, period, _now_mmddyyyy())
                continue

            for rssd in rssd_list:
                if stats["filings_downloaded"] >= max_downloads:
                    logger.info("Reached max_downloads=%s", max_downloads)
                    break

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
                    stats["errors"].append(f"download {rssd}/{period}: {exc}")
                    continue

                archived = save_raw_filing(
                    content,
                    source_endpoint="RetrieveFacsimile",
                    request_params=params,
                    data_series=data_series,
                )

                if filing_exists(conn, archived.sha256):
                    stats["filings_skipped"] += 1
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

            set_checkpoint(conn, data_series, period, _now_mmddyyyy())

        conn.execute(
            """
            UPDATE sync_runs SET finished_at=?, status='completed',
                periods_processed=?, filings_downloaded=?, filings_skipped=?, errors=?
            WHERE id=?
            """,
            (
                utc_now(),
                len(periods),
                stats["filings_downloaded"],
                stats["filings_skipped"],
                "; ".join(stats["errors"][:20]),
                run_id,
            ),
        )

    return stats


def _now_mmddyyyy() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%m/%d/%Y")
