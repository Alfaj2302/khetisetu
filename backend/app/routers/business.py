from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from psycopg import Cursor

from ..db import get_cursor
from ..errors import ApiError
from ..schemas import (
    AlertItem,
    BusinessDashboardResponse,
    CropIntentSummaryItem,
    ForecastItem,
    InputDemandItem,
    InventoryItem,
    RecommendedAction,
    TransferItem,
)
from ..services import business as business_service

# Open by design: this app has no sign-in flow, so the dashboard reads these
# straight from the database. Everything served here is already aggregated —
# `farmer_crop_intent` is grouped by crop and never selects user_id — so no
# per-farmer row is exposed. Re-add a `require_roles("AGRI_BUSINESS", "ADMIN")`
# router dependency if this API is ever exposed outside a trusted network.
router = APIRouter(prefix="/business", tags=["business"])


@router.get("/dashboard", response_model=BusinessDashboardResponse)
def dashboard(
    district_id: int = Query(...),
    season_id: int = Query(...),
    year: int = Query(...),
    cur: Cursor = Depends(get_cursor),
) -> BusinessDashboardResponse:
    cur.execute("SELECT name FROM districts WHERE id = %s", (district_id,))
    if cur.fetchone() is None:
        raise ApiError(404, "NOT_FOUND", f"district {district_id} not found")

    cur.execute("SELECT name FROM seasons WHERE id = %s", (season_id,))
    season_row = cur.fetchone()
    if season_row is None:
        raise ApiError(404, "NOT_FOUND", f"season {season_id} not found")

    recommended_action = business_service.get_recommended_action(cur, district_id)

    return BusinessDashboardResponse(
        season=f"{season_row[0]} {year}",
        expected_input_demand=[
            InputDemandItem(**item) for item in business_service.get_expected_input_demand(cur, district_id, year)
        ],
        farmer_crop_intent=[
            CropIntentSummaryItem(**item)
            for item in business_service.get_farmer_crop_intent_summary(cur, district_id, season_id, year)
        ],
        alerts=[AlertItem(**item) for item in business_service.get_alerts(cur, district_id)],
        recommended_action=RecommendedAction(**recommended_action) if recommended_action else None,
    )


@router.get("/forecast", response_model=list[ForecastItem])
def forecast(
    district_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    year: int | None = Query(default=None),
    cur: Cursor = Depends(get_cursor),
) -> list[ForecastItem]:
    return [ForecastItem(**item) for item in business_service.get_forecast(cur, district_id, product_id, year)]


@router.get("/inventory", response_model=list[InventoryItem])
def inventory(
    district_id: int | None = Query(default=None),
    cur: Cursor = Depends(get_cursor),
) -> list[InventoryItem]:
    return [InventoryItem(**item) for item in business_service.get_inventory(cur, district_id)]


@router.get("/transfers", response_model=list[TransferItem])
def transfers(cur: Cursor = Depends(get_cursor)) -> list[TransferItem]:
    return [TransferItem(**item) for item in business_service.get_transfers(cur)]


@router.get("/alerts", response_model=list[AlertItem])
def alerts(
    district_id: int | None = Query(default=None),
    cur: Cursor = Depends(get_cursor),
) -> list[AlertItem]:
    return [AlertItem(**item) for item in business_service.get_alerts(cur, district_id)]
