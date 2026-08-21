import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { CalendarDays, Droplets, MapPin, MessageCircle, Ruler, Wheat } from "lucide-react";
import { useFarm } from "@/lib/farm-store";
import { getCropRecommendations, getDemandSupply, getWeather } from "@/lib/khetiService";
import type { CropRecommendation } from "@/lib/mockData";
import { CropRecommendationCard } from "@/components/kheti/CropRecommendationCard";
import { WhyDrawer } from "@/components/kheti/WhyDrawer";
import { WeatherOutlookCard } from "@/components/kheti/WeatherOutlookCard";
import { DemandSupplyChart } from "@/components/kheti/charts";
import { DemoDataBadge, Disclaimer, Section } from "@/components/kheti/primitives";

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

function Recommendations() {
  const { farmer } = useFarm();
  const recs = getCropRecommendations(farmer);
  const [why, setWhy] = useState<CropRecommendation | null>(null);

  const context = [
    { icon: MapPin, text: farmer.district },
    { icon: Ruler, text: `${farmer.landAcres} acres` },
    { icon: Droplets, text: farmer.irrigation ? "Irrigation available" : "No irrigation" },
    { icon: Wheat, text: `Previous crop: ${farmer.previousCrop}` },
    { icon: CalendarDays, text: `Sowing: ${farmer.sowingMonth}` },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-12">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">Your Crop Opportunities</h1>
          <p className="mt-2 text-muted-foreground">
            Based on your location, season, weather and historical demand.
          </p>
        </div>
        <DemoDataBadge />
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
          <Link to="/farmer" className="inline-flex items-center rounded-full px-3 py-1.5 text-sm font-semibold text-primary underline underline-offset-4">
            Change details
          </Link>
        </li>
      </ul>

      <h2 className="mt-8 text-xl font-bold text-foreground">Top 3 crops to consider</h2>
      <div className="mt-4 space-y-4">
        {recs.map((rec, i) => (
          <CropRecommendationCard key={rec.id} rec={rec} rank={i + 1} onWhy={setWhy} />
        ))}
      </div>

      <div className="mt-8 space-y-6">
        <Section
          title="Demand vs expected supply"
          description="Positive gap = opportunity. Negative gap = possible oversupply."
          action={<DemoDataBadge />}
        >
          <DemandSupplyChart data={getDemandSupply()} />
        </Section>

        <WeatherOutlookCard weather={getWeather(farmer.district)} />

        <Disclaimer>
          These are projected demo values, not observed market facts. KhetiSetu provides decision
          support — the final crop decision remains yours.
        </Disclaimer>

        <Link
          to="/ask"
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary hover:bg-primary/10 sm:w-auto"
        >
          <MessageCircle className="h-4 w-4" aria-hidden /> Ask KhetiSetu about this recommendation
        </Link>
      </div>

      <WhyDrawer rec={why} onClose={() => setWhy(null)} />
    </div>
  );
}
