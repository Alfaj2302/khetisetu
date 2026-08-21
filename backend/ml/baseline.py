"""Job 1, step 3: the dumb guess the model has to beat.

Seasonal naive — "this month will look like the same month last year". For
seasonal demand this is a genuinely strong baseline, and publishing its error
first is what stops a model from being called good when it is merely present.

reliability.tsx currently hard-codes "baseline error 14.8%, model error 8.6%".
Those two numbers should come from here and from train.py respectively, or be
deleted from the UI.

Usage:
    .venv/bin/python ml/baseline.py --test-year 2024
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import psycopg

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL  # noqa: E402
from ml.features import build_panel  # noqa: E402
from ml.metrics import report  # noqa: E402


def seasonal_naive(panel):
    """Last year's same month, falling back to the trailing 3-month mean when
    the series has no 12-month history yet, then to 0."""
    prediction = panel["lag_12"].copy()
    prediction = prediction.fillna(panel["roll_mean_3"])
    return prediction.fillna(0.0).to_numpy(dtype=float)


def moving_average(panel):
    return panel["roll_mean_12"].fillna(panel["roll_mean_3"]).fillna(0.0).to_numpy(dtype=float)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test-year", type=int, default=2024)
    ap.add_argument("--include-synthetic", action="store_true")
    args = ap.parse_args()

    if not DATABASE_URL:
        print("DATABASE_URL is not set (backend/.env)", file=sys.stderr)
        return 1

    with psycopg.connect(DATABASE_URL) as conn:
        panel = build_panel(conn, include_synthetic=args.include_synthetic)

    test = panel[panel["year"] == args.test_year]
    if test.empty:
        print(f"no rows for test year {args.test_year}", file=sys.stderr)
        return 1

    actual = test["y"].to_numpy(dtype=float)
    print(f"holdout: {args.test_year}   rows: {len(test):,}   total actual: {actual.sum():,.0f} packets\n")
    print(report("seasonal naive", actual, seasonal_naive(test)))
    print(report("12-mo moving average", actual, moving_average(test)))
    print(report("predict zero", actual, np.zeros_like(actual)))
    print(report("predict train mean", actual,
                 np.full_like(actual, panel[panel["year"] < args.test_year]["y"].mean())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
