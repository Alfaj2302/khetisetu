import { useEffect } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { RecommendationItem } from "@/services/api";
import { useCropDetail, useRagExplain } from "@/services/queries";
import {
  ConfidenceIndicator,
  DecisionTrace,
  Disclaimer,
  ErrorState,
  LoadingState,
  SourceList,
  UnverifiedBadge,
} from "./primitives";

/**
 * Side drawer on desktop, bottom sheet on mobile.
 *
 * Two requests, answering two different questions:
 *
 * - GET /farmer/crop/{id} — the deterministic decision trace. Which factors
 *   moved the score, and by how much. Always available.
 * - POST /rag/query (explain) — the prose "why", grounded in retrieved source
 *   documents with citations. This is the half that turns "46%" into a reason
 *   a farmer can act on.
 *
 * The RAG panel is additive and never blocks the drawer: if it declines, errors,
 * or has no corpus to draw on, the decision trace above it still renders.
 */
export function WhyDrawer({
  rec,
  districtId,
  landAreaAcres,
  irrigationAvailable,
  onClose,
}: {
  rec: RecommendationItem | null;
  districtId: number | null;
  landAreaAcres: number | null;
  irrigationAvailable: boolean | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const detail = useCropDetail(
    rec ? rec.crop.id : null,
    rec && districtId !== null
      ? {
          district_id: districtId,
          land_area_acres: landAreaAcres,
          irrigation_available: irrigationAvailable,
        }
      : null,
  );

  // Hand the model the numbers it must explain rather than recompute. Passing
  // the score keeps the prose consistent with the badge the farmer is looking at.
  const explanation = useRagExplain(rec ? rec.crop.id : null, districtId, {
    opportunity_pct: rec?.opportunity_pct,
    confidence_pct: rec?.confidence_pct,
  });

  useEffect(() => {
    if (!rec) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [rec, onClose]);

  if (!rec) return null;

  const guidance = detail.data?.agronomic_guidance;

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label={t("whyDrawer.closeExplanation")}
        onClick={onClose}
        className="absolute inset-0 bg-foreground/40 animate-in fade-in"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("whyDrawer.title", { crop: rec.crop.name })}
        className="absolute inset-x-0 bottom-0 max-h-[88vh] overflow-y-auto rounded-t-2xl bg-card p-5 shadow-lift animate-in slide-in-from-bottom duration-300 sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-[460px] sm:rounded-none sm:rounded-l-2xl sm:p-6 sm:slide-in-from-right"
      >
        <div className="mx-auto mb-4 h-1.5 w-10 rounded-full bg-border sm:hidden" aria-hidden />
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
          <h2 className="text-xl font-bold text-foreground">
            {t("whyDrawer.title", { crop: rec.crop.name })}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{rec.summary}</p>

        {/* Grounded explanation. Skipped entirely on error — the decision trace
            below is the guaranteed content, and a failed RAG call should cost
            the farmer nothing. */}
        {!explanation.isError && (
          <div className="mt-5 rounded-lg border border-border bg-muted/40 p-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {t("whyDrawer.grounded")}
              </h3>
              {explanation.data?.used_placeholder_data && <UnverifiedBadge />}
            </div>

            {explanation.isPending ? (
              <div className="mt-3">
                <LoadingState label={t("whyDrawer.loadingGrounded")} />
              </div>
            ) : (
              <>
                <p className="mt-3 text-sm leading-relaxed text-foreground">
                  {explanation.data?.answer}
                </p>

                {/* The passages the answer actually rests on. Shown verbatim so
                    a claim can be checked rather than trusted. */}
                {(explanation.data?.citations.length ?? 0) > 0 && (
                  <ul className="mt-3 space-y-2 border-l-2 border-border pl-3">
                    {explanation.data?.citations.slice(0, 3).map((citation) => (
                      <li key={citation.chunk_id} className="text-xs italic text-muted-foreground">
                        &ldquo;{citation.cited_text}&rdquo;
                        {citation.page_start != null && (
                          <span className="not-italic"> (p. {citation.page_start})</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}

                {/* Say why the answer is thin instead of letting it look like a
                    bad model: no corpus ingested, or no generation key set. */}
                {explanation.data?.generated_by === "template" && (
                  <p className="mt-3 text-xs text-muted-foreground">
                    {t("whyDrawer.noSourcesYet")}
                  </p>
                )}
              </>
            )}
          </div>
        )}

        <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {t("whyDrawer.decisionTrace")}
        </h3>
        <div className="mt-3">
          {detail.isPending ? (
            <LoadingState label={t("whyDrawer.loadingTrace")} />
          ) : detail.isError ? (
            <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
          ) : (
            <DecisionTrace
              items={(detail.data?.why ?? []).map((factor) => ({
                title: factor.factor,
                detail: factor.detail,
              }))}
            />
          )}
        </div>

        <div className="mt-6">
          <ConfidenceIndicator value={rec.confidence_pct} basis={rec.confidence_basis} />
        </div>

        {detail.data && (
          <>
            <div className="mt-6 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {t("sources.title")}
              </h3>
              {guidance && !guidance.is_verified && <UnverifiedBadge />}
            </div>
            <div className="mt-3">
              <SourceList
                sources={detail.data.sources.map((source) => ({
                  id: source.id,
                  title: source.organization ?? t("sources.fallback", { id: source.id }),
                  detail: source.source_type,
                }))}
              />
            </div>
          </>
        )}

        <div className="mt-6">
          <Disclaimer>{t("whyDrawer.disclaimer")}</Disclaimer>
        </div>
      </div>
    </div>
  );
}
