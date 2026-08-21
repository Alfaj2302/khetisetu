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
import { Trans, useTranslation } from "react-i18next";

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
import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";
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
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("cropDetail.meta.title") },
        { name: "description", content: t("cropDetail.meta.description") },
        { property: "og:title", content: t("cropDetail.meta.ogTitle") },
        { property: "og:description", content: t("cropDetail.meta.ogDescription") },
        { property: "og:type", content: "article" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: CropDetails,
});

function CropDetails() {
  const { t } = useTranslation();
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
          title={t("cropDetail.needDistrictTitle")}
          detail={t("cropDetail.needDistrictDetail")}
          action={
            <Link
              to="/farmer"
              className="inline-flex items-center justify-center rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark"
            >
              {t("common.analyseMyFarm")}
            </Link>
          }
        />
      </div>
    );
  }

  if (detail.isPending) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-12 md:px-6">
        <LoadingState label={t("cropDetail.loading")} />
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
          <ArrowLeft className="h-4 w-4" aria-hidden /> {t("common.backToRecommendations")}
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
    { label: t("cropDetail.guidance.nitrogen"), value: guidance.nitrogen_kg_ha },
    { label: t("cropDetail.guidance.phosphorus"), value: guidance.phosphorus_kg_ha },
    { label: t("cropDetail.guidance.potassium"), value: guidance.potassium_kg_ha },
  ].filter((row) => row.value !== null);

  function saveIntent() {
    const seasonId = recommendation?.season_id;
    if (seasonId === null || seasonId === undefined) {
      toast.error(t("cropDetail.intent.seasonUnknownTitle"), {
        description: t("cropDetail.intent.seasonUnknownDetail"),
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
          toast.success(t("cropDetail.intent.savedToastTitle"), {
            description: t("cropDetail.intent.savedToastDetail", { crop: crop.crop.name }),
          });
        },
        onError: () => toast.error(t("cropDetail.intent.errorTitle")),
      },
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-12">
      <Link
        to="/recommendations"
        className="inline-flex items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden /> {t("common.backToRecommendations")}
      </Link>

      <header className="surface-card mt-4 grid gap-5 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:p-7">
        <div className="min-w-0">
          <h1 className="text-3xl font-extrabold text-foreground">{crop.crop.name}</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            {crop.tags["demand"] && (
              <Pill tone="primary">
                {t("cropDetail.demandTag", { level: crop.tags["demand"] })}
              </Pill>
            )}
            {crop.tags["weather"] && (
              <Pill tone="success">
                {t("cropDetail.weatherTag", { tag: crop.tags["weather"] })}
              </Pill>
            )}
            <RiskBadge risk={crop.risk.level} />
          </div>
        </div>
        <OpportunityScore value={crop.opportunity_pct} />
      </header>

      <div className="mt-6 space-y-6">
        <Section
          title={t("cropDetail.why.title", { crop: crop.crop.name })}
          description={t("cropDetail.why.description")}
        >
          <DecisionTrace
            items={crop.why.map((factor) => ({ title: factor.factor, detail: factor.detail }))}
          />
        </Section>

        <Section
          title={t("cropDetail.demandOutlook.title")}
          description={t("cropDetail.demandOutlook.description")}
        >
          {outlook.expected_demand_qty === null && outlook.expected_supply_qty === null ? (
            <EmptyState
              title={t("cropDetail.demandOutlook.emptyTitle")}
              detail={t("cropDetail.demandOutlook.emptyDetail")}
            />
          ) : (
            <dl className="grid gap-3 sm:grid-cols-3">
              <Metric
                label={t("metrics.expectedDemand")}
                value={formatQty(t, outlook.expected_demand_qty, unit)}
              />
              <Metric
                label={t("metrics.expectedSupply")}
                value={formatQty(t, outlook.expected_supply_qty, unit)}
              />
              <Metric
                label={t("metrics.demandGap")}
                value={formatSignedQty(t, outlook.demand_gap, unit)}
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

        <Section
          title={t("cropDetail.weather.title")}
          description={t("cropDetail.weather.description")}
        >
          <dl className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <CloudSun className="h-4 w-4 text-primary" aria-hidden /> {t("weather.rainfall")}
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">
                {crop.weather_suitability.rainfall}
              </dd>
            </div>
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Thermometer className="h-4 w-4 text-primary" aria-hidden />{" "}
                {t("weather.temperature")}
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">
                {formatTemp(crop.weather_suitability.temperature_c)}
              </dd>
            </div>
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Droplets className="h-4 w-4 text-primary" aria-hidden /> {t("weather.humidity")}
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">
                {formatPct(crop.weather_suitability.humidity_pct)}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-sm text-muted-foreground">
            <Trans
              i18nKey="cropDetail.weather.overall"
              values={{ crop: crop.crop.name, score: crop.weather_suitability.score }}
              components={{ score: <strong className="text-foreground" /> }}
            />
          </p>
          <Link
            to="/whatif"
            className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary hover:bg-primary/10 sm:w-auto"
          >
            {t("common.testWeatherScenario")}
          </Link>
        </Section>

        <Section
          title={t("cropDetail.season.title")}
          description={t("cropDetail.season.description")}
        >
          <ol className="grid gap-3 sm:grid-cols-3">
            {[
              {
                label: t("cropDetail.season.sowingMonths"),
                value: monthRangeLabel(t, crop.crop_season.sowing_months),
              },
              {
                label: t("cropDetail.season.growingPeriod"),
                value: weeksRangeLabel(t, crop.crop_season.growing_period_weeks),
              },
              {
                label: t("cropDetail.season.harvestWindow"),
                value: monthRangeLabel(t, crop.crop_season.harvest_months),
              },
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
          title={t("cropDetail.guidance.title")}
          description={t("cropDetail.guidance.description")}
          action={guidance.is_verified ? undefined : <UnverifiedBadge />}
        >
          {npk.length === 0 ? (
            <EmptyState
              title={t("cropDetail.guidance.emptyTitle")}
              detail={guidance.warning ?? t("cropDetail.guidance.emptyDetail")}
            />
          ) : (
            <>
              <ul className="grid gap-3 sm:grid-cols-3">
                {npk.map((row) => (
                  <li key={row.label} className="rounded-lg border border-border bg-muted/50 p-4">
                    <p className="text-base font-bold text-foreground">{row.label}</p>
                    <p className="mt-1 text-sm font-semibold text-primary">
                      {t("cropDetail.guidance.rate", { value: row.value })}
                    </p>
                  </li>
                ))}
              </ul>
              {guidance.application_stage && (
                <p className="mt-3 text-sm text-muted-foreground">
                  <Trans
                    i18nKey="cropDetail.guidance.applicationStage"
                    values={{ stage: guidance.application_stage }}
                    components={{ stage: <strong className="text-foreground" /> }}
                  />
                </p>
              )}
            </>
          )}
          <div className="mt-4">
            <Disclaimer>{guidance.warning ?? t("cropDetail.guidance.disclaimer")}</Disclaimer>
          </div>
        </Section>

        <Section title={t("cropDetail.risk.title")} description={t("cropDetail.risk.description")}>
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

        <Section
          title={t("cropDetail.confidence.title")}
          description={t("cropDetail.confidence.description")}
        >
          <ConfidenceIndicator value={crop.confidence_pct} basis={matchingRec?.confidence_basis} />
        </Section>

        <Section
          title={t("cropDetail.sources.title")}
          description={t("cropDetail.sources.description")}
          action={
            <button
              type="button"
              onClick={() => setShowSources((v) => !v)}
              aria-expanded={showSources}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-foreground hover:bg-muted"
            >
              {showSources ? t("cropDetail.sources.hide") : t("cropDetail.sources.show")}
            </button>
          }
        >
          {showSources ? (
            <SourceList
              sources={crop.sources.map((source) => ({
                id: source.id,
                title: source.organization ?? t("sources.fallback", { id: source.id }),
                detail: source.source_type,
              }))}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              {crop.sources.length === 0
                ? t("cropDetail.sources.none")
                : t("cropDetail.sources.count", { count: crop.sources.length })}
            </p>
          )}
        </Section>

        <Section
          title={t("cropDetail.intent.title")}
          description={t("cropDetail.intent.description")}
        >
          {savedIntentId !== null ? (
            <p className="flex items-center gap-2 rounded-lg border border-success/40 bg-success/5 p-3 text-sm font-semibold text-success">
              <CheckCircle2 className="h-4 w-4" aria-hidden />
              {t("cropDetail.intent.saved", { crop: crop.crop.name })}
            </p>
          ) : (
            <button
              type="button"
              onClick={saveIntent}
              disabled={createIntent.isPending}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark disabled:bg-muted disabled:text-muted-foreground sm:w-auto"
            >
              {createIntent.isPending
                ? t("cropDetail.intent.saving")
                : t("cropDetail.intent.cta", { crop: crop.crop.name })}
            </button>
          )}
        </Section>
      </div>
    </div>
  );
}
