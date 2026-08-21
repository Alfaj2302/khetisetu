import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CloudSun,
  Droplets,
  Thermometer,
} from "lucide-react";
import { toast } from "sonner";

import { useCropDetail, useCropIntentMutation } from "@/services/queries";
import { useFarm } from "@/lib/farm-store";
import {
  formatPct,
  formatQty,
  formatSignedQty,
  formatTemp,
  monthRangeLabel,
  weeksRangeLabel,
} from "@/lib/format";
import {
  ConfidenceIndicator,
  DecisionTrace,
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingState,
  Metric,
  OpportunityScore,
  Pill,
  RiskBadge,
  Section,
  SourceList,
  UnverifiedBadge,
} from "@/components/kheti/primitives";

export const Route = createFileRoute("/crop/$cropId")({
  head: () => ({
    meta: [
      { title: "Crop plan | KhetiSetu" },
      {
        name: "description",
        content:
          "Demand outlook, weather suitability, indicative inputs, risk and confidence for a crop in your district.",
      },
      { property: "og:title", content: "Crop plan | KhetiSetu" },
      { property: "og:description", content: "Explainable crop decision support." },
      { property: "og:type", content: "article" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CropDetails,
});

function CropDetails() {
  const { cropId } = Route.useParams();
  const { farmer, recommendation } = useFarm();
  const [showSources, setShowSources] = useState(false);
  const [savedIntentId, setSavedIntentId] = useState<number | null>(null);

  const parsedCropId = Number(cropId);
  const districtId = recommendation?.district.id ?? farmer.districtId;

  const detail = useCropDetail(
    Number.isInteger(parsedCropId) ? parsedCropId : null,
    districtId === null
      ? null
      : {
          district_id: districtId,
          land_area_acres: farmer.landAcres,
          irrigation_available: farmer.irrigation,
        },
  );
  const createIntent = useCropIntentMutation();

  if (districtId === null) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
        <EmptyState
          title="Pick your district first"
          detail="Crop details are district-specific — the API needs a district to look up market and weather data."
          action={
            <Link
              to="/farmer"
              className="inline-flex items-center justify-center rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark"
            >
              Analyse my farm
            </Link>
          }
        />
      </div>
    );
  }

  if (detail.isPending) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 md:px-6">
        <LoadingState label="Loading crop plan…" />
      </div>
    );
  }

  if (detail.isError || !detail.data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
        <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
        <Link
          to="/recommendations"
          className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden /> Back to recommendations
        </Link>
      </div>
    );
  }

  const crop = detail.data;
  const guidance = crop.agronomic_guidance;
  const outlook = crop.demand_outlook;
  const matchingRec = recommendation?.recommendations.find((r) => r.crop.id === crop.crop.id);
  const unit = matchingRec?.unit ?? "";
  const npk = [
    { label: "Nitrogen (N)", value: guidance.nitrogen_kg_ha },
    { label: "Phosphorus (P)", value: guidance.phosphorus_kg_ha },
    { label: "Potassium (K)", value: guidance.potassium_kg_ha },
  ].filter((row) => row.value !== null);

  function saveIntent() {
    const seasonId = recommendation?.season_id;
    if (seasonId === null || seasonId === undefined) {
      toast.error("Season unknown", {
        description: "Run the farm analysis first so KhetiSetu knows which season this is.",
      });
      return;
    }
    createIntent.mutate(
      {
        district_id: districtId as number,
        crop_id: crop.crop.id,
        season_id: seasonId,
        year: new Date().getFullYear(),
        land_area_acres: farmer.landAcres,
        irrigation_available: farmer.irrigation,
      },
      {
        onSuccess: (result) => {
          setSavedIntentId(result.id);
          toast.success("Saved", {
            description: `Recorded that you plan to grow ${crop.crop.name}.`,
          });
        },
        onError: () => toast.error("Could not save your crop plan"),
      },
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-12">
      <Link
        to="/recommendations"
        className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> Back to recommendations
      </Link>

      <header className="surface-card mt-4 grid gap-5 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:p-7">
        <div className="min-w-0">
          <h1 className="text-3xl font-extrabold text-foreground">{crop.crop.name}</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            {crop.tags["demand"] && <Pill tone="primary">{crop.tags["demand"]} DEMAND</Pill>}
            {crop.tags["weather"] && <Pill tone="success">{crop.tags["weather"]} WEATHER</Pill>}
            <RiskBadge risk={crop.risk.level} />
          </div>
        </div>
        <OpportunityScore value={crop.opportunity_pct} />
      </header>

      <div className="mt-6 space-y-6">
        <Section
          title={`Why ${crop.crop.name}?`}
          description="How KhetiSetu reached this recommendation."
        >
          <DecisionTrace
            items={crop.why.map((factor) => ({ title: factor.factor, detail: factor.detail }))}
          />
        </Section>

        <Section
          title="Demand outlook"
          description="Latest recorded demand and supply for this crop in your district."
        >
          {outlook.expected_demand_qty === null && outlook.expected_supply_qty === null ? (
            <EmptyState
              title="No market figures recorded"
              detail="The API has no demand/supply row for this district and crop yet."
            />
          ) : (
            <dl className="grid gap-3 sm:grid-cols-3">
              <Metric
                label="Expected demand"
                value={formatQty(outlook.expected_demand_qty, unit)}
              />
              <Metric
                label="Expected supply"
                value={formatQty(outlook.expected_supply_qty, unit)}
              />
              <Metric
                label="Demand gap"
                value={formatSignedQty(outlook.demand_gap, unit)}
                tone={
                  outlook.demand_gap === null
                    ? "neutral"
                    : outlook.demand_gap > 0
                      ? "positive"
                      : "negative"
                }
              />
            </dl>
          )}
        </Section>

        <Section title="Weather suitability" description="Averaged from recorded weather history.">
          <dl className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <CloudSun className="h-4 w-4 text-primary" aria-hidden /> Rainfall
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">
                {crop.weather_suitability.rainfall}
              </dd>
            </div>
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Thermometer className="h-4 w-4 text-primary" aria-hidden /> Temperature
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">
                {formatTemp(crop.weather_suitability.temperature_c)}
              </dd>
            </div>
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Droplets className="h-4 w-4 text-primary" aria-hidden /> Humidity
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">
                {formatPct(crop.weather_suitability.humidity_pct)}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-sm text-muted-foreground">
            Overall weather suitability for {crop.crop.name}:{" "}
            <strong className="text-foreground">{crop.weather_suitability.score}/100</strong>.
          </p>
          <Link
            to="/whatif"
            className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary hover:bg-primary/10 sm:w-auto"
          >
            Test weather scenario
          </Link>
        </Section>

        <Section title="Crop season" description="From the crop calendar for your district.">
          <ol className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Sowing months", value: monthRangeLabel(crop.crop_season.sowing_months) },
              {
                label: "Growing period",
                value: weeksRangeLabel(crop.crop_season.growing_period_weeks),
              },
              { label: "Harvest window", value: monthRangeLabel(crop.crop_season.harvest_months) },
            ].map((item, i) => (
              <li key={item.label} className="rounded-lg border border-border bg-muted/50 p-3">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                  {i + 1}
                </span>
                <p className="mt-2 text-xs font-medium text-muted-foreground">{item.label}</p>
                <p className="text-base font-bold text-foreground">{item.value}</p>
              </li>
            ))}
          </ol>
        </Section>

        <Section
          title="Indicative agronomic guidance"
          description="Nutrient rates recorded for this crop."
          action={guidance.is_verified ? undefined : <UnverifiedBadge />}
        >
          {npk.length === 0 ? (
            <EmptyState
              title="No nutrient guidance recorded"
              detail={guidance.warning ?? "The API has no fertilizer recommendation for this crop."}
            />
          ) : (
            <>
              <ul className="grid gap-3 sm:grid-cols-3">
                {npk.map((row) => (
                  <li key={row.label} className="rounded-lg border border-border bg-muted/50 p-4">
                    <p className="text-base font-bold text-foreground">{row.label}</p>
                    <p className="mt-1 text-sm font-semibold text-primary">{row.value} kg / ha</p>
                  </li>
                ))}
              </ul>
              {guidance.application_stage && (
                <p className="mt-3 text-sm text-muted-foreground">
                  Application stage:{" "}
                  <strong className="text-foreground">{guidance.application_stage}</strong>
                </p>
              )}
            </>
          )}
          <div className="mt-4">
            <Disclaimer>
              {guidance.warning ??
                "Final fertilizer recommendations should follow local agricultural advisories / soil-test recommendations."}
            </Disclaimer>
          </div>
        </Section>

        <Section title="Risk" description="What could go differently this season.">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge risk={crop.risk.level} />
          </div>
          <ul className="mt-3 space-y-2">
            {crop.risk.factors.map((factor) => (
              <li
                key={factor}
                className="flex items-start gap-2 rounded-lg border border-border bg-muted/50 p-3 text-sm text-foreground"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                {factor}
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Confidence" description="How sure the system is about this recommendation.">
          <ConfidenceIndicator value={crop.confidence_pct} basis={matchingRec?.confidence_basis} />
        </Section>

        <Section
          title="Sources"
          description="Documents linked to the guidance above."
          action={
            <button
              type="button"
              onClick={() => setShowSources((v) => !v)}
              aria-expanded={showSources}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-foreground hover:bg-muted"
            >
              {showSources ? "Hide sources" : "View sources"}
            </button>
          }
        >
          {showSources ? (
            <SourceList
              sources={crop.sources.map((source) => ({
                id: source.id,
                title: source.organization ?? `Source #${source.id}`,
                detail: source.source_type,
              }))}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              {crop.sources.length === 0
                ? "No source document is linked to this crop's guidance yet."
                : `${crop.sources.length} linked source${crop.sources.length === 1 ? "" : "s"}.`}
            </p>
          )}
        </Section>

        <Section
          title="Planning to grow this?"
          description="Records your intent so agri-businesses can plan input supply. Aggregated only — never shown per farmer."
        >
          {savedIntentId !== null ? (
            <p className="flex items-center gap-2 rounded-lg border border-success/40 bg-success/5 p-3 text-sm font-semibold text-success">
              <CheckCircle2 className="h-4 w-4" aria-hidden />
              Saved — your {crop.crop.name} plan was recorded.
            </p>
          ) : (
            <button
              type="button"
              onClick={saveIntent}
              disabled={createIntent.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark disabled:bg-muted disabled:text-muted-foreground sm:w-auto"
            >
              {createIntent.isPending ? "Saving…" : `I'm growing ${crop.crop.name}`}
            </button>
          )}
        </Section>
      </div>
    </div>
  );
}
