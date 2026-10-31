import { defineConfig, devices } from "@playwright/test";

// Test nel browser: avviano un sito finto e il server vero (vedi e2e/server.mjs).
// Prima serve la PWA compilata: npm run build.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: "http://127.0.0.1:8097", locale: "it-IT", trace: "retain-on-failure" },
  webServer: {
    command: "node e2e/server.mjs",
    url: "http://127.0.0.1:8097/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
