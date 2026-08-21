import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { CloudRain, Trophy } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useScenario } from "@/services/queries";
import { useFarm } from "@/lib/farm-store";
import {
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingState,
  Pill,
} from "@/components/kheti/primitives";
import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";

export const Route = createFileRoute("/whatif")({
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("whatif.meta.title") },
        { name: "description", content: t("whatif.meta.description") },
        { property: "og:title", content: t("whatif.meta.ogTitle") },
        { property: "og:description", content: t("whatif.meta.ogDescription") },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: WhatIf,
});

function WhatIf() {
  const { t } = useTranslation();
  const { recommendation } = useFarm();
  const [delta, setDelta] = useState(0);

  const cropIds = useMemo(
    () => (recommendation?.recommendations ?? []).map((rec) => rec.crop.id),
    [recommendation],
  );

  const scenario = useScenario(
    recommendation && cropIds.length > 0
      ? {
          district_id: recommendation.district.id,
          crop_ids: cropIds,
          rainfall_change_pct: delta,
        }
      : null,
  );

  if (!recommendation || cropIds.length === 0) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
        <EmptyState
          title={t("whatif.emptyTitle")}
          detail={t("whatif.emptyDetail")}
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

  const cropName = (cropId: number) =>
    recommendation.recommendations.find((rec) => rec.crop.id === cropId)?.crop.name ??
    t("whatif.cropFallback", { id: cropId });

  // The API returns scores in the order crop_ids was sent; rank them here.
  const ranked = [...(scenario.data?.scenario_scores ?? [])].sort(
    (a, b) => b.opportunity_pct - a.opportunity_pct,
  );
  const leader = ranked[0];

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:px-6 md:py-12">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">{t("whatif.title")}</h1>
        <p className="mt-2 text-muted-foreground">
          {t("whatif.subtitle", { district: recommendation.district.name })}
        </p>
      </div>

      <section className="surface-card mt-6 p-5 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
            <CloudRain className="h-4 w-4 text-info" aria-hidden /> {t("whatif.expectedRainfall")}
          </span>
          <span className="text-2xl font-extrabold text-foreground">{100 + delta}%</span>
        </div>

        <label htmlFor="rainfall" className="mt-4 block text-sm font-semibold text-foreground">
          {t("whatif.sliderLabel")}
        </label>
        <input
          id="rainfall"
          type="range"
          min={-30}
          max={30}
          step={5}
          value={delta}
          onChange={(e) => setDelta(Number(e.target.value))}
          aria-valuetext={t("whatif.sliderValueText", {
            delta: `${delta > 0 ? "+" : ""}${delta}`,
          })}
          className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-full bg-muted accent-[var(--color-primary)]"
        />
        <div className="mt-2 flex justify-between text-xs font-medium text-muted-foreground">
          <span>-30%</span>
          <span>{t("whatif.normal")}</span>
          <span>+30%</span>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {[-30, -15, 0, 15, 30].map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setDelta(value)}
              className={`rounded-lg border px-3 py-2 text-sm font-semibold transition-colors ${
                delta === value
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-card text-muted-foreground hover:bg-muted"
              }`}
            >
              {value > 0 ? `+${value}%` : value === 0 ? t("whatif.normal") : `${value}%`}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-6 space-y-3" aria-live="polite" aria-busy={scenario.isFetching}>
        <h2 className="text-lg font-bold text-foreground">{t("whatif.scoresHeading")}</h2>

        {scenario.isPending ? (
          <LoadingState label={t("whatif.running")} />
        ) : scenario.isError ? (
          <ErrorState error={scenario.error} onRetry={() => void scenario.refetch()} />
        ) : (
          ranked.map((score, i) => {
            const isImproved = score.change.startsWith("+");
            const isWorse = score.change.startsWith("-");
            return (
              <article key={score.crop_id} className="surface-card p-4">
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-muted px-2 text-xs font-bold text-muted-foreground">
                        #{i + 1}
                      </span>
                      <h3 className="truncate text-lg font-bold text-foreground">
                        {cropName(score.crop_id)}
                      </h3>
                      {i === 0 && scenario.data?.recommendation_changed && (
                        <Pill tone="harvest" icon={Trophy}>
                          {t("whatif.newSaferOption")}
                        </Pill>
                      )}
                    </div>
                    <div
                      className="mt-2 h-2 w-full overflow-hidden rounded-full bg-muted"
                      role="presentation"
                    >
                      <div
                        className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
                        style={{ width: `${score.opportunity_pct}%` }}
                      />
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-extrabold tabular-nums text-foreground">
                      {score.opportunity_pct}%
                    </p>
                    {/* `change` is the API's own delta against its baseline run. */}
                    <p
                      className={`text-xs font-semibold ${
                        isImproved
                          ? "text-success"
                          : isWorse
                            ? "text-destructive"
                            : "text-muted-foreground"
                      }`}
                    >
                      {score.change}
                    </p>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </section>

      {scenario.data && leader && (
        <section className="surface-card mt-6 border-harvest/40 bg-harvest-soft/15 p-5">
          <h2 className="flex items-center gap-2 text-base font-bold text-foreground">
            <Trophy className="h-5 w-5 text-harvest" aria-hidden />
            {scenario.data.recommendation_changed
              ? t("whatif.changedTitle")
              : t("whatif.unchangedTitle")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-foreground">
            {scenario.data.recommendation_changed
              ? t("whatif.changedDetail", {
                  delta: `${delta > 0 ? "+" : ""}${delta}`,
                  crop: cropName(leader.crop_id),
                })
              : t("whatif.unchangedDetail", {
                  delta: `${delta > 0 ? "+" : ""}${delta}`,
                  crop: cropName(leader.crop_id),
                })}
          </p>
          <Link
            to="/crop/$cropId"
            params={{ cropId: String(leader.crop_id) }}
            className="mt-4 inline-flex w-full items-center justify-center rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark sm:w-auto"
          >
            {t("whatif.viewPlan", { crop: cropName(leader.crop_id) })}
          </Link>
        </section>
      )}

      <div className="mt-6">
        <Disclaimer>{t("whatif.disclaimer")}</Disclaimer>
      </div>
    </div>
  );
}
