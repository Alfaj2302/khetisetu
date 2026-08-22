"""Business endpoints.

These are unauthenticated — the app has no sign-in flow, so the dashboard
reads them straight from the database (see the note on the router). Every
response is aggregated or product-level, never per-farmer.

`forecast`/`recommendations` are batch-ML-job output tables that are empty in
a freshly-seeded dev database, so most of these tests seed a throwaway row
directly (inside the same per-test transaction, rolled back at teardown) to
exercise the actual filter logic rather than just asserting on an empty list.
"""

from __future__ import annotations

API = "/api/v1"


# ---------------------------------------------------------------
# Open access (checked once; no route in this router is gated)
# ---------------------------------------------------------------


def test_dashboard_needs_no_token(client):
    resp = client.get(f"{API}/business/dashboard", params={"district_id": 1, "season_id": 1, "year": 2026})
    assert resp.status_code == 200


def test_dashboard_ignores_a_farmer_role_token(client, farmer_token):
    # Nothing here is role-gated any more, so a token of any role — or none —
    # gets the same response rather than a 403.
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 1, "year": 2026},
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code == 200


def test_dashboard_unknown_district_is_404(client):
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 999, "season_id": 1, "year": 2026},
    )
    assert resp.status_code == 404


def test_dashboard_unknown_season_is_404(client):
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 999, "year": 2026},
    )
    assert resp.status_code == 404


def test_dashboard_missing_required_query_param_is_400(client):
    resp = client.get(f"{API}/business/dashboard", params={"district_id": 1})
    assert resp.status_code == 400


def test_dashboard_farmer_crop_intent_is_aggregated_never_per_farmer(client):
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 1, "year": 2025},
    )
    assert resp.status_code == 200
    for row in resp.json()["farmer_crop_intent"]:
        assert set(row.keys()) == {"crop", "acres"}  # structurally no user_id/farmer identity possible


# ---------------------------------------------------------------
# GET /business/forecast — district_id / product_id / year filters
# ---------------------------------------------------------------


def _seed_forecast_row(db_conn, **overrides):
    row = {
        "district_id": 1, "product_id": 26, "crop_id": None, "year": 2026, "month": 7,
        "predicted_demand": 1430, "lower_bound": 1250, "upper_bound": 1700,
        "confidence": "Reasonably Sure", "model_version": "test_v1",
    }
    row.update(overrides)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO forecast (district_id, product_id, crop_id, year, month,
                                   predicted_demand, lower_bound, upper_bound, confidence, model_version)
            VALUES (%(district_id)s, %(product_id)s, %(crop_id)s, %(year)s, %(month)s,
                    %(predicted_demand)s, %(lower_bound)s, %(upper_bound)s, %(confidence)s, %(model_version)s)
            """,
            row,
        )


def test_forecast_rows_are_wellformed_whatever_the_batch_job_wrote(client, business_token):
    """`forecast` is batch-ML output: empty before ml/predict.py has ever run,
    thousands of rows after. So this asserts shape, not emptiness - the earlier
    version asserted `== []` and broke the moment the pipeline ran for real."""
    resp = client.get(f"{API}/business/forecast", params={"district_id": 1}, headers=auth_header(business_token))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    for row in body:
        assert row["model_version"]
        assert row["predicted_demand"] >= 0
        if row["lower_bound"] is not None:
            assert row["lower_bound"] <= row["predicted_demand"]
        if row["upper_bound"] is not None:
            assert row["predicted_demand"] <= row["upper_bound"]


def test_forecast_filters_by_district_product_and_year(client, db_conn):
    _seed_forecast_row(db_conn)
    _seed_forecast_row(db_conn, district_id=2, model_version="test_v1_other_district")
    seeded = {"test_v1", "test_v1_other_district"}

    def only_seeded(**params):
        """Counts are scoped to the rows this test wrote - the nightly job has
        very likely filled `forecast` with thousands of others."""
        rows = client.get(
            f"{API}/business/forecast", params=params, headers=auth_header(business_token),
        ).json()
        return [r for r in rows if r["model_version"] in seeded]

    matching = only_seeded(district_id=1, product_id=26, year=2026)
    assert len(matching) == 1
    assert matching[0]["predicted_demand"] == 1430.0

    assert len(only_seeded(district_id=2)) == 1
    assert len(only_seeded()) == 2


# ---------------------------------------------------------------
# GET /business/inventory — district_id filter
# ---------------------------------------------------------------


def test_inventory_unfiltered_returns_all_203_seeded_rows(client):
    resp = client.get(f"{API}/business/inventory")
    assert resp.status_code == 200
    assert len(resp.json()) == 203


def test_inventory_filtered_by_district_is_a_strict_subset(client):
    all_rows = client.get(f"{API}/business/inventory").json()
    district_rows = client.get(f"{API}/business/inventory", params={"district_id": 1}).json()
    assert 0 < len(district_rows) < len(all_rows)
    for row in district_rows:
        assert set(row.keys()) == {"product_id", "quantity", "batch_no", "manufacturing_date", "expiry_date"}


# ---------------------------------------------------------------
# GET /business/transfers — no filters, but exercises real cross-district logic
# ---------------------------------------------------------------


def test_transfers_pairs_real_shortage_and_surplus_districts(client):
    resp = client.get(f"{API}/business/transfers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0  # real seeded inventory/historical_sales produce at least one pairing
    for row in body:
        assert row["from_district_id"] != row["to_district_id"]
        assert row["recommended_transfer_qty"] > 0
        assert "excess vs" in row["reason"] and "shortage" in row["reason"]


# ---------------------------------------------------------------
# GET /business/alerts — district_id filter, action != 'MONITOR'
# ---------------------------------------------------------------


def _seed_recommendation_row(db_conn, **overrides):
    row = {
        "district_id": 1, "product_id": 26, "forecast_quantity": 1000, "current_stock": 200,
        "safety_stock": 150, "recommended_dispatch": 800, "action": "DISPATCH", "reason": "test shortage",
    }
    row.update(overrides)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO recommendations (district_id, product_id, forecast_quantity, current_stock,
                                          safety_stock, recommended_dispatch, action, reason)
            VALUES (%(district_id)s, %(product_id)s, %(forecast_quantity)s, %(current_stock)s,
                    %(safety_stock)s, %(recommended_dispatch)s, %(action)s, %(reason)s)
            """,
            row,
        )


def test_alerts_are_wellformed_whatever_the_batch_job_wrote(client, business_token):
    """Shape, not emptiness - `recommendations` is batch-ML output. See the note
    on test_forecast_rows_are_wellformed_whatever_the_batch_job_wrote."""
    resp = client.get(f"{API}/business/alerts", headers=auth_header(business_token))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert all(r["severity"] in {"High", "Medium"} for r in body)
    assert all(r["district"] and r["product"] and r["message"] for r in body)


def test_alerts_excludes_monitor_action_and_respects_district_filter(client, db_conn):
    _seed_recommendation_row(db_conn, action="DISPATCH", reason="Urea shortage expected")
    _seed_recommendation_row(db_conn, district_id=2, action="MONITOR", reason="nothing to see here")

    def alerts(**params):
        return client.get(
            f"{API}/business/alerts", params=params, headers=auth_header(business_token),
        ).json()

    # Scoped to this test's own rows by their distinctive reason text, since the
    # nightly job's own recommendations are very likely in the table too.
    mine = [r for r in alerts(district_id=1) if r["message"] == "Urea shortage expected"]
    assert len(mine) == 1
    assert mine[0]["severity"] == "High"

    # The MONITOR row must not surface anywhere, filtered by district or not.
    assert "nothing to see here" not in [r["message"] for r in alerts(district_id=2)]
    assert "nothing to see here" not in [r["message"] for r in alerts()]
    assert "Urea shortage expected" in [r["message"] for r in alerts()]
