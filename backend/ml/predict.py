"""Job 1, steps 9-10: forecast forward, allocate, write the `forecast` table.

WHAT THIS WRITES
    One row per (district, product, year, month) with predicted_demand,
    lower_bound, upper_bound, confidence, model_version. crop_id is NULL -
    this is total input demand, not per-crop.

HOW THE NUMBER IS PRODUCED
    1. A trained model forecasts district x quarter (the only level with real
       signal - see ml/train.py's docstring).
    2. The quarter is split across its months by historical month-of-quarter
       share, then across products by historical product-mix share.
    So every row written is an ALLOCATION of a forecast. `confidence` carries
    the word "Allocated" on every row so no consumer can mistake it for a
    direct per-product prediction.

FUTURE FEATURES
    Forecasting forward needs feature values that do not exist yet:
      lags        - generated recursively (predict Q, feed it in as Q+1's lag)
      weather     - climatological mean for that district+quarter across all
                    seeded years; there is no weather forecast source wired up
      crops_sown  - from crop_calendar, which is static per district+month
      intent      - carried forward from the most recent year that has any
    Recursive lags compound error, so confidence degrades with horizon, and the
    label says which bucket each row landed in.

HORIZON WARNING
    Sales data ends 2024-12. Anything requested for 2026 is therefore a
    7-8 quarter extrapolation and is labelled "Allocated: Very Low".

Usage:
    .venv/bin/python ml/predict.py                 # dry run, writes nothing
    .venv/bin/python ml/predict.py --write         # actually writes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
import xgboost as xgb

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL  # noqa: E402
from ml.features import LAGS_Q, ROLL_WINDOWS_Q, build_district_quarter_panel, build_panel  # noqa: E402
from ml.train import QUARTER_FEATURES, predict_quantiles  # noqa: E402

ARTIFACT_DIR = BACKEND_DIR / "ml" / "artifacts"

# forecast.confidence is VARCHAR(30), so these have to stay short. The word
# "Allocated" is the load-bearing part - it says the row is a split of a
# coarser forecast, not a prediction at this granularity.
def confidence_label(quarters_ahead: int) -> str:
    if quarters_ahead <= 2:
        return "Allocated: Moderate"
    if quarters_ahead <= 4:
        return "Allocated: Low"
    return "Allocated: Very Low"


def latest_version() -> str:
    metas = sorted(ARTIFACT_DIR.glob("*_meta.json"))
    if not metas:
        raise SystemExit("no artifacts found - run ml/train.py first")
    return json.loads(metas[-1].read_text())["model_version"]


def load_artifacts(version: str) -> tuple[xgb.XGBRegressor, pd.DataFrame, pd.DataFrame, dict]:
    meta = json.loads((ARTIFACT_DIR / f"{version}_meta.json").read_text())
    model = xgb.XGBRegressor()
    model.load_model(ARTIFACT_DIR / f"{version}_quarter.json")
    month_shares = pd.read_csv(ARTIFACT_DIR / f"{version}_month_shares.csv")
    product_shares = pd.read_csv(ARTIFACT_DIR / f"{version}_product_shares.csv")
    return model, month_shares, product_shares, meta


def climatology(conn: psycopg.Connection) -> pd.DataFrame:
    """Per district+quarter weather and sowing breadth, averaged over all seeded
    years. Stands in for a weather forecast, which this project does not have -
    weather_forecast is empty and no API is wired up."""
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH q AS (
                SELECT district_id, year, (month - 1) / 3 + 1 AS quarter,
                       sum(rainfall_mm) AS rain, avg(temperature_c) AS temp, avg(humidity_pct) AS hum
                FROM weather_history GROUP BY 1, 2, 3
            )
            SELECT district_id, quarter, avg(rain), avg(temp), avg(hum)
            FROM q GROUP BY 1, 2
            """,
        )
        weather = pd.DataFrame(cur.fetchall(),
                              columns=["district_id", "quarter", "rainfall_mm", "temperature_c", "humidity_pct"])
        cur.execute(
            """
            SELECT district_id, (month - 1) / 3 + 1 AS quarter, count(DISTINCT crop_id) AS crops_sown
            FROM crop_calendar WHERE expected_usage GROUP BY 1, 2
            """,
        )
        calendar = pd.DataFrame(cur.fetchall(), columns=["district_id", "quarter", "crops_sown"])
    out = weather.merge(calendar, on=["district_id", "quarter"], how="outer")
    for col in ("rainfall_mm", "temperature_c", "humidity_pct", "crops_sown"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype(float)
    return out


def forecast_quarters(
    model: xgb.XGBRegressor,
    quarter_panel: pd.DataFrame,
    clim: pd.DataFrame,
    *,
    through_year: int,
    offsets: tuple[float, float],
) -> pd.DataFrame:
    """Roll the model forward one quarter at a time, per district, feeding each
    prediction back in as the next quarter's lag."""
    low_offset, high_offset = offsets
    last_q = int(quarter_panel["q"].max())
    target_q = through_year * 4 + 3
    if target_q <= last_q:
        raise SystemExit(f"through-year {through_year} is not beyond the last observed quarter")

    rows = []
    for district_id in quarter_panel["district_id"].cat.categories:
        history = (
            quarter_panel[quarter_panel["district_id"] == district_id]
            .sort_values("q")[["q", "y"]]
            .set_index("q")["y"]
            .to_dict()
        )
        # carry the latest known declared acreage forward
        district_rows = quarter_panel[quarter_panel["district_id"] == district_id].sort_values("q")
        intent_acres = district_rows["intent_acres"].dropna().iloc[-1] if district_rows["intent_acres"].notna().any() else np.nan
        intent_rows_v = district_rows["intent_rows"].dropna().iloc[-1] if district_rows["intent_rows"].notna().any() else np.nan

        for q in range(last_q + 1, target_q + 1):
            year, quarter = q // 4, q % 4 + 1
            clim_row = clim[(clim["district_id"] == district_id) & (clim["quarter"] == quarter)]
            feature = {
                "quarter": quarter,
                "quarter_sin": np.sin(2 * np.pi * quarter / 4),
                "quarter_cos": np.cos(2 * np.pi * quarter / 4),
                "rainfall_mm": float(clim_row["rainfall_mm"].iloc[0]) if len(clim_row) else np.nan,
                "temperature_c": float(clim_row["temperature_c"].iloc[0]) if len(clim_row) else np.nan,
                "humidity_pct": float(clim_row["humidity_pct"].iloc[0]) if len(clim_row) else np.nan,
                "crops_sown": float(clim_row["crops_sown"].iloc[0]) if len(clim_row) else np.nan,
                "intent_acres": intent_acres,
                "intent_rows": intent_rows_v,
                "district_id": district_id,
            }
            for lag in LAGS_Q:
                feature[f"lag_{lag}"] = history.get(q - lag, np.nan)
            for window in ROLL_WINDOWS_Q:
                prior = [history[q - k] for k in range(1, window + 1) if q - k in history]
                feature[f"roll_mean_{window}"] = float(np.mean(prior)) if prior else np.nan

            frame = pd.DataFrame([feature])
            frame["district_id"] = pd.Categorical(
                frame["district_id"], categories=quarter_panel["district_id"].cat.categories,
            )
            mid = float(predict_quantiles(model, frame, QUARTER_FEATURES, ["district_id"])[0, 1])
            history[q] = mid  # recursive: this prediction becomes the next lag

            rows.append(
                {
                    "district_id": district_id,
                    "year": year,
                    "quarter": quarter,
                    "q": q,
                    "quarters_ahead": q - last_q,
                    "q_mid": mid,
                    "q_low": max(0.0, mid + low_offset),
                    "q_high": max(0.0, mid + high_offset),
                },
            )
    return pd.DataFrame(rows)


def allocate(quarterly: pd.DataFrame, month_shares: pd.DataFrame, product_shares: pd.DataFrame) -> pd.DataFrame:
    """quarter -> month -> product. Shares are renormalised so the split always
    sums back to the quarterly total instead of quietly losing volume."""
    monthly = quarterly.merge(month_shares, on=["district_id", "quarter"], how="left")
    monthly["month_share"] = monthly["month_share"].fillna(1 / 3)
    monthly["month_share"] /= monthly.groupby(["district_id", "q"])["month_share"].transform("sum")

    rows = monthly.merge(product_shares, on="district_id", how="inner")
    rows["product_share"] /= rows.groupby(["district_id", "q", "month"])["product_share"].transform("sum")

    weight = rows["month_share"] * rows["product_share"]
    for src, dst in (("q_mid", "predicted_demand"), ("q_low", "lower_bound"), ("q_high", "upper_bound")):
        rows[dst] = (rows[src] * weight).round(3)
    rows["confidence"] = rows["quarters_ahead"].map(confidence_label)
    # CHECK constraints on `forecast` reject lower > predicted > upper.
    rows["lower_bound"] = np.minimum(rows["lower_bound"], rows["predicted_demand"])
    rows["upper_bound"] = np.maximum(rows["upper_bound"], rows["predicted_demand"])
    return rows[rows["predicted_demand"] > 0][
        ["district_id", "product_id", "year", "month", "predicted_demand",
         "lower_bound", "upper_bound", "confidence"]
    ]


def write_forecast(conn: psycopg.Connection, rows: pd.DataFrame, version: str) -> int:
    """Delete-then-insert, in one transaction.

    NOT ON CONFLICT: forecast's UNIQUE covers crop_id, which is NULL for every
    row here, and Postgres treats NULLs as distinct - so ON CONFLICT would
    never fire and a second nightly run would silently double every row.
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM forecast WHERE model_version = %s", (version,))
        deleted = cur.rowcount
        cur.executemany(
            """
            INSERT INTO forecast (district_id, product_id, crop_id, year, month,
                                  predicted_demand, lower_bound, upper_bound, confidence, model_version)
            VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (int(r.district_id), int(r.product_id), int(r.year), int(r.month),
                 float(r.predicted_demand), float(r.lower_bound), float(r.upper_bound),
                 r.confidence, version)
                for r in rows.itertuples()
            ],
        )
    # No commit here on purpose: the caller owns the transaction, so tests can
    # run the whole chain inside one and roll it back.
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--through-year", type=int, default=2026)
    ap.add_argument("--version", help="artifact version (default: newest)")
    ap.add_argument("--write", action="store_true", help="write to the forecast table (default: dry run)")
    args = ap.parse_args()

    if not DATABASE_URL:
        print("DATABASE_URL is not set (backend/.env)", file=sys.stderr)
        return 1

    version = args.version or latest_version()
    model, month_shares, product_shares, meta = load_artifacts(version)
    offsets = (meta["interval_offsets"]["low"], meta["interval_offsets"]["high"])
    print(f"model {version}  forecast level: {meta['forecast_level']}")
    print(f"  district-quarter WAPE {meta['wape']['district_quarter_model']:.1%} "
          f"(baseline {meta['wape']['district_quarter_baseline']:.1%}), "
          f"interval coverage {meta['interval_coverage_district_quarter_calibrated']:.1%}\n")

    with psycopg.connect(DATABASE_URL) as conn:
        panel = build_panel(conn)
        quarter_panel = build_district_quarter_panel(panel)
        clim = climatology(conn)

        quarterly = forecast_quarters(model, quarter_panel, clim,
                                      through_year=args.through_year, offsets=offsets)
        rows = allocate(quarterly, month_shares, product_shares)

        last_q = int(quarter_panel["q"].max())
        print(f"last observed quarter: {last_q // 4}-Q{last_q % 4 + 1}")
        print(f"forecast horizon     : through {args.through_year}-Q4 "
              f"({quarterly['quarters_ahead'].max()} quarters ahead)\n")
        print("district-quarter forecast (packets):")
        pivot = quarterly.pivot_table(index=["year", "quarter"], values=["q_low", "q_mid", "q_high"], aggfunc="sum")
        for (year, quarter), r in pivot.iterrows():
            print(f"  {year}-Q{quarter}   {r['q_mid']:>9,.0f}   [{r['q_low']:>9,.0f} .. {r['q_high']:>9,.0f}]")
        print(f"\nallocated to {len(rows):,} district x product x month rows")
        print(f"confidence mix: {dict(rows['confidence'].value_counts())}")

        if args.write:
            deleted = write_forecast(conn, rows, version)
            conn.commit()
            print(f"\nwrote {len(rows):,} rows to forecast (replaced {deleted:,} for {version})")
        else:
            print("\nDRY RUN - nothing written. Re-run with --write to persist.")
            print(rows.head(8).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
