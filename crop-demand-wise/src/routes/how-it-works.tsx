import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowDown, BarChart3, Brain, ListOrdered, Sprout, User } from "lucide-react";

export const Route = createFileRoute("/how-it-works")({
  head: () => ({
    meta: [
      { title: "How KhetiSetu works | Crop opportunity in five steps" },
      {
        name: "description",
        content:
          "From farmer context and agricultural data to AI forecast, crop ranking, explanation and weather what-if.",
      },
      { property: "og:title", content: "How KhetiSetu works" },
      { property: "og:description", content: "Five steps from farm details to an explained crop recommendation." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: HowItWorks,
});

const STEPS = [
  { icon: User, title: "Farmer context", body: "Location • Land • Irrigation • Previous crop" },
  { icon: BarChart3, title: "Agricultural data", body: "Weather • Crop calendar • Historical data" },
  { icon: Brain, title: "AI forecast", body: "Expected demand • Expected supply" },
  { icon: ListOrdered, title: "Crop ranking", body: "Top 3 opportunities for your farm" },
  { icon: Sprout, title: "Explain & simulate", body: "AI explanation • Weather what-if" },
];

function HowItWorks() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:px-6 md:py-12">
      <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">How KhetiSetu works</h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">
        Five steps that connect what you can grow with what the market may need.
      </p>

      <ol className="mt-8 space-y-3">
        {STEPS.map(({ icon: Icon, title, body }, i) => (
          <li key={title}>
            <div className="surface-card flex items-start gap-4 p-5">
              <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Step {i + 1}</p>
                <h2 className="text-lg font-bold text-foreground">{title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{body}</p>
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div className="flex justify-center py-1" aria-hidden>
                <ArrowDown className="h-5 w-5 text-border" />
              </div>
            )}
          </li>
        ))}
      </ol>

      <div className="surface-card mt-8 p-5 md:p-6">
        <h2 className="text-lg font-bold text-foreground">The core idea</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Farmers need to understand not only what they can grow, but whether there may be demand when the
          crop is ready. KhetiSetu turns the gap between expected demand and expected supply into a clear
          crop opportunity — and explains how it got there.
        </p>
        <Link
          to="/farmer"
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark sm:w-auto"
        >
          <Sprout className="h-4 w-4" aria-hidden /> Find Best Crops
        </Link>
      </div>
    </div>
  );
}
