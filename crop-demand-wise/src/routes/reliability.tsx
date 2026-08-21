import { createFileRoute } from "@tanstack/react-router";
import { Check, CloudOff, DatabaseZap, MapPinOff, ShieldQuestion, Waves } from "lucide-react";
import { DemoDataBadge, Disclaimer, Metric, Section } from "@/components/kheti/primitives";

export const Route = createFileRoute("/reliability")({
  head: () => ({
    meta: [
      { title: "AI Reliability & Responsible AI | KhetiSetu" },
      {
        name: "description",
        content:
          "How KhetiSetu evaluates forecasts, communicates confidence, and handles edge cases responsibly.",
      },
      { property: "og:title", content: "AI Reliability & Responsible AI | KhetiSetu" },
      { property: "og:description", content: "Evaluation, confidence and responsible AI practices." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Reliability,
});

const CHECKLIST = [
  "Source-backed recommendations",
  "Confidence shown with every recommendation",
  "Farmer data protected and never shown individually",
  "No unsupported numeric claims",
  "Human decision remains final",
  "Synthetic demo data clearly labeled",
];

const EDGE_CASES = [
  { icon: DatabaseZap, title: "No historical data", body: "Confidence drops and the crop is shown as low-evidence." },
  { icon: CloudOff, title: "Weather unavailable", body: "Weather suitability is withheld instead of estimated." },
  { icon: Waves, title: "Extreme rainfall", body: "Scenario warning is shown and risk is raised." },
  { icon: MapPinOff, title: "New district", body: "Nearby district patterns are used, clearly labeled as such." },
  { icon: ShieldQuestion, title: "No reliable source", body: "The system declines to answer rather than guessing." },
];

function Reliability() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-12">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">AI Reliability & Responsible AI</h1>
          <p className="mt-2 text-muted-foreground">
            Why the recommendations can be trusted — and where their limits are.
          </p>
        </div>
        <DemoDataBadge label="Demo evaluation" />
      </div>

      <div className="mt-6 space-y-6">
        <Section
          title="Forecast evaluation"
          description="Demand forecast error compared against a seasonal-average baseline."
          action={<DemoDataBadge label="Demo evaluation values" />}
        >
          <dl className="grid gap-3 sm:grid-cols-3">
            <Metric label="Baseline error" value="14.8%" hint="Seasonal average baseline" />
            <Metric label="ML model error" value="8.6%" hint="Demo model" />
            <Metric label="Improvement" value="41.9%" tone="positive" hint="Relative error reduction" />
          </dl>
          <div className="mt-4">
            <Disclaimer>
              These are demo evaluation values from a prototype dataset. They are not production-validated
              results.
            </Disclaimer>
          </div>
        </Section>

        <Section title="Confidence levels" description="What high, medium and low confidence mean.">
          <ul className="grid gap-3 sm:grid-cols-3">
            {[
              { level: "High", range: "80–100%", body: "Several seasons of consistent data and stable weather." },
              { level: "Medium", range: "60–79%", body: "Partial data coverage or moderate weather variation." },
              { level: "Low", range: "Below 60%", body: "Limited history or unusual conditions — treat with caution." },
            ].map((c) => (
              <li key={c.level} className="rounded-lg border border-border bg-muted/50 p-4">
                <p className="text-base font-bold text-foreground">{c.level}</p>
                <p className="text-sm font-semibold text-primary">{c.range}</p>
                <p className="mt-1 text-sm text-muted-foreground">{c.body}</p>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-muted-foreground">
            Confidence decreases when historical data is limited or weather conditions are unusual.
          </p>
        </Section>

        <Section title="Responsible AI checklist" description="Practices applied across the product.">
          <ul className="grid gap-2 sm:grid-cols-2">
            {CHECKLIST.map((item) => (
              <li key={item} className="flex items-start gap-2 rounded-lg border border-border bg-muted/50 p-3 text-sm text-foreground">
                <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-success/15 text-success">
                  <Check className="h-3 w-3" aria-hidden />
                </span>
                {item}
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Edge cases" description="What happens when the data is not good enough.">
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {EDGE_CASES.map(({ icon: Icon, title, body }) => (
              <li key={title} className="rounded-lg border border-border bg-muted/50 p-4">
                <Icon className="h-5 w-5 text-primary" aria-hidden />
                <p className="mt-2 text-base font-bold text-foreground">{title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{body}</p>
              </li>
            ))}
          </ul>
          <p className="mt-4 rounded-lg border border-info/30 bg-info/5 p-3 text-sm font-medium text-foreground">
            In all of these cases, KhetiSetu reduces confidence or asks for more information instead of
            guessing.
          </p>
        </Section>
      </div>
    </div>
  );
}
