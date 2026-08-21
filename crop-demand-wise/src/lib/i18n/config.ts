/**
 * Language configuration.
 *
 * The selected language is persisted in a cookie (mirrored into localStorage)
 * rather than only in the browser: this app renders on the server, so the
 * server has to know the language before the first byte or the SSR markup and
 * the hydrated markup would disagree. A cookie is readable in both places.
 */
export const SUPPORTED_LANGUAGES = ["en", "hi", "mr"] as const;

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const DEFAULT_LANGUAGE: SupportedLanguage = "en";

/** Read on the server (`getCookie`) and in the browser (`document.cookie`). */
export const LANGUAGE_COOKIE = "khetisetu_lang";

/** Mirror of the cookie, for browsers where cookies are unavailable. */
export const LANGUAGE_STORAGE_KEY = "khetisetu.language";

/** One year, so a returning farmer keeps the language they picked. */
export const LANGUAGE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

export function isSupportedLanguage(value: unknown): value is SupportedLanguage {
  return typeof value === "string" && (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}

/** Anything unrecognised (unset cookie, stale value) falls back to English. */
export function normalizeLanguage(value: string | null | undefined): SupportedLanguage {
  return isSupportedLanguage(value) ? value : DEFAULT_LANGUAGE;
}

/** BCP 47 tag for `Intl` formatting (weekday names). */
export function localeOf(language: SupportedLanguage): string {
  return `${language}-IN`;
}
