import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { VitePWA } from "vite-plugin-pwa";

// In sviluppo (npm run dev) le chiamate /api vanno al backend su localhost:8080.
const backend = process.env.BACKEND_URL || "http://localhost:8080";

export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.js",
      registerType: "prompt",
      injectRegister: false,
      manifestFilename: "manifest.webmanifest",
      includeAssets: ["icons/*.png", "icons/*.svg"],
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,svg}", "**/*-latin-[0-9]*.woff2", "icons/apple-touch-icon.png"],
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
