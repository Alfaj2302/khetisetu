import { useEffect } from "react";
import { X } from "lucide-react";
import type { CropRecommendation } from "@/lib/mockData";
import { getSources } from "@/lib/khetiService";
import { ConfidenceIndicator, DecisionTrace, Disclaimer, SourceList } from "./primitives";

/**
 * Side drawer on desktop, bottom sheet on mobile.
 */
export function WhyDrawer({
  rec,
  onClose,
}: {
  rec: CropRecommendation | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!rec) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [rec, onClose]);

  if (!rec) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="Close explanation"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/40 animate-in fade-in"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Why did KhetiSetu recommend ${rec.crop}?`}
        className="absolute inset-x-0 bottom-0 max-h-[88vh] overflow-y-auto rounded-t-2xl bg-card p-5 shadow-lift animate-in slide-in-from-bottom duration-300 sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-[460px] sm:rounded-none sm:rounded-l-2xl sm:p-6 sm:slide-in-from-right"
      >
        <div className="mx-auto mb-4 h-1.5 w-10 rounded-full bg-border sm:hidden" aria-hidden />
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
          <h2 className="text-xl font-bold text-foreground">Why did KhetiSetu recommend {rec.crop}?</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{rec.explanation}</p>

        <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Decision trace
        </h3>
        <div className="mt-3">
          <DecisionTrace items={rec.trace} />
        </div>

        <div className="mt-6">
          <ConfidenceIndicator value={rec.confidence} />
        </div>

        <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Based on agricultural knowledge sources
        </h3>
        <div className="mt-3">
          <SourceList sources={getSources()} />
        </div>

        <div className="mt-6">
          <Disclaimer>
            AI does not guarantee crop profitability. This recommendation is decision support based on
            available data, and all values shown are synthetic demo data.
          </Disclaimer>
        </div>
      </div>
    </div>
  );
}
