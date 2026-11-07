// Colori principali (issue #14): i valori in base.css coincidono con quelli mostrati nelle
// Impostazioni e hanno contrasto AA (4,5:1) in chiaro e in scuro.
import fs from "node:fs";
import { describe, expect, it } from "vitest";
import { ACCENTS } from "../src/lib/format.js";

const css = fs.readFileSync(new URL("../src/styles/base.css", import.meta.url), "utf8");

function block(selector) {
  const start = css.indexOf(selector + " {");
  return css.slice(start, css.indexOf("}", start));
}

function vars(text) {
  return Object.fromEntries([...text.matchAll(/--(acc-[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
}

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const lin = (c) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
function contrast(a, b) {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}
const over = (fg, bg, alpha) => fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha)));

const LIGHT = { surface: "#FFFFFF", app: "#F4F5F9" };
const DARK = { surface: "#151A2D", app: "#0C0F1C", surface2: "#1C2238" };

describe("colori principali", () => {
  for (const accent of ACCENTS) {
    const v = vars(accent.key === "galassia" ? block(":root") : block(`:root[data-accent="${accent.key}"]`));

    it(`${accent.name}: stessi valori in base.css`, () => {
      expect(v["acc-l"]).toBe(accent.light);
      expect(v["acc-d"]).toBe(accent.dark);
    });

    it(`${accent.name}: contrasto AA in chiaro e in scuro`, () => {
      const l = rgb(v["acc-l"]);
      for (const bg of Object.values(LIGHT)) {
        expect(contrast(l, rgb(bg))).toBeGreaterThanOrEqual(4.5);
        expect(contrast(l, over(l, rgb(bg), 0.12))).toBeGreaterThanOrEqual(4.5);
      }
      expect(contrast(rgb(v["acc-on-l"]), l)).toBeGreaterThanOrEqual(4.5);
      const d = rgb(v["acc-d"]);
      for (const bg of Object.values(DARK)) {
        expect(contrast(d, rgb(bg))).toBeGreaterThanOrEqual(4.5);
        expect(contrast(d, over(d, rgb(bg), 0.14))).toBeGreaterThanOrEqual(4.5);
      }
      expect(contrast(rgb(v["acc-on-d"]), d)).toBeGreaterThanOrEqual(4.5);
    });
  }
});

// Varianti dei temi: scuro grigio e nero, chiaro carta. Ogni colore principale resta AA sugli
// sfondi della variante, e il testo secondario (--ink-3) si legge sulle schede.
function palette(selector) {
  const text = block(selector);
  return Object.fromEntries([...text.matchAll(/--([\w-]+):\s*(#[0-9A-Fa-f]{6});/g)].map((m) => [m[1], m[2]]));
}

describe("varianti dei temi", () => {
  const variants = [
    ["scuro grigio", ':root[data-theme="dark"][data-dark="grigio"]', "acc-d", 0.14],
    ["scuro nero", ':root[data-theme="dark"][data-dark="nero"]', "acc-d", 0.14],
    ["chiaro carta", ':root[data-theme="light"][data-light="carta"]', "acc-l", 0.12],
  ];
  for (const [name, selector, key, alpha] of variants) {
    const p = palette(selector);

    it(`${name}: stessi valori anche con il tema automatico`, () => {
      const auto = selector.replace(/:root\[data-theme="(dark|light)"\]/, (_, t) => `:root:not([data-theme="${t === "dark" ? "light" : "dark"}"])`);
      expect(palette(auto)).toEqual(p);
    });

    it(`${name}: contrasto AA per testo e colori principali`, () => {
      const backgrounds = [p["app-bg"], p.surface, p["surface-2"]].map(rgb);
      for (const bg of backgrounds) {
        expect(contrast(rgb(p.ink), bg)).toBeGreaterThanOrEqual(7);
        expect(contrast(rgb(p["ink-2"]), bg)).toBeGreaterThanOrEqual(4.5);
      }
      expect(contrast(rgb(p["ink-3"]), rgb(p.surface))).toBeGreaterThanOrEqual(4.5);
      // Come per i temi predefiniti: in chiaro sfondo e schede, in scuro anche --surface-2.
      const accentBackgrounds = key === "acc-d" ? backgrounds : backgrounds.slice(0, 2);
      for (const accent of ACCENTS) {
        const v = vars(accent.key === "galassia" ? block(":root") : block(`:root[data-accent="${accent.key}"]`));
        const c = rgb(v[key]);
        for (const bg of accentBackgrounds) {
          expect(contrast(c, bg), `${accent.name} su ${name}`).toBeGreaterThanOrEqual(4.5);
          expect(contrast(c, over(c, bg, alpha)), `${accent.name} su sfondo tenue, ${name}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    });
  }
});
