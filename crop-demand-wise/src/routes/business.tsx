import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AlertTriangle, CircleAlert, Truck, X } from "lucide-react";
import { getAgriBusinessData } from "@/lib/khetiService";
import { DemoDataBadge, Disclaimer, Metric, Pill, Section } from "@/components/kheti/primitives";

export const Route = createFileRoute("/business")({
  head: () => ({
    meta: [
      { title: "Agri Business supply planning | KhetiSetu" },
      {
        name: "description",
        content:
          "Turn aggregated farmer crop intent into fertilizer demand forecasts, supply alerts and dispatch actions.",
      },
      { property: "og:title", content: "Agri Business supply planning | KhetiSetu" },
      { property: "og:description", content: "From farmer intent to smart supply planning." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Business,
});

type PanelKey = "forecast" | "inventory" | "transfers" | null;

const PANELS: Record<Exclude<PanelKey, null>, { title: string; rows: [string, string][] }> = {
  forecast: {
    title: "Urea demand forecast — Kharif 2026",
    rows: [
      ["June", "3,900 MT"],
      ["July", "4,600 MT"],
      ["August", "2,600 MT"],
      ["September", "1,300 MT"],
    ],
  },
  inventory: {
    title: "Urea inventory by depot",
    rows: [
      ["Nashik depot", "3,100 MT"],
      ["Pune depot", "4,200 MT"],
      ["Aurangabad depot", "2,500 MT"],
    ],
  },
  transfers: {
    title: "Suggested stock transfers",
    rows: [
      ["Pune → Nashik", "2,600 MT"],
      ["Aurangabad → Nashik", "1,500 MT"],
    ],
  },
};

function Business() {
  const data = getAgriBusinessData();
  const [panel, setPanel] = useState<PanelKey>(null);
  const active = panel ? PANELS[panel] : null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-12">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">KhetiSetu — Agri Business</h1>
          <p className="mt-2 text-muted-foreground">From farmer intent to smart supply planning.</p>
          <div className="mt-3">
            <Pill tone="primary">{data.season}</Pill>
          </div>
        </div>
        <DemoDataBadge />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Section title="Expected input demand" description="Forecast fertilizer volumes for the season.">
          <dl className="grid gap-3 sm:grid-cols-3">
            {data.demand.map((d) => (
              <Metric key={d.input} label={d.input} value={d.volume} />
            ))}
          </dl>
        </Section>

        <Section title="Farmer crop intent" description="Aggregated and anonymized — Nashik cluster.">
          <ul className="space-y-2">
            {data.intent.map((i) => {
              const max = Math.max(...data.intent.map((x) => x.acres));
              return (
                <li key={i.crop}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-semibold text-foreground">{i.crop}</span>
                    <span className="text-muted-foreground">{i.acres.toLocaleString("en-IN")} acres</span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-crop" style={{ width: `${(i.acres / max) * 100}%` }} />
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="mt-3 text-xs text-muted-foreground">
            Individual farmer information is never shown. Only aggregated, anonymized intent.
          </p>
        </Section>

        <Section title="Supply alerts" description="Where attention is needed this week.">
          <ul className="space-y-2">
            {data.alerts.map((a) => {
              const isError = a.level === "error";
              const Icon = isError ? CircleAlert : AlertTriangle;
              return (
                <li
                  key={a.region}
                  className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${
                    isError ? "border-destructive/40 bg-destructive/5" : "border-warning/40 bg-warning/5"
                  }`}
                >
                  <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${isError ? "text-destructive" : "text-warning"}`} aria-hidden />
                  <span className="text-foreground">
                    <strong>{a.region}</strong> — {a.message}{" "}
                    <span className={`font-semibold ${isError ? "text-destructive" : "text-warning"}`}>
                      ({isError ? "High priority" : "Watch"})
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </Section>

        <Section title="Recommended action" description="Urea position for the Nashik cluster.">
          <dl className="grid gap-3 sm:grid-cols-3">
            <Metric label="Forecast" value={data.action.forecast} />
            <Metric label="Current stock" value={data.action.stock} />
            <Metric label="Safety stock" value={data.action.safety} />
          </dl>
          <p className="mt-4 flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-base font-bold text-primary">
            <Truck className="h-5 w-5" aria-hidden /> {data.action.recommended}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {(["forecast", "inventory", "transfers"] as const).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setPanel(key)}
                className="rounded-lg border border-border bg-card px-4 py-3 text-sm font-semibold text-foreground hover:bg-muted"
              >
                View {key}
              </button>
            ))}
          </div>
        </Section>
      </div>

      <div className="mt-6">
        <Disclaimer>
          All volumes, alerts and intent figures on this screen are synthetic demo data for the prototype.
        </Disclaimer>
      </div>

      {active && (
        <div className="fixed inset-0 z-50">
          <button type="button" aria-label="Close panel" onClick={() => setPanel(null)} className="absolute inset-0 bg-foreground/40" />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={active.title}
            className="absolute inset-x-0 bottom-0 rounded-t-2xl bg-card p-5 shadow-lift animate-in slide-in-from-bottom sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[420px] sm:rounded-none sm:rounded-l-2xl sm:p-6 sm:slide-in-from-right"
          >
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
              <h2 className="text-lg font-bold text-foreground">{active.title}</h2>
              <button
                type="button"
                onClick={() => setPanel(null)}
                aria-label="Close"
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <dl className="mt-4 space-y-2">
              {active.rows.map(([k, v]) => (
                <div key={k} className="flex items-center justify-between rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="font-semibold text-foreground">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-4">
              <DemoDataBadge />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
