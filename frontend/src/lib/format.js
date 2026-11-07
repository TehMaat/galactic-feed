// Formati in italiano: tempi relativi, iniziali delle fonti, frequenze, colori.

const MONTHS = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];

/** «25 min», «3 h», «ieri», «4 giorni», «12 ott». */
export function timeAgo(iso, now = Date.now()) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return "adesso";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h`;
  const d = Math.round(h / 24);
  if (d === 1) return "ieri";
  if (d < 7) return `${d} giorni`;
  const date = new Date(t);
  const sameYear = date.getFullYear() === new Date(now).getFullYear();
  return `${date.getDate()} ${MONTHS[date.getMonth()]}${sameYear ? "" : " " + date.getFullYear()}`;
}

/** Come timeAgo, ma da leggere in una frase: «25 min fa», «ieri», «il 12 ott». */
export function timeAgoLong(iso, now = Date.now()) {
  const t = timeAgo(iso, now);
  if (!t || t === "adesso" || t === "ieri") return t;
  if (/^\d+ (min|h|giorni)$/.test(t)) return t + " fa";
  return "il " + t;
}

/** Durata in giorni da un momento passato: «da 2 giorni», «da 3 ore». */
export function since(iso, now = Date.now()) {
  if (!iso) return "";
  const h = Math.round((now - new Date(iso).getTime()) / 3600000);
  if (h < 1) return "da poco";
  if (h < 24) return h === 1 ? "da un'ora" : `da ${h} ore`;
  const d = Math.round(h / 24);
  return d === 1 ? "da un giorno" : `da ${d} giorni`;
}

/** Due lettere per l'avatar della fonte: «Orbita» → «Or», «Bit & Byte» → «BB». */
export function initials(title) {
  const words = String(title || "").replace(/^(https?:\/\/)?(www\.)?/, "").split(/[\s\-–—_/.:]+/).filter((w) => /[\p{L}\p{N}]/u.test(w));
  if (!words.length) return "·";
  if (words.length === 1) {
    const w = words[0].replace(/[^\p{L}\p{N}]/gu, "");
    return w.charAt(0).toUpperCase() + w.charAt(1).toLowerCase();
  }
  return (words[0].replace(/[^\p{L}\p{N}]/gu, "").charAt(0) + words[1].replace(/[^\p{L}\p{N}]/gu, "").charAt(0)).toUpperCase();
}

export function intervalLabel(min) {
  if (min < 60) return `${min} min`;
  return `${min / 60} h`;
}

/** Frequenza di pubblicazione di un feed trovato: «circa 25 articoli al giorno», «3 a settimana». */
export function frequency(perWeek) {
  if (perWeek == null) return "";
  if (perWeek >= 10.5) return `circa ${Math.round(perWeek / 7)} articoli al giorno`;
  if (perWeek >= 1) return `${Math.round(perWeek)} a settimana`;
  return "meno di uno a settimana";
}

export function readingInfo(a) {
  if (a.video) return "Video";
  return a.reading_minutes ? `${a.reading_minutes} min di lettura` : "";
}

export const KIND_LABEL = { rss: "RSS", youtube: "YouTube" };

/** Colore CSS di una cartella (stessa palette del mockup). */
export function folderColor(color) {
  return `var(--c-${color || "grigio"})`;
}

/** Colore della fonte: rosso-arancio per YouTube, altrimenti quello della cartella. */
export function sourceColor(source, foldersById) {
  if (source?.kind === "youtube") return "var(--c-video)";
  const f = source?.folder_id != null ? foldersById[source.folder_id] : null;
  return folderColor(f?.color);
}

export function shortUrl(url) {
  try {
    const u = new URL(url);
    return (u.hostname.replace(/^www\./, "") + u.pathname + u.search).replace(/\/$/, "");
  } catch {
    return url;
  }
}

export function pathOf(url) {
  try {
    const u = new URL(url);
    return (u.pathname + u.search) || "/";
  } catch {
    return url;
  }
}

/** Colori principali tra cui scegliere (gli stessi valori di styles/base.css, verificati dai test). */
export const ACCENTS = [
  { key: "galassia", name: "Galassia", light: "#096E5F", dark: "#5FE0C7" },
  { key: "indaco", name: "Indaco", light: "#4A54D7", dark: "#A3AAFF" },
  { key: "blu", name: "Blu", light: "#1B63B7", dark: "#74B2FF" },
  { key: "viola", name: "Viola", light: "#8141C3", dark: "#C9A3FF" },
  { key: "rosa", name: "Rosa", light: "#B42F55", dark: "#FF94B4" },
  { key: "arancio", name: "Arancio", light: "#A5451A", dark: "#FF9F7A" },
  { key: "ambra", name: "Ambra", light: "#8A5600", dark: "#F2B35B" },
  { key: "verde", name: "Verde", light: "#277137", dark: "#86DC95" },
];

/** Varianti dei temi: [chiave, nome, sfondo, scheda, testo] per l'anteprima (valori di base.css). */
export const DARK_STYLES = [
  ["notte", "Notte", "#0C0F1C", "#151A2D", "#ECEAF3"],
  ["grigio", "Grigio", "#18181B", "#232327", "#EDEDF0"],
  ["nero", "Nero", "#000000", "#121214", "#EDEDF0"],
];
export const LIGHT_STYLES = [
  ["neutro", "Neutro", "#F4F5F9", "#FFFFFF", "#13162A"],
  ["carta", "Carta", "#F8F5EE", "#FBF8F2", "#26211A"],
];

/** Font dell'interfaccia e del testo degli articoli: [chiave, nome, font per l'anteprima]. */
export const FONTS = [
  ["galactic", "Galactic", "var(--font-brand)"],
  ["sistema", "Sistema", "var(--font-system)"],
  ["inter", "Inter", '"Inter Variable", var(--font-system)'],
  ["leggibile", "Alta leggibilità", '"Atkinson Hyperlegible", var(--font-system)'],
];
export const READ_FONTS = [
  ["serif", "Serif", '"Newsreader", Georgia, serif'],
  ["sans", "Come l'interfaccia", "var(--font-ui)"],
  ["sistema", "Sistema", "var(--font-system)"],
];
export const SIZES = [[0.92, "Piccolo"], [1, "Normale"], [1.12, "Grande"]];

/** Una durata in parole: (90, "giorni") → «90 giorni», (168, "ore") → «1 settimana», (60, "minuti") → «1 ora». */
export function durationLabel(n, unit) {
  if (unit === "minuti") return n < 60 ? `${n} min` : n === 60 ? "1 ora" : `${n / 60} ore`;
  if (unit === "ore") {
    if (n === 168) return "1 settimana";
    return n === 1 ? "1 ora" : `${n} ore`;
  }
  if (n === 7) return "1 settimana";
  if (n === 365) return "1 anno";
  if (n === 730) return "2 anni";
  return n === 1 ? "1 giorno" : `${n} giorni`;
}

/** Dimensione di un file: «512 KB», «3,4 MB». */
export function bytesLabel(n) {
  if (n == null) return "—";
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1).replace(".", ",")} MB`;
  return `${(n / 1024 ** 3).toFixed(2).replace(".", ",")} GB`;
}

/** Il testo della corrispondenza: «Motori · Ferrari» per un gruppo di parole, altrimenti la parola trovata. */
export function matchLabel(match) {
  if (!match) return "";
  return match.group && match.group !== match.keyword ? `${match.group} · ${match.keyword}` : match.keyword;
}

// ---------- Nazioni (#20) ----------

/** Le nazioni proposte nelle scelte (le altre si possono comunque avere dalle fonti). */
export const COUNTRIES = ["IT", "US", "GB", "FR", "DE", "ES", "CH", "AT", "BE", "NL", "PT", "IE", "SE", "NO", "DK", "FI", "PL", "GR",
  "UA", "RU", "TR", "IL", "CA", "MX", "BR", "AR", "AU", "NZ", "JP", "CN", "KR", "IN", "ZA", "SM", "VA"];

let regionNames;
/** «IT» → «Italia». */
export function countryName(code) {
  if (!code) return "";
  try {
    regionNames ??= new Intl.DisplayNames(["it"], { type: "region" });
    return regionNames.of(code) || code;
  } catch {
    return code;
  }
}

/** «IT» → la bandierina (emoji). */
export function flag(code) {
  if (!code || !/^[A-Z]{2}$/.test(code)) return "";
  return String.fromCodePoint(...[...code].map((c) => 127397 + c.charCodeAt(0)));
}

/** Data di una prossima uscita, nel fuso dell'Edizione: «oggi alle 07:30», «lunedì 9 novembre alle 07:30». */
export function nextRun(iso, timeZone, now = Date.now()) {
  if (!iso) return "";
  const opts = timeZone ? { timeZone } : {};
  const d = new Date(iso);
  const dayOf = (t) => new Date(t).toLocaleDateString("en-CA", opts);
  const time = d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", ...opts });
  if (dayOf(d) === dayOf(now)) return `oggi alle ${time}`;
  if (dayOf(d) === dayOf(now + 86400000)) return `domani alle ${time}`;
  return `${d.toLocaleDateString("it-IT", { weekday: "long", day: "numeric", month: "long", ...opts })} alle ${time}`;
}
