/**
 * i18next wiring for the app.
 *
 * Two instances with different jobs:
 *   - `getAppI18n` backs the React tree. On the server it is created per render
 *     so two concurrent requests in different languages can't overwrite each
 *     other's `language`; in the browser it is a singleton that
 *     `changeLanguage` mutates.
 *   - `tFor` serves lookups outside React (route `head`, the SSR error page,
 *     the API client). It never changes language — `getFixedT` binds one.
 */
import { createInstance, type i18n as I18nInstance, type TFunction } from "i18next";
import { initReactI18next } from "react-i18next";

import en from "@/locales/en/translation.json";
import hi from "@/locales/hi/translation.json";
import mr from "@/locales/mr/translation.json";
import { DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, type SupportedLanguage } from "./config";

export const resources = {
  en: { translation: en },
  hi: { translation: hi },
  mr: { translation: mr },
} as const;

function initInstance(instance: I18nInstance, language: SupportedLanguage): I18nInstance {
  void instance.init({
    resources,
    lng: language,
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: [...SUPPORTED_LANGUAGES],
    defaultNS: "translation",
    // React escapes for us; escaping here would double-encode API values.
    interpolation: { escapeValue: false },
    // Resources are bundled, so there is never a loading state to suspend on.
    react: { useSuspense: false },
  });
  return instance;
}

let browserInstance: I18nInstance | undefined;

/** The instance handed to `I18nextProvider`. */
export function getAppI18n(language: SupportedLanguage): I18nInstance {
  if (typeof document === "undefined") {
    return initInstance(createInstance().use(initReactI18next), language);
  }
  if (!browserInstance) {
    browserInstance = initInstance(createInstance().use(initReactI18next), language);
  }
  return browserInstance;
}

const lookupInstance = initInstance(createInstance(), DEFAULT_LANGUAGE);

/** `t` for code that has no React context. */
export function tFor(language: SupportedLanguage): TFunction {
  return lookupInstance.getFixedT(language);
}

export type { SupportedLanguage };
export {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  isSupportedLanguage,
  localeOf,
  normalizeLanguage,
} from "./config";
