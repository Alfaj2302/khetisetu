/**
 * GET /api/v1/{states,districts,crops,seasons,products}
 *
 * Small fixed lookup tables (<= 29 rows each), returned in full and ordered by
 * id — no pagination or search on the API side, so these are cached hard.
 */
import { apiClient } from "./client";
import { API_V1 } from "./config";
import type { CropOut, DistrictOut, ProductOut, SeasonOut, StateOut } from "./types";

export const referenceService = {
  listStates: () => apiClient.get<StateOut[]>(`${API_V1}/states`),

  listDistricts: (stateId?: number | null) =>
    apiClient.get<DistrictOut[]>(`${API_V1}/districts`, { state_id: stateId }),

  listCrops: () => apiClient.get<CropOut[]>(`${API_V1}/crops`),

  listSeasons: () => apiClient.get<SeasonOut[]>(`${API_V1}/seasons`),

  listProducts: (fertilizerType?: string | null) =>
    apiClient.get<ProductOut[]>(`${API_V1}/products`, { fertilizer_type: fertilizerType }),
};
