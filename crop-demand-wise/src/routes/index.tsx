import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, BarChart3, CloudSun, Compass, Sprout, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";

import heroImage from "@/assets/hero-farmer.jpg";
import { DemoDataBadge } from "@/components/kheti/primitives";
import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";

export const Route = createFileRoute("/")({
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("home.meta.title") },
        { name: "description", content: t("home.meta.description") },
        { property: "og:title", content: t("home.meta.ogTitle") },
        { property: "og:description", content: t("home.meta.ogDescription") },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: Landing,
});

const BENEFITS = [
  { icon: Sprout, key: "crop" },
  { icon: CloudSun, key: "weather" },
  { icon: BarChart3, key: "demand" },
] as const;

const OVERLAYS = [
  { labelKey: "home.overlays.districtLabel", valueKey: "home.overlays.districtValue" },
  { labelKey: "home.overlays.weatherLabel", valueKey: "home.overlays.weatherValue" },
  { labelKey: "home.overlays.demandLabel", valueKey: "home.overlays.demandValue" },
  { labelKey: "home.overlays.opportunityLabel", valueKey: "home.overlays.opportunityValue" },
] as const;

const PIPELINE_STEPS = [
  "home.pipeline.steps.context",
  "home.pipeline.steps.demand",
  "home.pipeline.steps.supply",
  "home.pipeline.steps.weather",
  "home.pipeline.steps.season",
  "home.pipeline.steps.result",
] as const;

function Landing() {
  const { t } = useTranslation();

  return (
    <div>
      {/* Hero */}
      <section className="border-b border-border bg-card">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 md:px-6 md:py-16 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:gap-14 lg:py-20">
          <div className="min-w-0">
            <h1 className="mt-4 text-3xl font-extrabold leading-[1.1] text-foreground sm:text-4xl lg:text-5xl">
              {t("home.headlineTop")}
              <br />
              <span className="text-primary">{t("home.headlineBottom")}</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground md:text-lg">
              {t("home.intro")}
            </p>

            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Link
                to="/farmer"
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-6 py-4 text-base font-semibold text-primary-foreground shadow-card transition-colors hover:bg-primary-dark active:bg-primary-dark"
              >
                <Sprout className="h-5 w-5" aria-hidden /> {t("common.findBestCrops")}
              </Link>
              <Link
                to="/how-it-works"
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-6 py-4 text-base font-semibold text-foreground transition-colors hover:bg-muted"
              >
                {t("home.seeHowItWorks")} <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            </div>

            <p className="mt-5 max-w-xl text-sm text-muted-foreground">{t("home.note")}</p>
          </div>

          <div className="relative">
            <img
              src={heroImage}
              alt={t("home.heroAlt")}
              width={1408}
              height={1104}
              className="w-full rounded-2xl border border-border object-cover shadow-lift"
            />
            <dl className="mt-4 grid grid-cols-2 gap-2 lg:absolute lg:-bottom-6 lg:-left-6 lg:mt-0 lg:w-64 lg:grid-cols-1 lg:gap-2 lg:rounded-xl lg:border lg:border-border lg:bg-card/95 lg:p-4 lg:shadow-lift lg:backdrop-blur">
              {OVERLAYS.map((o) => (
                <div
                  key={o.labelKey}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm lg:border-0 lg:bg-transparent lg:px-0 lg:py-0"
                >
                  <dt className="text-muted-foreground">{t(o.labelKey)}</dt>
                  <dd className="font-semibold text-foreground">{t(o.valueKey)}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="mx-auto max-w-7xl px-4 py-12 md:px-6 md:py-16">
        <h2 className="text-2xl font-bold text-foreground md:text-3xl">
          {t("home.benefits.heading")}
        </h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">{t("home.benefits.subheading")}</p>
        <ul className="mt-8 grid gap-4 md:grid-cols-3">
          {BENEFITS.map(({ icon: Icon, key }) => (
            <li key={key} className="surface-card p-6">
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-lg font-semibold text-foreground">
                {t(`home.benefits.${key}.title`)}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {t(`home.benefits.${key}.body`)}
              </p>
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
                {t("home.pipeline.heading")}
              </h2>
              <p className="mt-3 max-w-xl leading-relaxed text-muted-foreground">
                {t("home.pipeline.body")}
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  to="/business"
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 text-sm font-semibold text-foreground hover:bg-muted"
                >
                  <Compass className="h-4 w-4" aria-hidden /> {t("home.pipeline.businessCta")}
                </Link>
                <Link
                  to="/reliability"
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 text-sm font-semibold text-foreground hover:bg-muted"
                >
                  <TrendingUp className="h-4 w-4" aria-hidden /> {t("home.pipeline.reliabilityCta")}
                </Link>
              </div>
            </div>
            <ol className="grid gap-2 rounded-xl border border-border bg-muted/40 p-4 sm:grid-cols-2">
              {PIPELINE_STEPS.map((stepKey) => (
                <li
                  key={stepKey}
                  className="rounded-lg border border-border bg-card px-3 py-3 text-sm font-medium text-foreground"
                >
                  {t(stepKey)}
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>
    </div>
  );
}
