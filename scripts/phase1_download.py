#!/usr/bin/env python3
"""
Phase 1: prove the FFIEC CDR pipeline end-to-end.

Uses Phase 2 archive + database when available.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.archive import save_raw_filing  # noqa: E402
from ffiec_cdr.client import FFIECClient, FFIECClientError, client_from_env  # noqa: E402
from ffiec_cdr.db import connect, init_db, insert_filing, upsert_institution  # noqa: E402
from ffiec_cdr.parser import parse_xbrl  # noqa: E402
from ffiec_cdr.db import insert_facts  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")
    try:
        client = client_from_env()
    except ValueError:
        print("Set FFIEC_USER_ID and FFIEC_TOKEN in .env (see .env.example).")
        return 1

    facsimile_format = os.environ.get("FFIEC_FACSIMILE_FORMAT", "XBRL").upper()
    init_db()

    print("Step 1: reporting periods …")
    periods = client.retrieve_reporting_periods()
    if not periods:
        print("No reporting periods returned.")
        return 1
    period = periods[0]
    print(f"  Latest period: {period} ({len(periods)} available)")

    print("Step 2: panel of reporters …")
    panel = client.retrieve_panel_of_reporters(period)
    print(f"  {len(panel)} institutions")

    filer = next((r for r in panel if r.get("HasFiledForReportingPeriod")), None)
    if not filer:
        print("No filer with HasFiledForReportingPeriod=true.")
        return 1

    rssd = filer["ID_RSSD"]
    print(f"  Downloading: {filer.get('Name', '').strip()} (ID_RSSD={rssd})")

    params = {
        "dataSeries": "Call",
        "reportingPeriodEndDate": period,
        "fiIdType": "ID_RSSD",
        "fiId": str(rssd),
        "facsimileFormat": facsimile_format,
    }

    print(f"Step 3: facsimile ({facsimile_format}) …")
    try:
        content = client.retrieve_facsimile(
            period, rssd, facsimile_format=facsimile_format
        )
    except FFIECClientError as exc:
        print(f"Download failed: {exc}")
        return 1

    archived = save_raw_filing(
        content,
        source_endpoint="RetrieveFacsimile",
        request_params=params,
    )
    print(f"  Archived → {archived.file_path}")
    print(f"  Metadata → {archived.metadata_path}")
    print(f"  SHA-256: {archived.sha256}")

    with connect() as conn:
        upsert_institution(conn, filer)
        filing_id = insert_filing(
            conn,
            id_rssd=int(rssd),
            data_series="Call",
            reporting_period=period,
            facsimile_format=facsimile_format,
            source_endpoint="RetrieveFacsimile",
            request_params=params,
            file_path=str(archived.file_path),
            sha256=archived.sha256,
            file_size=archived.file_size,
        )
        if filing_id and facsimile_format == "XBRL":
            facts = parse_xbrl(content)
            insert_facts(conn, filing_id, facts)
            print(f"  Parsed {len(facts)} XBRL facts into database (filing_id={filing_id})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
