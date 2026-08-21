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
    max_depth=3,             # 27 quarterly training rows - keep it very shallow
    learning_rate=0.05,
    n_estimators=600,
    subsample=0.9,
    colsample_bytree=0.9,
    min_child_weight=3,
    reg_lambda=2.0,
    early_stopping_rounds=50,
    random_state=17,
)


def _matrix(frame: pd.DataFrame, numeric: list[str], categorical: list[str]) -> pd.DataFrame:
    return frame[[c for c in numeric if c in frame] + [c for c in categorical if c in frame]]


def _fit(train, valid, numeric, categorical, **overrides) -> xgb.XGBRegressor:
    params = {**PARAMS, **overrides}
    model = xgb.XGBRegressor(**params)
    model.fit(
        _matrix(train, numeric, categorical),
        train["y"],
        eval_set=[(_matrix(valid, numeric, categorical), valid["y"])],
        verbose=False,
    )
    return model


def predict_quantiles(model, frame, numeric, categorical) -> np.ndarray:
    """(n, 3) of [low, mid, high]. Sorted and floored: quantile crossing is
    possible, and `forecast`'s CHECK constraints reject lower > predicted."""
    raw = np.asarray(model.predict(_matrix(frame, numeric, categorical)))
    if raw.ndim == 1:
        raw = np.repeat(raw[:, None], 3, axis=1)
    return np.sort(np.clip(raw, 0, None), axis=1)


def calibrate_interval(valid_actual: np.ndarray, valid_mid: np.ndarray) -> tuple[float, float]:
    """Empirical (split-conformal style) interval offsets.

    XGBoost's quantile heads are badly overconfident here - fitted on ~50
    quarterly rows they produced 40.7% coverage against an 80% target, i.e. the
    stated range excluded the truth 6 times out of 10. An interval that lies is
    worse than no interval, so the width is taken from how wrong the model
    actually was on held-out data instead of from the model's own opinion.

    Returns (low_offset, high_offset) to add to the median prediction.

    Caveat: the validation year is also what early stopping used, so these
    offsets are mildly optimistic. With 52 training rows that trade is worth
    making; revisit with a dedicated calibration split once there is more data.
    """
    residuals = valid_actual - valid_mid
    return float(np.percentile(residuals, 10)), float(np.percentile(residuals, 90))


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

    test_year, valid_year = args.test_year, args.test_year - 1
    quarter_panel = build_district_quarter_panel(panel)

    # ---------- production model: district x quarter ----------
    q_train = quarter_panel[quarter_panel["year"] < valid_year]
    q_valid = quarter_panel[quarter_panel["year"] == valid_year]
    q_test = quarter_panel[quarter_panel["year"] == test_year]
    if q_train.empty or q_valid.empty or q_test.empty:
        print(f"quarterly split empty ({len(q_train)}/{len(q_valid)}/{len(q_test)})", file=sys.stderr)
        return 1

    print(f"quarterly panel {len(quarter_panel)} rows | train {len(q_train)} "
          f"valid {len(q_valid)} test {len(q_test)}\n")
    print("--- PRODUCTION LEVEL: district x quarter ---")
    q_actual = q_test["y"].to_numpy(dtype=float)
    q_base = quarterly_seasonal_naive(q_test)
    print(report("baseline seasonal naive", q_actual, q_base))

    q_model = _fit(q_train, q_valid, QUARTER_FEATURES, ["district_id"])
    q_pred = predict_quantiles(q_model, q_test, QUARTER_FEATURES, ["district_id"])
    print(report("xgboost district-quarter", q_actual, q_pred[:, 1]))
    q_base_wape, q_model_wape = wape(q_actual, q_base), wape(q_actual, q_pred[:, 1])

    raw_cov = coverage(q_actual, q_pred[:, 0], q_pred[:, 2])
    valid_mid = predict_quantiles(q_model, q_valid, QUARTER_FEATURES, ["district_id"])[:, 1]
    low_offset, high_offset = calibrate_interval(q_valid["y"].to_numpy(dtype=float), valid_mid)
    cal_low = np.clip(q_pred[:, 1] + low_offset, 0, None)
    cal_high = np.clip(q_pred[:, 1] + high_offset, 0, None)
    q_cov = coverage(q_actual, cal_low, cal_high)
    print(f"interval coverage: {raw_cov:.1%} raw (model quantiles) "
          f"-> {q_cov:.1%} calibrated  [target ~80%]")
    print(f"calibrated offsets: {low_offset:+.0f} / {high_offset:+.0f} packets per district-quarter")
    use_model = q_model_wape < q_base_wape
    print(f"-> ship {'the model' if use_model else 'the BASELINE (model did not beat it)'}"
          f"  [{min(q_base_wape, q_model_wape):.1%}]")

    # ---------- evidence: the granularity we are NOT forecasting at ----------
    print("\n--- REFERENCE LEVEL: district x product x month (why we do not forecast here) ---")
    p_train = panel[panel["year"] < valid_year]
    p_valid = panel[panel["year"] == valid_year]
    p_test = panel[panel["year"] == test_year]
    p_actual = p_test["y"].to_numpy(dtype=float)
    print(report("baseline seasonal naive", p_actual, seasonal_naive(p_test)))
    prod_cats = [c for c in CATEGORICAL if c in panel]
    p_model = _fit(p_train, p_valid, PRODUCT_FEATURES, prod_cats, max_depth=4)
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
        "use_model": bool(use_model),
        "test_year": test_year,
        "include_synthetic": args.include_synthetic,
        "last_observed_quarter": int(quarter_panel["q"].max()),
        "quarter_features": [c for c in QUARTER_FEATURES if c in quarter_panel],
        "quantiles": list(QUANTILES),
        "wape": {
            "district_quarter_baseline": q_base_wape,
            "district_quarter_model": q_model_wape,
            "product_month_baseline": wape(p_actual, seasonal_naive(p_test)),
            "product_month_model": wape(p_actual, p_pred[:, 1]),
        },
        "interval_coverage_district_quarter_raw": raw_cov,
        "interval_coverage_district_quarter_calibrated": q_cov,
        "interval_offsets": {"low": low_offset, "high": high_offset},
        "target": "net packets sold, floored at 0",
        "unit": "packets",
    }
    (ARTIFACT_DIR / f"{version}_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"saved {version} to {ARTIFACT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
