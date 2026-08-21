/**
 * Business-dashboard queries. Each takes an `enabled` flag so the dashboard can
 * hold requests back until its district/season/year selectors are resolved.
 */
import { useQuery } from "@tanstack/react-query";

import { businessService } from "../api";
import type { BusinessDashboardQuery, ForecastQuery } from "../api/types";
import { queryKeys } from "./keys";

export function useBusinessDashboard(query: BusinessDashboardQuery, enabled = true) {
  return useQuery({
    queryKey: queryKeys.business.dashboard(query),
    queryFn: () => businessService.getDashboard(query),
    enabled,
  });
}

export function useBusinessForecast(query: ForecastQuery, enabled = true) {
  return useQuery({
    queryKey: queryKeys.business.forecast(query),
    queryFn: () => businessService.getForecast(query),
    enabled,
  });
}

export function useBusinessInventory(districtId?: number | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.business.inventory(districtId),
    queryFn: () => businessService.getInventory(districtId),
    enabled,
  });
}

export function useBusinessTransfers(enabled = true) {
  return useQuery({
    queryKey: queryKeys.business.transfers(),
    queryFn: () => businessService.getTransfers(),
    enabled,
  });
}

export function useBusinessAlerts(districtId?: number | null, enabled = true) {
  return useQuery({
    queryKey: queryKeys.business.alerts(districtId),
    queryFn: () => businessService.getAlerts(districtId),
    enabled,
  });
}
