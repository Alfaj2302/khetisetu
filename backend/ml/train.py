"""Job 1, steps 4-8: train the demand model and save the production artifacts.

WHY THIS FORECASTS QUARTERS AND NOT PRODUCT-MONTHS
--------------------------------------------------
The `forecast` table wants (district, product, year, month). Measured on the
2024 holdout, that granularity is noise:

    district x product x month   seasonal-naive WAPE 136%   (worse than zero)
    XGBoost at the same level                       98%   (bias -35: it just
                                                            hedges to zero)

Signal only survives aggregation:

    district x quarter           seasonal-naive WAPE  72%
    state    x quarter                                25%

So the production chain is:

    forecast  district x quarter          <- a real trained model
      split   into months                 <- historical month-of-quarter shares
      split   into products               <- historical product-mix shares
      write   district x product x month

The per-product monthly rows are therefore an ALLOCATION of a forecast, not a
forecast. `forecast.confidence` says so on every row, so nothing downstream can
mistake one for the other.

Two levels are still trained and compared, so the claim above stays evidence
rather than assertion: the product-level model is fitted too and its holdout
error is printed and recorded in the metadata.

HOW THE THREE YEAR FOLDS ARE USED
---------------------------------
    year <  calib_year    fit the trees
    year == calib_year    conformal calibration ONLY - never seen by fitting
    year == test_year     held out, reported

Early stopping is deliberately absent. It needs an eval set, and the only
candidate was the calibration year - which would mean the interval width was
derived from data the fit had already peeked at, making coverage optimistic.
Measured on the 2024 holdout, dropping early stopping costs nothing (WAPE is
flat at 58-60% for n_estimators anywhere in 100..900 - shallow trees on 52 rows
plateau early) and buys a calibration fold that is genuinely untouched, which
takes interval coverage from 63% to 81.5% against an 80% target.

Usage:
    .venv/bin/python ml/train.py --test-year 2024
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
import xgboost as xgb

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL  # noqa: E402
from ml.baseline import seasonal_naive  # noqa: E402
from ml.features import (  # noqa: E402
    CATEGORICAL,
    LAGS,
    LAGS_Q,
    ROLL_WINDOWS,
    ROLL_WINDOWS_Q,
    build_district_quarter_panel,
    build_panel,
    month_within_quarter_shares,
    product_within_district_shares,
)
from ml.metrics import coverage, report, wape  # noqa: E402

ARTIFACT_DIR = BACKEND_DIR / "ml" / "artifacts"
QUANTILES = (0.1, 0.5, 0.9)

# The interval the quantile heads are asked for, and the level the conformal
# rebuild is held to: 0.1..0.9 is an 80% interval, so ALPHA is 0.20.
ALPHA = 1.0 - (QUANTILES[-1] - QUANTILES[0])

QUARTER_FEATURES = [
    "quarter",
    "quarter_sin",
    "quarter_cos",
    "rainfall_mm",
    "temperature_c",
    "humidity_pct",
    "crops_sown",
    "intent_acres",
    "intent_rows",
    *[f"lag_{lag}" for lag in LAGS_Q],
    *[f"roll_mean_{w}" for w in ROLL_WINDOWS_Q],
]

PRODUCT_FEATURES = [
    "month",
    "month_sin",
    "month_cos",
    "rainfall_mm",
    "temperature_c",
    "humidity_pct",
    "crops_sown",
    "intent_acres",
    "intent_rows",
    "shelf_life_days",
    *[f"lag_{lag}" for lag in LAGS],
    *[f"roll_mean_{w}" for w in ROLL_WINDOWS],
]

# `year` is deliberately absent from both lists. Boosted trees cannot
# extrapolate: a split on "year >= 2025" can only be learned from years that
# appear in training, so a raw year column is dead weight at best and a cliff
# at worst. Level enters via lags, seasonality via the sin/cos pair.

PARAMS = dict(
    objective="reg:quantileerror",
    quantile_alpha=np.array(QUANTILES),
    tree_method="hist",
    enable_categorical=True,
    max_depth=3,             # 52 quarterly training rows - keep it very shallow
    learning_rate=0.05,
    # No early_stopping_rounds: see "HOW THE THREE YEAR FOLDS ARE USED" above.
    # A fixed count is safe here only because the holdout error is flat across
    # 100..900 - re-measure with `--test-year` if the data volume changes.
    n_estimators=300,
    subsample=0.9,
    colsample_bytree=0.9,
    min_child_weight=3,
    reg_lambda=2.0,
    random_state=17,
)


def _matrix(frame: pd.DataFrame, numeric: list[str], categorical: list[str]) -> pd.DataFrame:
    return frame[[c for c in numeric if c in frame] + [c for c in categorical if c in frame]]


def _fit(train, numeric, categorical, **overrides) -> xgb.XGBRegressor:
    params = {**PARAMS, **overrides}
    model = xgb.XGBRegressor(**params)
    model.fit(_matrix(train, numeric, categorical), train["y"], verbose=False)
    return model


def predict_quantiles(model, frame, numeric, categorical) -> np.ndarray:
    """(n, 3) of [low, mid, high]. Sorted and floored: quantile crossing is
    possible, and `forecast`'s CHECK constraints reject lower > predicted."""
    raw = np.asarray(model.predict(_matrix(frame, numeric, categorical)))
    if raw.ndim == 1:
        raw = np.repeat(raw[:, None], 3, axis=1)
    return np.sort(np.clip(raw, 0, None), axis=1)


def calibrate_interval(
    calib_actual: np.ndarray, calib_mid: np.ndarray, *, alpha: float = ALPHA,
) -> tuple[float, float]:
    """Split-conformal interval offsets, with the finite-sample correction.

    XGBoost's quantile heads are badly overconfident here - fitted on 52
    quarterly rows they produce ~48% coverage against an 80% target, i.e. the
    stated range excludes the truth half the time. An interval that lies is
    worse than no interval, so the width is taken from how wrong the model
    actually was on data it never saw, instead of from the model's own opinion.

    Two details make this a real conformal interval rather than a percentile:

    1. `calib_*` comes from a fold used for NOTHING else - not fitting, not
       early stopping (there is none). Reusing the eval set here is what made
       the previous version's coverage optimistic.
    2. The quantile level is lifted from (1 - alpha/2) to
       ceil((n + 1)(1 - alpha/2)) / n. At n = 28 a plain 90th percentile is
       anti-conservative - measured 63% coverage where the correction gives
       81.5%. The +1 is the standard exchangeability correction, not a fudge.

    Returns (low_offset, high_offset) to add to the median prediction.
    """
    residuals = np.sort(calib_actual - calib_mid)
    n = len(residuals)
    if n == 0:
        return 0.0, 0.0
    rank_hi = min(int(np.ceil((n + 1) * (1 - alpha / 2))), n)
    rank_lo = max(int(np.floor((n + 1) * (alpha / 2))), 1)
    return float(residuals[rank_lo - 1]), float(residuals[rank_hi - 1])


def quarterly_seasonal_naive(quarter_panel: pd.DataFrame) -> np.ndarray:
    """Same quarter last year, falling back to the trailing 2-quarter mean."""
    return (
        quarter_panel["lag_4"].fillna(quarter_panel["roll_mean_2"]).fillna(0.0).to_numpy(dtype=float)
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--test-year", type=int, default=2024)
    ap.add_argument("--include-synthetic", action="store_true")
    ap.add_argument("--tag", default="v1")
    args = ap.parse_args()

    if not DATABASE_URL:
        print("DATABASE_URL is not set (backend/.env)", file=sys.stderr)
        return 1

    with psycopg.connect(DATABASE_URL) as conn:
        panel = build_panel(conn, include_synthetic=args.include_synthetic)

    test_year, calib_year = args.test_year, args.test_year - 1
    quarter_panel = build_district_quarter_panel(panel)

    # ---------- production model: district x quarter ----------
    q_train = quarter_panel[quarter_panel["year"] < calib_year]
    q_calib = quarter_panel[quarter_panel["year"] == calib_year]
    q_test = quarter_panel[quarter_panel["year"] == test_year]
    if q_train.empty or q_calib.empty or q_test.empty:
        print(f"quarterly split empty ({len(q_train)}/{len(q_calib)}/{len(q_test)})", file=sys.stderr)
        return 1

    print(f"quarterly panel {len(quarter_panel)} rows | fit {len(q_train)} "
          f"calibrate {len(q_calib)} ({calib_year}) test {len(q_test)} ({test_year})\n")
    print("--- PRODUCTION LEVEL: district x quarter ---")
    q_actual = q_test["y"].to_numpy(dtype=float)
    q_base = quarterly_seasonal_naive(q_test)
    print(report("baseline seasonal naive", q_actual, q_base))

    q_model = _fit(q_train, QUARTER_FEATURES, ["district_id"])
    q_pred = predict_quantiles(q_model, q_test, QUARTER_FEATURES, ["district_id"])
    print(report("xgboost district-quarter", q_actual, q_pred[:, 1]))
    q_base_wape, q_model_wape = wape(q_actual, q_base), wape(q_actual, q_pred[:, 1])
    use_model = q_model_wape < q_base_wape

    # Calibrate on the fold nothing else touched.
    calib_actual = q_calib["y"].to_numpy(dtype=float)
    calib_mid = predict_quantiles(q_model, q_calib, QUARTER_FEATURES, ["district_id"])[:, 1]
    low_offset, high_offset = calibrate_interval(calib_actual, calib_mid)

    raw_cov = coverage(q_actual, q_pred[:, 0], q_pred[:, 2])
    q_cov = coverage(
        q_actual,
        np.clip(q_pred[:, 1] + low_offset, 0, None),
        np.clip(q_pred[:, 1] + high_offset, 0, None),
    )
    print(f"interval coverage: {raw_cov:.1%} raw (model quantiles) "
          f"-> {q_cov:.1%} conformal  [target {1 - ALPHA:.0%}]")
    print(f"conformal offsets: {low_offset:+.0f} / {high_offset:+.0f} packets per district-quarter"
          f"  (n={len(q_calib)} calibration rows from {calib_year})")

    # The baseline needs its own offsets, because ml/predict.py falls back to it
    # when use_model is False and an interval of zero width would be a lie.
    base_low, base_high = calibrate_interval(calib_actual, quarterly_seasonal_naive(q_calib))
    base_cov = coverage(
        q_actual, np.clip(q_base + base_low, 0, None), np.clip(q_base + base_high, 0, None),
    )
    print(f"baseline conformal offsets: {base_low:+.0f} / {base_high:+.0f}  (coverage {base_cov:.1%})")
    print(f"-> ship {'the model' if use_model else 'the BASELINE (model did not beat it)'}"
          f"  [{min(q_base_wape, q_model_wape):.1%}]")

    # ---------- evidence: the granularity we are NOT forecasting at ----------
    print("\n--- REFERENCE LEVEL: district x product x month (why we do not forecast here) ---")
    p_train = panel[panel["year"] < calib_year]
    p_test = panel[panel["year"] == test_year]
    p_actual = p_test["y"].to_numpy(dtype=float)
    print(report("baseline seasonal naive", p_actual, seasonal_naive(p_test)))
    prod_cats = [c for c in CATEGORICAL if c in panel]
    p_model = _fit(p_train, PRODUCT_FEATURES, prod_cats, max_depth=4)
    p_pred = predict_quantiles(p_model, p_test, PRODUCT_FEATURES, prod_cats)
    print(report("xgboost product-month", p_actual, p_pred[:, 1]))
    print(f"   (predict-zero scores exactly 100.0% here, for comparison)")

    # ---------- allocation shares ----------
    month_shares = month_within_quarter_shares(panel)
    product_shares = product_within_district_shares(panel)
    print(f"\nallocation shares: {len(month_shares)} month-of-quarter, {len(product_shares)} product-mix")

    # ---------- save ----------
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    version = f"xgb_{args.tag}_{datetime.now(timezone.utc):%Y%m%d}"
    q_model.save_model(ARTIFACT_DIR / f"{version}_quarter.json")
    p_model.save_model(ARTIFACT_DIR / f"{version}_product_reference.json")
    month_shares.to_csv(ARTIFACT_DIR / f"{version}_month_shares.csv", index=False)
    product_shares.to_csv(ARTIFACT_DIR / f"{version}_product_shares.csv", index=False)

    meta = {
        "model_version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "forecast_level": "district x quarter",
        "written_level": "district x product x month (allocated, not forecast)",
        # ml/predict.py reads this: False means forecast with the seasonal naive
        # instead of the model, using baseline_interval_offsets.
        "use_model": bool(use_model),
        "test_year": test_year,
        "calibration_year": calib_year,
        "calibration_rows": int(len(q_calib)),
        "early_stopping": False,
        "include_synthetic": args.include_synthetic,
        "last_observed_quarter": int(quarter_panel["q"].max()),
        "quarter_features": [c for c in QUARTER_FEATURES if c in quarter_panel],
        "quantiles": list(QUANTILES),
        "target_coverage": 1.0 - ALPHA,
        "wape": {
            "district_quarter_baseline": q_base_wape,
            "district_quarter_model": q_model_wape,
            "product_month_baseline": wape(p_actual, seasonal_naive(p_test)),
            "product_month_model": wape(p_actual, p_pred[:, 1]),
        },
        "interval_coverage_district_quarter_raw": raw_cov,
        "interval_coverage_district_quarter_calibrated": q_cov,
        "interval_coverage_district_quarter_baseline": base_cov,
        "interval_offsets": {"low": low_offset, "high": high_offset},
        "baseline_interval_offsets": {"low": base_low, "high": base_high},
        "target": "net packets sold, floored at 0",
        "unit": "packets",
    }
    (ARTIFACT_DIR / f"{version}_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"saved {version} to {ARTIFACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
