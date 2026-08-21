"""Business endpoints.

All require role AGRI_BUSINESS/ADMIN (tested once here and assumed for the
rest). `forecast`/`recommendations` are batch-ML-job output tables that are
empty in a freshly-seeded dev database, so most of these tests seed a
throwaway row directly (inside the same per-test transaction, rolled back
at teardown) to exercise the actual filter logic rather than just asserting
on an empty list.
"""

from __future__ import annotations

API = "/api/v1"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------
# Role enforcement (checked once; every other route in this router
# shares the same `require_roles("AGRI_BUSINESS", "ADMIN")` dependency)
# ---------------------------------------------------------------


def test_dashboard_requires_a_token(client):
    resp = client.get(f"{API}/business/dashboard", params={"district_id": 1, "season_id": 1, "year": 2026})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_dashboard_rejects_farmer_role(client, farmer_token):
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 1, "year": 2026},
        headers=auth_header(farmer_token),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_dashboard_allows_agri_business_and_admin(client, business_token, admin_token):
    for token in (business_token, admin_token):
        resp = client.get(
            f"{API}/business/dashboard",
            params={"district_id": 1, "season_id": 1, "year": 2026},
            headers=auth_header(token),
        )
        assert resp.status_code == 200


def test_dashboard_unknown_district_is_404(client, business_token):
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 999, "season_id": 1, "year": 2026},
        headers=auth_header(business_token),
    )
    assert resp.status_code == 404


def test_dashboard_unknown_season_is_404(client, business_token):
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 999, "year": 2026},
        headers=auth_header(business_token),
    )
    assert resp.status_code == 404


def test_dashboard_missing_required_query_param_is_400(client, business_token):
    resp = client.get(f"{API}/business/dashboard", params={"district_id": 1}, headers=auth_header(business_token))
    assert resp.status_code == 400


def test_dashboard_farmer_crop_intent_is_aggregated_never_per_farmer(client, business_token):
    resp = client.get(
        f"{API}/business/dashboard",
        params={"district_id": 1, "season_id": 1, "year": 2025},
        headers=auth_header(business_token),
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


def test_forecast_is_empty_on_a_fresh_seed(client, business_token):
    resp = client.get(f"{API}/business/forecast", params={"district_id": 1}, headers=auth_header(business_token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_forecast_filters_by_district_product_and_year(client, business_token, db_conn):
    _seed_forecast_row(db_conn)
    _seed_forecast_row(db_conn, district_id=2, model_version="test_v1_other_district")

    matching = client.get(
        f"{API}/business/forecast",
        params={"district_id": 1, "product_id": 26, "year": 2026},
        headers=auth_header(business_token),
    ).json()
    assert len(matching) == 1
    assert matching[0]["predicted_demand"] == 1430.0

    other_district = client.get(
        f"{API}/business/forecast", params={"district_id": 2}, headers=auth_header(business_token),
    ).json()
    assert len(other_district) == 1

    no_filter = client.get(f"{API}/business/forecast", headers=auth_header(business_token)).json()
    assert len(no_filter) == 2


# ---------------------------------------------------------------
# GET /business/inventory — district_id filter
# ---------------------------------------------------------------


def test_inventory_unfiltered_returns_all_203_seeded_rows(client, business_token):
    resp = client.get(f"{API}/business/inventory", headers=auth_header(business_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 203


def test_inventory_filtered_by_district_is_a_strict_subset(client, business_token):
    all_rows = client.get(f"{API}/business/inventory", headers=auth_header(business_token)).json()
    district_rows = client.get(
        f"{API}/business/inventory", params={"district_id": 1}, headers=auth_header(business_token),
    ).json()
    assert 0 < len(district_rows) < len(all_rows)
    for row in district_rows:
        assert set(row.keys()) == {"product_id", "quantity", "batch_no", "manufacturing_date", "expiry_date"}


# ---------------------------------------------------------------
# GET /business/transfers — no filters, but exercises real cross-district logic
# ---------------------------------------------------------------


def test_transfers_pairs_real_shortage_and_surplus_districts(client, business_token):
    resp = client.get(f"{API}/business/transfers", headers=auth_header(business_token))
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


def test_alerts_is_empty_on_a_fresh_seed(client, business_token):
    resp = client.get(f"{API}/business/alerts", headers=auth_header(business_token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_alerts_excludes_monitor_action_and_respects_district_filter(client, business_token, db_conn):
    _seed_recommendation_row(db_conn, action="DISPATCH", reason="Urea shortage expected")
    _seed_recommendation_row(db_conn, district_id=2, action="MONITOR", reason="nothing to see here")

    district_1 = client.get(
        f"{API}/business/alerts", params={"district_id": 1}, headers=auth_header(business_token),
    ).json()
    assert len(district_1) == 1
    assert district_1[0]["severity"] == "High"
    assert district_1[0]["message"] == "Urea shortage expected"

    district_2 = client.get(
        f"{API}/business/alerts", params={"district_id": 2}, headers=auth_header(business_token),
    ).json()
    assert district_2 == []  # the only row there is MONITOR, filtered out

    unfiltered = client.get(f"{API}/business/alerts", headers=auth_header(business_token)).json()
    assert len(unfiltered) == 1
