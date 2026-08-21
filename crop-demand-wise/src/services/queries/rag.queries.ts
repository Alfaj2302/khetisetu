/** RAG explain/ask. Modelled as a mutation — each ask is a user-triggered send. */
import { useMutation } from "@tanstack/react-query";

import { ragService } from "../api";
import type { RagQueryRequest } from "../api/types";

export function useRagQueryMutation() {
  return useMutation({
    mutationFn: (payload: RagQueryRequest) => ragService.query(payload),
  });
}
