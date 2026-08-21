/**
 * POST /api/v1/rag/query — grounded explanation / Q&A.
 *
 * The backend requires a bearer token here, so this needs VITE_API_TOKEN set.
 *
 * There is no LLM behind it: "explain" builds its answer from real
 * `crop_market_data` rows plus the caller's `computed_context`, and "ask" does a
 * metadata-filtered lookup over `document_chunks` and declines outright when
 * nothing matches. An "I don't have grounded information" answer is the API
 * working as designed, not a failure.
 */
import { apiClient } from "./client";
import { API_V1 } from "./config";
import type { RagQueryRequest, RagQueryResponse } from "./types";

export const ragService = {
  query: (payload: RagQueryRequest) =>
    apiClient.post<RagQueryResponse>(`${API_V1}/rag/query`, payload),

  explain: (args: {
    cropId: number;
    districtId: number;
    computedContext?: Record<string, unknown>;
  }) =>
    ragService.query({
      mode: "explain",
      crop_id: args.cropId,
      district_id: args.districtId,
      computed_context: args.computedContext ?? null,
    }),

  ask: (args: { question: string; districtId?: number | null }) =>
    ragService.query({
      mode: "ask",
      question: args.question,
      district_id: args.districtId ?? null,
    }),
};
