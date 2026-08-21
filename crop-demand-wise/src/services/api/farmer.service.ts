/**
 * POST/GET /api/v1/farmer/* — the farmer decision-support flow.
 *
 * Auth is optional on all of these. Without a token the recorded
 * `farmer_crop_intent` rows are stored with user_id NULL; the responses are
 * identical either way, so this whole flow works with no token configured.
 */
import { apiClient } from "./client";
import { API_V1 } from "./config";
import type {
  CropDetailQuery,
  CropDetailResponse,
  CropIntentRequest,
  CropIntentResponse,
  CropRecommendationRequest,
  CropRecommendationResponse,
  ScenarioRequest,
  ScenarioResponse,
  WeatherResponse,
} from "./types";

export const farmerService = {
  /**
   * Ranks the crops eligible for this district + sowing month and returns the
   * top 3. Side effect: records an implicit `farmer_crop_intent` row using the
   * #1 crop as the working guess (see `backend/app/routers/farmer.py`), so this
   * is a mutation — never call it from a plain `useQuery`.
   */
  getCropRecommendations: (payload: CropRecommendationRequest) =>
    apiClient.post<CropRecommendationResponse>(`${API_V1}/farmer/crop-recommendation`, payload),

  getWeather: (districtId: number) =>
    apiClient.get<WeatherResponse>(`${API_V1}/farmer/weather`, { district_id: districtId }),

  getCropDetail: (cropId: number, query: CropDetailQuery) =>
    apiClient.get<CropDetailResponse>(`${API_V1}/farmer/crop/${cropId}`, {
      district_id: query.district_id,
      land_area_acres: query.land_area_acres,
      irrigation_available: query.irrigation_available,
    }),

  getScenario: (payload: ScenarioRequest) =>
    apiClient.post<ScenarioResponse>(`${API_V1}/farmer/scenario`, payload),

  /** Explicit "I'm growing this" confirmation, as opposed to the implicit row above. */
  createCropIntent: (payload: CropIntentRequest) =>
    apiClient.post<CropIntentResponse>(`${API_V1}/farmer/crop-intent`, payload),
};
