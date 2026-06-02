#!/usr/bin/env python3
"""Run incremental sync (Phase 4)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.client import client_from_env  # noqa: E402
from ffiec_cdr.sync import run_sync  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="FFIEC incremental sync")
    parser.add_argument("--period", action="append", help="Reporting period MM/DD/YYYY (repeatable)")
    parser.add_argument("--format", default="XBRL", choices=["XBRL", "PDF", "SDF"])
    parser.add_argument("--max-downloads", type=int, default=None)
    args = parser.parse_args()

    client = client_from_env()
    kwargs = {}
    if args.max_downloads is not None:
        kwargs["max_downloads"] = args.max_downloads

    stats = run_sync(
        client,
        periods=args.period,
        facsimile_format=args.format,
        **kwargs,
    )
    print("Sync complete:", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
