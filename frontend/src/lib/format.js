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
