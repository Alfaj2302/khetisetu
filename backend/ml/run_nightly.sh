#!/usr/bin/env bash
# Job 1, step 11: the nightly batch.
#
#   train  -> refit on whatever sales data has landed since last night
#   predict-> forecast forward and rewrite the `forecast` table
#   recommend -> rebuild `recommendations` from forecast + inventory
#
# The API never computes any of this on request; it only reads the two tables
# this script fills (schema.sql: "written by the batch ML job, read by the API").
#
# Install (runs 02:15 daily):
#   crontab -e
#   15 2 * * * /home/ttpl-rt-127/Hack/khetisetu/backend/ml/run_nightly.sh
#
# Both write steps are idempotent, so a re-run after a failure is safe.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$BACKEND_DIR/.venv/bin/python"
LOG_DIR="$BACKEND_DIR/ml/logs"
LOCK="$BACKEND_DIR/ml/.nightly.lock"

# Planning window the recommendations are built for. Override in the crontab
# (e.g. TARGET_YEAR=2027) rather than editing this file.
THROUGH_YEAR="${THROUGH_YEAR:-2026}"
TARGET_YEAR="${TARGET_YEAR:-2026}"
TARGET_QUARTER="${TARGET_QUARTER:-3}"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/nightly-$(date +%Y%m%d).log"

# A long training run overlapping the next night's would have two writers
# racing on the same two tables. flock makes the second invocation exit instead.
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -Is) another nightly run holds the lock; exiting" >>"$LOG"
    exit 0
fi

cd "$BACKEND_DIR"
{
    echo "=== $(date -Is) nightly start ==="
    echo "--- train ---";     "$PYTHON" ml/train.py
    echo "--- predict ---";   "$PYTHON" ml/predict.py --through-year "$THROUGH_YEAR" --write
    echo "--- recommend ---"; "$PYTHON" ml/recommend.py --year "$TARGET_YEAR" --quarter "$TARGET_QUARTER" --write
    echo "=== $(date -Is) nightly done ==="
} >>"$LOG" 2>&1
