/** Farmer-flow queries and mutations. */
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { farmerService } from "../api";
import type {
  CropDetailQuery,
  CropIntentRequest,
  CropRecommendationRequest,
  ScenarioRequest,
} from "../api/types";
import { queryKeys } from "./keys";

/**
 * Ranking is a POST that also records an intent row, so it's a mutation: one
 * submit, one row. Callers keep the response in the farm store rather than
 * re-running it on the results screen.
 */
export function useCropRecommendationMutation() {
  return useMutation({
    mutationFn: (payload: CropRecommendationRequest) =>
      farmerService.getCropRecommendations(payload),
  });
}

export function useWeather(districtId: number | null) {
  return useQuery({
    queryKey: queryKeys.farmer.weather(districtId ?? 0),
    queryFn: () => farmerService.getWeather(districtId as number),
    enabled: districtId !== null,
  });
}

export function useCropDetail(cropId: number | null, query: CropDetailQuery | null) {
  return useQuery({
    queryKey: queryKeys.farmer.cropDetail(cropId ?? 0, query ?? { district_id: 0 }),
    queryFn: () => farmerService.getCropDetail(cropId as number, query as CropDetailQuery),
    enabled: cropId !== null && query !== null,
    retry: false, // a 404 for an unknown crop/district is an answer, not a blip
  });
}

/**
 * Scenario scores for one rainfall delta. The delta is part of the key, so
 * dragging the slider warms a cache entry per stop and revisiting one is
 * instant; `keepPreviousData` holds the last scores on screen while the next
 * request is in flight instead of collapsing the list to a spinner.
 */
export function useScenario(payload: ScenarioRequest | null) {
  return useQuery({
    queryKey: queryKeys.farmer.scenario(payload ?? { district_id: 0, crop_ids: [] }),
    queryFn: () => farmerService.getScenario(payload as ScenarioRequest),
    enabled: payload !== null && payload.crop_ids.length > 0,
    placeholderData: keepPreviousData,
  });
}

export function useCropIntentMutation() {
  return useMutation({
    mutationFn: (payload: CropIntentRequest) => farmerService.createCropIntent(payload),
  });
}
