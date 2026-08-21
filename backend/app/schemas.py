from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field

Role = Literal["FARMER", "AGRI_BUSINESS", "ADMIN"]
Month = Annotated[int, Field(ge=1, le=12)]

# ---------------------------------------------------------------
# Auth
# ---------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str | None = None
    role: Role
    email: EmailStr
    password: str = Field(min_length=8)
    state_id: int | None = None
    district_id: int | None = None
    phone: str | None = None


class RegisterResponse(BaseModel):
    id: int
    name: str | None
    role: Role
    email: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginUser(BaseModel):
    id: int
    role: Role
    district_id: int | None


class LoginResponse(BaseModel):
    token: str
    user: LoginUser


# ---------------------------------------------------------------
# Reference
# ---------------------------------------------------------------


class StateOut(BaseModel):
    id: int
    name: str
    state_code: str | None


class DistrictOut(BaseModel):
    id: int
    state_id: int
    name: str
    latitude: float | None
    longitude: float | None
    also_known_as: str | None


class CropOut(BaseModel):
    id: int
    name: str
    scientific_name: str | None
    crop_category: str | None


class SeasonOut(BaseModel):
    id: int
    name: str
    start_month: int | None
    end_month: int | None


class ProductOut(BaseModel):
    id: int
    product_name: str
    product_type: str | None
    fertilizer_type: str | None


# ---------------------------------------------------------------
# Farmer: crop-recommendation
# ---------------------------------------------------------------


class CropRecommendationRequest(BaseModel):
    district_id: int
    land_area_acres: float
    irrigation_available: bool
    previous_crop_id: int | None = None
    sowing_month: Month


class ScoreComponents(BaseModel):
    """The four terms behind opportunity_pct, each 0-100.

    Exposed so the UI can show a farmer WHY a crop scored what it did, instead
    of one opaque percentage. `weights` on the parent says how they combine.
    """

    weather_fit: float
    demand_supply: float
    demand_trend: float
    stability: float


class DistrictRef(BaseModel):
    id: int
    name: str


class CropRef(BaseModel):
    id: int
    name: str


class RecommendationItem(BaseModel):
    rank: int
    crop: CropRef
    opportunity_pct: int
    demand_level: Literal["High", "Medium", "Low"]
    weather_tag: Literal["Good", "Moderate", "Poor"]
    risk_tag: Literal["Low", "Medium", "High"]
    summary: str
    expected_demand_qty: float | None
    expected_supply_qty: float | None
    demand_gap: float | None
    unit: str | None
    weather_suitability_score: int
    confidence_pct: int
    confidence_basis: str
    components: ScoreComponents
    component_notes: dict[str, str]
    weights: dict[str, float]


class CropRecommendationResponse(BaseModel):
    farmer_intent_id: int | None
    district: DistrictRef
    season_id: int | None
    recommendations: list[RecommendationItem]
    # Set only when `recommendations` is empty, to say why. Optional so every
    # existing caller keeps working unchanged.
    notice: str | None = None


# ---------------------------------------------------------------
# Farmer: weather
# ---------------------------------------------------------------


class CurrentWeather(BaseModel):
    rainfall: str
    temperature_c: float | None
    humidity_pct: float | None
    forecast: str


class ForecastDay(BaseModel):
    date: str
    temperature_c: float | None
    rain_probability_pct: int | None


class WeatherResponse(BaseModel):
    district_id: int
    current: CurrentWeather
    next_7_days: list[ForecastDay]


# ---------------------------------------------------------------
# Farmer: crop detail
# ---------------------------------------------------------------


class WhyFactor(BaseModel):
    factor: str
    detail: str


class DemandOutlook(BaseModel):
    expected_demand_qty: float | None
    expected_supply_qty: float | None
    demand_gap: float | None


class WeatherSuitability(BaseModel):
    rainfall: str
    temperature_c: float | None
    humidity_pct: float | None
    score: int


class CropSeason(BaseModel):
    sowing_months: list[int]
    growing_period_weeks: list[int]
    harvest_months: list[int]


class AgronomicGuidance(BaseModel):
    is_verified: bool
    warning: str | None
    nitrogen_kg_ha: float | None
    phosphorus_kg_ha: float | None
    potassium_kg_ha: float | None
    application_stage: str | None


class RiskInfo(BaseModel):
    level: Literal["Low", "Medium", "High"]
    factors: list[str]


class SourceRef(BaseModel):
    id: int
    organization: str | None
    source_type: str | None


class CropDetailResponse(BaseModel):
    crop: CropRef
    tags: dict[str, str]
    opportunity_pct: int
    why: list[WhyFactor]
    demand_outlook: DemandOutlook
    weather_suitability: WeatherSuitability
    crop_season: CropSeason
    agronomic_guidance: AgronomicGuidance
    risk: RiskInfo
    confidence_pct: int
    sources: list[SourceRef]
    components: ScoreComponents
    component_notes: dict[str, str]
    weights: dict[str, float]
    # Which month the score was computed for. Callers that pass sowing_month get
    # it back; callers that don't can see which month was assumed.
    reference_month: int


# ---------------------------------------------------------------
# Farmer: what-if scenario
# ---------------------------------------------------------------


class ScenarioRequest(BaseModel):
    district_id: int
    crop_ids: list[int] = Field(min_length=1)
    rainfall_change_pct: float = 0


class ScenarioScore(BaseModel):
    crop_id: int
    opportunity_pct: int
    change: str
    baseline_opportunity_pct: int
    # weather_fit is the only term rainfall moves, so surfacing it explains the
    # delta rather than leaving the farmer to trust it.
    weather_fit: float


class ScenarioResponse(BaseModel):
    rainfall_change_pct: float
    scenario_scores: list[ScenarioScore]
    recommendation_changed: bool


# ---------------------------------------------------------------
# Farmer: crop-intent ("I'm growing this")
# ---------------------------------------------------------------


class CropIntentRequest(BaseModel):
    district_id: int
    crop_id: int
    season_id: int
    year: int
    land_area_acres: float | None = None
    irrigation_available: bool | None = None
    soil_type: str | None = None


class CropIntentResponse(BaseModel):
    id: int


# ---------------------------------------------------------------
# Business
# ---------------------------------------------------------------


class InputDemandItem(BaseModel):
    product: str
    quantity: float
    unit: str  # "packets" - the forecast's native unit, not metric tons


class CropIntentSummaryItem(BaseModel):
    crop: str
    acres: float


class AlertItem(BaseModel):
    district: str
    product: str
    severity: str
    message: str


class RecommendedAction(BaseModel):
    # These were forecast_mt / current_stock_mt / etc. Nothing in the pipeline
    # produces metric tons - the model is trained on historical_sales.qty_in_pkts
    # and `recommendations` stores packets - so the _mt suffix was a 1000x
    # mislabel on a dispatch decision. `unit` now states it explicitly.
    product: str
    forecast: float | None
    current_stock: float | None
    safety_stock: float | None
    recommended_dispatch: float | None
    action: str
    unit: str


class BusinessDashboardResponse(BaseModel):
    season: str
    expected_input_demand: list[InputDemandItem]
    farmer_crop_intent: list[CropIntentSummaryItem]
    alerts: list[AlertItem]
    recommended_action: RecommendedAction | None


class ForecastItem(BaseModel):
    product_id: int
    year: int
    month: int
    predicted_demand: float
    lower_bound: float | None
    upper_bound: float | None
    confidence: str | None
    model_version: str


class InventoryItem(BaseModel):
    product_id: int
    quantity: float | None
    batch_no: str | None
    manufacturing_date: str | None
    expiry_date: str | None


class TransferItem(BaseModel):
    product_id: int
    from_district_id: int
    to_district_id: int
    recommended_transfer_qty: float
    reason: str


# ---------------------------------------------------------------
# RAG
# ---------------------------------------------------------------


class RagQueryRequest(BaseModel):
    mode: Literal["explain", "ask"]
    crop_id: int | None = None
    district_id: int | None = None
    computed_context: dict[str, Any] | None = None
    question: str | None = None


class RagSourceRef(BaseModel):
    source_id: int
    organization: str | None


class RagQueryResponse(BaseModel):
    answer: str
    sources: list[RagSourceRef]
    used_placeholder_data: bool
