import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { CalendarDays, Droplets, MapPin, MessageCircle, Ruler, Wheat } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { RecommendationItem } from "@/services/api";
import { useCrops, useWeather } from "@/services/queries";
import { useFarm } from "@/lib/farm-store";
import { monthLabel } from "@/lib/format";
import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";
import { CropRecommendationCard } from "@/components/kheti/CropRecommendationCard";
import { WhyDrawer } from "@/components/kheti/WhyDrawer";
import { WeatherOutlookCard } from "@/components/kheti/WeatherOutlookCard";
import { DemandSupplyChart, type DemandSupplyRow } from "@/components/kheti/charts";
import {
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingState,
  Section,
} from "@/components/kheti/primitives";

export const Route = createFileRoute("/recommendations")({
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("recommendations.meta.title") },
        { name: "description", content: t("recommendations.meta.description") },
        { property: "og:title", content: t("recommendations.meta.ogTitle") },
        { property: "og:description", content: t("recommendations.meta.ogDescription") },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: Recommendations,
});

/** Only rows carrying both figures can go on the demand-vs-supply chart. */
function toChartRows(recommendations: RecommendationItem[]): DemandSupplyRow[] {
  return recommendations
    .filter(
      (
        rec,
      ): rec is RecommendationItem & {
        expected_demand_qty: number;
        expected_supply_qty: number;
      } => rec.expected_demand_qty !== null && rec.expected_supply_qty !== null,
    )
    .map((rec) => ({
      crop: rec.crop.name,
      demand: rec.expected_demand_qty,
      supply: rec.expected_supply_qty,
      gap: rec.demand_gap ?? rec.expected_demand_qty - rec.expected_supply_qty,
    }));
}

function Recommendations() {
  const { t } = useTranslation();
  const { farmer, recommendation } = useFarm();
  const [why, setWhy] = useState<RecommendationItem | null>(null);
  const crops = useCrops();
  const weather = useWeather(recommendation?.district.id ?? null);

  // The ranking comes from a POST that also records an intent row, so it is
  // never refetched here — the farmer submits the form to (re)generate it.
  if (!recommendation) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
        <EmptyState
          title={t("recommendations.empty.title")}
          detail={t("recommendations.empty.detail")}
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

  const previousCropName = crops.data?.find((c) => c.id === farmer.previousCropId)?.name;
  const chartRows = toChartRows(recommendation.recommendations);
  const unit = recommendation.recommendations.find((r) => r.unit)?.unit ?? t("format.units");

  const context = [
    { icon: MapPin, text: recommendation.district.name },
    { icon: Ruler, text: t("common.acres", { value: farmer.landAcres }) },
    {
      icon: Droplets,
      text: farmer.irrigation
        ? t("recommendations.context.irrigationAvailable")
        : t("recommendations.context.noIrrigation"),
    },
    ...(previousCropName
      ? [
          {
            icon: Wheat,
            text: t("recommendations.context.previousCrop", { crop: previousCropName }),
          },
        ]
      : []),
    {
      icon: CalendarDays,
      text: t("recommendations.context.sowing", { month: monthLabel(t, farmer.sowingMonth) }),
    },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-12">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">
          {t("recommendations.title")}
        </h1>
        <p className="mt-2 text-muted-foreground">{t("recommendations.subtitle")}</p>
      </div>

      <ul className="mt-5 flex flex-wrap gap-2">
        {context.map(({ icon: Icon, text }) => (
          <li
            key={text}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-sm text-foreground"
          >
            <Icon className="h-4 w-4 text-primary" aria-hidden />
            {text}
          </li>
        ))}
        <li>
          <Link
            to="/farmer"
            className="inline-flex items-center rounded-full px-3 py-1.5 text-sm font-semibold text-primary underline underline-offset-4"
          >
            {t("recommendations.changeDetails")}
          </Link>
        </li>
      </ul>

      {recommendation.recommendations.length === 0 ? (
        <div className="mt-8">
          <EmptyState
            title={t("recommendations.noEligible.title")}
            detail={t("recommendations.noEligible.detail", {
              district: recommendation.district.name,
              month: monthLabel(t, farmer.sowingMonth),
            })}
            action={
              <Link
                to="/farmer"
                className="inline-flex items-center justify-center rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark"
              >
                {t("recommendations.noEligible.action")}
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <h2 className="mt-8 text-xl font-bold text-foreground">
            {t("recommendations.topCrops", { count: recommendation.recommendations.length })}
          </h2>
          <div className="mt-4 space-y-4">
            {recommendation.recommendations.map((rec) => (
              <CropRecommendationCard key={rec.crop.id} rec={rec} onWhy={setWhy} />
            ))}
          </div>
        </>
      )}

      <div className="mt-8 space-y-6">
        <Section
          title={t("recommendations.chart.title")}
          description={t("recommendations.chart.description")}
        >
          {chartRows.length > 0 ? (
            <DemandSupplyChart data={chartRows} unit={unit} />
          ) : (
            <EmptyState
              title={t("recommendations.chart.emptyTitle")}
              detail={t("recommendations.chart.emptyDetail")}
            />
          )}
        </Section>

        {weather.isPending ? (
          <LoadingState label={t("recommendations.weatherLoading")} />
        ) : weather.isError ? (
          <ErrorState error={weather.error} onRetry={() => void weather.refetch()} />
        ) : weather.data ? (
          <WeatherOutlookCard weather={weather.data} districtName={recommendation.district.name} />
        ) : null}

        <Disclaimer>{t("recommendations.disclaimer")}</Disclaimer>

        <Link
          to="/ask"
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary hover:bg-primary/10 sm:w-auto"
        >
          <MessageCircle className="h-4 w-4" aria-hidden /> {t("recommendations.askCta")}
        </Link>
      </div>

      <WhyDrawer
        rec={why}
        districtId={recommendation.district.id}
        landAreaAcres={farmer.landAcres}
        irrigationAvailable={farmer.irrigation}
        onClose={() => setWhy(null)}
      />
    </div>
  );
}
