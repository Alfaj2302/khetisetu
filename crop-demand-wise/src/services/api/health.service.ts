/** GET /health and /health/db — unversioned, no auth. */
import { apiClient } from "./client";
import type { HealthDbResponse, HealthResponse } from "./types";

export const healthService = {
  check: () => apiClient.get<HealthResponse>("/health"),
  checkDb: () => apiClient.get<HealthDbResponse>("/health/db"),
};
