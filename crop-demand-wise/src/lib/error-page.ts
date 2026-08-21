import { tFor, type SupportedLanguage } from "./i18n";

/**
 * Last-resort HTML for an SSR failure, rendered without React — so it reads the
 * language straight from the request cookie (see `server.ts`) instead of the
 * i18n provider.
 */
export function renderErrorPage(language: SupportedLanguage = "en"): string {
  const t = tFor(language);
  return `<!doctype html>
<html lang="${language}">
  <head>
    <meta charset="utf-8" />
    <title>${t("root.error.title")}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body { font: 15px/1.5 system-ui, -apple-system, sans-serif; background: #fafafa; color: #111; display: grid; place-items: center; min-height: 100vh; margin: 0; padding: 1.5rem; }
      .card { max-width: 28rem; width: 100%; text-align: center; padding: 2rem; }
      h1 { font-size: 1.25rem; margin: 0 0 0.5rem; }
      p { color: #4b5563; margin: 0 0 1.5rem; }
      .actions { display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; }
      a, button { padding: 0.5rem 1rem; border-radius: 0.375rem; font: inherit; cursor: pointer; text-decoration: none; border: 1px solid transparent; }
      .primary { background: #111; color: #fff; }
      .secondary { background: #fff; color: #111; border-color: #d1d5db; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>${t("root.error.title")}</h1>
      <p>${t("root.error.detail")}</p>
      <div class="actions">
        <button class="primary" onclick="location.reload()">${t("common.tryAgain")}</button>
        <a class="secondary" href="/">${t("common.goHome")}</a>
      </div>
    </div>
  </body>
</html>`;
}
