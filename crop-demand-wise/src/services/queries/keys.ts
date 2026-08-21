/**
 * Query-key factory. One place to look when invalidating, so no route has to
 * guess how another route spelled its key.
 */
import type {
  BusinessDashboardQuery,
  CropDetailQuery,
  ForecastQuery,
  ScenarioRequest,
} from "../api/types";

export const queryKeys = {
  reference: {
    all: ["reference"] as const,
    states: () => [...queryKeys.reference.all, "states"] as const,
    districts: (stateId?: number | null) =>
      [...queryKeys.reference.all, "districts", stateId ?? null] as const,
    crops: () => [...queryKeys.reference.all, "crops"] as const,
    seasons: () => [...queryKeys.reference.all, "seasons"] as const,
    products: (fertilizerType?: string | null) =>
      [...queryKeys.reference.all, "products", fertilizerType ?? null] as const,
  },
  farmer: {
    all: ["farmer"] as const,
    weather: (districtId: number) => [...queryKeys.farmer.all, "weather", districtId] as const,
    cropDetail: (cropId: number, query: CropDetailQuery) =>
      [...queryKeys.farmer.all, "crop", cropId, query] as const,
    scenario: (payload: ScenarioRequest) => [...queryKeys.farmer.all, "scenario", payload] as const,
  },
  business: {
    all: ["business"] as const,
    dashboard: (query: BusinessDashboardQuery) =>
      [...queryKeys.business.all, "dashboard", query] as const,
    forecast: (query: ForecastQuery) => [...queryKeys.business.all, "forecast", query] as const,
    inventory: (districtId?: number | null) =>
      [...queryKeys.business.all, "inventory", districtId ?? null] as const,
    transfers: () => [...queryKeys.business.all, "transfers"] as const,
    alerts: (districtId?: number | null) =>
      [...queryKeys.business.all, "alerts", districtId ?? null] as const,
  },
  health: {
    all: ["health"] as const,
    db: () => ["health", "db"] as const,
  },
} as const;
