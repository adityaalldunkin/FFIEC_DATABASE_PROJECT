#!/usr/bin/env python3
"""Start FastAPI server (Phase 6)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("ffiec_cdr.api:app", host="0.0.0.0", port=8000, reload=False)
