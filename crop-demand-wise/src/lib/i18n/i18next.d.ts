/** Types `t()` against the English resource file, so keys are checked at build time. */
import type en from "@/locales/en/translation.json";

declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "translation";
    resources: { translation: typeof en };
  }
}
