import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowDown, BarChart3, Brain, ListOrdered, Sprout, User } from "lucide-react";
import { useTranslation } from "react-i18next";

import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";

export const Route = createFileRoute("/how-it-works")({
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("howItWorks.meta.title") },
        { name: "description", content: t("howItWorks.meta.description") },
        { property: "og:title", content: t("howItWorks.meta.ogTitle") },
        { property: "og:description", content: t("howItWorks.meta.ogDescription") },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: HowItWorks,
});

const STEPS = [
  { icon: User, key: "context" },
  { icon: BarChart3, key: "data" },
  { icon: Brain, key: "forecast" },
  { icon: ListOrdered, key: "ranking" },
  { icon: Sprout, key: "explain" },
] as const;

function HowItWorks() {
  const { t } = useTranslation();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:px-6 md:py-12">
      <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">
        {t("howItWorks.title")}
      </h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">{t("howItWorks.subtitle")}</p>

      <ol className="mt-8 space-y-3">
        {STEPS.map(({ icon: Icon, key }, i) => (
          <li key={key}>
            <div className="surface-card flex items-start gap-4 p-5">
              <span className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                  {t("howItWorks.stepLabel", { index: i + 1 })}
                </p>
                <h2 className="text-lg font-bold text-foreground">
                  {t(`howItWorks.steps.${key}.title`)}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {t(`howItWorks.steps.${key}.body`)}
                </p>
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
        <h2 className="text-lg font-bold text-foreground">{t("howItWorks.coreIdeaTitle")}</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {t("howItWorks.coreIdeaBody")}
        </p>
        <Link
          to="/farmer"
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary-dark sm:w-auto"
        >
          <Sprout className="h-4 w-4" aria-hidden /> {t("common.findBestCrops")}
        </Link>
      </div>
    </div>
  );
}
