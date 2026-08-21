import { useEffect, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";

import { getAppI18n } from "./index";
import {
  persistLanguage,
  readCookieLanguage,
  readLanguage,
  readMirroredLanguage,
} from "./language";

/**
 * Supplies the i18next instance for the language in the request cookie.
 *
 * Used by the root component and by the root's not-found/error screens, which
 * render in place of it and would otherwise have no i18n context.
 */
export function AppI18nProvider({ children }: { children: ReactNode }) {
  const [i18n] = useState(() => getAppI18n(readLanguage()));

  // Cookie missing but a mirror present (cookies cleared, storage kept): adopt
  // it after hydration, where changing the language no longer risks a mismatch.
  useEffect(() => {
    if (readCookieLanguage() !== null) return;
    const mirrored = readMirroredLanguage();
    if (mirrored === null || mirrored === i18n.language) return;
    persistLanguage(mirrored);
    void i18n.changeLanguage(mirrored);
  }, [i18n]);

  // Keep <html lang> in step with the active language for screen readers.
  useEffect(() => {
    const apply = (language: string) => {
      document.documentElement.lang = language;
    };
    apply(i18n.language);
    i18n.on("languageChanged", apply);
    return () => i18n.off("languageChanged", apply);
  }, [i18n]);

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}
