/**
 * POST /api/v1/rag/query — grounded explanation / Q&A.
 *
 * The backend requires a bearer token here, so this needs VITE_API_TOKEN set.
 *
 * Claude writes the answer, but only from documents retrieved for that specific
 * crop, and the API discards any answer that cites none of them. So a response
 * with `declined: true` and "I don't have grounded information" is the feature
 * working as designed, not a failure — surface it, don't retry it.
 *
 * `generated_by` says which path produced the text:
 *   "claude"     — retrieved documents, explained by the model, with citations
 *   "extractive" — no ANTHROPIC_API_KEY, so retrieved passages are quoted as-is
 *   "template"   — explain mode with no matching documents; the answer is built
 *                  from database columns (market rows, computed score) instead
 *
 * GET /api/v1/rag/status reports which of those is live and whether any corpus
 * has been ingested — check it before concluding an answer is bad.
 */
import { apiClient } from "./client";
import { API_V1 } from "./config";
import type { RagQueryRequest, RagQueryResponse, RagStatusResponse } from "./types";

export const ragService = {
  query: (payload: RagQueryRequest) =>
    apiClient.post<RagQueryResponse>(`${API_V1}/rag/query`, payload),

  status: () => apiClient.get<RagStatusResponse>(`${API_V1}/rag/status`),

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
