import { useRouter } from "@tanstack/react-router";
import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "@/lib/i18n";
import { persistLanguage } from "@/lib/i18n/language";

/**
 * Native select, styled like the other selectors in the app.
 *
 * Route `head()` (page title, meta description) is evaluated when a route
 * loads, not on every render, so the language change is followed by an
 * invalidate to re-run it. No route here has a loader, so nothing refetches.
 */
export function LanguageSwitcher({ className = "" }: { className?: string }) {
  const { t, i18n } = useTranslation();
  const router = useRouter();

  async function change(language: SupportedLanguage) {
    if (language === i18n.language) return;
    persistLanguage(language);
    await i18n.changeLanguage(language);
    await router.invalidate();
  }

  return (
    <div className={`relative ${className}`}>
      <Languages
        className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <label className="sr-only" htmlFor="language">
        {t("language.label")}
      </label>
      <select
        id="language"
        value={i18n.language}
        onChange={(event) => void change(event.target.value as SupportedLanguage)}
        className="h-11 rounded-lg border border-border bg-card pl-8 pr-2 text-sm font-medium text-foreground transition-colors hover:bg-muted focus:border-primary"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <option key={language} value={language}>
            {t(`language.${language}`)}
          </option>
        ))}
      </select>
    </div>
  );
}
