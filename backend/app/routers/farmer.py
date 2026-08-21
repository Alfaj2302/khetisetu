from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from psycopg import Cursor

from ..db import get_cursor
from ..deps import CurrentUser, get_current_user_optional
from ..errors import ApiError
from ..schemas import (
    AgronomicGuidance,
    CropDetailResponse,
    CropIntentRequest,
    CropIntentResponse,
    CropRecommendationRequest,
    CropRecommendationResponse,
    CropRef,
    CropSeason,
    CurrentWeather,
    DemandOutlook,
    DistrictRef,
    ForecastDay,
    RecommendationItem,
    RiskInfo,
    ScenarioRequest,
    ScenarioResponse,
    ScenarioScore,
    SourceRef,
    WeatherResponse,
    WeatherSuitability,
    WhyFactor,
)
from ..services import scoring

router = APIRouter(prefix="/farmer", tags=["farmer"])


def _get_district(cur: Cursor, district_id: int) -> tuple[int, str]:
    cur.execute("SELECT id, name FROM districts WHERE id = %s", (district_id,))
    row = cur.fetchone()
    if row is None:
        raise ApiError(404, "NOT_FOUND", f"district {district_id} not found")
    return row[0], row[1]


def _get_crop(cur: Cursor, crop_id: int) -> tuple[int, str, str | None]:
    cur.execute("SELECT id, name, crop_category FROM crops WHERE id = %s", (crop_id,))
    row = cur.fetchone()
    if row is None:
        raise ApiError(404, "NOT_FOUND", f"crop {crop_id} not found")
    return row[0], row[1], row[2]


@router.post("/crop-recommendation", response_model=CropRecommendationResponse)
def crop_recommendation(
    payload: CropRecommendationRequest,
    cur: Cursor = Depends(get_cursor),
    user: CurrentUser | None = Depends(get_current_user_optional),
) -> CropRecommendationResponse:
    district_id, district_name = _get_district(cur, payload.district_id)
    season_id = scoring.resolve_season_id(cur, payload.sowing_month)

    eligible_crops = scoring.get_eligible_crops(cur, district_id, payload.sowing_month)

    scored = [
        (crop, scoring.score_crop(cur, district_id, crop["id"], payload.sowing_month)) for crop in eligible_crops
    ]
    scored.sort(key=lambda item: item[1]["opportunity_pct"], reverse=True)
    top3 = scored[:3]

    recommendations = [
        RecommendationItem(
            rank=rank,
            crop=CropRef(id=crop["id"], name=crop["name"]),
            opportunity_pct=result["opportunity_pct"],
            demand_level=result["demand_level"],
            weather_tag=result["weather_tag"],
            risk_tag=result["risk_tag"],
            summary=result["summary"],
            expected_demand_qty=result["market"]["expected_demand_qty"],
            expected_supply_qty=result["market"]["expected_supply_qty"],
            demand_gap=result["market"]["demand_gap"],
            unit=result["market"]["unit"],
            weather_suitability_score=result["weather_score"],
            confidence_pct=result["confidence_pct"],
            confidence_basis=result["confidence_basis"],
        )
        for rank, (crop, result) in enumerate(top3, start=1)
    ]

    # Flow A's "implicit" intent snapshot: farmer_crop_intent.crop_id is
    # NOT NULL in schema.sql, but this endpoint's whole point is that the
    # farmer hasn't chosen a crop yet — so this records the top recommendation
    # as the working guess. POST /farmer/crop-intent is the explicit
    # confirmation the spec distinguishes this from.
    farmer_intent_id: int | None = None
    if top3:
        top_crop_id = top3[0][0]["id"]
        cur.execute(
            """
            INSERT INTO farmer_crop_intent
                (user_id, district_id, crop_id, previous_crop_id, season_id, year,
                 sowing_month, land_area_acres, irrigation_available, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTUAL')
            RETURNING id
            """,
            (
                user.id if user else None,
                district_id,
                top_crop_id,
                payload.previous_crop_id,
                season_id,
                date.today().year,
                payload.sowing_month,
                payload.land_area_acres,
                payload.irrigation_available,
            ),
        )
        farmer_intent_id = cur.fetchone()[0]

    return CropRecommendationResponse(
        farmer_intent_id=farmer_intent_id,
        district=DistrictRef(id=district_id, name=district_name),
        season_id=season_id,
        recommendations=recommendations,
    )


@router.get("/weather", response_model=WeatherResponse)
def farmer_weather(district_id: int = Query(...), cur: Cursor = Depends(get_cursor)) -> WeatherResponse:
    _get_district(cur, district_id)

    cur.execute(
        """
        SELECT rainfall_mm, temperature_c, humidity_pct
        FROM weather_history
        WHERE district_id = %s
        ORDER BY year DESC, month DESC
        LIMIT 1
        """,
        (district_id,),
    )
    row = cur.fetchone()
    if row:
        rainfall_mm, temperature_c, humidity_pct = row
        weather = {
            "rainfall_mm": float(rainfall_mm) if rainfall_mm is not None else None,
            "temperature_c": float(temperature_c) if temperature_c is not None else None,
            "humidity_pct": float(humidity_pct) if humidity_pct is not None else None,
            "rainfall_stddev": None,
        }
        weather_score = scoring.compute_weather_suitability(weather)
        forecast_label = scoring.FORECAST_LABEL[scoring.weather_tag_from_score(weather_score)]
    else:
        weather = {"rainfall_mm": None, "temperature_c": None, "humidity_pct": None, "rainfall_stddev": None}
        forecast_label = "Unknown"

    current = CurrentWeather(
        rainfall=scoring.rainfall_bucket(weather["rainfall_mm"]),
        temperature_c=weather["temperature_c"],
        humidity_pct=weather["humidity_pct"],
        forecast=forecast_label,
    )

    # weather_forecast is meant to be refreshed from a live weather API
    # (per schema.sql's own comment) — that integration isn't built yet, so
    # this is legitimately empty rather than a bug, until it is.
    cur.execute(
        """
        SELECT forecast_date, temperature_c, rainfall_mm
        FROM weather_forecast
        WHERE district_id = %s AND forecast_date >= current_date
        ORDER BY forecast_date
        LIMIT 7
        """,
        (district_id,),
    )
    next_7_days = [
        ForecastDay(
            date=r[0].isoformat(),
            temperature_c=float(r[1]) if r[1] is not None else None,
            rain_probability_pct=min(100, round(float(r[2]) * 5)) if r[2] is not None else None,
        )
        for r in cur.fetchall()
    ]

    return WeatherResponse(district_id=district_id, current=current, next_7_days=next_7_days)


@router.get("/crop/{crop_id}", response_model=CropDetailResponse)
def crop_detail(
    crop_id: int,
    district_id: int = Query(...),
    land_area_acres: float | None = Query(default=None),
    irrigation_available: bool | None = Query(default=None),
    cur: Cursor = Depends(get_cursor),
) -> CropDetailResponse:
    crop_id, crop_name, crop_category = _get_crop(cur, crop_id)
    district_id, _district_name = _get_district(cur, district_id)

    calendar_months = scoring.get_calendar_months(cur, district_id, crop_id)
    reference_month = calendar_months[0] if calendar_months else date.today().month

    result = scoring.score_crop(cur, district_id, crop_id, reference_month)

    cycle_weeks = scoring.crop_cycle_weeks(crop_category)
    source_months = calendar_months or [reference_month]
    harvest_months = sorted({scoring.estimate_harvest_month(m, cycle_weeks) for m in source_months})

    why = [
        WhyFactor(
            factor="Historical demand",
            detail={
                "High": "Demand has increased relative to supply in recent seasons",
                "Medium": "Demand and supply are broadly balanced in recent seasons",
                "Low": "Demand has softened relative to supply in recent seasons",
            }[result["demand_level"]],
        ),
        WhyFactor(
            factor="Seasonal suitability",
            detail=(
                "Eligible for the selected sowing window"
                if reference_month in calendar_months
                else "No crop calendar entry for this district/month yet"
            ),
        ),
        WhyFactor(factor="Weather", detail=f"Expected conditions are {result['weather_tag'].lower()}"),
        WhyFactor(
            factor="Demand gap",
            detail=(
                "Expected demand is higher than expected supply"
                if (result["market"]["demand_gap"] or 0) > 0
                else "Expected demand does not exceed expected supply"
            ),
        ),
    ]
    if irrigation_available is not None:
        why.append(
            WhyFactor(
                factor="Farmer context",
                detail=(
                    "Irrigation is available on your farm"
                    if irrigation_available
                    else "No irrigation available on your farm"
                ),
            ),
        )
    if land_area_acres is not None:
        why.append(WhyFactor(factor="Farm size", detail=f"Sized for a {land_area_acres:g}-acre plot"))

    cur.execute(
        """
        SELECT is_verified, nitrogen_kg_ha, phosphorus_kg_ha, potassium_kg_ha, application_stage, source_id
        FROM fertilizer_recommendations
        WHERE crop_id = %s
        ORDER BY is_verified DESC, id
        LIMIT 1
        """,
        (crop_id,),
    )
    fert_row = cur.fetchone()
    source_id = None
    if fert_row:
        is_verified, nitrogen, phosphorus, potassium, application_stage, source_id = fert_row
        agronomic_guidance = AgronomicGuidance(
            is_verified=is_verified,
            warning=None if is_verified else "Indicative only - not a verified agronomic prescription",
            nitrogen_kg_ha=float(nitrogen) if nitrogen is not None else None,
            phosphorus_kg_ha=float(phosphorus) if phosphorus is not None else None,
            potassium_kg_ha=float(potassium) if potassium is not None else None,
            application_stage=application_stage,
        )
    else:
        agronomic_guidance = AgronomicGuidance(
            is_verified=False,
            warning="No agronomic guidance available yet for this crop",
            nitrogen_kg_ha=None,
            phosphorus_kg_ha=None,
            potassium_kg_ha=None,
            application_stage=None,
        )

    sources: list[SourceRef] = []
    if source_id is not None:
        cur.execute("SELECT id, organization, source_type FROM sources WHERE id = %s", (source_id,))
        source_row = cur.fetchone()
        if source_row:
            sources.append(SourceRef(id=source_row[0], organization=source_row[1], source_type=source_row[2]))

    return CropDetailResponse(
        crop=CropRef(id=crop_id, name=crop_name),
        tags={"demand": result["demand_level"], "weather": result["weather_tag"], "risk": result["risk_tag"]},
        opportunity_pct=result["opportunity_pct"],
        why=why,
        demand_outlook=DemandOutlook(
            expected_demand_qty=result["market"]["expected_demand_qty"],
            expected_supply_qty=result["market"]["expected_supply_qty"],
            demand_gap=result["market"]["demand_gap"],
        ),
        weather_suitability=WeatherSuitability(
            rainfall=scoring.rainfall_bucket(result["weather"]["rainfall_mm"]),
            temperature_c=result["weather"]["temperature_c"],
            humidity_pct=result["weather"]["humidity_pct"],
            score=result["weather_score"],
        ),
        crop_season=CropSeason(
            sowing_months=calendar_months,
            growing_period_weeks=list(cycle_weeks),
            harvest_months=harvest_months,
        ),
        agronomic_guidance=agronomic_guidance,
        risk=RiskInfo(level=result["risk_tag"], factors=scoring.RISK_FACTORS[result["risk_tag"]]),
        confidence_pct=result["confidence_pct"],
        sources=sources,
    )


@router.post("/scenario", response_model=ScenarioResponse)
def scenario(payload: ScenarioRequest, cur: Cursor = Depends(get_cursor)) -> ScenarioResponse:
    _get_district(cur, payload.district_id)

    cur.execute("SELECT id FROM crops WHERE id = ANY(%s)", (payload.crop_ids,))
    found_ids = {r[0] for r in cur.fetchall()}
    missing = [c for c in payload.crop_ids if c not in found_ids]
    if missing:
        raise ApiError(400, "VALIDATION_ERROR", f"unknown crop_id(s): {missing}")

    baseline_top: int | None = None
    scenario_top: int | None = None
    best_baseline = -1.0
    best_scenario = -1.0
    scores: list[ScenarioScore] = []

    for crop_id in payload.crop_ids:
        calendar_months = scoring.get_calendar_months(cur, payload.district_id, crop_id)
        month = calendar_months[0] if calendar_months else date.today().month

        weather = scoring.get_weather_aggregate(cur, payload.district_id, month)
        market = scoring.get_market_data(cur, payload.district_id, crop_id)
        _, gap_ratio = scoring.demand_level_from_gap(market["demand_gap"], market["expected_demand_qty"])

        baseline_score = scoring.compute_weather_suitability(weather)
        baseline_opportunity = scoring.compute_opportunity_pct(gap_ratio, baseline_score)
        if baseline_opportunity > best_baseline:
            best_baseline, baseline_top = baseline_opportunity, crop_id

        adjusted_weather = dict(weather)
        if adjusted_weather["rainfall_mm"] is not None:
            adjusted_weather["rainfall_mm"] *= 1 + payload.rainfall_change_pct / 100
        scenario_score = scoring.compute_weather_suitability(adjusted_weather)
        scenario_opportunity = scoring.compute_opportunity_pct(gap_ratio, scenario_score)
        if scenario_opportunity > best_scenario:
            best_scenario, scenario_top = scenario_opportunity, crop_id

        delta = scenario_opportunity - baseline_opportunity
        change = "No change" if delta == 0 else (f"+{delta} pts" if delta > 0 else f"{delta} pts")
        scores.append(ScenarioScore(crop_id=crop_id, opportunity_pct=scenario_opportunity, change=change))

    return ScenarioResponse(
        rainfall_change_pct=payload.rainfall_change_pct,
        scenario_scores=scores,
        recommendation_changed=baseline_top != scenario_top,
    )


@router.post("/crop-intent", response_model=CropIntentResponse, status_code=201)
def crop_intent(
    payload: CropIntentRequest,
    cur: Cursor = Depends(get_cursor),
    user: CurrentUser | None = Depends(get_current_user_optional),
) -> CropIntentResponse:
    _get_district(cur, payload.district_id)
    _get_crop(cur, payload.crop_id)

    cur.execute(
        """
        INSERT INTO farmer_crop_intent
            (user_id, district_id, crop_id, season_id, year, land_area_acres,
             irrigation_available, soil_type, data_source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTUAL')
        RETURNING id
        """,
        (
            user.id if user else None,
            payload.district_id,
            payload.crop_id,
            payload.season_id,
            payload.year,
            payload.land_area_acres,
            payload.irrigation_available,
            payload.soil_type,
        ),
    )
    return CropIntentResponse(id=cur.fetchone()[0])
