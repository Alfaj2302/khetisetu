"""Business-dashboard reads.

`forecast` and `recommendations` are batch-ML-job output tables (per
schema.sql's own comments) — nothing here computes a substitute for them
live, so `get_expected_input_demand`, `get_recommended_action`,
`get_forecast`, and `get_alerts` will legitimately return empty until that
job has run at least once. `get_farmer_crop_intent_summary` and
`get_inventory` read tables that already have real seeded data.
`get_transfers` is the one exception: it builds a working comparison from
`inventory` + `historical_sales` so the endpoint is demonstrable before the
real forecast-driven transfer logic exists.
"""

from __future__ import annotations

from typing import Any

from psycopg import Cursor

# Leave this fraction of stock behind in the surplus district rather than
# draining it completely. A fixed absolute buffer (matching the spec's own
# worked example, 900 vs 900 -> 700, i.e. -200) would work for bulk-fertilizer
# quintal quantities but zeroes out every transfer in this dataset, where
# inventory/historical_sales run in the tens-to-hundreds of packets — a
# relative buffer keeps the same "don't fully drain the surplus" intent at
# any scale.
TRANSFER_BUFFER_FRACTION = 0.2


def get_expected_input_demand(cur: Cursor, district_id: int, year: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT p.product_name, sum(f.predicted_demand) AS qty
        FROM forecast f
        JOIN products p ON p.id = f.product_id
        WHERE f.district_id = %s AND f.year = %s
        GROUP BY p.product_name
        ORDER BY qty DESC
        """,
        (district_id, year),
    )
    return [{"product": r[0], "quantity_mt": float(r[1])} for r in cur.fetchall()]


def get_farmer_crop_intent_summary(
    cur: Cursor,
    district_id: int,
    season_id: int,
    year: int,
) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT c.name, sum(fci.land_area_acres) AS acres
        FROM farmer_crop_intent fci
        JOIN crops c ON c.id = fci.crop_id
        WHERE fci.district_id = %s AND fci.season_id = %s AND fci.year = %s
        GROUP BY c.name
        ORDER BY acres DESC
        """,
        (district_id, season_id, year),
    )
    return [{"crop": r[0], "acres": float(r[1]) if r[1] is not None else 0.0} for r in cur.fetchall()]


def get_recommended_action(cur: Cursor, district_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT p.product_name, r.forecast_quantity, r.current_stock, r.safety_stock,
               r.recommended_dispatch, r.action
        FROM recommendations r
        JOIN products p ON p.id = r.product_id
        WHERE r.district_id = %s
        ORDER BY r.created_at DESC
        LIMIT 1
        """,
        (district_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    product, forecast_qty, current_stock, safety_stock, dispatch, action = row
    return {
        "product": product,
        "forecast_mt": float(forecast_qty) if forecast_qty is not None else None,
        "current_stock_mt": float(current_stock) if current_stock is not None else None,
        "safety_stock_mt": float(safety_stock) if safety_stock is not None else None,
        "recommended_dispatch_mt": float(dispatch) if dispatch is not None else None,
        "action": action,
    }


def get_alerts(cur: Cursor, district_id: int | None) -> list[dict[str, Any]]:
    where = "r.action != 'MONITOR'"
    params: tuple = ()
    if district_id is not None:
        where += " AND r.district_id = %s"
        params = (district_id,)
    cur.execute(
        f"""
        SELECT d.name, p.product_name,
               CASE WHEN r.action IN ('DISPATCH', 'MANUFACTURE') THEN 'High' ELSE 'Medium' END,
               r.reason
        FROM recommendations r
        JOIN districts d ON d.id = r.district_id
        JOIN products p ON p.id = r.product_id
        WHERE {where}
        ORDER BY r.created_at DESC
        """,
        params,
    )
    return [
        {
            "district": r[0],
            "product": r[1],
            "severity": r[2],
            "message": r[3] or f"{r[1]} flagged for action in {r[0]}",
        }
        for r in cur.fetchall()
    ]


def get_forecast(
    cur: Cursor,
    district_id: int | None,
    product_id: int | None,
    year: int | None,
) -> list[dict[str, Any]]:
    conditions = ["1 = 1"]
    params: list[int] = []
    if district_id is not None:
        conditions.append("district_id = %s")
        params.append(district_id)
    if product_id is not None:
        conditions.append("product_id = %s")
        params.append(product_id)
    if year is not None:
        conditions.append("year = %s")
        params.append(year)

    cur.execute(
        f"""
        SELECT product_id, year, month, predicted_demand, lower_bound, upper_bound, confidence, model_version
        FROM forecast
        WHERE {" AND ".join(conditions)}
        ORDER BY year, month
        """,
        params,
    )
    return [
        {
            "product_id": r[0],
            "year": r[1],
            "month": r[2],
            "predicted_demand": float(r[3]),
            "lower_bound": float(r[4]) if r[4] is not None else None,
            "upper_bound": float(r[5]) if r[5] is not None else None,
            "confidence": r[6],
            "model_version": r[7],
        }
        for r in cur.fetchall()
    ]


def get_inventory(cur: Cursor, district_id: int | None) -> list[dict[str, Any]]:
    if district_id is not None:
        cur.execute(
            """
            SELECT product_id, quantity, batch_no, manufacturing_date, expiry_date
            FROM inventory WHERE district_id = %s ORDER BY product_id
            """,
            (district_id,),
        )
    else:
        cur.execute(
            "SELECT product_id, quantity, batch_no, manufacturing_date, expiry_date "
            "FROM inventory ORDER BY district_id, product_id",
        )
    return [
        {
            "product_id": r[0],
            "quantity": float(r[1]) if r[1] is not None else None,
            "batch_no": r[2],
            "manufacturing_date": r[3].isoformat() if r[3] else None,
            "expiry_date": r[4].isoformat() if r[4] else None,
        }
        for r in cur.fetchall()
    ]


def get_transfers(cur: Cursor) -> list[dict[str, Any]]:
    cur.execute("SELECT id, name FROM districts")
    district_names = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute(
        """
        WITH expected_monthly AS (
            SELECT district_id, product_id, avg(qty_in_pkts) AS avg_monthly_qty
            FROM historical_sales
            WHERE qty_in_pkts IS NOT NULL
            GROUP BY district_id, product_id
        ),
        position AS (
            SELECT i.district_id, i.product_id,
                   sum(i.quantity) AS on_hand,
                   coalesce(e.avg_monthly_qty, 0) AS expected_monthly_qty
            FROM inventory i
            LEFT JOIN expected_monthly e
                ON e.district_id = i.district_id AND e.product_id = i.product_id
            GROUP BY i.district_id, i.product_id, e.avg_monthly_qty
        )
        SELECT district_id, product_id, on_hand, expected_monthly_qty FROM position
        """,
    )

    by_product: dict[int, list[tuple[int, float, float]]] = {}
    for district_id, product_id, on_hand, expected in cur.fetchall():
        by_product.setdefault(product_id, []).append((district_id, float(on_hand or 0), float(expected or 0)))

    transfers: list[dict[str, Any]] = []
    for product_id, positions in by_product.items():
        shortages = sorted(
            ((d, expected - on_hand) for d, on_hand, expected in positions if expected - on_hand > 0),
            key=lambda item: item[1],
            reverse=True,
        )
        surpluses = sorted(
            ((d, on_hand - expected) for d, on_hand, expected in positions if on_hand - expected > 0),
            key=lambda item: item[1],
            reverse=True,
        )
        for (short_district, shortage_qty), (surplus_district, surplus_qty) in zip(shortages, surpluses):
            transfer_qty = round(min(shortage_qty, surplus_qty) * (1 - TRANSFER_BUFFER_FRACTION), 1)
            if transfer_qty <= 0:
                continue
            transfers.append(
                {
                    "product_id": product_id,
                    "from_district_id": surplus_district,
                    "to_district_id": short_district,
                    "recommended_transfer_qty": transfer_qty,
                    "reason": (
                        f"{district_names.get(surplus_district, surplus_district)} excess vs "
                        f"{district_names.get(short_district, short_district)} shortage"
                    ),
                },
            )
    return transfers
