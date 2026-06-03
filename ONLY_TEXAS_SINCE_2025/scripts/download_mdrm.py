#!/usr/bin/env python3
"""Download Federal Reserve MDRM_CSV.csv if not present."""

import zipfile
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MDRM_DIR = ROOT / "data" / "mdrm"
ZIP_URL = "https://www.federalreserve.gov/apps/mdrm/pdf/MDRM.zip"


def main() -> None:
    MDRM_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = MDRM_DIR / "MDRM_CSV.csv"
    if csv_path.is_file():
        print(f"Already exists: {csv_path}")
        return
    zip_path = MDRM_DIR / "MDRM.zip"
    print(f"Downloading {ZIP_URL} …")
    urllib.request.urlretrieve(ZIP_URL, zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extract("MDRM_CSV.csv", MDRM_DIR)
    print(f"Extracted → {csv_path}")


if __name__ == "__main__":
    main()
