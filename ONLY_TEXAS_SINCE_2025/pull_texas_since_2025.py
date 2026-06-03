#!/usr/bin/env python3
"""
Download FFIEC Call Report XBRL filings for Texas banks (2025+).

Outputs CSV files under ONLY_TEXAS_SINCE_2025/exports/
Stores raw XBRL under ONLY_TEXAS_SINCE_2025/archive/

Uses credentials from ../.env (FFIEC_USER_ID, FFIEC_TOKEN).

  python pull_texas_since_2025.py
  python pull_texas_since_2025.py --max 5    # test run
  python pull_texas_since_2025.py --format PDF
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Reuse main project client + XBRL parser
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ffiec_cdr.client import FFIECClient, client_from_env  # noqa: E402
from ffiec_cdr.parser import parse_xbrl  # noqa: E402

ARCHIVE_DIR = ROOT / "archive" / "call"
EXPORT_DIR = ROOT / "exports"
LOG_FILE = ROOT / "data" / "pull.log"
PROGRESS_FILE = ROOT / "data" / "progress.json"

EXTENSIONS = {"PDF": ".pdf", "XBRL": ".xbrl", "SDF": ".txt"}
TEXAS_STATE = "TX"
MIN_YEAR = 2025

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _period_year(period: str) -> int:
    """Parse MM/DD/YYYY → year."""
    parts = period.split("/")
    return int(parts[2])


def _periods_since_2025(client: FFIECClient) -> list[str]:
    all_periods = client.retrieve_reporting_periods(data_series="Call")
    return [p for p in all_periods if _period_year(p) >= MIN_YEAR]


def _archive_path(period: str, rssd: int, fmt: str) -> Path:
    safe = period.replace("/", "-")
    ext = EXTENSIONS.get(fmt.upper(), ".bin")
    return ARCHIVE_DIR / safe / f"{rssd}{ext}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_progress() -> dict:
    if PROGRESS_FILE.is_file():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"completed": []}


def _save_progress(done: set[tuple[str, int]]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps({"completed": [f"{p}|{r}" for p, r in sorted(done)]}, indent=2),
        encoding="utf-8",
    )


def _is_done(done: set[tuple[str, int]], period: str, rssd: int) -> bool:
    return (period, rssd) in done


def _init_csv_writers(export_dir: Path) -> tuple:
    export_dir.mkdir(parents=True, exist_ok=True)
    inst_path = export_dir / "texas_institutions.csv"
    fil_path = export_dir / "texas_filings.csv"
    facts_path = export_dir / "texas_xbrl_facts.csv"

    inst_f = inst_path.open("w", newline="", encoding="utf-8")
    fil_f = fil_path.open("w", newline="", encoding="utf-8")
    facts_f = facts_path.open("w", newline="", encoding="utf-8")

    inst_w = csv.DictWriter(
        inst_f,
        fieldnames=[
            "id_rssd",
            "name",
            "state",
            "city",
            "filing_type",
            "reporting_period",
            "has_filed",
        ],
    )
    fil_w = csv.DictWriter(
        fil_f,
        fieldnames=[
            "id_rssd",
            "institution_name",
            "state",
            "city",
            "reporting_period",
            "facsimile_format",
            "retrieved_at",
            "file_path",
            "sha256",
            "file_size_bytes",
        ],
    )
    facts_w = csv.DictWriter(
        facts_f,
        fieldnames=[
            "id_rssd",
            "institution_name",
            "reporting_period",
            "concept",
            "context_ref",
            "unit_ref",
            "value_text",
            "value_num",
        ],
    )
    inst_w.writeheader()
    fil_w.writeheader()
    facts_w.writeheader()
    return inst_f, fil_f, facts_f, inst_w, fil_w, facts_w


def run(*, max_downloads: int | None = None, facsimile_format: str = "XBRL") -> dict:
    load_dotenv(PROJECT_ROOT / ".env")
    client = client_from_env()

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    periods = _periods_since_2025(client)
    logger.info("Texas pull: %s periods (year >= %s): %s", len(periods), MIN_YEAR, periods)

    done_keys: set[tuple[str, int]] = set()
    prog = _load_progress()
    for item in prog.get("completed", []):
        if "|" in item:
            p, r = item.split("|", 1)
            done_keys.add((p, int(r)))

    stats = {"downloaded": 0, "skipped": 0, "errors": 0, "facts_rows": 0}
    retrieved_at = datetime.now(timezone.utc).isoformat()

    inst_f, fil_f, facts_f, inst_w, fil_w, facts_w = _init_csv_writers(EXPORT_DIR)
    seen_inst: set[tuple[str, int]] = set()

    try:
        for period in periods:
            logger.info("Period %s — fetching panel …", period)
            try:
                panel = client.retrieve_panel_of_reporters(period, data_series="Call")
            except Exception as exc:
                logger.error("Panel failed %s: %s", period, exc)
                stats["errors"] += 1
                continue

            texas = [r for r in panel if (r.get("State") or "").upper() == TEXAS_STATE]
            logger.info("Period %s — %s Texas institutions", period, len(texas))

            for inst in texas:
                rssd = int(inst["ID_RSSD"])
                name = (inst.get("Name") or "").strip()
                has_filed = bool(inst.get("HasFiledForReportingPeriod"))

                key_inst = (period, rssd)
                if key_inst not in seen_inst:
                    seen_inst.add(key_inst)
                    inst_w.writerow(
                        {
                            "id_rssd": rssd,
                            "name": name,
                            "state": inst.get("State"),
                            "city": inst.get("City"),
                            "filing_type": inst.get("FilingType"),
                            "reporting_period": period,
                            "has_filed": has_filed,
                        }
                    )

                if _is_done(done_keys, period, rssd):
                    stats["skipped"] += 1
                    continue

                if not has_filed:
                    stats["skipped"] += 1
                    continue

                if max_downloads is not None and stats["downloaded"] >= max_downloads:
                    logger.info("Reached --max %s", max_downloads)
                    return stats

                try:
                    content = client.retrieve_facsimile(
                        period,
                        rssd,
                        facsimile_format=facsimile_format,
                    )
                except Exception as exc:
                    logger.warning("Download failed %s / %s: %s", rssd, period, exc)
                    stats["errors"] += 1
                    continue

                path = _archive_path(period, rssd, facsimile_format)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                digest = _sha256(content)

                meta = {
                    "id_rssd": rssd,
                    "period": period,
                    "format": facsimile_format,
                    "sha256": digest,
                    "retrieved_at": retrieved_at,
                }
                path.with_suffix(path.suffix + ".meta.json").write_text(
                    json.dumps(meta, indent=2), encoding="utf-8"
                )

                fil_w.writerow(
                    {
                        "id_rssd": rssd,
                        "institution_name": name,
                        "state": TEXAS_STATE,
                        "city": inst.get("City"),
                        "reporting_period": period,
                        "facsimile_format": facsimile_format,
                        "retrieved_at": retrieved_at,
                        "file_path": str(path),
                        "sha256": digest,
                        "file_size_bytes": len(content),
                    }
                )

                if facsimile_format.upper() == "XBRL":
                    for fact in parse_xbrl(content):
                        facts_w.writerow(
                            {
                                "id_rssd": rssd,
                                "institution_name": name,
                                "reporting_period": period,
                                "concept": fact.get("concept"),
                                "context_ref": fact.get("context_ref"),
                                "unit_ref": fact.get("unit_ref"),
                                "value_text": fact.get("value_text"),
                                "value_num": fact.get("value_num"),
                            }
                        )
                        stats["facts_rows"] += 1

                done_keys.add((period, rssd))
                _save_progress(done_keys)
                stats["downloaded"] += 1

                if stats["downloaded"] % 10 == 0:
                    logger.info(
                        "Downloaded %s filings, %s fact rows",
                        stats["downloaded"],
                        stats["facts_rows"],
                    )
                    inst_f.flush()
                    fil_f.flush()
                    facts_f.flush()

    finally:
        inst_f.close()
        fil_f.close()
        facts_f.close()

    logger.info("Done: %s", stats)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull Texas Call Reports since 2025")
    parser.add_argument("--max", type=int, default=None, help="Limit new downloads")
    parser.add_argument("--format", default="XBRL", choices=["XBRL", "PDF", "SDF"])
    args = parser.parse_args()
    stats = run(max_downloads=args.max, facsimile_format=args.format)
    print("\nExports written to:", EXPORT_DIR)
    print("  texas_institutions.csv")
    print("  texas_filings.csv")
    print("  texas_xbrl_facts.csv")
    print("Stats:", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
