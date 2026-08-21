"""Job 1 end-to-end: forecast -> recommendations -> business dashboard.

Everything runs inside the per-test transaction from conftest and is rolled
back, so this exercises the real INSERTs, the real CHECK constraints, and the
real API reads without leaving rows behind.

What these tests are actually guarding:

* the delete-then-insert idempotency of write_forecast. `forecast`'s UNIQUE
  includes crop_id, which is NULL for every row this pipeline writes, and
  Postgres treats NULLs as distinct - so ON CONFLICT can never fire and a
  second nightly run would silently double every row. That bug would only show
  up as quietly inflated demand on the dashboard.
* the bound ordering. XGBoost quantile heads can cross, and `forecast` has
  CHECK constraints that reject lower > predicted > upper.
* that the three previously-empty dashboard panels actually populate.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ml import predict, recommend

API = "/api/v1"
VERSION = "test_pipeline_v1"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def forecast_rows() -> pd.DataFrame:
    """Two districts x two products x a full quarter, shaped like predict.allocate output."""
    rows = []
    for district_id in (1, 2):
        for product_id in (3, 5):
            for month in (7, 8, 9):
                mid = 100.0 * district_id + 10.0 * month
                rows.append(
                    {
                        "district_id": district_id,
                        "product_id": product_id,
                        "year": 2026,
                        "month": month,
                        "predicted_demand": mid,
                        "lower_bound": mid * 0.6,
                        "upper_bound": mid * 1.5,
                        "confidence": "Allocated: Very Low",
                    },
                )
    return pd.DataFrame(rows)


def test_write_forecast_is_idempotent_despite_null_crop_id(db_conn, forecast_rows):
    first = predict.write_forecast(db_conn, forecast_rows, VERSION)
    assert first == 0  # nothing to replace on the first run

    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM forecast WHERE model_version = %s", (VERSION,))
        after_first = cur.fetchone()[0]
    assert after_first == len(forecast_rows)

    # The bug this guards: a second run must REPLACE, not append.
    replaced = predict.write_forecast(db_conn, forecast_rows, VERSION)
    assert replaced == len(forecast_rows)
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM forecast WHERE model_version = %s", (VERSION,))
        assert cur.fetchone()[0] == len(forecast_rows)


def test_written_bounds_satisfy_the_check_constraints(db_conn, forecast_rows):
    predict.write_forecast(db_conn, forecast_rows, VERSION)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM forecast
            WHERE model_version = %s
              AND (lower_bound > predicted_demand OR predicted_demand > upper_bound)
            """,
            (VERSION,),
        )
        assert cur.fetchone()[0] == 0


def test_crossed_quantiles_are_repaired_before_writing():
    """allocate() must not hand the DB a lower > upper row, whatever the model says."""
    quarterly = pd.DataFrame(
        [{"district_id": 1, "year": 2026, "quarter": 3, "q": 2026 * 4 + 2,
          "quarters_ahead": 8, "q_mid": 100.0, "q_low": 400.0, "q_high": 10.0}],  # deliberately crossed
    )
    month_shares = pd.DataFrame([{"district_id": 1, "quarter": 3, "month": m, "month_share": 1 / 3}
                                 for m in (7, 8, 9)])
    product_shares = pd.DataFrame([{"district_id": 1, "product_id": 3, "product_share": 1.0}])
    out = predict.allocate(quarterly, month_shares, product_shares)
    assert (out["lower_bound"] <= out["predicted_demand"]).all()
    assert (out["predicted_demand"] <= out["upper_bound"]).all()


def test_confidence_label_degrades_with_horizon():
    assert predict.confidence_label(1) == "Allocated: Moderate"
    assert predict.confidence_label(4) == "Allocated: Low"
    assert predict.confidence_label(8) == "Allocated: Very Low"
    # forecast.confidence is VARCHAR(30)
    assert all(len(predict.confidence_label(n)) <= 30 for n in range(1, 13))


def test_recommendations_are_derived_and_classified(db_conn, forecast_rows):
    predict.write_forecast(db_conn, forecast_rows, VERSION)
    rows = recommend.build(db_conn, year=2026, quarter=3, version=VERSION)

    assert not rows.empty
    assert set(rows["action"]) <= {"DISPATCH", "HOLD", "TRANSFER", "MANUFACTURE",
                                  "REDUCE_PRODUCTION", "MONITOR"}  # the CHECK constraint
    assert (rows["dispatch"] >= 0).all()
    # safety buffer comes from the model's own interval width
    assert (rows["safety"] > 0).all()
    # every reason states that the number is an allocation, not a prediction
    assert rows["reason"].str.contains("allocation of a district-quarter model").all()

    written = recommend.write(db_conn, rows)
    assert written >= 0
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM recommendations")
        assert cur.fetchone()[0] == len(rows)


def test_pipeline_fills_the_three_empty_dashboard_panels(client, business_token, db_conn, forecast_rows):
    """Before this pipeline runs, expected_input_demand / alerts / recommended_action
    are all empty. This is the regression test for them being non-empty."""
    before = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 1, "year": 2026},
        headers=auth_header(business_token),
    ).json()
    assert before["expected_input_demand"] == []
    assert before["recommended_action"] is None

    predict.write_forecast(db_conn, forecast_rows, VERSION)
    recommend.write(db_conn, recommend.build(db_conn, year=2026, quarter=3, version=VERSION))

    after = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 1, "year": 2026},
        headers=auth_header(business_token),
    ).json()

    assert after["expected_input_demand"], "forecast rows did not reach the dashboard"
    assert all(item["unit"] == "packets" for item in after["expected_input_demand"])
    assert after["recommended_action"] is not None
    assert after["recommended_action"]["unit"] == "packets"
    assert after["alerts"], "recommendations did not surface as alerts"


def test_forecast_endpoint_serves_the_written_rows(client, business_token, db_conn, forecast_rows):
    predict.write_forecast(db_conn, forecast_rows, VERSION)
    body = client.get(
        f"{API}/business/forecast",
        params={"district_id": 1, "product_id": 3, "year": 2026},
        headers=auth_header(business_token),
    ).json()
    assert len(body) == 3  # three months of one district/product
    assert all(r["model_version"] == VERSION for r in body)
    assert all(r["confidence"].startswith("Allocated") for r in body)
    assert [r["month"] for r in body] == [7, 8, 9]  # ordered
