/** RAG explain/ask. Modelled as a mutation — each ask is a user-triggered send. */
import { useMutation, useQuery } from "@tanstack/react-query";

import { ragService } from "../api";
import type { RagQueryRequest } from "../api/types";
import { queryKeys } from "./keys";

export function useRagQueryMutation() {
  return useMutation({
    mutationFn: (payload: RagQueryRequest) => ragService.query(payload),
  });
}

/**
 * The grounded explanation behind one crop's score — the "Why <crop>?" panel.
 *
 * A query rather than a mutation: opening the drawer is not a user action with
 * side effects, and the same crop reopened should come from cache. `enabled`
 * keeps it from firing until the drawer actually has a crop and district.
 *
 * Retries are off. The most common failure here is a 401 from a missing
 * VITE_API_TOKEN, and retrying that three times just delays the message that
 * tells you what to fix.
 */
export function useRagExplain(
  cropId: number | null,
  districtId: number | null,
  computedContext?: Record<string, unknown>,
) {
  const enabled = cropId !== null && districtId !== null;
  return useQuery({
    queryKey: queryKeys.rag.explain(cropId, districtId, computedContext ?? null),
    queryFn: () =>
      ragService.explain({
        cropId: cropId as number,
        districtId: districtId as number,
        // Spread rather than pass undefined: `exactOptionalPropertyTypes` treats
        // an explicit undefined as different from an absent key.
        ...(computedContext ? { computedContext } : {}),
      }),
    enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

/** Whether retrieval and generation are actually wired up. */
export function useRagStatus() {
  return useQuery({
    queryKey: queryKeys.rag.status(),
    queryFn: () => ragService.status(),
    retry: false,
    staleTime: 60 * 1000,
  });
}
