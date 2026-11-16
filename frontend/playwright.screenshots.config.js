import { defineConfig } from "@playwright/test";

// Screenshot della documentazione (#55), con dati inventati (vedi screenshots/server.mjs).
// Prima serve la PWA compilata: npm run build. Poi:
//   npx playwright test -c playwright.screenshots.config.js
// Le immagini finiscono in docs/img/screenshot/.
export default defineConfig({
  testDir: "screenshots",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:8197", locale: "it-IT", timezoneId: "Europe/Rome", trace: "off" },
  webServer: {
    command: "node screenshots/server.mjs",
    url: "http://127.0.0.1:8197/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
