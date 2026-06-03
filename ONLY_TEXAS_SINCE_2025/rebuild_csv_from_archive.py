#!/usr/bin/env python3
"""Rebuild exports/*.csv from archived XBRL files (use if CSVs are incomplete after resume)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ffiec_cdr.parser import parse_xbrl  # noqa: E402

ARCHIVE = ROOT / "archive" / "call"
EXPORT = ROOT / "exports"
INST_CSV = EXPORT / "texas_institutions.csv"


def _period_from_dir(name: str) -> str:
    parts = name.split("-")
    if len(parts) == 3:
        return f"{parts[0]}/{parts[1]}/{parts[2]}"
    return name


def _load_names() -> dict[int, str]:
    names: dict[int, str] = {}
    if INST_CSV.is_file():
        with INST_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                names[int(row["id_rssd"])] = row.get("name", "")
    return names


def main() -> None:
    EXPORT.mkdir(parents=True, exist_ok=True)
    names = _load_names()
    fil_rows = []
    fact_count = 0

    facts_path = EXPORT / "texas_xbrl_facts.csv"
    with facts_path.open("w", newline="", encoding="utf-8") as facts_f:
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
        facts_w.writeheader()

        for period_dir in sorted(ARCHIVE.iterdir()):
            if not period_dir.is_dir():
                continue
            period = _period_from_dir(period_dir.name)
            for xbrl in sorted(period_dir.glob("*.xbrl")):
                rssd = int(xbrl.stem)
                meta_path = xbrl.with_suffix(".xbrl.meta.json")
                meta = {}
                if meta_path.is_file():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                content = xbrl.read_bytes()
                inst_name = names.get(rssd, "")
                fil_rows.append(
                    {
                        "id_rssd": rssd,
                        "institution_name": inst_name,
                        "state": "TX",
                        "city": "",
                        "reporting_period": period,
                        "facsimile_format": "XBRL",
                        "retrieved_at": meta.get("retrieved_at", ""),
                        "file_path": str(xbrl),
                        "sha256": meta.get("sha256", ""),
                        "file_size_bytes": len(content),
                    }
                )
                for fact in parse_xbrl(content):
                    facts_w.writerow(
                        {
                            "id_rssd": rssd,
                            "institution_name": inst_name,
                            "reporting_period": period,
                            "concept": fact.get("concept"),
                            "context_ref": fact.get("context_ref"),
                            "unit_ref": fact.get("unit_ref"),
                            "value_text": fact.get("value_text"),
                            "value_num": fact.get("value_num"),
                        }
                    )
                    fact_count += 1

    fil_path = EXPORT / "texas_filings.csv"
    with fil_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
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
        w.writeheader()
        w.writerows(fil_rows)

    print(f"Rebuilt {len(fil_rows)} filings, {fact_count:,} fact rows → {EXPORT}")


if __name__ == "__main__":
    main()
