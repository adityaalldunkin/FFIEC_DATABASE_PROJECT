#!/bin/bash
# Run in Terminal.app (keeps running after you close Cursor).
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

mkdir -p data
if pgrep -f "scripts/backfill_all.py" >/dev/null 2>&1; then
  echo "Backfill already running:"
  pgrep -fl backfill_all
else
  echo "Starting full backfill → data/backfill.log"
  nohup python scripts/backfill_all.py >> data/backfill.log 2>&1 &
  echo "PID: $!"
fi

echo ""
python scripts/backfill_status.py
echo ""
echo "Monitor live:  python scripts/backfill_agent.py"
echo "Quick status:  python scripts/backfill_status.py --short"
echo "Export CSV:    python scripts/export_csv.py"
