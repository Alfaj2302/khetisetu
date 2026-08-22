import { createFileRoute } from "@tanstack/react-router";
import { Check, CloudOff, DatabaseZap, MapPinOff, ShieldQuestion, Waves } from "lucide-react";
import { useTranslation } from "react-i18next";

import { DemoDataBadge, Disclaimer, Metric, Section } from "@/components/kheti/primitives";
import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";

export const Route = createFileRoute("/reliability")({
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("reliability.meta.title") },
        { name: "description", content: t("reliability.meta.description") },
        { property: "og:title", content: t("reliability.meta.ogTitle") },
        { property: "og:description", content: t("reliability.meta.ogDescription") },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: Reliability,
});

const CHECKLIST = [
  "reliability.checklist.sourceBacked",
  "reliability.checklist.confidenceShown",
  "reliability.checklist.dataProtected",
  "reliability.checklist.noUnsupportedClaims",
  "reliability.checklist.humanFinal",
  "reliability.checklist.demoLabelled",
] as const;

const EDGE_CASES = [
  { icon: DatabaseZap, key: "noHistory" },
  { icon: CloudOff, key: "noWeather" },
  { icon: Waves, key: "extremeRain" },
  { icon: MapPinOff, key: "newDistrict" },
  { icon: ShieldQuestion, key: "noSource" },
] as const;

const CONFIDENCE_LEVELS = ["high", "medium", "low"] as const;

function Reliability() {
  const { t } = useTranslation();

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-6 md:py-12">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">
            {t("reliability.title")}
          </h1>
          <p className="mt-2 text-muted-foreground">{t("reliability.subtitle")}</p>
        </div>
      </div>

      <div className="mt-6 space-y-6">
        <Section
          title={t("reliability.evaluation.title")}
          description={t("reliability.evaluation.description")}
        >
          <dl className="grid gap-3 sm:grid-cols-3">
            <Metric
              label={t("reliability.evaluation.baseline")}
              value="14.8%"
              hint={t("reliability.evaluation.baselineHint")}
            />
            <Metric
              label={t("reliability.evaluation.model")}
              value="8.6%"
              hint={t("reliability.evaluation.modelHint")}
            />
            <Metric
              label={t("reliability.evaluation.improvement")}
              value="41.9%"
              tone="positive"
              hint={t("reliability.evaluation.improvementHint")}
            />
          </dl>
          <div className="mt-4">
            <Disclaimer>{t("reliability.evaluation.disclaimer")}</Disclaimer>
          </div>
        </Section>

        <Section
          title={t("reliability.confidence.title")}
          description={t("reliability.confidence.description")}
        >
          <ul className="grid gap-3 sm:grid-cols-3">
            {CONFIDENCE_LEVELS.map((level) => (
              <li key={level} className="rounded-lg border border-border bg-muted/50 p-4">
                <p className="text-base font-bold text-foreground">
                  {t(`reliability.confidence.${level}.level`)}
                </p>
                <p className="text-sm font-semibold text-primary">
                  {t(`reliability.confidence.${level}.range`)}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {t(`reliability.confidence.${level}.body`)}
                </p>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-muted-foreground">{t("reliability.confidence.note")}</p>
        </Section>

        <Section
          title={t("reliability.checklist.title")}
          description={t("reliability.checklist.description")}
        >
          <ul className="grid gap-2 sm:grid-cols-2">
            {CHECKLIST.map((itemKey) => (
              <li
                key={itemKey}
                className="flex items-start gap-2 rounded-lg border border-border bg-muted/50 p-3 text-sm text-foreground"
              >
                <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-success/15 text-success">
                  <Check className="h-3 w-3" aria-hidden />
                </span>
                {t(itemKey)}
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title={t("reliability.edgeCases.title")}
          description={t("reliability.edgeCases.description")}
        >
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {EDGE_CASES.map(({ icon: Icon, key }) => (
              <li key={key} className="rounded-lg border border-border bg-muted/50 p-4">
                <Icon className="h-5 w-5 text-primary" aria-hidden />
                <p className="mt-2 text-base font-bold text-foreground">
                  {t(`reliability.edgeCases.${key}.title`)}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {t(`reliability.edgeCases.${key}.body`)}
                </p>
              </li>
            ))}
          </ul>
          <p className="mt-4 rounded-lg border border-info/30 bg-info/5 p-3 text-sm font-medium text-foreground">
            {t("reliability.edgeCases.note")}
          </p>
        </Section>
      </div>
    </div>
  );
}
