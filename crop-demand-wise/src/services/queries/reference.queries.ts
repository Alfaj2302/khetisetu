/** Reference/dropdown data. Cached aggressively — these tables barely change. */
import { useQuery } from "@tanstack/react-query";

import { referenceService } from "../api";
import { queryKeys } from "./keys";

/** Lookup tables are effectively static for the length of a session. */
const REFERENCE_STALE_TIME = 60 * 60 * 1000;

export function useStates() {
  return useQuery({
    queryKey: queryKeys.reference.states(),
    queryFn: () => referenceService.listStates(),
    staleTime: REFERENCE_STALE_TIME,
  });
}

export function useDistricts(stateId?: number | null) {
  return useQuery({
    queryKey: queryKeys.reference.districts(stateId),
    queryFn: () => referenceService.listDistricts(stateId),
    staleTime: REFERENCE_STALE_TIME,
  });
}

export function useCrops() {
  return useQuery({
    queryKey: queryKeys.reference.crops(),
    queryFn: () => referenceService.listCrops(),
    staleTime: REFERENCE_STALE_TIME,
  });
}

export function useSeasons() {
  return useQuery({
    queryKey: queryKeys.reference.seasons(),
    queryFn: () => referenceService.listSeasons(),
    staleTime: REFERENCE_STALE_TIME,
  });
}

export function useProducts(fertilizerType?: string | null) {
  return useQuery({
    queryKey: queryKeys.reference.products(fertilizerType),
    queryFn: () => referenceService.listProducts(fertilizerType),
    staleTime: REFERENCE_STALE_TIME,
  });
}
