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
# Install (runs 02:15 daily). The repo path contains spaces, so the crontab
# entry must quote it:
#   crontab -e
#   15 2 * * * "/home/ttpl-rt-245/WORKSPACE/KhetiSetu Project/khetisetu/backend/ml/run_nightly.sh"
#
# Both write steps are idempotent, so a re-run after a failure is safe.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$BACKEND_DIR/.venv/bin/python"
LOG_DIR="$BACKEND_DIR/ml/logs"
LOCK="$BACKEND_DIR/ml/.nightly.lock"

# Planning window: the quarter AFTER the one we are currently in, derived from
# today rather than hardcoded. A fixed window here was the bug - the job would
# happily rebuild `recommendations` for one long-past quarter every night
# forever, and the dashboard would look live while being frozen.
# Still overridable from the crontab for a backfill: TARGET_YEAR=2027 ...
_now_year=$(date +%Y)
_now_quarter=$(( ($(date +%-m) - 1) / 3 + 1 ))
if [ "$_now_quarter" -eq 4 ]; then
    _next_year=$(( _now_year + 1 )); _next_quarter=1
else
    _next_year=$_now_year;           _next_quarter=$(( _now_quarter + 1 ))
fi

TARGET_YEAR="${TARGET_YEAR:-$_next_year}"
TARGET_QUARTER="${TARGET_QUARTER:-$_next_quarter}"
# Forecast out to the end of the target year, so the planning quarter is always
# inside the horizon. predict.py extends this itself if loaded sales data has
# already caught up past it.
THROUGH_YEAR="${THROUGH_YEAR:-$TARGET_YEAR}"

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
    echo "planning window: ${TARGET_YEAR}-Q${TARGET_QUARTER}  (horizon through ${THROUGH_YEAR}-Q4)"
    echo "--- train ---";     "$PYTHON" ml/train.py
    echo "--- predict ---";   "$PYTHON" ml/predict.py --through-year "$THROUGH_YEAR" --write
    echo "--- recommend ---"; "$PYTHON" ml/recommend.py --year "$TARGET_YEAR" --quarter "$TARGET_QUARTER" --write
    echo "=== $(date -Is) nightly done ==="
} >>"$LOG" 2>&1
