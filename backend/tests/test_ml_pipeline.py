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
* the same doubling via the other door: the model and baseline paths write
  different model_version labels, so the night a retrain flips the verdict must
  clear the sibling label too.
* the bound ordering. XGBoost quantile heads can cross, and `forecast` has
  CHECK constraints that reject lower > predicted > upper.
* that the seasonal-naive fallback is a real forecasting path, not just a log
  line - train.py's `use_model` verdict has to change what gets written.
* that the horizon guard extends instead of exiting, because the nightly job
  now derives its window from the current date and will eventually ask for a
  quarter the loaded sales data has already passed.
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


def test_baseline_label_is_distinct_and_fits_the_column():
    assert predict.version_label("xgb_v1_20260821", use_model=True) == "xgb_v1_20260821"
    baseline = predict.version_label("xgb_v1_20260821", use_model=False)
    assert baseline == "xgb_v1_20260821_baseline"
    assert baseline != predict.version_label("xgb_v1_20260821", use_model=True)
    assert len(baseline) <= 50  # forecast.model_version is VARCHAR(50)


def test_flipping_to_baseline_replaces_the_model_rows(db_conn, forecast_rows):
    """The doubling bug: night 1 ships the model, night 2 the baseline. If the
    baseline write only cleared its own label, both would sit in `forecast` and
    the dashboard would sum them."""
    model_label = predict.version_label(VERSION, use_model=True)
    baseline_label = predict.version_label(VERSION, use_model=False)

    predict.write_forecast(db_conn, forecast_rows, model_label, replace_also=(baseline_label,))
    replaced = predict.write_forecast(db_conn, forecast_rows, baseline_label,
                                      replace_also=(model_label,))
    assert replaced == len(forecast_rows)  # it cleared the model's rows, not zero

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT model_version, count(*) FROM forecast WHERE model_version = ANY(%s) GROUP BY 1",
            ([model_label, baseline_label],),
        )
        surviving = dict(cur.fetchall())
    assert surviving == {baseline_label: len(forecast_rows)}


def test_baseline_step_is_seasonal_naive_over_its_own_history():
    history = {100: 10.0, 101: 20.0, 102: 30.0, 103: 40.0}
    # same quarter last year wins
    assert predict.baseline_step(pd.DataFrame([{}]), history, 104) == 10.0
    # no lag-4 available -> trailing two-quarter mean
    assert predict.baseline_step(pd.DataFrame([{}]), {102: 30.0, 103: 40.0}, 104) == 35.0
    # nothing at all -> zero, never NaN (forecast.predicted_demand is NOT NULL)
    assert predict.baseline_step(pd.DataFrame([{}]), {}, 104) == 0.0


def _tiny_quarter_panel() -> pd.DataFrame:
    panel = pd.DataFrame(
        [{"district_id": 1, "year": 2024, "quarter": q, "q": 2024 * 4 + (q - 1),
          "y": 100.0 * q, "intent_acres": 10.0, "intent_rows": 2.0} for q in (1, 2, 3, 4)],
    )
    panel["district_id"] = panel["district_id"].astype("category")
    return panel


EMPTY_CLIMATOLOGY = pd.DataFrame(
    columns=["district_id", "quarter", "rainfall_mm", "temperature_c", "humidity_pct", "crops_sown"],
)


def test_horizon_that_data_has_caught_up_to_extends_instead_of_exiting():
    """through_year 2024 is NOT beyond the last observed quarter (2024-Q4). The
    old guard raised SystemExit here, which would kill the nightly job outright
    once loaded sales reached the derived planning window."""
    out = predict.forecast_quarters(
        predict.baseline_step, _tiny_quarter_panel(), EMPTY_CLIMATOLOGY,
        through_year=2024, offsets=(-10.0, 20.0),
    )
    assert len(out) == 4  # extended a full year past the last observation
    assert list(out["quarters_ahead"]) == [1, 2, 3, 4]
    # seasonal naive repeats 2024 into 2025
    assert list(out["q_mid"]) == [100.0, 200.0, 300.0, 400.0]
    assert (out["q_low"] <= out["q_mid"]).all()
    assert (out["q_mid"] <= out["q_high"]).all()
    assert (out["q_low"] >= 0).all()  # bounds are floored, not negative


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


def test_pipeline_rows_reach_the_dashboard_panels(client, business_token, db_conn, forecast_rows):
    """The regression this guards: written forecast rows actually arriving in
    expected_input_demand / recommended_action / alerts.

    It asserts the DELTA the fixture causes rather than "empty before, non-empty
    after". Once the real nightly job has run, `forecast` is never empty again,
    and the previous before-assertions started failing.
    """
    def dashboard():
        return client.get(
            f"{API}/business/dashboard",
            params={"district_id": 1, "season_id": 1, "year": 2026},
            headers=auth_header(business_token),
        ).json()

    before_total = sum(item["quantity"] for item in dashboard()["expected_input_demand"])

    predict.write_forecast(db_conn, forecast_rows, VERSION)
    recommend.write(db_conn, recommend.build(db_conn, year=2026, quarter=3, version=VERSION))

    after = dashboard()
    after_total = sum(item["quantity"] for item in after["expected_input_demand"])

    # The fixture is district 1 x products 3,5 x months 7,8,9 at mid = 100 + 10*month,
    # and get_expected_input_demand filters on district and year only, so all six
    # rows land in this panel.
    expected_delta = 2 * sum(100.0 + 10.0 * month for month in (7, 8, 9))
    assert after_total - before_total == pytest.approx(expected_delta)

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
    ours = [r for r in body if r["model_version"] == VERSION]
    assert len(ours) == 3  # three months of one district/product
    assert all(r["confidence"].startswith("Allocated") for r in ours)
    assert [r["month"] for r in ours] == [7, 8, 9]  # ordered
