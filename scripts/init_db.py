#!/usr/bin/env python3
"""Initialize SQLite database schema."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ffiec_cdr.db import init_db  # noqa: E402

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
