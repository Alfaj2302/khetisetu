import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import { AlertTriangle, ArrowLeft, CloudSun, Droplets, Thermometer } from "lucide-react";
import { getCropDetails, getSources, getWeather } from "@/lib/khetiService";
import { DemandTrendChart } from "@/components/kheti/charts";
import {
  ConfidenceIndicator,
  DecisionTrace,
  DemoDataBadge,
  Disclaimer,
  Metric,
  OpportunityScore,
  Pill,
  RiskBadge,
  Section,
  SourceList,
} from "@/components/kheti/primitives";

export const Route = createFileRoute("/crop/$cropId")({
  loader: ({ params }) => {
    const crop = getCropDetails(params.cropId);
    if (!crop) throw notFound();
    return { crop };
  },
  head: ({ loaderData }) => ({
    meta: loaderData
      ? [
          { title: `${loaderData.crop.crop} crop plan | KhetiSetu` },
          {
            name: "description",
            content: `Demand outlook, weather suitability, indicative inputs, risk and confidence for ${loaderData.crop.crop}.`,
          },
          { property: "og:title", content: `${loaderData.crop.crop} crop plan | KhetiSetu` },
          { property: "og:description", content: "Explainable crop decision support." },
          { property: "og:type", content: "article" },
          { name: "twitter:card", content: "summary_large_image" },
        ]
      : [{ title: "Crop unavailable | KhetiSetu" }, { name: "robots", content: "noindex" }],
  }),
  component: CropDetails,
});

function CropDetails() {
  const { crop } = Route.useLoaderData();
  const weather = getWeather();
  const [showSources, setShowSources] = useState(false);

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
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-extrabold text-foreground">{crop.crop}</h1>
            <DemoDataBadge />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Pill tone="primary">{crop.demandLevel.toUpperCase()} DEMAND</Pill>
            <Pill tone="success">{crop.weatherLabel.toUpperCase()} WEATHER</Pill>
            <RiskBadge risk={crop.risk} />
          </div>
          <p className="mt-4 max-w-prose text-sm leading-relaxed text-muted-foreground">{crop.explanation}</p>
        </div>
        <OpportunityScore value={crop.opportunityScore} />
      </header>

      <div className="mt-6 space-y-6">
        <Section title={`Why ${crop.crop}?`} description="How KhetiSetu reached this recommendation.">
          <DecisionTrace items={crop.trace} />
        </Section>

        <Section
          title="Demand outlook"
          description="Past three seasons and the projected upcoming season."
          action={<DemoDataBadge />}
        >
          <DemandTrendChart data={crop.demandHistory} />
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <Metric label="Expected demand" value={`${crop.expectedDemand.toLocaleString("en-IN")} q`} hint={crop.demandChangeLabel} />
            <Metric label="Expected supply" value={`${crop.expectedSupply.toLocaleString("en-IN")} q`} />
            <Metric
              label="Demand gap"
              value={`${crop.demandGap > 0 ? "+" : ""}${crop.demandGap.toLocaleString("en-IN")} q`}
              tone={crop.demandGap > 0 ? "positive" : "negative"}
            />
          </dl>
        </Section>

        <Section title="Weather suitability" description={`Expected conditions in ${weather.district}.`}>
          <dl className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <CloudSun className="h-4 w-4 text-primary" aria-hidden /> Rainfall
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">{weather.rainfall}</dd>
            </div>
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Thermometer className="h-4 w-4 text-primary" aria-hidden /> Temperature
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">{weather.temperature}°C</dd>
            </div>
            <div className="rounded-lg border border-border bg-muted/50 p-3">
              <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Droplets className="h-4 w-4 text-primary" aria-hidden /> Humidity
              </dt>
              <dd className="mt-1 text-lg font-bold text-foreground">{weather.humidity}%</dd>
            </div>
          </dl>
          <p className="mt-3 text-sm text-muted-foreground">
            Overall weather suitability for {crop.crop}: <strong className="text-foreground">{crop.weatherSuitability}/100</strong>.
          </p>
          <Link
            to="/whatif"
            className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary hover:bg-primary/10 sm:w-auto"
          >
            Test weather scenario
          </Link>
        </Section>

        <Section title="Crop season" description="Suggested timeline for your sowing window.">
          <ol className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Recommended sowing", value: crop.sowingWindow },
              { label: "Growing period", value: crop.growingPeriod },
              { label: "Expected harvest window", value: "Sep–Oct (indicative)" },
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
          description="Example input plan for reference only."
          action={<DemoDataBadge />}
        >
          <ul className="grid gap-3 sm:grid-cols-3">
            {crop.inputs.map((input) => (
              <li key={input.name} className="rounded-lg border border-border bg-muted/50 p-4">
                <p className="text-base font-bold text-foreground">{input.name}</p>
                <p className="mt-1 text-sm font-semibold text-primary">{input.dose}</p>
                <p className="mt-1 text-xs text-muted-foreground">{input.stage}</p>
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <Disclaimer>
              Final fertilizer recommendations should follow local agricultural advisories / soil-test
              recommendations. These are demo values, not a prescription.
            </Disclaimer>
          </div>
        </Section>

        <Section title="Risk" description="What could go differently this season.">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge risk={crop.risk} />
          </div>
          <ul className="mt-3 space-y-2">
            {crop.risks.map((r) => (
              <li key={r} className="flex items-start gap-2 rounded-lg border border-border bg-muted/50 p-3 text-sm text-foreground">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                {r}
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Confidence" description="How sure the system is about this recommendation.">
          <ConfidenceIndicator value={crop.confidence} />
        </Section>

        <Section
          title="Based on agricultural knowledge sources"
          description="Source categories that informed this recommendation."
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
            <div className="space-y-3">
              <SourceList sources={getSources()} />
              <Disclaimer>
                These are demo source categories. No live integrations are connected in this prototype.
              </Disclaimer>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Agricultural guidance, historical crop data and weather data informed this recommendation.
            </p>
          )}
        </Section>
      </div>
    </div>
  );
}
