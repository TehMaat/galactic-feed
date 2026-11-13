// Genera le PNG delle icone da icons-src/*.svg (#30): «npm run icons».
// Usa il Chromium di Playwright (dipendenza di sviluppo); se non è installato:
// «npx playwright install chromium», oppure CHROMIUM_PATH=/percorso/del/browser.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// sorgente → [file in public/icons, lato in pixel]
const ICONS = [
  ["apple-touch-icon.svg", "apple-touch-icon.png", 180],
  ["apple-touch-icon-dark.svg", "apple-touch-icon-dark.png", 180],
];

const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
try {
  for (const [source, target, size] of ICONS) {
    const svg = readFileSync(join(root, "icons-src", source), "utf8");
    const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
    await page.setContent(`<style>html,body{margin:0}svg{display:block;width:${size}px;height:${size}px}</style>${svg}`);
    // PNG opaca: iOS rende nere le parti trasparenti.
    await page.screenshot({ path: join(root, "public", "icons", target), omitBackground: false });
    await page.close();
    console.log(`public/icons/${target} (${size}×${size})`);
  }
} finally {
  await browser.close();
}
