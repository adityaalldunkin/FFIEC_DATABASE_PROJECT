#!/usr/bin/env python3
"""
Backfill agent: runs extraction and prints progress + ETA on a schedule.

  python scripts/backfill_agent.py              # start backfill + monitor
  python scripts/backfill_agent.py --monitor-only   # only print status (no start)
  python scripts/backfill_agent.py --interval 30    # update every 30 seconds
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.monitor import get_status  # noqa: E402

BACKFILL_SCRIPT = ROOT / "scripts" / "backfill_all.py"
LOG_FILE = ROOT / "data" / "backfill.log"


def _is_running() -> bool:
    return get_status().is_running


def _start_backfill() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log:
        subprocess.Popen(
            [sys.executable, str(BACKFILL_SCRIPT)],
            cwd=str(ROOT),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print("Started backfill process → logging to data/backfill.log\n")


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="FFIEC backfill monitor agent")
    parser.add_argument(
        "--monitor-only",
        action="store_true",
        help="Do not start backfill; only show status updates",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between status updates (default 60)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print status once and exit",
    )
    args = parser.parse_args()

    if not args.monitor_only and not _is_running():
        _start_backfill()
        time.sleep(2)

    while True:
        # Clear-ish separator for terminal
        print("\n" + get_status().format_report())
        if args.once:
            return 0
        status = get_status()
        if not status.is_running and status.periods_completed >= status.periods_total:
            print("\nBackfill complete. Run: python scripts/export_csv.py")
            return 0
        if not status.is_running and args.monitor_only:
            return 0
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nMonitor stopped. Backfill keeps running in background.")
        print("Status anytime: python scripts/backfill_status.py")
        raise SystemExit(0)
