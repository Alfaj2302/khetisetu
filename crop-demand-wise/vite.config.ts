// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  vite: {
    // Pin the dev origin. Without this the server falls back through 8080, 8081,
    // ... to whatever is free, so the origin changes between runs and the
    // backend's CORS_ORIGINS (which lists :3000) stops matching — the app then
    // reports "Could not reach the KhetiSetu API". strictPort makes a taken port
    // a startup error instead of a silent shift back to that failure.
    server: { port: 3000, strictPort: true },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
