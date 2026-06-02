#!/usr/bin/env python3
"""Print progress report for FFIEC backfill."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.monitor import get_status  # noqa: E402


def _fmt_eta(seconds: float | None) -> str:
    if not seconds:
        return "—"
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


if __name__ == "__main__":
    s = get_status()
    if "--short" in sys.argv:
        run = "RUNNING" if s.is_running else "STOPPED"
        print(
            f"[{run}] {s.percent_complete:.1f}% | "
            f"{s.filings_in_db:,}/{s.estimated_total_filings:,} filings | "
            f"quarters {s.periods_completed}/{s.periods_total} | "
            f"ETA {_fmt_eta(s.eta_seconds)}"
        )
    else:
        print(s.format_report())
