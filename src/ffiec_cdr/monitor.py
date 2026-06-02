"""Progress reporting and ETA for FFIEC backfill."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ffiec_cdr.backfill import PROGRESS_FILE
from ffiec_cdr.config import DB_PATH, ROOT

LOG_FILE = ROOT / "data" / "backfill.log"


@dataclass
class BackfillStatus:
    is_running: bool
    pid: int | None
    started_at: str | None
    elapsed_seconds: float
    periods_total: int
    periods_completed: int
    current_period: str | None
    current_period_total: int
    current_period_done: int
    filings_in_db: int
    facts_in_db: int
    downloaded_this_run: int
    skipped_this_run: int
    errors_this_run: int
    estimated_total_filings: int
    estimated_remaining_filings: int
    percent_complete: float
    filings_per_minute: float
    eta_seconds: float | None
    message: str

    def format_report(self) -> str:
        lines = [
            "═" * 52,
            "  FFIEC data extraction status",
            "═" * 52,
            f"  Running:        {'YES' if self.is_running else 'NO'}"
            + (f"  (PID {self.pid})" if self.pid else ""),
            f"  Started:        {self.started_at or '—'}",
            f"  Elapsed:        {_fmt_duration(self.elapsed_seconds)}",
            "",
            f"  Quarters done:  {self.periods_completed} / {self.periods_total}"
            f"  ({_pct(self.periods_completed, self.periods_total)})",
            f"  Filings in DB:  {self.filings_in_db:,}"
            f"  / ~{self.estimated_total_filings:,} estimated"
            f"  ({self.percent_complete:.1f}%)",
            f"  XBRL facts:     {self.facts_in_db:,}",
        ]
        if self.current_period:
            lines.append(
                f"  Current quarter: {self.current_period}"
                f" — {_pct(self.current_period_done, self.current_period_total)}"
                f" ({self.current_period_done:,} / {self.current_period_total:,} banks)"
            )
        lines.extend(
            [
                "",
                f"  This run:       +{self.downloaded_this_run:,} downloaded,"
                f" {self.skipped_this_run:,} skipped,"
                f" {self.errors_this_run} errors",
                f"  Speed:          {self.filings_per_minute:.1f} filings/min",
                f"  Remaining:      ~{self.estimated_remaining_filings:,} filings",
                f"  ETA:            {_fmt_duration(self.eta_seconds) if self.eta_seconds else '—'}",
                "",
                f"  {self.message}",
                "═" * 52,
            ]
        )
        return "\n".join(lines)


def _pct(done: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{100.0 * done / total:.1f}%"


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    if s < 86400:
        h, rem = divmod(s, 3600)
        return f"{h}h {rem // 60}m"
    d, rem = divmod(s, 86400)
    return f"{d}d {rem // 3600}h"


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _find_backfill_pid() -> int | None:
    try:
        out = subprocess.run(
            ["pgrep", "-f", "scripts/backfill_all.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = [int(p) for p in out.stdout.strip().split() if p.strip().isdigit()]
        return pids[0] if pids else None
    except (OSError, ValueError):
        return None


def _db_counts() -> tuple[int, int]:
    if not DB_PATH.is_file():
        return 0, 0
    with sqlite3.connect(DB_PATH) as conn:
        filings = conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
        facts = conn.execute("SELECT COUNT(*) FROM xbrl_facts").fetchone()[0]
    return int(filings), int(facts)


def _filings_for_period(period: str) -> int:
    if not DB_PATH.is_file():
        return 0
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM filings WHERE reporting_period = ?", (period,)
        ).fetchone()
    return int(row[0])


def load_progress() -> dict[str, Any]:
    if PROGRESS_FILE.is_file():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {}


def get_status() -> BackfillStatus:
    progress = load_progress()
    pid = _find_backfill_pid()
    is_running = pid is not None

    periods_total = int(progress.get("periods_total") or 101)
    completed = progress.get("completed_periods") or []
    periods_completed = len(completed)

    period_totals: dict[str, int] = progress.get("period_filer_totals") or {}
    current_period = progress.get("last_period")
    current_period_total = int(period_totals.get(current_period or "", 0))
    current_period_done = _filings_for_period(current_period) if current_period else 0

    stats = progress.get("stats") or {}
    downloaded_this_run = int(stats.get("filings_downloaded") or 0)
    skipped_this_run = int(stats.get("filings_skipped") or 0)
    errors_this_run = len(stats.get("errors") or [])

    filings_in_db, facts_in_db = _db_counts()

    # Estimate total filings across all quarters
    known_totals = list(period_totals.values())
    if known_totals:
        avg_per_period = sum(known_totals) / len(known_totals)
    else:
        avg_per_period = 4000.0
    estimated_total = int(avg_per_period * periods_total)

    # Remaining: unknown periods + incomplete current
    remaining_periods = periods_total - periods_completed
    estimated_remaining = 0
    for p, total in period_totals.items():
        if p in completed:
            continue
        have = _filings_for_period(p)
        estimated_remaining += max(0, total - have)
    estimated_remaining += int(remaining_periods * avg_per_period)
    if current_period and current_period not in completed:
        # avoid double-counting current period in remaining_periods bucket
        estimated_remaining = max(0, estimated_remaining - int(avg_per_period))
        estimated_remaining += max(0, current_period_total - current_period_done)

    percent_complete = (
        100.0 * filings_in_db / estimated_total if estimated_total else 0.0
    )

    started_at = progress.get("started_at")
    elapsed = 0.0
    if started_at:
        try:
            elapsed = (
                datetime.now(timezone.utc) - _parse_iso(started_at)
            ).total_seconds()
        except ValueError:
            pass

    filings_per_minute = 0.0
    eta_seconds: float | None = None
    if elapsed > 60 and filings_in_db > 0:
        filings_per_minute = filings_in_db / (elapsed / 60.0)
        if filings_per_minute > 0 and estimated_remaining > 0:
            eta_seconds = (estimated_remaining / filings_per_minute) * 60.0
    elif downloaded_this_run > 0 and elapsed > 0:
        filings_per_minute = downloaded_this_run / (elapsed / 60.0)
        if filings_per_minute > 0:
            eta_seconds = (estimated_remaining / filings_per_minute) * 60.0

    if is_running:
        message = "Extraction in progress. Re-run: python scripts/backfill_status.py"
    elif periods_completed >= periods_total:
        message = "All quarters complete. Run: python scripts/export_csv.py"
    elif filings_in_db > 0:
        message = "Paused or stopped. Resume: python scripts/backfill_agent.py"
    else:
        message = "Not started. Run: python scripts/backfill_agent.py"

    return BackfillStatus(
        is_running=is_running,
        pid=pid,
        started_at=started_at,
        elapsed_seconds=elapsed,
        periods_total=periods_total,
        periods_completed=periods_completed,
        current_period=current_period,
        current_period_total=current_period_total,
        current_period_done=current_period_done,
        filings_in_db=filings_in_db,
        facts_in_db=facts_in_db,
        downloaded_this_run=downloaded_this_run,
        skipped_this_run=skipped_this_run,
        errors_this_run=errors_this_run,
        estimated_total_filings=estimated_total,
        estimated_remaining_filings=max(0, estimated_remaining),
        percent_complete=min(100.0, percent_complete),
        filings_per_minute=filings_per_minute,
        eta_seconds=eta_seconds,
        message=message,
    )
