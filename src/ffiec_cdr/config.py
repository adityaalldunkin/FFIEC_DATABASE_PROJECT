"""Project paths and environment settings."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = ROOT / "archive"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "ffiec.db"
CHECKPOINT_PATH = DATA_DIR / "sync_checkpoint.json"

# ~2400/hour per FFIEC guidance (1.5s spacing)
DEFAULT_REQUEST_DELAY_SEC = float(os.environ.get("FFIEC_REQUEST_DELAY_SEC", "1.5"))
MAX_DOWNLOADS_PER_RUN = int(os.environ.get("FFIEC_MAX_DOWNLOADS_PER_RUN", "10"))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")


def ensure_dirs() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
