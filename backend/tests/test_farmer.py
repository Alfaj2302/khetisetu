from __future__ import annotations

from app.security import decode_access_token

API = "/api/v1"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------
# POST /farmer/crop-recommendation
# ---------------------------------------------------------------


def test_crop_recommendation_unauthenticated_demo_mode(client):
    resp = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 6},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["district"] == {"id": 1, "name": "Nashik"}
    assert body["farmer_intent_id"] is not None
    assert 1 <= len(body["recommendations"]) <= 3
    ranks = [r["rank"] for r in body["recommendations"]]
    assert ranks == list(range(1, len(ranks) + 1))
    # descending opportunity_pct
    scores = [r["opportunity_pct"] for r in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)
    for rec in body["recommendations"]:
        assert rec["demand_level"] in {"High", "Medium", "Low"}
        assert rec["weather_tag"] in {"Good", "Moderate", "Poor"}
        assert rec["risk_tag"] in {"Low", "Medium", "High"}


def test_crop_recommendation_authenticated_attributes_intent_to_user(client, farmer_token, db_conn):
    resp = client.post(
        f"{API}/farmer/crop-recommendation",
        headers=auth_header(farmer_token),
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "previous_crop_id": 6, "sowing_month": 6},
    )
    assert resp.status_code == 200
    intent_id = resp.json()["farmer_intent_id"]
    assert intent_id is not None

    with db_conn.cursor() as cur:
        cur.execute("SELECT user_id, previous_crop_id, sowing_month, data_source FROM farmer_crop_intent WHERE id = %s", (intent_id,))
        user_id, previous_crop_id, sowing_month, data_source = cur.fetchone()
    assert user_id == int(decode_access_token(farmer_token)["sub"])
    assert previous_crop_id == 6
    assert sowing_month == 6
    assert data_source == "ACTUAL"


def test_crop_recommendation_rejects_out_of_range_month(client):
    resp = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 13},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    resp0 = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 0},
    )
    assert resp0.status_code == 400


def test_crop_recommendation_rejects_missing_required_field(client):
    resp = client.post(f"{API}/farmer/crop-recommendation", json={"district_id": 1, "sowing_month": 6})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_crop_recommendation_unknown_district_is_404(client):
    resp = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 999, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 6},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------
# GET /farmer/weather
# ---------------------------------------------------------------


def test_farmer_weather_success(client):
    resp = client.get(f"{API}/farmer/weather", params={"district_id": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["district_id"] == 1
    assert set(body["current"].keys()) == {"rainfall", "temperature_c", "humidity_pct", "forecast"}
    assert isinstance(body["next_7_days"], list)


def test_farmer_weather_requires_district_id(client):
    resp = client.get(f"{API}/farmer/weather")
    assert resp.status_code == 400


def test_farmer_weather_unknown_district_is_404(client):
    resp = client.get(f"{API}/farmer/weather", params={"district_id": 999})
    assert resp.status_code == 404


# ---------------------------------------------------------------
# GET /farmer/crop/{crop_id}
# ---------------------------------------------------------------


def test_crop_detail_matches_known_tomato_nashik_figures(client):
    resp = client.get(f"{API}/farmer/crop/7", params={"district_id": 1, "land_area_acres": 5, "irrigation_available": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["crop"] == {"id": 7, "name": "Tomato"}
    assert body["demand_outlook"]["expected_demand_qty"] == 229794.3
    assert body["demand_outlook"]["expected_supply_qty"] == 193150.0
    assert body["demand_outlook"]["demand_gap"] == 36644.3
    assert body["agronomic_guidance"]["is_verified"] is False
    assert body["agronomic_guidance"]["warning"] is not None
    assert body["agronomic_guidance"]["nitrogen_kg_ha"] == 120.0
    factor_names = {w["factor"] for w in body["why"]}
    assert {"Historical demand", "Seasonal suitability", "Weather", "Demand gap", "Farmer context", "Farm size"} <= factor_names


def test_crop_detail_omits_farmer_context_factor_when_not_provided(client):
    resp = client.get(f"{API}/farmer/crop/7", params={"district_id": 1})
    assert resp.status_code == 200
    factor_names = {w["factor"] for w in resp.json()["why"]}
    assert "Farmer context" not in factor_names
    assert "Farm size" not in factor_names


def test_crop_detail_unknown_crop_is_404(client):
    resp = client.get(f"{API}/farmer/crop/999999", params={"district_id": 1})
    assert resp.status_code == 404


def test_crop_detail_unknown_district_is_404(client):
    resp = client.get(f"{API}/farmer/crop/7", params={"district_id": 999})
    assert resp.status_code == 404


# ---------------------------------------------------------------
# POST /farmer/scenario
# ---------------------------------------------------------------


def test_scenario_zero_rainfall_change_is_no_change(client):
    resp = client.post(f"{API}/farmer/scenario", json={"district_id": 1, "crop_ids": [7, 6, 8], "rainfall_change_pct": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["rainfall_change_pct"] == 0
    assert len(body["scenario_scores"]) == 3
    assert {s["crop_id"] for s in body["scenario_scores"]} == {7, 6, 8}
    assert all(s["change"] == "No change" for s in body["scenario_scores"])
    assert body["recommendation_changed"] is False


def test_scenario_large_rainfall_swing_can_change_scores(client):
    resp = client.post(f"{API}/farmer/scenario", json={"district_id": 1, "crop_ids": [7], "rainfall_change_pct": 300})
    assert resp.status_code == 200
    score = resp.json()["scenario_scores"][0]
    assert score["change"] != "No change"


def test_scenario_rejects_unknown_crop_id(client):
    resp = client.post(f"{API}/farmer/scenario", json={"district_id": 1, "crop_ids": [7, 9999]})
    assert resp.status_code == 400
    assert "9999" in resp.json()["error"]["message"]


def test_scenario_rejects_empty_crop_ids(client):
    resp = client.post(f"{API}/farmer/scenario", json={"district_id": 1, "crop_ids": []})
    assert resp.status_code == 400


def test_scenario_unknown_district_is_404(client):
    resp = client.post(f"{API}/farmer/scenario", json={"district_id": 999, "crop_ids": [7]})
    assert resp.status_code == 404


# ---------------------------------------------------------------
# POST /farmer/crop-intent
# ---------------------------------------------------------------


def test_crop_intent_authenticated(client, farmer_token, db_conn):
    resp = client.post(
        f"{API}/farmer/crop-intent",
        headers=auth_header(farmer_token),
        json={
            "district_id": 1, "crop_id": 7, "season_id": 1, "year": 2026,
            "land_area_acres": 5, "irrigation_available": True, "soil_type": "Black soil",
        },
    )
    assert resp.status_code == 201
    intent_id = resp.json()["id"]

    with db_conn.cursor() as cur:
        cur.execute("SELECT user_id, soil_type, data_source FROM farmer_crop_intent WHERE id = %s", (intent_id,))
        user_id, soil_type, data_source = cur.fetchone()
    assert user_id == int(decode_access_token(farmer_token)["sub"])
    assert soil_type == "Black soil"
    assert data_source == "ACTUAL"


def test_crop_intent_unauthenticated_leaves_user_id_null(client, db_conn):
    resp = client.post(
        f"{API}/farmer/crop-intent",
        json={"district_id": 1, "crop_id": 7, "season_id": 1, "year": 2026},
    )
    assert resp.status_code == 201
    intent_id = resp.json()["id"]
    with db_conn.cursor() as cur:
        cur.execute("SELECT user_id FROM farmer_crop_intent WHERE id = %s", (intent_id,))
        (user_id,) = cur.fetchone()
    assert user_id is None


def test_crop_intent_unknown_crop_is_404(client):
    resp = client.post(f"{API}/farmer/crop-intent", json={"district_id": 1, "crop_id": 999999, "season_id": 1, "year": 2026})
    assert resp.status_code == 404
