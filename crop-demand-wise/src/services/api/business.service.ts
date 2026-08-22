/**
 * GET /api/v1/business/* — agri-business supply planning.
 *
 * Unauthenticated: the app has no sign-in flow, so these read straight from
 * the database (see `backend/app/routers/business.py`). Every response is
 * aggregated or product-level — no per-farmer row is ever exposed.
 *
 * `dashboard.expected_input_demand`, `dashboard.recommended_action`, `forecast`
 * and `alerts` read the batch-ML output tables (`forecast`, `recommendations`),
 * which are empty until that job has run — an empty array there is a real
 * state, not a bug. `inventory` and `transfers` read live tables.
 */
import { apiClient } from "./client";
import { API_V1 } from "./config";
import type {
  AlertItem,
  BusinessDashboardQuery,
  BusinessDashboardResponse,
  ForecastItem,
  ForecastQuery,
  InventoryItem,
  TransferItem,
} from "./types";

export const businessService = {
  getDashboard: (query: BusinessDashboardQuery) =>
    apiClient.get<BusinessDashboardResponse>(`${API_V1}/business/dashboard`, {
      district_id: query.district_id,
      season_id: query.season_id,
      year: query.year,
    }),

  getForecast: (query: ForecastQuery = {}) =>
    apiClient.get<ForecastItem[]>(`${API_V1}/business/forecast`, {
      district_id: query.district_id,
      product_id: query.product_id,
      year: query.year,
    }),

  getInventory: (districtId?: number | null) =>
    apiClient.get<InventoryItem[]>(`${API_V1}/business/inventory`, { district_id: districtId }),

  getTransfers: () => apiClient.get<TransferItem[]>(`${API_V1}/business/transfers`),

  getAlerts: (districtId?: number | null) =>
    apiClient.get<AlertItem[]>(`${API_V1}/business/alerts`, { district_id: districtId }),
};
