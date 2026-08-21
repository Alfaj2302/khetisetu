"""Unit tests for the Job 2 opportunity formula.

Pure functions, no database. These pin the properties the formula has to have,
rather than specific scores - the weights are tunable and a test that asserts
"Tomato scores 41" would just have to be edited every time someone tunes them.

The load-bearing property is CONTINUITY. The previous implementation subtracted
fixed penalties at hard rainfall thresholds, so a +-30% rainfall change usually
crossed no threshold and the what-if slider reported "No change" across its
entire range. test_band_score_is_strictly_monotonic_outside_the_plateau is the
regression guard for that.
"""

from __future__ import annotations

import pytest

from app.services import scoring


# ---------------------------------------------------------------
# band_score: the continuity primitive
# ---------------------------------------------------------------


def test_band_score_is_flat_inside_the_optimal_band():
    # Inside the ideal range, more water genuinely does not help. That is
    # correct agronomy, not a bug - the fix was making the DECAY continuous.
    assert scoring.band_score(25, 20, 30, 10, 40) == 100.0
    assert scoring.band_score(20, 20, 30, 10, 40) == 100.0
    assert scoring.band_score(30, 20, 30, 10, 40) == 100.0


def test_band_score_is_strictly_monotonic_outside_the_plateau():
    """THE regression test for the dead slider."""
    below = [scoring.band_score(v, 20, 30, 10, 40) for v in (11, 13, 15, 17, 19)]
    assert below == sorted(below), "score must rise as we approach the ideal band"
    assert len(set(below)) == len(below), "every step must change the score"

    above = [scoring.band_score(v, 20, 30, 10, 40) for v in (31, 33, 35, 37, 39)]
    assert above == sorted(above, reverse=True), "score must fall past the ideal band"
    assert len(set(above)) == len(above)


def test_band_score_clamps_at_the_absolute_limits():
    assert scoring.band_score(10, 20, 30, 10, 40) == 0.0
    assert scoring.band_score(5, 20, 30, 10, 40) == 0.0
    assert scoring.band_score(40, 20, 30, 10, 40) == 0.0
    assert scoring.band_score(99, 20, 30, 10, 40) == 0.0


def test_band_score_never_leaves_zero_to_hundred():
    for value in range(-50, 150):
        assert 0.0 <= scoring.band_score(value, 20, 30, 10, 40) <= 100.0


def test_band_score_survives_degenerate_bands():
    # abs_lo == opt_lo would divide by zero if unguarded.
    assert scoring.band_score(5, 10, 20, 10, 20) == 0.0
    assert scoring.band_score(25, 10, 20, 10, 20) == 0.0


# ---------------------------------------------------------------
# demand trend
# ---------------------------------------------------------------


def test_trend_scores_growth_above_flat_above_decline():
    growing = scoring.score_demand_trend([(2023, 100.0), (2024, 110.0), (2025, 121.0)])[0]
    flat = scoring.score_demand_trend([(2023, 100.0), (2024, 100.0), (2025, 100.0)])[0]
    shrinking = scoring.score_demand_trend([(2023, 121.0), (2024, 110.0), (2025, 100.0)])[0]
    assert growing > flat > shrinking
    assert flat == pytest.approx(50.0, abs=0.5), "flat demand must be neutral, not favourable"


def test_trend_saturates_and_stays_in_range():
    explosive = scoring.score_demand_trend([(2020, 1.0), (2025, 1000.0)])[0]
    collapse = scoring.score_demand_trend([(2020, 1000.0), (2025, 1.0)])[0]
    assert explosive == 100.0
    assert collapse == 0.0


def test_trend_is_neutral_without_enough_history():
    score, note = scoring.score_demand_trend([(2025, 100.0)])
    assert score == 50.0
    assert "not enough" in note.lower()
    assert scoring.score_demand_trend([])[0] == 50.0


def test_trend_ignores_non_positive_values():
    # A zero or negative demand row would break the CAGR ratio.
    score, _ = scoring.score_demand_trend([(2023, 0.0), (2024, 100.0), (2025, 110.0)])
    assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------
# stability
# ---------------------------------------------------------------


def test_stability_falls_as_variability_rises():
    steady = scoring.score_stability({"rainfall_mm": 100.0, "rainfall_stddev": 5.0}, [])
    jumpy = scoring.score_stability({"rainfall_mm": 100.0, "rainfall_stddev": 45.0}, [])
    assert steady[0] > jumpy[0]
    assert steady[1] == "Low"          # risk_tag
    assert jumpy[1] in {"Medium", "High"}


def test_stability_risk_tag_is_one_the_api_can_serve():
    for stddev in (0.0, 10.0, 25.0, 50.0, 200.0):
        _, risk_tag, _ = scoring.score_stability({"rainfall_mm": 100.0, "rainfall_stddev": stddev}, [])
        assert risk_tag in scoring.RISK_FACTORS


def test_stability_is_neutral_with_no_history():
    score, risk, note = scoring.score_stability({"rainfall_mm": None, "rainfall_stddev": None}, [])
    assert score == 50.0
    assert risk == "Medium"


# ---------------------------------------------------------------
# weather fit + the farmer's own irrigation answer
# ---------------------------------------------------------------


def _dry_month() -> dict:
    # far below FALLBACK_REQUIREMENT's ~152 mm/month need
    return {"rainfall_mm": 15.0, "temperature_c": 25.0, "humidity_pct": 50.0, "rainfall_stddev": 3.0}


def test_irrigation_offsets_a_rainfall_deficit():
    req = scoring.FALLBACK_REQUIREMENT
    without, _ = scoring.score_weather_fit(_dry_month(), req, irrigation_available=False)
    with_irrigation, note = scoring.score_weather_fit(_dry_month(), req, irrigation_available=True)
    assert with_irrigation > without, "the farmer's irrigation answer must affect the score"
    assert "irrigation" in note.lower()


def test_irrigation_does_not_rescue_waterlogging():
    req = scoring.FALLBACK_REQUIREMENT
    flooded = {"rainfall_mm": req.monthly_water_mm * 2.8, "temperature_c": 25.0,
               "humidity_pct": 90.0, "rainfall_stddev": 10.0}
    without, _ = scoring.score_weather_fit(flooded, req, irrigation_available=False)
    with_irrigation, _ = scoring.score_weather_fit(flooded, req, irrigation_available=True)
    assert with_irrigation == without, "irrigation cannot fix too much water"


def test_weather_fit_is_neutral_with_no_weather_data():
    score, note = scoring.score_weather_fit(
        {"rainfall_mm": None, "temperature_c": None, "humidity_pct": None, "rainfall_stddev": None},
        scoring.FALLBACK_REQUIREMENT,
    )
    assert score == 50.0
    assert "no weather" in note.lower()


def test_weather_fit_responds_to_every_rainfall_step():
    """Second guard on the slider, at the component the slider actually moves."""
    req = scoring.FALLBACK_REQUIREMENT
    scores = []
    for pct in (-30, -20, -10, 0, 10, 20, 30):
        weather = _dry_month()
        weather["rainfall_mm"] = 15.0 * (1 + pct / 100)
        scores.append(scoring.score_weather_fit(weather, req)[0])
    assert len(set(scores)) == len(scores), f"slider produced duplicate scores: {scores}"
    assert scores == sorted(scores)


# ---------------------------------------------------------------
# combination + requirement lookup
# ---------------------------------------------------------------


def test_weights_sum_to_one():
    assert sum(scoring.COMPONENT_WEIGHTS.values()) == pytest.approx(1.0)


def test_combine_respects_bounds_and_ordering():
    floor = scoring.combine(dict.fromkeys(scoring.COMPONENT_WEIGHTS, 0.0))
    ceiling = scoring.combine(dict.fromkeys(scoring.COMPONENT_WEIGHTS, 100.0))
    middle = scoring.combine(dict.fromkeys(scoring.COMPONENT_WEIGHTS, 50.0))
    assert floor == 0
    assert ceiling == 100
    assert middle == 50


def test_requirement_lookup_falls_back_by_name_then_category_then_generic():
    assert scoring.crop_requirement("NoSuchCrop", "NoSuchCategory") is scoring.FALLBACK_REQUIREMENT
    scoring.CATEGORY_REQUIREMENTS["TestCategory"] = scoring.FALLBACK_REQUIREMENT
    try:
        assert scoring.crop_requirement("NoSuchCrop", "TestCategory") is scoring.FALLBACK_REQUIREMENT
    finally:
        del scoring.CATEGORY_REQUIREMENTS["TestCategory"]


def test_monthly_water_is_derived_from_seasonal_need():
    req = scoring.CropRequirement(
        temp_optimal_min_c=20, temp_optimal_max_c=30,
        temp_absolute_min_c=10, temp_absolute_max_c=40,
        water_seasonal_mm_min=600, water_seasonal_mm_max=600,
        growing_days_min=120, growing_days_max=120,
    )
    # 600 mm over ~3.94 months
    assert req.monthly_water_mm == pytest.approx(600 / (120 / 30.44), rel=0.01)
