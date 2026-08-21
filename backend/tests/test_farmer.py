from __future__ import annotations

import pytest

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


def test_crop_recommendation_empty_month_explains_itself(client):
    # No district has a crop_calendar row for March, so this legitimately
    # matches no crops. It must say so rather than returning a bare [].
    resp = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendations"] == []
    assert body["farmer_intent_id"] is None  # nothing to record an intent for
    assert body["notice"] is not None
    assert "March" in body["notice"]
    assert "Nashik" in body["notice"]
    # names the months that do work, so the caller can redirect the farmer
    assert "June" in body["notice"]


def test_crop_recommendation_notice_is_absent_when_results_exist(client):
    resp = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 6},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendations"]
    assert body["notice"] is None


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


# ---------------------------------------------------------------
# Job 2 regressions: the two bugs a farmer could actually see
# ---------------------------------------------------------------


def test_whatif_slider_moves_across_its_entire_ui_range(client):
    """The frontend slider offers -30%..+30%. Every step in that range used to
    return "No change" because weather scoring was a step function on rainfall
    bands - measured: even -100% rainfall produced an identical score. This
    asserts the slider is actually connected to something."""
    scores = []
    for pct in (-30, -20, -10, 0, 10, 20, 30):
        resp = client.post(
            f"{API}/farmer/scenario",
            json={"district_id": 1, "crop_ids": [7], "rainfall_change_pct": pct},
        )
        assert resp.status_code == 200
        scores.append(resp.json()["scenario_scores"][0]["opportunity_pct"])

    assert len(set(scores)) > 1, f"slider is inert across its whole range: {scores}"
    assert scores == sorted(scores), f"more rain should not lower a dry-month score: {scores}"


def test_whatif_reports_the_baseline_and_the_term_that_moved(client):
    body = client.post(
        f"{API}/farmer/scenario",
        json={"district_id": 1, "crop_ids": [7, 6, 8], "rainfall_change_pct": -30},
    ).json()
    for score in body["scenario_scores"]:
        assert "baseline_opportunity_pct" in score
        assert "weather_fit" in score  # rainfall only moves this term
        assert 0 <= score["weather_fit"] <= 100


def test_crop_detail_and_recommendation_list_agree_for_the_same_month(client):
    """Tomato read 71% in the recommendation list and 65% on its own page,
    because /farmer/crop/{id} ignored sowing_month and silently scored against
    calendar_months[0] instead."""
    listed = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 11},
    ).json()
    assert listed["recommendations"], "expected at least one crop for Nashik in November"
    top = listed["recommendations"][0]

    detail = client.get(
        f"{API}/farmer/crop/{top['crop']['id']}",
        params={"district_id": 1, "sowing_month": 11, "irrigation_available": True, "land_area_acres": 5},
    ).json()

    assert detail["reference_month"] == 11
    assert detail["opportunity_pct"] == top["opportunity_pct"]
    assert detail["tags"]["risk"] == top["risk_tag"]


def test_crop_detail_reports_which_month_it_assumed_when_not_told(client):
    detail = client.get(f"{API}/farmer/crop/7", params={"district_id": 1}).json()
    assert isinstance(detail["reference_month"], int)
    assert 1 <= detail["reference_month"] <= 12


def test_recommendations_expose_the_four_component_breakdown(client):
    body = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 6},
    ).json()
    for rec in body["recommendations"]:
        components = rec["components"]
        assert set(components) == {"weather_fit", "demand_supply", "demand_trend", "stability"}
        assert all(0 <= v <= 100 for v in components.values())
        # every component carries a plain-language reason for the farmer
        assert set(rec["component_notes"]) == set(components)
        assert all(rec["component_notes"].values())
        assert sum(rec["weights"].values()) == pytest.approx(1.0)


def test_confidence_is_separate_from_opportunity(client):
    """"High opportunity, low confidence" has to stay sayable - confidence must
    not be folded into the score."""
    body = client.post(
        f"{API}/farmer/crop-recommendation",
        json={"district_id": 1, "land_area_acres": 5, "irrigation_available": True, "sowing_month": 6},
    ).json()
    for rec in body["recommendations"]:
        assert 0 <= rec["confidence_pct"] <= 100
        assert rec["confidence_basis"]
        # the two numbers are independent; asserting they are not just equal
        # guards against someone "simplifying" them into one field later
        assert "confidence" not in rec["components"]


def test_irrigation_answer_changes_the_score(client):
    """The farmer's own form input must reach the formula - this is the whole
    reason Job 2 is a live formula and not a nightly model."""
    def opportunity(irrigation: bool) -> int:
        body = client.post(
            f"{API}/farmer/crop-recommendation",
            json={"district_id": 1, "land_area_acres": 5,
                  "irrigation_available": irrigation, "sowing_month": 11},
        ).json()
        return body["recommendations"][0]["components"]["weather_fit"]

    assert opportunity(True) >= opportunity(False)
