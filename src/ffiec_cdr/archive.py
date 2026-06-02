"""Phase 2: store raw facsimiles with full request provenance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ffiec_cdr.config import ARCHIVE_DIR, ensure_dirs
from ffiec_cdr.db import utc_now as _utc_now

EXTENSIONS = {"PDF": ".pdf", "XBRL": ".xbrl", "SDF": ".txt", "UBPR_XBRL": ".xbrl"}


@dataclass
class ArchiveResult:
    file_path: Path
    metadata_path: Path
    sha256: str
    file_size: int
    request_params: dict[str, Any]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_path(
    data_series: str,
    id_rssd: int,
    period: str,
    fmt: str,
) -> Path:
    safe_period = period.replace("/", "-")
    ext = EXTENSIONS.get(fmt.upper(), ".bin")
    sub = "ubpr" if data_series.upper() == "UBPR" else "call"
    return ARCHIVE_DIR / sub / safe_period / f"{id_rssd}{ext}"


def save_raw_filing(
    content: bytes,
    *,
    source_endpoint: str,
    request_params: dict[str, Any],
    data_series: str = "Call",
) -> ArchiveResult:
    """Write raw bytes + sidecar metadata JSON."""
    ensure_dirs()
    fmt = request_params.get("facsimileFormat", "XBRL")
    if data_series.upper() == "UBPR":
        fmt = "UBPR_XBRL"
    id_rssd = int(request_params["fiId"])
    period = request_params["reportingPeriodEndDate"]

    path = archive_path(data_series, id_rssd, period, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    digest = sha256_bytes(content)
    meta = {
        "source_endpoint": source_endpoint,
        "request_params": request_params,
        "retrieved_at": _utc_now(),
        "id_rssd": id_rssd,
        "reporting_period": period,
        "data_series": data_series,
        "facsimile_format": fmt,
        "sha256": digest,
        "file_size": len(content),
        "file_path": str(path),
    }
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return ArchiveResult(
        file_path=path,
        metadata_path=meta_path,
        sha256=digest,
        file_size=len(content),
        request_params=request_params,
    )
