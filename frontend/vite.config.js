import fs from "node:fs";
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { VitePWA } from "vite-plugin-pwa";

// In sviluppo (npm run dev) le chiamate /api vanno al backend su localhost:8080.
const backend = process.env.BACKEND_URL || "http://localhost:8080";
// Versione dell'interfaccia, scritta nel JS: le Impostazioni la mostrano accanto a quella del server.
// Si legge da package.json (scripts/release.py la tiene uguale a VERSION): nella build Docker
// c'è solo la cartella frontend/.
const { version } = JSON.parse(fs.readFileSync(new URL("./package.json", import.meta.url), "utf8"));

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(version) },
  plugins: [
    svelte(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.js",
      // Il service worker lo registra e lo aggiorna src/lib/pwa.svelte.js.
      injectRegister: false,
      manifestFilename: "manifest.webmanifest",
      includeAssets: ["icons/*.png", "icons/*.svg"],
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,svg}", "**/*-latin-[0-9]*.woff2", "**/*-latin-wght-normal*.woff2", "icons/apple-touch-icon*.png"],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
      manifest: {
        id: "/",
        name: "Galactic Feed",
        short_name: "Galactic",
        description: "Il tuo lettore di notizie: feed RSS e canali YouTube scelti da te.",
        lang: "it",
        dir: "ltr",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "any",
        background_color: "#F4F5F9",
        theme_color: "#F4F5F9",
        categories: ["news", "productivity"],
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  server: {
    proxy: { "/api": { target: backend, changeOrigin: false } },
  },
  build: { target: "es2020", sourcemap: false },
  // vitest esegue solo i test unitari; quelli nel browser (e2e/) li esegue Playwright.
  test: { include: ["tests/**/*.test.js"] },
});
