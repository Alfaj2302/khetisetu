import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  BarChart3,
  CloudSun,
  Compass,
  Sprout,
  TrendingUp,
} from "lucide-react";
import heroImage from "@/assets/hero-farmer.jpg";
import { DemoDataBadge } from "@/components/kheti/primitives";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "KhetiSetu — Know what to grow, know what the market needs" },
      {
        name: "description",
        content:
          "KhetiSetu combines historical crop demand, weather and season rules to help Indian farmers find crops with stronger demand opportunities.",
      },
      { property: "og:title", content: "KhetiSetu — Know what to grow" },
      {
        property: "og:description",
        content:
          "Crop opportunity intelligence for farmers and supply planning for agri-businesses.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Landing,
});

const BENEFITS = [
  {
    icon: Sprout,
    title: "Smarter crop decisions",
    body: "Compare crop options for your farm instead of guessing from last season's prices.",
  },
  {
    icon: CloudSun,
    title: "Weather-aware recommendations",
    body: "See how expected rainfall and temperature influence crop suitability.",
  },
  {
    icon: BarChart3,
    title: "Demand–supply intelligence",
    body: "Identify demand gaps before you decide what to sow.",
  },
];

const OVERLAYS = [
  { label: "Nashik", value: "Kharif 2026" },
  { label: "Weather", value: "Favorable" },
  { label: "Demand", value: "Increasing" },
  { label: "Opportunity", value: "High" },
];

function Landing() {
  return (
    <div>
      {/* Hero */}
      <section className="border-b border-border bg-card">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:px-6 md:py-16 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:gap-14 lg:py-20">
          <div className="min-w-0">
            <DemoDataBadge label="Prototype · demo data" />
            <h1 className="mt-4 text-3xl font-extrabold leading-[1.1] text-foreground sm:text-4xl lg:text-5xl">
              Know what to grow.
              <br />
              <span className="text-primary">Know what the market needs.</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground md:text-lg">
              KhetiSetu combines historical crop demand, weather and agricultural season rules to help
              farmers identify crops with stronger future demand opportunities.
            </p>

            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/farmer"
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-4 text-base font-semibold text-primary-foreground shadow-card transition-colors hover:bg-primary-dark active:bg-primary-dark"
              >
                <Sprout className="h-5 w-5" aria-hidden /> Find Best Crops
              </Link>
              <Link
                to="/how-it-works"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-6 py-4 text-base font-semibold text-foreground transition-colors hover:bg-muted"
              >
                See How It Works <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            </div>

            <p className="mt-5 max-w-xl text-sm text-muted-foreground">
              Decision support, not a profit guarantee. Every number in this prototype is synthetic demo
              data.
            </p>
          </div>

          <div className="relative">
            <img
              src={heroImage}
              alt="Indian farmer checking crop information on a mobile phone in a tomato and onion field"
              width={1408}
              height={1104}
              className="w-full rounded-2xl border border-border object-cover shadow-lift"
            />
            <dl className="mt-4 grid grid-cols-2 gap-2 lg:absolute lg:-bottom-6 lg:-left-6 lg:mt-0 lg:w-64 lg:grid-cols-1 lg:gap-2 lg:rounded-xl lg:border lg:border-border lg:bg-card/95 lg:p-4 lg:shadow-lift lg:backdrop-blur">
              {OVERLAYS.map((o) => (
                <div
                  key={o.label}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm lg:border-0 lg:bg-transparent lg:px-0 lg:py-0"
                >
                  <dt className="text-muted-foreground">{o.label}</dt>
                  <dd className="font-semibold text-foreground">{o.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="mx-auto max-w-7xl px-4 py-12 md:px-6 md:py-16">
        <h2 className="text-2xl font-bold text-foreground md:text-3xl">
          Built around one question farmers actually face
        </h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Not just "how do I grow this crop", but "will there likely be demand when my crop is ready?"
        </p>
        <ul className="mt-8 grid gap-4 md:grid-cols-3">
          {BENEFITS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="surface-card p-6">
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-lg font-semibold text-foreground">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* Differentiator strip */}
      <section className="border-y border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 py-12 md:px-6">
          <div className="grid gap-8 lg:grid-cols-[1fr_1fr] lg:items-center">
            <div>
              <h2 className="text-2xl font-bold text-foreground md:text-3xl">
                From demand gap to crop opportunity
              </h2>
              <p className="mt-3 max-w-xl leading-relaxed text-muted-foreground">
                KhetiSetu brings farmer context, historical demand, expected supply, weather and crop
                season rules together — then explains the recommendation instead of pretending to
                predict the future perfectly.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  to="/business"
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 text-sm font-semibold text-foreground hover:bg-muted"
                >
                  <Compass className="h-4 w-4" aria-hidden /> Agri Business preview
                </Link>
                <Link
                  to="/reliability"
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 text-sm font-semibold text-foreground hover:bg-muted"
                >
                  <TrendingUp className="h-4 w-4" aria-hidden /> AI reliability
                </Link>
              </div>
            </div>
            <ol className="grid gap-2 rounded-xl border border-border bg-muted/40 p-4 sm:grid-cols-2">
              {[
                "Farmer context",
                "Historical demand",
                "Expected supply",
                "Weather",
                "Crop season rules",
                "→ Demand gap → Recommendation",
              ].map((step) => (
                <li
                  key={step}
                  className="rounded-lg border border-border bg-card px-3 py-3 text-sm font-medium text-foreground"
                >
                  {step}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>
    </div>
  );
}
