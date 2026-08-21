/**
 * Reading and persisting the selected language.
 *
 * `readLanguage` is isomorphic on purpose: the server reads the request cookie
 * and the browser reads the same cookie from `document`, so SSR and hydration
 * always agree. localStorage is only a mirror, applied after hydration (see
 * `AppI18nProvider`), because a value the server could not see would otherwise
 * change the markup mid-hydration.
 */
import { createIsomorphicFn } from "@tanstack/react-start";
import { getCookie } from "@tanstack/react-start/server";

import {
  DEFAULT_LANGUAGE,
  LANGUAGE_COOKIE,
  LANGUAGE_COOKIE_MAX_AGE,
  LANGUAGE_STORAGE_KEY,
  isSupportedLanguage,
  normalizeLanguage,
  type SupportedLanguage,
} from "./config";

/** Null when the cookie is absent, so callers can tell "unset" from "English". */
export function languageFromCookieHeader(
  header: string | null | undefined,
): SupportedLanguage | null {
  if (!header) return null;
  for (const part of header.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name?.trim() !== LANGUAGE_COOKIE) continue;
    const value = decodeURIComponent(rest.join("="));
    return isSupportedLanguage(value) ? value : null;
  }
  return null;
}

export const readLanguage = createIsomorphicFn()
  .server((): SupportedLanguage => normalizeLanguage(getCookie(LANGUAGE_COOKIE)))
  .client((): SupportedLanguage => readCookieLanguage() ?? DEFAULT_LANGUAGE);

/** Browser-only: the cookie as it stands, or null when it was never set. */
export function readCookieLanguage(): SupportedLanguage | null {
  return languageFromCookieHeader(document.cookie);
}

/** The localStorage mirror, for browsers that dropped the cookie. */
export function readMirroredLanguage(): SupportedLanguage | null {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return isSupportedLanguage(stored) ? stored : null;
  } catch {
    // Private mode / storage disabled — the cookie is the source of truth anyway.
    return null;
  }
}

export function persistLanguage(language: SupportedLanguage): void {
  document.cookie = `${LANGUAGE_COOKIE}=${language}; path=/; max-age=${LANGUAGE_COOKIE_MAX_AGE}; samesite=lax`;
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Nothing to do: the cookie above already persisted the choice.
  }
}
