import { Link } from "@tanstack/react-router";
import { ArrowRight, HelpCircle, TrendingUp } from "lucide-react";

import type { RecommendationItem } from "@/services/api";
import { formatQty, formatSignedQty } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ConfidenceIndicator, Metric, OpportunityScore, Pill, RiskBadge } from "./primitives";

export function CropRecommendationCard({
  rec,
  onWhy,
}: {
  rec: RecommendationItem;
  onWhy: (rec: RecommendationItem) => void;
}) {
  const primary = rec.rank === 1;
  const unit = rec.unit ?? "";
  const gap = rec.demand_gap;

  return (
    <article
      className={cn(
        "surface-card transition-shadow hover:shadow-lift",
        primary ? "border-primary/30 p-5 md:p-7" : "p-5",
      )}
    >
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex h-7 min-w-7 items-center justify-center rounded-full px-2 text-sm font-bold",
                primary ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
              )}
            >
              #{rec.rank}
            </span>
            <h3
              className={cn(
                "truncate font-bold text-foreground",
                primary ? "text-2xl md:text-3xl" : "text-xl",
              )}
            >
              {rec.crop.name}
            </h3>
            {primary && (
              <Pill tone="harvest" icon={TrendingUp}>
                Top opportunity
              </Pill>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <Pill tone="primary">{rec.demand_level} demand</Pill>
            <Pill tone="success">Weather: {rec.weather_tag}</Pill>
            <RiskBadge risk={rec.risk_tag} />
          </div>

          {/* `summary` is the API's own one-line rationale for this ranking. */}
          {primary && (
            <p className="mt-3 max-w-prose text-sm leading-relaxed text-muted-foreground">
              {rec.summary}
            </p>
          )}
        </div>

        <OpportunityScore value={rec.opportunity_pct} size={primary ? 132 : 96} />
      </div>

      <dl className={cn("mt-5 grid gap-3", primary ? "sm:grid-cols-4" : "sm:grid-cols-3")}>
        <Metric label="Expected demand" value={formatQty(rec.expected_demand_qty, unit)} />
        <Metric label="Expected supply" value={formatQty(rec.expected_supply_qty, unit)} />
        <Metric
          label="Demand gap"
          value={formatSignedQty(gap, unit)}
          tone={gap === null ? "neutral" : gap > 0 ? "positive" : "negative"}
          {...(gap === null
            ? {}
            : { hint: gap > 0 ? "Positive gap = opportunity" : "Negative gap = oversupply risk" })}
        />
        {primary && (
          <Metric label="Weather suitability" value={`${rec.weather_suitability_score}/100`} />
        )}
      </dl>

      <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
        <ConfidenceIndicator value={rec.confidence_pct} compact />
        <div className="flex flex-col gap-2 sm:flex-row">
          <Link
            to="/crop/$cropId"
            params={{ cropId: String(rec.crop.id) }}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary-dark active:bg-primary-dark"
          >
            View crop plan <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
          <button
            type="button"
            onClick={() => onWhy(rec)}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
          >
            <HelpCircle className="h-4 w-4" aria-hidden /> Why {rec.crop.name}?
          </button>
        </div>
      </div>
    </article>
  );
}
