"""Job 1, step 1-2: build the training panel for the fertilizer-demand forecast.

One row per (district, product, month). Target is net packets sold that month.

Four decisions worth knowing, because the data forced them:

1. ACTUAL rows only, by default. historical_sales also holds 7,344 SYNTHETIC
   rows for 2015-2019, but those were generated *from* a pattern — training on
   them teaches the model the generator, not the market. --include-synthetic
   exists so you can measure that claim rather than trust it.

2. The 4 bulk products (Urea/DAP/MOP/NPK, ids 26-29) are dropped. They were
   added to `products` for dashboard parity and have zero real sales, so there
   is nothing to learn. The JOIN in PRODUCT_SQL removes them automatically.

3. Zero-fill happens *within* each series' observed span, not across the whole
   7x25x60 grid. The full grid is 86% empty (1,466 real cells out of 10,500):
   most of that emptiness is "this product is not stocked in this district",
   which is not a demand observation. Filling it would drown the signal in
   9,000 fabricated zeros. Filling only between a series' first and last real
   sale keeps the honest "no demand this month" zeros.

4. The target is floored at 0. 100 monthly cells go net-negative (down to
   -1,614) because returns and credit notes outweighed sales that month. A
   negative demand forecast is meaningless downstream — recommended_dispatch
   would ask you to ship negative stock — so those months count as zero demand.
   The raw signed value is kept in `net_qty_raw` for diagnostics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL  # noqa: E402

LAGS = (1, 2, 3, 12)
ROLL_WINDOWS = (3, 6, 12)

# Quarterly equivalents: lag 1 = last quarter, lag 4 = same quarter last year.
LAGS_Q = (1, 2, 4)
ROLL_WINDOWS_Q = (2, 4)

# Categorical columns handed to XGBoost's native categorical support.
CATEGORICAL = ["district_id", "product_id", "category", "form", "fertilizer_type", "product_type"]

SALES_SQL = """
    SELECT district_id, product_id, year_start AS year, month, sum(qty_in_pkts) AS net_qty_raw
    FROM historical_sales
    WHERE qty_in_pkts IS NOT NULL AND data_source = ANY(%(sources)s)
    GROUP BY 1, 2, 3, 4
"""

WEATHER_SQL = """
    SELECT district_id, year, month, rainfall_mm, temperature_c, humidity_pct
    FROM weather_history
"""

# INNER JOIN drops products with no real sales — see decision 2 in the docstring.
# category/form live on the transaction, not the product, so take the modal value.
PRODUCT_SQL = """
    SELECT p.id AS product_id, p.product_type, p.fertilizer_type, p.shelf_life_days,
           mode() WITHIN GROUP (ORDER BY hs.category) AS category,
           mode() WITHIN GROUP (ORDER BY hs.form)     AS form
    FROM products p
    JOIN historical_sales hs ON hs.product_id = p.id AND hs.data_source = 'ACTUAL'
    GROUP BY p.id, p.product_type, p.fertilizer_type, p.shelf_life_days
"""

# How many crops the calendar says are sown in this district this month — a
# proxy for how much field activity (and therefore input demand) to expect.
CALENDAR_SQL = """
    SELECT district_id, month, count(DISTINCT crop_id) AS crops_sown
    FROM crop_calendar
    WHERE expected_usage
    GROUP BY 1, 2
"""

# Declared acreage. Only covers 2023+, so it is NaN for most of the panel —
# left as NaN on purpose; XGBoost splits on missingness natively.
INTENT_SQL = """
    SELECT district_id, year, sum(land_area_acres) AS intent_acres, count(*) AS intent_rows
    FROM farmer_crop_intent
    GROUP BY 1, 2
"""


def _read(conn: psycopg.Connection, sql: str, params: dict | None = None) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def _to_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    """psycopg returns NUMERIC as Decimal; XGBoost needs float."""
    for c in cols:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)


def build_panel(conn: psycopg.Connection, *, include_synthetic: bool = False) -> pd.DataFrame:
    sources = ["ACTUAL", "SYNTHETIC"] if include_synthetic else ["ACTUAL"]

    sales = _read(conn, SALES_SQL, {"sources": sources})
    weather = _read(conn, WEATHER_SQL)
    products = _read(conn, PRODUCT_SQL)
    calendar = _read(conn, CALENDAR_SQL)
    intent = _read(conn, INTENT_SQL)

    _to_numeric(sales, ["net_qty_raw"])
    _to_numeric(weather, ["rainfall_mm", "temperature_c", "humidity_pct"])
    _to_numeric(intent, ["intent_acres"])
    _to_numeric(products, ["shelf_life_days"])

    sales = sales[sales["product_id"].isin(products["product_id"])]

    # Absolute month index, so reindexing and lags are plain integer arithmetic.
    sales["t"] = sales["year"] * 12 + (sales["month"] - 1)

    # Decision 3: dense within each series' own span, nothing outside it.
    frames = []
    for (district_id, product_id), grp in sales.groupby(["district_id", "product_id"], sort=False):
        full_t = np.arange(grp["t"].min(), grp["t"].max() + 1)
        frames.append(
            pd.DataFrame({"district_id": district_id, "product_id": product_id, "t": full_t})
            .merge(grp[["t", "net_qty_raw"]], on="t", how="left"),
        )
    panel = pd.concat(frames, ignore_index=True)
    panel["net_qty_raw"] = panel["net_qty_raw"].fillna(0.0)
    panel["year"] = panel["t"] // 12
    panel["month"] = panel["t"] % 12 + 1

    # Decision 4: floor the target, keep the signed value for diagnostics.
    panel["y"] = panel["net_qty_raw"].clip(lower=0.0)

    panel = panel.merge(weather, on=["district_id", "year", "month"], how="left")
    panel = panel.merge(products, on="product_id", how="left")
    panel = panel.merge(calendar, on=["district_id", "month"], how="left")
    panel = panel.merge(intent, on=["district_id", "year"], how="left")

    # Seasonality as a smooth cycle, so December and January sit next to each
    # other instead of 11 apart.
    panel["month_sin"] = np.sin(2 * np.pi * panel["month"] / 12)
    panel["month_cos"] = np.cos(2 * np.pi * panel["month"] / 12)

    panel = panel.sort_values(["district_id", "product_id", "t"]).reset_index(drop=True)
    grouped = panel.groupby(["district_id", "product_id"], sort=False)["y"]

    for lag in LAGS:
        panel[f"lag_{lag}"] = grouped.shift(lag)
    for window in ROLL_WINDOWS:
        # shift(1) before rolling: month t must never see its own value.
        # transform keeps the window inside one series.
        panel[f"roll_mean_{window}"] = grouped.transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean(),
        )

    # Aggregation key for the two-level forecast: category is far denser than
    # product, so the model is fit there and split down afterwards.
    panel["series_category"] = panel["category"].fillna("UNKNOWN")

    for col in CATEGORICAL:
        panel[col] = panel[col].astype("category")

    return panel


def summarise(panel: pd.DataFrame) -> str:
    n_series = panel.groupby(["district_id", "product_id"], observed=True).ngroups
    zero_share = (panel["y"] == 0).mean()
    return "\n".join(
        [
            f"rows                : {len(panel):,}",
            f"series (dist x prod): {n_series}",
            f"months              : {panel['t'].min() // 12}-{panel['t'].min() % 12 + 1}"
            f" .. {panel['t'].max() // 12}-{panel['t'].max() % 12 + 1}",
            f"target zero share   : {zero_share:.1%}",
            f"target mean / max   : {panel['y'].mean():.1f} / {panel['y'].max():.1f}",
            f"negatives floored   : {(panel['net_qty_raw'] < 0).sum()} rows",
            f"lag_12 available    : {panel['lag_12'].notna().mean():.1%} of rows",
            f"intent_acres present: {panel['intent_acres'].notna().mean():.1%} of rows",
        ],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-synthetic", action="store_true", help="also train on the 2015-2019 fabricated rows")
    ap.add_argument("--out", type=Path, help="write the panel to this CSV")
    args = ap.parse_args()

    if not DATABASE_URL:
        print("DATABASE_URL is not set (backend/.env)", file=sys.stderr)
        return 1

    with psycopg.connect(DATABASE_URL) as conn:
        panel = build_panel(conn, include_synthetic=args.include_synthetic)

    print(summarise(panel))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        panel.to_csv(args.out, index=False)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------
# Production forecast level + allocation shares
#
# The product-month panel above is what the `forecast` table wants, but it is
# noise: seasonal-naive WAPE there is 136%, worse than forecasting zero. Signal
# only appears after aggregation (district x quarter = 72%, state x quarter =
# 25%). So the production chain forecasts district x quarter and allocates back
# down, and `forecast.confidence` records which half of each number is which.
# ---------------------------------------------------------------


def build_district_quarter_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Roll the product-month panel up to district x quarter.

    Time features are rebuilt at this level rather than summed: a sum of
    lagged monthly means is not the lagged mean of quarterly sums.
    """
    frame = panel.copy()
    frame["quarter"] = (frame["month"] - 1) // 3 + 1

    volume = (
        frame.groupby(["district_id", "year", "quarter"], observed=True)["y"].sum().rename("y").reset_index()
    )

    # Weather is per (district, year, month) and repeats across products, so
    # de-duplicate before aggregating or the mean is product-count weighted.
    per_month = frame.drop_duplicates(subset=["district_id", "year", "month"])
    exogenous = (
        per_month.groupby(["district_id", "year", "quarter"], observed=True)
        .agg(
            rainfall_mm=("rainfall_mm", "sum"),        # total rain over the quarter
            temperature_c=("temperature_c", "mean"),
            humidity_pct=("humidity_pct", "mean"),
            crops_sown=("crops_sown", "sum"),          # total sowing activity
            intent_acres=("intent_acres", "mean"),
            intent_rows=("intent_rows", "mean"),
        )
        .reset_index()
    )

    agg = volume.merge(exogenous, on=["district_id", "year", "quarter"], how="left")
    agg["q"] = agg["year"] * 4 + (agg["quarter"] - 1)
    agg["quarter_sin"] = np.sin(2 * np.pi * agg["quarter"] / 4)
    agg["quarter_cos"] = np.cos(2 * np.pi * agg["quarter"] / 4)
    agg = agg.sort_values(["district_id", "q"]).reset_index(drop=True)

    grouped = agg.groupby("district_id", observed=True)["y"]
    for lag in LAGS_Q:
        agg[f"lag_{lag}"] = grouped.shift(lag)
    for window in ROLL_WINDOWS_Q:
        agg[f"roll_mean_{window}"] = grouped.transform(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean(),
        )

    agg["district_id"] = agg["district_id"].astype("category")
    return agg


def month_within_quarter_shares(panel: pd.DataFrame, *, lookback_years: int = 2) -> pd.DataFrame:
    """For each district, how a quarter's volume historically splits across its
    three months. Falls back to an even third when a district has no history."""
    frame = panel.copy()
    frame["quarter"] = (frame["month"] - 1) // 3 + 1
    recent = frame[frame["year"] >= frame["year"].max() - (lookback_years - 1)]

    by_month = (
        recent.groupby(["district_id", "quarter", "month"], observed=True)["y"].sum().rename("m_total").reset_index()
    )
    by_quarter = recent.groupby(["district_id", "quarter"], observed=True)["y"].sum().rename("q_total").reset_index()
    shares = by_month.merge(by_quarter, on=["district_id", "quarter"], how="left")
    shares["month_share"] = np.where(shares["q_total"] > 0, shares["m_total"] / shares["q_total"], 1 / 3)
    return shares[["district_id", "quarter", "month", "month_share"]]


def product_within_district_shares(panel: pd.DataFrame, *, lookback_years: int = 2) -> pd.DataFrame:
    """For each district, each product's share of that district's volume.
    Districts with no recent volume split evenly across their known products."""
    recent = panel[panel["year"] >= panel["year"].max() - (lookback_years - 1)]

    by_product = (
        recent.groupby(["district_id", "product_id"], observed=True)["y"].sum().rename("p_total").reset_index()
    )
    by_district = recent.groupby(["district_id"], observed=True)["y"].sum().rename("d_total").reset_index()
    shares = by_product.merge(by_district, on="district_id", how="left")
    counts = shares.groupby("district_id", observed=True)["product_id"].transform("size")
    shares["product_share"] = np.where(
        shares["d_total"] > 0, shares["p_total"] / shares["d_total"], 1.0 / counts,
    )
    return shares[["district_id", "product_id", "product_share"]]
