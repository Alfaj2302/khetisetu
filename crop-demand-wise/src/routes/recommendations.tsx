import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { CalendarDays, Droplets, MapPin, MessageCircle, Ruler, Wheat } from "lucide-react";

import type { RecommendationItem } from "@/services/api";
import { useCrops, useWeather } from "@/services/queries";
import { useFarm } from "@/lib/farm-store";
import { monthLabel } from "@/lib/format";
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
  head: () => ({
    meta: [
      { title: "Your crop opportunities | KhetiSetu" },
      {
        name: "description",
        content:
          "Top crop opportunities for your farm, with demand gap, weather suitability, risk and confidence.",
      },
      { property: "og:title", content: "Your crop opportunities | KhetiSetu" },
      { property: "og:description", content: "Ranked crop opportunities with explanations." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
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
          title="No analysis yet"
          detail="Tell KhetiSetu about your farm and it will rank the crops that are eligible for your district and sowing month."
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

  const previousCropName = crops.data?.find((c) => c.id === farmer.previousCropId)?.name;
  const chartRows = toChartRows(recommendation.recommendations);
  const unit = recommendation.recommendations.find((r) => r.unit)?.unit ?? "units";

  const context = [
    { icon: MapPin, text: recommendation.district.name },
    { icon: Ruler, text: `${farmer.landAcres} acres` },
    { icon: Droplets, text: farmer.irrigation ? "Irrigation available" : "No irrigation" },
    ...(previousCropName ? [{ icon: Wheat, text: `Previous crop: ${previousCropName}` }] : []),
    { icon: CalendarDays, text: `Sowing: ${monthLabel(farmer.sowingMonth)}` },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-12">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">
          Your Crop Opportunities
        </h1>
        <p className="mt-2 text-muted-foreground">
          Based on your location, season, weather and recorded demand.
        </p>
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
            Change details
          </Link>
        </li>
      </ul>

      {recommendation.recommendations.length === 0 ? (
        <div className="mt-8">
          <EmptyState
            title="No crops are eligible for this district and month"
            detail={`The API found no crop calendar entry for ${recommendation.district.name} in ${monthLabel(farmer.sowingMonth)}. Try a different sowing month or district.`}
            action={
              <Link
                to="/farmer"
                className="inline-flex items-center justify-center rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark"
              >
                Change my details
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <h2 className="mt-8 text-xl font-bold text-foreground">
            Top {recommendation.recommendations.length} crop
            {recommendation.recommendations.length === 1 ? "" : "s"} to consider
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
          title="Demand vs expected supply"
          description="Positive gap = opportunity. Negative gap = possible oversupply."
        >
          {chartRows.length > 0 ? (
            <DemandSupplyChart data={chartRows} unit={unit} />
          ) : (
            <EmptyState
              title="No market figures for these crops yet"
              detail="The API has no demand/supply row for this district and crop combination."
            />
          )}
        </Section>

        {weather.isPending ? (
          <LoadingState label="Loading weather outlook…" />
        ) : weather.isError ? (
          <ErrorState error={weather.error} onRetry={() => void weather.refetch()} />
        ) : weather.data ? (
          <WeatherOutlookCard weather={weather.data} districtName={recommendation.district.name} />
        ) : null}

        <Disclaimer>
          Demand and supply figures come from the API's recorded market data; rows extended by
          synthetic backfill are marked as such at the source. KhetiSetu provides decision support —
          the final crop decision remains yours.
        </Disclaimer>

        <Link
          to="/ask"
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary hover:bg-primary/10 sm:w-auto"
        >
          <MessageCircle className="h-4 w-4" aria-hidden /> Ask KhetiSetu about this recommendation
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
