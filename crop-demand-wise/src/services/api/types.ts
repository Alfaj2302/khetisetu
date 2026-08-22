/**
 * Wire types for the FasalCast / KhetiSetu API.
 *
 * These mirror `backend/openapi.json` (generated from `backend/app/schemas.py`)
 * field for field. Keep them in sync when the backend schema changes — nothing
 * generates them automatically.
 *
 * The /auth/* request and response types are deliberately absent: this app has
 * no sign-in flow and never calls those endpoints.
 */

/* ---------------- shared ---------------- */

export type Role = "FARMER" | "AGRI_BUSINESS" | "ADMIN";
export type RiskLevel = "Low" | "Medium" | "High";
export type DemandLevel = "High" | "Medium" | "Low";
export type WeatherTag = "Good" | "Moderate" | "Poor";

export interface CropRef {
  id: number;
  name: string;
}

export interface DistrictRef {
  id: number;
  name: string;
}

/* ---------------- reference ---------------- */

export interface StateOut {
  id: number;
  name: string;
  state_code: string | null;
}

export interface DistrictOut {
  id: number;
  state_id: number;
  name: string;
  latitude: number | null;
  longitude: number | null;
  also_known_as: string | null;
}

export interface CropOut {
  id: number;
  name: string;
  scientific_name: string | null;
  crop_category: string | null;
}

export interface SeasonOut {
  id: number;
  name: string;
  start_month: number | null;
  end_month: number | null;
}

export interface ProductOut {
  id: number;
  product_name: string;
  product_type: string | null;
  fertilizer_type: string | null;
}

/* ---------------- farmer: crop recommendation ---------------- */

export interface CropRecommendationRequest {
  district_id: number;
  land_area_acres: number;
  irrigation_available: boolean;
  previous_crop_id?: number | null;
  /** 1-12 */
  sowing_month: number;
}

export interface RecommendationItem {
  rank: number;
  crop: CropRef;
  opportunity_pct: number;
  demand_level: DemandLevel;
  weather_tag: WeatherTag;
  risk_tag: RiskLevel;
  summary: string;
  expected_demand_qty: number | null;
  expected_supply_qty: number | null;
  demand_gap: number | null;
  unit: string | null;
  weather_suitability_score: number;
  confidence_pct: number;
  confidence_basis: string;
}

export interface CropRecommendationResponse {
  farmer_intent_id: number | null;
  district: DistrictRef;
  season_id: number | null;
  recommendations: RecommendationItem[];
}

/* ---------------- farmer: weather ---------------- */

export interface CurrentWeather {
  rainfall: string;
  temperature_c: number | null;
  humidity_pct: number | null;
  forecast: string;
}

export interface ForecastDay {
  /** ISO date, e.g. "2026-06-14" */
  date: string;
  temperature_c: number | null;
  rain_probability_pct: number | null;
}

export interface WeatherResponse {
  district_id: number;
  current: CurrentWeather;
  next_7_days: ForecastDay[];
}

/* ---------------- farmer: crop detail ---------------- */

export interface WhyFactor {
  factor: string;
  detail: string;
}

export interface DemandOutlook {
  expected_demand_qty: number | null;
  expected_supply_qty: number | null;
  demand_gap: number | null;
}

export interface WeatherSuitability {
  rainfall: string;
  temperature_c: number | null;
  humidity_pct: number | null;
  score: number;
}

export interface CropSeason {
  sowing_months: number[];
  /** [min, max] pair. */
  growing_period_weeks: number[];
  harvest_months: number[];
}

export interface AgronomicGuidance {
  is_verified: boolean;
  warning: string | null;
  nitrogen_kg_ha: number | null;
  phosphorus_kg_ha: number | null;
  potassium_kg_ha: number | null;
  application_stage: string | null;
}

export interface RiskInfo {
  level: RiskLevel;
  factors: string[];
}

export interface SourceRef {
  id: number;
  organization: string | null;
  source_type: string | null;
}

export interface CropDetailResponse {
  crop: CropRef;
  /** Keys are "demand" | "weather" | "risk" (free-form dict on the wire). */
  tags: Record<string, string>;
  opportunity_pct: number;
  why: WhyFactor[];
  demand_outlook: DemandOutlook;
  weather_suitability: WeatherSuitability;
  crop_season: CropSeason;
  agronomic_guidance: AgronomicGuidance;
  risk: RiskInfo;
  confidence_pct: number;
  sources: SourceRef[];
}

export interface CropDetailQuery {
  district_id: number;
  land_area_acres?: number | null;
  irrigation_available?: boolean | null;
}

/* ---------------- farmer: scenario ---------------- */

export interface ScenarioRequest {
  district_id: number;
  crop_ids: number[];
  rainfall_change_pct?: number;
}

export interface ScenarioScore {
  crop_id: number;
  opportunity_pct: number;
  /** Pre-formatted by the API, e.g. "+4 pts" / "No change". */
  change: string;
}

export interface ScenarioResponse {
  rainfall_change_pct: number;
  scenario_scores: ScenarioScore[];
  recommendation_changed: boolean;
}

/* ---------------- farmer: crop intent ---------------- */

export interface CropIntentRequest {
  district_id: number;
  crop_id: number;
  season_id: number;
  year: number;
  land_area_acres?: number | null;
  irrigation_available?: boolean | null;
  soil_type?: string | null;
}

export interface CropIntentResponse {
  id: number;
}

/* ---------------- business ---------------- */

export interface InputDemandItem {
  product: string;
  quantity: number;
  unit: string;
}

export interface CropIntentSummaryItem {
  crop: string;
  acres: number;
}

export interface AlertItem {
  district: string;
  product: string;
  severity: string;
  message: string;
}

export interface RecommendedAction {
  product: string;
  forecast: number | null;
  current_stock: number | null;
  safety_stock: number | null;
  recommended_dispatch: number | null;
  unit: string;
  action: string;
}

export interface BusinessDashboardResponse {
  season: string;
  expected_input_demand: InputDemandItem[];
  farmer_crop_intent: CropIntentSummaryItem[];
  alerts: AlertItem[];
  recommended_action: RecommendedAction | null;
}

export interface BusinessDashboardQuery {
  district_id: number;
  season_id: number;
  year: number;
}

export interface ForecastItem {
  product_id: number;
  year: number;
  month: number;
  predicted_demand: number;
  lower_bound: number | null;
  upper_bound: number | null;
  confidence: string | null;
  model_version: string;
}

export interface ForecastQuery {
  district_id?: number | null;
  product_id?: number | null;
  year?: number | null;
}

export interface InventoryItem {
  product_id: number;
  quantity: number | null;
  batch_no: string | null;
  manufacturing_date: string | null;
  expiry_date: string | null;
}

export interface TransferItem {
  product_id: number;
  from_district_id: number;
  to_district_id: number;
  recommended_transfer_qty: number;
  reason: string;
}

/* ---------------- rag ---------------- */

export interface RagQueryRequest {
  mode: "explain" | "ask";
  crop_id?: number | null;
  district_id?: number | null;
  computed_context?: Record<string, unknown> | null;
  question?: string | null;
}

export interface RagSourceRef {
  source_id: number;
  organization: string | null;
  title?: string | null;
  url?: string | null;
  source_type?: string | null;
  publication_date?: string | null;
}

/**
 * A passage that actually supports a claim in the answer.
 *
 * Distinct from `sources`: that is what was consulted, this is what was used.
 * Comes from the Messages API's own citation blocks, so it cannot point at a
 * passage the model did not cite.
 */
export interface RagCitation {
  source_id: number;
  chunk_id: number;
  cited_text?: string | null;
  page_start?: number | null;
  page_end?: number | null;
}

export interface RagQueryResponse {
  answer: string;
  sources: RagSourceRef[];
  /**
   * True when the answer leaned on an unverified
   * `fertilizer_recommendations` row (is_verified = false).
   */
  used_placeholder_data: boolean;
  citations: RagCitation[];
  /** False means the answer is a decline, not a thin answer. */
  grounded: boolean;
  declined: boolean;
  /**
   * Which code path wrote the text — lets the UI tell a missing provider apart
   * from a weak answer.
   *   "model"      a generation backend answered, with citations
   *   "extractive" no backend configured/reachable; passages quoted verbatim
   *   "template"   explain mode with no matching documents; built from DB columns
   */
  generated_by: "model" | "template" | "extractive";
  /** "vector" | "metadata" | "none" */
  retrieval: "vector" | "metadata" | "none";
  /** Crops the question named, in ask mode. Two means it was refused. */
  crops_detected: { id: number; name: string }[];
}

export interface RagStatusResponse {
  chunks: number;
  chunks_embedded: number;
  sources_indexed: number;
  embedding_models_present: number;
  generation_model: string | null;
  generation_available: boolean;
  embedding_model: string | null;
  embeddings_available: boolean;
  /** False means citations are verified quotes, not reported by the API. */
  native_citations: boolean;
  readiness: string;
}

/* ---------------- health ---------------- */

export interface HealthResponse {
  status: string;
}

export interface HealthDbResponse {
  status: string;
  states: number;
}
