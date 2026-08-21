"""Job 2: live crop-opportunity scoring.

DELIBERATELY NOT A TRAINED MODEL. The farmer has just typed their acreage and
irrigation status and can drag a rainfall slider; a model fitted last night
knows nothing about any of that. A formula recomputes from their actual inputs
on every request, and every term can be shown to them and argued with.

The score is a weighted sum of four components, each 0-100 and each returned
separately so the UI can show the breakdown rather than one opaque number:

    weather_fit    is this month's weather right for THIS crop
    demand_supply  is expected demand above expected supply
    demand_trend   is demand growing or shrinking (last few years)
    stability      how much rainfall and demand jump around

`confidence_pct` is computed and reported SEPARATELY, and is not part of the
score. It answers a different question - how much real data is behind any of
this - so that "high opportunity, low confidence" stays sayable.

Two things the previous version got wrong, both fixed here:

1. Weather scoring was crop-agnostic. Every crop in a district got an identical
   weather score, which made "is the weather right for this crop" unanswerable.
2. It was a step function on rainfall bands, so a +-30% rainfall change usually
   crossed no threshold and the what-if slider returned "No change" across its
   entire range (measured: -100% rainfall produced the same score). Scoring is
   now continuous in both temperature and rainfall, so any change moves it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Cursor

# ---------------------------------------------------------------
# Tunables. Every magic number in this module lives here.
# ---------------------------------------------------------------

COMPONENT_WEIGHTS: dict[str, float] = {
    "weather_fit": 0.35,
    "demand_supply": 0.30,
    "demand_trend": 0.20,
    "stability": 0.15,
}

# Demand growth that saturates the trend component. +-10%/yr -> 0 or 100.
TREND_FULL_SCALE = 0.10

# Coefficient of variation that saturates the stability component (0 score).
CV_FULL_SCALE = 0.50

# Monthly rainfall band, as multiples of the crop's derived monthly need.
WATER_OPT_LO_MULT = 0.80
WATER_OPT_HI_MULT = 1.40
WATER_ABS_HI_MULT = 3.00  # beyond this, waterlogging

# How much of a rainfall DEFICIT irrigation makes up for. Only applied when the
# shortfall is on the dry side - irrigation cannot fix waterlogging.
IRRIGATION_RELIEF = 0.60

DEFAULT_CYCLE_WEEKS = (10, 14)
CROP_CYCLE_WEEKS_BY_CATEGORY: dict[str, tuple[int, int]] = {
    "Cereal": (10, 16),
    "Vegetable": (8, 12),
    "Fibre": (20, 26),
    "Oilseed": (12, 16),
    "Pulse": (10, 14),
    "Fruit": (20, 40),
    "Spice": (16, 24),
    "Cash crop": (40, 52),
}

RISK_FACTORS = {
    "Low": ["Stable historical rainfall", "Market demand broadly steady"],
    "Medium": ["Rainfall variability", "Market demand uncertainty"],
    "High": ["High rainfall variability", "Market demand uncertainty", "Limited historical data"],
}


# ---------------------------------------------------------------
# Per-crop agronomic requirements
# ---------------------------------------------------------------


@dataclass(frozen=True)
class CropRequirement:
    """Growing requirements for one crop.

    temp_optimal_*  mean-temperature band for good growth
    temp_absolute_* beyond this, severe stress or failure
    water_seasonal_mm_* total crop water requirement over one full season
    growing_days_*  season length, used to turn seasonal water into a monthly
                    expectation comparable with weather_history's monthly rows
    """

    temp_optimal_min_c: float
    temp_optimal_max_c: float
    temp_absolute_min_c: float
    temp_absolute_max_c: float
    water_seasonal_mm_min: float
    water_seasonal_mm_max: float
    growing_days_min: int
    growing_days_max: int
    certainty: str = "standard-knowledge"
    source: str = ""

    @property
    def monthly_water_mm(self) -> float:
        """Seasonal requirement spread over the season, in mm/month."""
        months = max(1.0, ((self.growing_days_min + self.growing_days_max) / 2) / 30.44)
        return ((self.water_seasonal_mm_min + self.water_seasonal_mm_max) / 2) / months


# Filled by ml-independent research; see CROP_REQUIREMENT_PROVENANCE below.
# Keyed by crops.name. Categories act as the fallback for anything unlisted.
CROP_REQUIREMENTS: dict[str, CropRequirement] = {}

CATEGORY_REQUIREMENTS: dict[str, CropRequirement] = {}

# A last-resort band wide enough not to punish an unknown crop, but honest
# enough that confidence reporting can flag it.
FALLBACK_REQUIREMENT = CropRequirement(
    temp_optimal_min_c=18.0,
    temp_optimal_max_c=32.0,
    temp_absolute_min_c=8.0,
    temp_absolute_max_c=42.0,
    water_seasonal_mm_min=400.0,
    water_seasonal_mm_max=700.0,
    growing_days_min=90,
    growing_days_max=130,
    certainty="uncertain",
    source="generic fallback - no per-crop figures available",
)


def crop_requirement(crop_name: str | None, crop_category: str | None) -> CropRequirement:
    if crop_name and crop_name in CROP_REQUIREMENTS:
        return CROP_REQUIREMENTS[crop_name]
    if crop_category and crop_category in CATEGORY_REQUIREMENTS:
        return CATEGORY_REQUIREMENTS[crop_category]
    return FALLBACK_REQUIREMENT


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def band_score(value: float, opt_lo: float, opt_hi: float, abs_lo: float, abs_hi: float) -> float:
    """Continuous 0-100 trapezoid: full marks inside the optimal band, decaying
    linearly to zero at the absolute limits.

    Continuity is the point. The previous implementation subtracted fixed
    penalties at hard thresholds, so a change that did not cross a threshold
    changed nothing at all - which is why the what-if slider was inert.
    """
    if opt_lo <= value <= opt_hi:
        return 100.0
    if value < opt_lo:
        if value <= abs_lo or opt_lo <= abs_lo:
            return 0.0
        return 100.0 * (value - abs_lo) / (opt_lo - abs_lo)
    if value >= abs_hi or abs_hi <= opt_hi:
        return 0.0
    return 100.0 * (abs_hi - value) / (abs_hi - opt_hi)


def coefficient_of_variation(mean: float | None, stddev: float | None) -> float | None:
    if not mean or mean <= 0 or stddev is None:
        return None
    return stddev / mean


# ---------------------------------------------------------------
# Reference reads
# ---------------------------------------------------------------


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


def get_district_calendar_months(cur: Cursor, district_id: int) -> list[int]:
    """Every month this district has any sowing entry for.

    Used only to explain an empty recommendation list. No district currently
    has a crop_calendar row for March, so a March request legitimately matches
    no crops - this is what lets the endpoint say which months do work instead
    of returning a bare [].
    """
    cur.execute(
        """
        SELECT DISTINCT month FROM crop_calendar
        WHERE district_id = %s AND expected_usage
        ORDER BY month
        """,
        (district_id,),
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


def get_demand_history(cur: Cursor, district_id: int, crop_id: int, years: int = 3) -> list[tuple[int, float]]:
    """Most recent `years` of expected demand, newest first. Feeds both the
    trend component and the demand half of stability."""
    cur.execute(
        """
        SELECT year, expected_demand_qty
        FROM crop_market_data
        WHERE district_id = %s AND crop_id = %s AND expected_demand_qty IS NOT NULL
        ORDER BY year DESC
        LIMIT %s
        """,
        (district_id, crop_id, years),
    )
    return [(r[0], float(r[1])) for r in cur.fetchall()]


# ---------------------------------------------------------------
# The four components
# ---------------------------------------------------------------


def score_weather_fit(
    weather: dict[str, float | None],
    requirement: CropRequirement,
    *,
    irrigation_available: bool | None = None,
) -> tuple[float, str]:
    """Temperature fit and water fit for THIS crop, averaged. Continuous."""
    rainfall_mm = weather.get("rainfall_mm")
    temperature_c = weather.get("temperature_c")

    if rainfall_mm is None and temperature_c is None:
        return 50.0, "No weather history for this district and month"

    parts: list[float] = []
    notes: list[str] = []

    if temperature_c is not None:
        temp_score = band_score(
            temperature_c,
            requirement.temp_optimal_min_c,
            requirement.temp_optimal_max_c,
            requirement.temp_absolute_min_c,
            requirement.temp_absolute_max_c,
        )
        parts.append(temp_score)
        if temp_score >= 95:
            notes.append(f"temperature {temperature_c:.0f}C is in the ideal band")
        elif temperature_c < requirement.temp_optimal_min_c:
            notes.append(f"temperature {temperature_c:.0f}C is below the ideal band")
        else:
            notes.append(f"temperature {temperature_c:.0f}C is above the ideal band")

    if rainfall_mm is not None:
        need = requirement.monthly_water_mm
        water_score = band_score(
            rainfall_mm,
            need * WATER_OPT_LO_MULT,
            need * WATER_OPT_HI_MULT,
            0.0,
            need * WATER_ABS_HI_MULT,
        )
        # Irrigation offsets a shortfall, not an excess.
        if irrigation_available and rainfall_mm < need * WATER_OPT_LO_MULT:
            water_score += (100.0 - water_score) * IRRIGATION_RELIEF
            notes.append(f"rainfall {rainfall_mm:.0f}mm is short of ~{need:.0f}mm, offset by irrigation")
        elif water_score >= 95:
            notes.append(f"rainfall {rainfall_mm:.0f}mm suits a ~{need:.0f}mm/month need")
        elif rainfall_mm < need:
            notes.append(f"rainfall {rainfall_mm:.0f}mm is short of a ~{need:.0f}mm/month need")
        else:
            notes.append(f"rainfall {rainfall_mm:.0f}mm exceeds a ~{need:.0f}mm/month need")
        parts.append(water_score)

    return clamp(sum(parts) / len(parts), 0, 100), "; ".join(notes)


def score_demand_supply(market: dict[str, Any]) -> tuple[float, str, str]:
    """Returns (score, demand_level, explanation)."""
    gap = market.get("demand_gap")
    demand = market.get("expected_demand_qty")
    if not gap or not demand:
        return 50.0, "Medium", "No demand/supply figures for this district and crop"

    ratio = clamp(gap / demand, -1.0, 1.0)
    score = 50.0 + ratio * 50.0
    if ratio > 0.15:
        level = "High"
    elif ratio > -0.05:
        level = "Medium"
    else:
        level = "Low"
    return score, level, f"expected demand exceeds supply by {ratio:+.1%}"


def score_demand_trend(history: list[tuple[int, float]]) -> tuple[float, str]:
    """Compound annual growth in expected demand, mapped onto 0-100.

    50 means flat. TREND_FULL_SCALE (10%/yr) in either direction saturates.
    """
    usable = [(year, value) for year, value in history if value > 0]
    if len(usable) < 2:
        return 50.0, "Not enough demand history to judge a trend"

    usable.sort(key=lambda item: item[0])
    (oldest_year, oldest), (newest_year, newest) = usable[0], usable[-1]
    span = max(1, newest_year - oldest_year)
    cagr = (newest / oldest) ** (1.0 / span) - 1.0

    score = 50.0 + clamp(cagr / TREND_FULL_SCALE, -1.0, 1.0) * 50.0
    direction = "growing" if cagr > 0.01 else ("shrinking" if cagr < -0.01 else "flat")
    return clamp(score, 0, 100), f"demand {direction} {cagr:+.1%}/yr over {span} year(s)"


def score_stability(
    weather: dict[str, float | None],
    history: list[tuple[int, float]],
) -> tuple[float, str, str]:
    """How much rainfall and demand jump around. Returns (score, risk_tag, why)."""
    variations: list[float] = []
    notes: list[str] = []

    rain_cv = coefficient_of_variation(weather.get("rainfall_mm"), weather.get("rainfall_stddev"))
    if rain_cv is not None:
        variations.append(rain_cv)
        notes.append(f"rainfall varies {rain_cv:.0%} year to year")

    values = [value for _, value in history if value > 0]
    if len(values) >= 2:
        mean = sum(values) / len(values)
        stddev = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
        demand_cv = coefficient_of_variation(mean, stddev)
        if demand_cv is not None:
            variations.append(demand_cv)
            notes.append(f"demand varies {demand_cv:.0%} year to year")

    if not variations:
        return 50.0, "Medium", "Not enough history to judge stability"

    mean_cv = sum(variations) / len(variations)
    score = 100.0 * (1.0 - clamp(mean_cv / CV_FULL_SCALE, 0.0, 1.0))
    risk_tag = "Low" if score >= 70 else ("Medium" if score >= 40 else "High")
    return clamp(score, 0, 100), risk_tag, "; ".join(notes)


def combine(components: dict[str, float]) -> int:
    total = sum(components[name] * weight for name, weight in COMPONENT_WEIGHTS.items())
    return round(clamp(total, 0, 100))


# ---------------------------------------------------------------
# Presentation helpers kept from the previous version
# ---------------------------------------------------------------


def rainfall_bucket(rainfall_mm: float | None) -> str:
    if rainfall_mm is None:
        return "Unknown"
    if rainfall_mm < 20:
        return "Low"
    if rainfall_mm > 250:
        return "High"
    return "Normal"


def weather_tag_from_score(score: float) -> str:
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Moderate"
    return "Poor"


FORECAST_LABEL = {"Good": "Favorable", "Moderate": "Mixed", "Poor": "Unfavorable"}


def generic_weather_suitability(weather: dict[str, float | None]) -> int:
    """Crop-agnostic plausibility, for GET /farmer/weather which has no crop
    context. Everything crop-facing uses score_weather_fit instead."""
    score, _ = score_weather_fit(weather, FALLBACK_REQUIREMENT)
    return round(score)


def crop_cycle_weeks(crop_category: str | None) -> tuple[int, int]:
    return CROP_CYCLE_WEEKS_BY_CATEGORY.get(crop_category or "", DEFAULT_CYCLE_WEEKS)


def estimate_harvest_month(sowing_month: int, cycle_weeks: tuple[int, int]) -> int:
    avg_weeks = sum(cycle_weeks) / 2
    months_offset = round(avg_weeks / 4.345)
    return ((sowing_month - 1 + months_offset) % 12) + 1


def compute_confidence(cur: Cursor, district_id: int, crop_id: int, month: int) -> tuple[int, str]:
    """How much real data is behind the score. Reported separately and NEVER
    folded into opportunity_pct - "high opportunity, low confidence" has to stay
    sayable."""
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


def build_summary(demand_level: str, weather_tag: str, trend_note: str) -> str:
    demand_phrase = {
        "High": "Demand is running ahead of supply",
        "Medium": "Demand and supply are broadly balanced",
        "Low": "Supply is running ahead of demand",
    }[demand_level]
    weather_phrase = {
        "Good": "the weather suits this crop",
        "Moderate": "the weather is workable",
        "Poor": "the weather is against it",
    }[weather_tag]
    return f"{demand_phrase}, {weather_phrase}, and {trend_note}."


# ---------------------------------------------------------------
# The single scoring pass every farmer endpoint reuses
# ---------------------------------------------------------------


def score_crop(
    cur: Cursor,
    district_id: int,
    crop_id: int,
    month: int,
    *,
    crop_name: str | None = None,
    crop_category: str | None = None,
    irrigation_available: bool | None = None,
    rainfall_change_pct: float = 0.0,
) -> dict[str, Any]:
    """One crop, one district, one month.

    `rainfall_change_pct` is what makes the what-if slider work: the scenario
    endpoint calls this with a shifted rainfall instead of maintaining a second,
    divergent scoring path.
    """
    if crop_name is None or crop_category is None:
        cur.execute("SELECT name, crop_category FROM crops WHERE id = %s", (crop_id,))
        row = cur.fetchone()
        if row:
            crop_name, crop_category = crop_name or row[0], crop_category or row[1]

    requirement = crop_requirement(crop_name, crop_category)
    weather = get_weather_aggregate(cur, district_id, month)
    if rainfall_change_pct and weather["rainfall_mm"] is not None:
        weather = dict(weather)
        weather["rainfall_mm"] = max(0.0, weather["rainfall_mm"] * (1 + rainfall_change_pct / 100))

    market = get_market_data(cur, district_id, crop_id)
    history = get_demand_history(cur, district_id, crop_id)

    weather_score, weather_note = score_weather_fit(
        weather, requirement, irrigation_available=irrigation_available,
    )
    demand_score, demand_level, demand_note = score_demand_supply(market)
    trend_score, trend_note = score_demand_trend(history)
    stability_score, risk_tag, stability_note = score_stability(weather, history)

    components = {
        "weather_fit": weather_score,
        "demand_supply": demand_score,
        "demand_trend": trend_score,
        "stability": stability_score,
    }
    opportunity_pct = combine(components)
    weather_tag = weather_tag_from_score(weather_score)
    confidence_pct, confidence_basis = compute_confidence(cur, district_id, crop_id, month)

    return {
        "crop_name": crop_name,
        "crop_category": crop_category,
        "market": market,
        "weather": weather,
        "components": {name: round(value, 1) for name, value in components.items()},
        "component_notes": {
            "weather_fit": weather_note,
            "demand_supply": demand_note,
            "demand_trend": trend_note,
            "stability": stability_note,
        },
        "weights": dict(COMPONENT_WEIGHTS),
        "weather_score": round(weather_score),
        "weather_tag": weather_tag,
        "demand_level": demand_level,
        "risk_tag": risk_tag,
        "opportunity_pct": opportunity_pct,
        "confidence_pct": confidence_pct,
        "confidence_basis": confidence_basis,
        "requirement_certainty": requirement.certainty,
        "summary": build_summary(demand_level, weather_tag, trend_note),
    }
