// Colore personalizzato (#74): dal colore scelto con il selettore si ricavano le varianti per il
// tema chiaro e per lo scuro, con contrasto AA (4,5:1) come la tavolozza di base.css. Si tiene la
// tinta e si cambia solo la luminosità finché il testo si legge su sfondi, schede e fondo tenue.

const LIGHT_BG = ["#FFFFFF", "#F4F5F9", "#FDF6E3", "#F8F5EE"];
const DARK_BG = ["#0C0F1C", "#151A2D", "#1C2238", "#18181B", "#232327", "#000000", "#002B36", "#073642"];

const hex2rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const rgb2hex = (c) => "#" + c.map((x) => Math.round(Math.min(255, Math.max(0, x))).toString(16).padStart(2, "0")).join("").toUpperCase();
const lin = (c) => ((c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);

export function contrast(a, b) {
  const [x, y] = [lum(hex2rgb(a)), lum(hex2rgb(b))].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
}

function rgb2hsl([r, g, b]) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, s, l];
}

function hsl2rgb([h, s, l]) {
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [f(0), f(8), f(4)].map((x) => x * 255);
}

const mix = (fg, bg, alpha) => rgb2hex(hex2rgb(fg).map((c, i) => c * alpha + hex2rgb(bg)[i] * (1 - alpha)));
const readable = (c, backgrounds, alpha) => backgrounds.every((bg) => contrast(c, bg) >= 4.5 && contrast(c, mix(c, bg, alpha)) >= 4.5);

/** Le variabili --acc-* per un colore «#RRGGBB»: chiaro (più scuro se serve) e scuro (più chiaro). */
export function accentVars(hex) {
  if (!/^#[0-9A-Fa-f]{6}$/.test(hex || "")) return null;
  const [h, s0, l0] = rgb2hsl(hex2rgb(hex));
  const s = Math.min(s0, 0.85);
  let light = rgb2hex(hsl2rgb([h, s, l0]));
  for (let l = l0; !readable(light, LIGHT_BG, 0.12) && l > 0; l -= 0.01) light = rgb2hex(hsl2rgb([h, s, l]));
  let dark = rgb2hex(hsl2rgb([h, s, l0]));
  for (let l = l0; !readable(dark, DARK_BG, 0.14) && l < 1; l += 0.01) dark = rgb2hex(hsl2rgb([h, s, l]));
  const soft = (c, a) => `rgba(${hex2rgb(c).join(", ")}, ${a})`;
  return {
    "--acc-l": light,
    "--acc-on-l": contrast("#FFFFFF", light) >= 4.5 ? "#FFFFFF" : "#10121C",
    "--acc-soft-l": soft(light, 0.12),
    "--acc-d": dark,
    "--acc-on-d": contrast("#10121C", dark) >= 4.5 ? "#10121C" : "#FFFFFF",
    "--acc-soft-d": soft(dark, 0.14),
  };
}

/** Applica (o toglie, con null) il colore personalizzato su <html>. */
export function applyCustomAccent(vars) {
  const style = document.documentElement.style;
  for (const key of ["--acc-l", "--acc-on-l", "--acc-soft-l", "--acc-d", "--acc-on-d", "--acc-soft-d"]) {
    if (vars) style.setProperty(key, vars[key]);
    else style.removeProperty(key);
  }
}
