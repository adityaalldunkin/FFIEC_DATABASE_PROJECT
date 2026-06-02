#!/usr/bin/env python3
"""
Download all available Call Report filings from FFIEC (resumable).

This can take many hours or days (100+ periods × thousands of banks).
Re-run the same command to resume; already-downloaded filings are skipped.

  python scripts/backfill_all.py              # no limit (full backfill)
  python scripts/backfill_all.py --max 100    # stop after 100 new downloads
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.backfill import run_backfill  # noqa: E402
from ffiec_cdr.client import client_from_env  # noqa: E402

if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT / "data" / "backfill.log", encoding="utf-8"),
        ],
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Max new downloads this run (default: unlimited)",
    )
    parser.add_argument(
        "--reprocess-periods",
        action="store_true",
        help="Do not skip periods marked complete in backfill_progress.json",
    )
    args = parser.parse_args()

    client = client_from_env()
    stats = run_backfill(
        client,
        max_downloads=args.max,
        skip_completed_periods=not args.reprocess_periods,
    )
    print("Backfill finished:", stats)
