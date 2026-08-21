"""Live crop-opportunity scoring.

`schema.sql` reserves `forecast`/`recommendations` for a batch-trained ML
model that isn't built yet ("written by the batch ML job... never computed
live" per its own comments). Everything in this module is the interim,
transparently-heuristic stand-in the farmer-facing endpoints use until that
model exists — deterministic, explainable, and built only from columns that
are actually in the schema. Replace piecemeal as the real model lands.
"""

from __future__ import annotations

from typing import Any

from psycopg import Cursor

CROP_CYCLE_WEEKS_BY_CATEGORY: dict[str, tuple[int, int]] = {
    "Cereal": (10, 16),
    "Vegetable": (8, 12),
    "Fibre": (20, 26),
    "Oilseed": (12, 16),
    "Pulse": (10, 14),
    "Fruit": (20, 40),
    "Spice": (16, 24),
}
DEFAULT_CYCLE_WEEKS = (10, 14)

RISK_FACTORS = {
    "Low": ["Stable historical rainfall", "Market demand broadly steady"],
    "Medium": ["Rainfall variability", "Market demand uncertainty"],
    "High": ["High rainfall variability", "Market demand uncertainty", "Limited historical data"],
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def resolve_season_id(cur: Cursor, month: int) -> int | None:
    cur.execute(
        """
        SELECT id FROM seasons
        WHERE (start_month <= end_month AND %(m)s BETWEEN start_month AND end_month)
           OR (start_month > end_month AND (%(m)s >= start_month OR %(m)s <= end_month))
        ORDER BY id
        LIMIT 1
        """,
        {"m": month},
    )
    row = cur.fetchone()
    return row[0] if row else None


def get_eligible_crops(cur: Cursor, district_id: int, month: int) -> list[dict]:
    cur.execute(
        """
        SELECT DISTINCT c.id, c.name, c.crop_category
        FROM crop_calendar cc
        JOIN crops c ON c.id = cc.crop_id
        WHERE cc.district_id = %s AND cc.month = %s AND cc.expected_usage
        ORDER BY c.id
        """,
        (district_id, month),
    )
    return [{"id": r[0], "name": r[1], "crop_category": r[2]} for r in cur.fetchall()]


def get_calendar_months(cur: Cursor, district_id: int, crop_id: int) -> list[int]:
    cur.execute(
        """
        SELECT DISTINCT month FROM crop_calendar
        WHERE district_id = %s AND crop_id = %s AND expected_usage
        ORDER BY month
        """,
        (district_id, crop_id),
    )
    return [row[0] for row in cur.fetchall()]


def get_weather_aggregate(cur: Cursor, district_id: int, month: int) -> dict[str, float | None]:
    """Average weather_history readings for this district+month across all seeded years."""
    cur.execute(
        """
        SELECT avg(rainfall_mm), avg(temperature_c), avg(humidity_pct), stddev_pop(rainfall_mm)
        FROM weather_history
        WHERE district_id = %s AND month = %s
        """,
        (district_id, month),
    )
    rainfall, temperature_c, humidity_pct, rainfall_stddev = cur.fetchone()
    return {
        "rainfall_mm": float(rainfall) if rainfall is not None else None,
        "temperature_c": float(temperature_c) if temperature_c is not None else None,
        "humidity_pct": float(humidity_pct) if humidity_pct is not None else None,
        "rainfall_stddev": float(rainfall_stddev) if rainfall_stddev is not None else None,
    }


def rainfall_bucket(rainfall_mm: float | None) -> str:
    if rainfall_mm is None:
        return "Unknown"
    if rainfall_mm < 20:
        return "Low"
    if rainfall_mm > 250:
        return "High"
    return "Normal"


def compute_weather_suitability(weather: dict[str, float | None]) -> int:
    """No per-crop ideal-range table exists in the schema, so this scores
    general growing-condition plausibility (rainfall present but not
    extreme, temperature in a broad crop-safe band) rather than a
    crop-specific fit."""
    rainfall_mm = weather["rainfall_mm"]
    temperature_c = weather["temperature_c"]
    if rainfall_mm is None or temperature_c is None:
        return 50  # no weather_history for this district/month yet

    score = 100.0
    if rainfall_mm < 10 or rainfall_mm > 350:
        score -= 25
    elif rainfall_mm < 20 or rainfall_mm > 250:
        score -= 10

    if temperature_c < 10 or temperature_c > 40:
        score -= 25
    elif temperature_c < 15 or temperature_c > 35:
        score -= 10

    return round(clamp(score, 0, 100))


def weather_tag_from_score(score: int) -> str:
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Moderate"
    return "Poor"


FORECAST_LABEL = {"Good": "Favorable", "Moderate": "Mixed", "Poor": "Unfavorable"}


def compute_risk(weather: dict[str, float | None]) -> str:
    """Rainfall variability across seeded years, as a proxy for weather risk."""
    rainfall_mm = weather["rainfall_mm"]
    rainfall_stddev = weather["rainfall_stddev"]
    if not rainfall_mm:
        return "Medium"
    coefficient_of_variation = (rainfall_stddev or 0) / rainfall_mm
    if coefficient_of_variation < 0.2:
        return "Low"
    if coefficient_of_variation < 0.4:
        return "Medium"
    return "High"


def get_market_data(cur: Cursor, district_id: int, crop_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT expected_supply_qty, expected_demand_qty, demand_gap, unit
        FROM crop_market_data
        WHERE district_id = %s AND crop_id = %s
        ORDER BY year DESC
        LIMIT 1
        """,
        (district_id, crop_id),
    )
    row = cur.fetchone()
    if row is None:
        return {"expected_supply_qty": None, "expected_demand_qty": None, "demand_gap": None, "unit": None}
    supply, demand, gap, unit = row
    return {
        "expected_supply_qty": float(supply) if supply is not None else None,
        "expected_demand_qty": float(demand) if demand is not None else None,
        "demand_gap": float(gap) if gap is not None else None,
        "unit": unit,
    }


def demand_level_from_gap(demand_gap: float | None, expected_demand_qty: float | None) -> tuple[str, float]:
    if not demand_gap or not expected_demand_qty:
        return "Medium", 0.0
    ratio = clamp(demand_gap / expected_demand_qty, -1, 1)
    if ratio > 0.15:
        return "High", ratio
    if ratio > -0.05:
        return "Medium", ratio
    return "Low", ratio


def compute_opportunity_pct(demand_gap_ratio: float, weather_score: int) -> int:
    demand_component = 50 + demand_gap_ratio * 50
    opportunity = 0.6 * demand_component + 0.4 * weather_score
    return round(clamp(opportunity, 0, 100))


def compute_confidence(cur: Cursor, district_id: int, crop_id: int, month: int) -> tuple[int, str]:
    cur.execute(
        """
        SELECT count(DISTINCT year) FROM crop_production
        WHERE district_id = %s AND crop_id = %s AND data_source = 'ACTUAL'
        """,
        (district_id, crop_id),
    )
    (actual_years,) = cur.fetchone()
    actual_years = min(actual_years or 0, 5)

    cur.execute(
        "SELECT count(*) FROM weather_history WHERE district_id = %s AND month = %s",
        (district_id, month),
    )
    (weather_rows,) = cur.fetchone()
    weather_recent = weather_rows > 0

    cur.execute(
        """
        SELECT count(*) FROM crop_calendar
        WHERE district_id = %s AND crop_id = %s AND month = %s AND expected_usage
        """,
        (district_id, crop_id, month),
    )
    (calendar_rows,) = cur.fetchone()
    calendar_complete = calendar_rows > 0

    confidence_pct = round((actual_years / 5) * 50 + (25 if weather_recent else 0) + (25 if calendar_complete else 0))
    basis = (
        f"{actual_years} year(s) of ACTUAL history, weather data "
        f"{'current' if weather_recent else 'unavailable'} for this month, "
        f"crop calendar coverage {'complete' if calendar_complete else 'partial'}"
    )
    return confidence_pct, basis


def build_summary(demand_level: str, weather_tag: str, demand_gap: float | None) -> str:
    demand_phrase = {
        "High": "Historical demand has increased",
        "Medium": "Historical demand is stable",
        "Low": "Historical demand has softened",
    }[demand_level]
    weather_phrase = {
        "Good": "weather is favourable",
        "Moderate": "weather is mixed",
        "Poor": "weather is unfavourable",
    }[weather_tag]
    gap_phrase = "the demand gap is positive" if (demand_gap or 0) > 0 else "the demand gap is narrow or negative"
    return f"{demand_phrase}, {weather_phrase}, and {gap_phrase}."


def crop_cycle_weeks(crop_category: str | None) -> tuple[int, int]:
    return CROP_CYCLE_WEEKS_BY_CATEGORY.get(crop_category or "", DEFAULT_CYCLE_WEEKS)


def estimate_harvest_month(sowing_month: int, cycle_weeks: tuple[int, int]) -> int:
    avg_weeks = sum(cycle_weeks) / 2
    months_offset = round(avg_weeks / 4.345)
    return ((sowing_month - 1 + months_offset) % 12) + 1


def score_crop(cur: Cursor, district_id: int, crop_id: int, month: int) -> dict[str, Any]:
    """The single scoring pass every farmer-facing endpoint reuses for one
    crop+district+month: market data, weather suitability, demand/risk
    tags, opportunity score, and a confidence figure."""
    market = get_market_data(cur, district_id, crop_id)
    weather = get_weather_aggregate(cur, district_id, month)
    weather_score = compute_weather_suitability(weather)
    weather_tag = weather_tag_from_score(weather_score)
    demand_level, gap_ratio = demand_level_from_gap(market["demand_gap"], market["expected_demand_qty"])
    risk_tag = compute_risk(weather)
    opportunity_pct = compute_opportunity_pct(gap_ratio, weather_score)
    confidence_pct, confidence_basis = compute_confidence(cur, district_id, crop_id, month)
    summary = build_summary(demand_level, weather_tag, market["demand_gap"])
    return {
        "market": market,
        "weather": weather,
        "weather_score": weather_score,
        "weather_tag": weather_tag,
        "demand_level": demand_level,
        "risk_tag": risk_tag,
        "opportunity_pct": opportunity_pct,
        "confidence_pct": confidence_pct,
        "confidence_basis": confidence_basis,
        "summary": summary,
    }
