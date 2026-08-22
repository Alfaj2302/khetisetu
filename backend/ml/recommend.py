"""Job 1, step 10b: turn the forecast into stock actions.

This is arithmetic, not a model, and it should stay that way. It reads the
`forecast` rows written by ml/predict.py plus current `inventory`, and writes
`recommendations` - which is what makes /business/alerts and the dashboard's
recommended_action panel non-empty.

    forecast_quantity     = sum(predicted_demand) over the planning window
    safety_stock          = sum(upper_bound - predicted_demand) over the window
                            i.e. the model's own uncertainty, used as the buffer
                            rather than an invented z-score. If the forecast is
                            vague the buffer is large - which is the point.
    current_stock         = sum(inventory.quantity) for that district+product
    recommended_dispatch  = max(0, forecast + safety - stock)

    action  MANUFACTURE       nothing on hand but demand expected
            DISPATCH          on hand, but short of forecast + buffer
            REDUCE_PRODUCTION sitting on more than twice what is needed
            HOLD              comfortably covered
            MONITOR           no expected demand

TRANSFER is not emitted here - /business/transfers already derives cross-district
moves from inventory and sales, and two systems proposing conflicting moves for
the same stock would be worse than one.

Usage:
    .venv/bin/python ml/recommend.py --year 2026 --quarter 3        # dry run
    .venv/bin/python ml/recommend.py --year 2026 --quarter 3 --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import psycopg

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import DATABASE_URL  # noqa: E402

OVERSTOCK_MULTIPLE = 2.0


def build(conn: psycopg.Connection, *, year: int, quarter: int, version: str | None) -> pd.DataFrame:
    months = [(quarter - 1) * 3 + n for n in (1, 2, 3)]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT f.district_id, f.product_id,
                   sum(f.predicted_demand) AS forecast_qty,
                   sum(coalesce(f.upper_bound, f.predicted_demand) - f.predicted_demand) AS safety,
                   min(f.confidence) AS confidence
            FROM forecast f
            WHERE f.year = %(year)s AND f.month = ANY(%(months)s)
              AND (%(version)s::text IS NULL OR f.model_version = %(version)s::text)
            GROUP BY 1, 2
            """,
            {"year": year, "months": months, "version": version},
        )
        forecast = pd.DataFrame(cur.fetchall(),
                                columns=["district_id", "product_id", "forecast_qty", "safety", "confidence"])
        cur.execute(
            "SELECT district_id, product_id, sum(quantity) AS on_hand FROM inventory GROUP BY 1, 2",
        )
        stock = pd.DataFrame(cur.fetchall(), columns=["district_id", "product_id", "on_hand"])

    if forecast.empty:
        return forecast

    merged = forecast.merge(stock, on=["district_id", "product_id"], how="left")
    for col in ("forecast_qty", "safety", "on_hand"):
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0).astype(float)

    merged["required"] = merged["forecast_qty"] + merged["safety"]
    merged["dispatch"] = (merged["required"] - merged["on_hand"]).clip(lower=0.0).round(1)

    def classify(row) -> str:
        if row["forecast_qty"] <= 0:
            return "MONITOR"
        if row["on_hand"] <= 0:
            return "MANUFACTURE"
        if row["dispatch"] > 0:
            return "DISPATCH"
        if row["on_hand"] > OVERSTOCK_MULTIPLE * row["required"]:
            return "REDUCE_PRODUCTION"
        return "HOLD"

    merged["action"] = merged.apply(classify, axis=1)
    merged["reason"] = merged.apply(
        lambda r: (
            f"Q{quarter} {year}: forecast {r['forecast_qty']:.0f} + buffer {r['safety']:.0f} packets "
            f"vs {r['on_hand']:.0f} on hand -> {r['action'].lower().replace('_', ' ')} "
            f"{r['dispatch']:.0f}. Forecast is an allocation of a district-quarter model "
            f"({r['confidence']}), not a per-product prediction."
        ),
        axis=1,
    )
    return merged


def write(conn: psycopg.Connection, rows: pd.DataFrame) -> int:
    """Rebuild the table wholesale.

    `recommendations` is pure derived output (schema.sql: "written by the batch
    ML job, read by the API") and carries no model_version to scope a delete by,
    so the nightly run replaces it rather than appending. Without this,
    get_recommended_action's ORDER BY created_at DESC LIMIT 1 would slowly walk
    back through every historical run.
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM recommendations")
        deleted = cur.rowcount
        cur.executemany(
            """
            INSERT INTO recommendations (district_id, product_id, forecast_quantity, current_stock,
                                         safety_stock, recommended_dispatch, action, reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (int(r.district_id), int(r.product_id), float(r.forecast_qty), float(r.on_hand),
                 float(r.safety), float(r.dispatch), r.action, r.reason)
                for r in rows.itertuples()
            ],
        )
    # No commit here: caller owns the transaction (see ml/predict.py).
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--quarter", type=int, default=3, choices=(1, 2, 3, 4))
    ap.add_argument("--version", help="only use this model_version's forecast rows")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    if not DATABASE_URL:
        print("DATABASE_URL is not set (backend/.env)", file=sys.stderr)
        return 1

    with psycopg.connect(DATABASE_URL) as conn:
        rows = build(conn, year=args.year, quarter=args.quarter, version=args.version)
        if rows.empty:
            print(f"no forecast rows for {args.year}-Q{args.quarter} - run ml/predict.py --write first")
            return 1

        print(f"planning window: {args.year}-Q{args.quarter}   {len(rows):,} district x product positions\n")
        print(rows["action"].value_counts().to_string())
        print(f"\ntotal dispatch recommended: {rows['dispatch'].sum():,.0f} packets")
        alerts = rows[rows["action"] != "MONITOR"]
        print(f"rows that will surface as alerts (action != MONITOR): {len(alerts):,}\n")
        print(rows.nlargest(5, "dispatch")[
            ["district_id", "product_id", "forecast_qty", "safety", "on_hand", "dispatch", "action"]
        ].to_string(index=False))

        if args.write:
            deleted = write(conn, rows)
            conn.commit()
            print(f"\nwrote {len(rows):,} rows to recommendations (replaced {deleted:,})")
        else:
            print("\nDRY RUN - nothing written. Re-run with --write to persist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
