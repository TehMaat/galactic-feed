// Stato dell'app e azioni. I componenti leggono da qui e chiamano queste funzioni.

import { api, qs, setUnauthorizedHandler } from "./api.js";

const TABS = { "/": "oggi", "/fonti": "fonti", "/interessi": "interessi", "/salvati": "salvati" };
const PATHS = { oggi: "/", fonti: "/fonti", interessi: "/interessi", salvati: "/salvati" };
export const TEXT_SIZES = [1, 1.12, 0.92];

// ---------- Sessione ----------

export const session = $state({
  phase: "loading", // loading · setup · login · invite · reset · ready
  user: null,
  version: "",
  token: null, // token dell'invito o del reset, preso dall'indirizzo
  invite: null, // { kind, invited_by, username }
  inviteError: "",
});

// ---------- Dati ----------

export const data = $state({
  sources: [],
  folders: [],
  colors: [],
  intervals: [],
  counts: { tutti: 0, perte: 0, nonletti: 0, video: 0, salvati: 0, folders: {}, no_folder: 0, hidden: 0 },
  interests: { keywords: [], muted: [], rules: { dedupe: true } },
  preview: null,
  loaded: false,
});

export function foldersById() {
  return Object.fromEntries(data.folders.map((f) => [f.id, f]));
}

// ---------- Interfaccia ----------

export const ui = $state({
  tab: "oggi",
  reader: null, // id dell'articolo aperto
  readerFromHistory: false,
  sheet: null, // add · settings · source · folder
  sheetArg: null,
  toast: "",
  toastOn: false,
  refreshing: false,
  online: typeof navigator === "undefined" ? true : navigator.onLine,
});

// ---------- Flusso ----------

export const stream = $state({
  view: "tutti", // tutti · perte · nonletti · video
  folder: null, // id cartella, «none» o null
  source: null, // id fonte o null
  sourceTitle: "",
  q: "",
  showMuted: false,
  items: [],
  cursor: null,
  loading: false,
  error: "",
  hidden: 0,
  serverTime: null,
  done: false,
});

export const saved = $state({ items: [], cursor: null, loading: false, error: "", done: false });

// Tutti gli articoli caricati, per aggiornare lo stato (letto/salvato) ovunque compaiano.
function allLists() {
  return [stream.items, saved.items];
}

// ---------- Toast ----------

let toastTimer;
export function toast(message) {
  ui.toast = message;
  ui.toastOn = true;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (ui.toastOn = false), 2800);
}

// ---------- Indirizzi ----------

function readLocation() {
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const params = new URLSearchParams(location.search);
  const id = Number(params.get("a"));
  return { path, tab: TABS[path] || "oggi", article: Number.isFinite(id) && id > 0 ? id : null };
}

function writeLocation(push) {
  const url = PATHS[ui.tab] + (ui.reader ? `?a=${ui.reader}` : "");
  if (url === location.pathname + location.search) return;
  history[push ? "pushState" : "replaceState"]({ gf: true }, "", url);
}

export function switchTab(tab) {
  ui.tab = tab;
  ui.sheet = null;
  if (!isWide()) ui.reader = null;
  writeLocation(true);
}

export function isWide() {
  return typeof window !== "undefined" && window.innerWidth >= 1100;
}

// ---------- Avvio ----------

export async function boot() {
  setUnauthorizedHandler(() => {
    if (session.phase === "ready") {
      session.user = null;
      session.phase = "login";
      toast("La sessione è scaduta: entra di nuovo.");
    }
  });
  window.addEventListener("popstate", () => {
    const loc = readLocation();
    ui.tab = loc.tab;
    ui.reader = loc.article;
    ui.sheet = null;
  });
  window.addEventListener("online", () => (ui.online = true));
  window.addEventListener("offline", () => (ui.online = false));
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && session.phase === "ready") refreshQuietly();
  });

  const loc = readLocation();
  const link = loc.path.match(/^\/(invito|reimposta)\/([\w-]+)$/);
  if (link) {
    session.token = link[2];
    session.phase = link[1] === "invito" ? "invite" : "reset";
    try {
      session.invite = await api(`/invites/${link[2]}`, { quiet401: true });
    } catch (err) {
      session.inviteError = err.message;
    }
    return;
  }
  ui.tab = loc.tab;
  ui.reader = loc.article;
  await checkSession();
}

export async function checkSession() {
  try {
    const st = await api("/auth/state", { quiet401: true });
    session.version = st.version;
    if (st.setup_needed) session.phase = "setup";
    else if (st.user) enter(st.user);
    else session.phase = "login";
  } catch (err) {
    session.phase = "login";
    session.inviteError = err.message;
  }
}

export function enter(user, { goHome = false } = {}) {
  session.user = user;
  session.phase = "ready";
  applyPrefs(user.prefs);
  if (goHome) {
    ui.tab = "oggi";
    ui.reader = null;
    history.replaceState({ gf: true }, "", "/");
  }
  loadAll();
}

export async function logout() {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {
    /* si esce comunque */
  }
  session.user = null;
  session.phase = "login";
  data.loaded = false;
  stream.items = [];
  saved.items = [];
  ui.sheet = null;
  ui.reader = null;
  history.replaceState({ gf: true }, "", "/");
}

// ---------- Preferenze ----------

export function applyPrefs(prefs) {
  if (!prefs) return;
  applyTheme(prefs.theme);
}

export function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.dataset.theme = theme;
  else delete root.dataset.theme;
  try {
    localStorage.setItem("gf-theme", theme || "auto");
  } catch {
    /* archivio non disponibile */
  }
}

export async function savePrefs(changes) {
  const before = { ...session.user.prefs };
  session.user.prefs = { ...session.user.prefs, ...changes };
  applyPrefs(session.user.prefs);
  try {
    const r = await api("/me", { method: "PATCH", body: { prefs: changes } });
    session.user = r.user;
  } catch (err) {
    session.user.prefs = before;
    applyPrefs(before);
    toast(err.message);
  }
}

// ---------- Caricamento ----------

export async function loadAll() {
  await Promise.all([loadSources(), loadInterests(), loadStream(true), loadCounts()]);
  data.loaded = true;
}

export async function loadSources() {
  try {
    const [s, f] = await Promise.all([api("/sources"), api("/folders")]);
    data.sources = s.sources;
    data.intervals = s.intervals;
    data.folders = f.folders;
    data.colors = f.colors;
  } catch (err) {
    if (err.status !== 401) toast(err.message);
  }
}

export async function loadInterests() {
  try {
    const [i, p] = await Promise.all([api("/interests"), api("/interests/preview")]);
    data.interests = i;
    data.preview = p;
  } catch (err) {
    if (err.status !== 401) toast(err.message);
  }
}

export async function loadCounts() {
  try {
    data.counts = await api("/articles/counts" + qs({ q: stream.q, show_muted: stream.showMuted }));
  } catch {
    /* i contatori non sono essenziali */
  }
}

let streamRequest = 0;
export async function loadStream(reset = false) {
  if (!reset && (stream.loading || stream.done)) return;
  const ticket = ++streamRequest;
  stream.loading = true;
  stream.error = "";
  try {
    const r = await api(
      "/articles" +
        qs({
          view: stream.view,
          folder: stream.folder,
          source: stream.source,
          q: stream.q,
          show_muted: stream.showMuted,
          cursor: reset ? null : stream.cursor,
        }),
    );
    if (ticket !== streamRequest) return;
    stream.items = reset ? r.items : [...stream.items, ...r.items];
    stream.cursor = r.next_cursor;
    stream.done = !r.next_cursor;
    if (reset) {
      stream.hidden = r.hidden;
      stream.serverTime = r.server_time;
    }
  } catch (err) {
    if (ticket === streamRequest) stream.error = err.message;
  } finally {
    if (ticket === streamRequest) stream.loading = false;
  }
}

export function setFilter(changes) {
  Object.assign(stream, changes);
  stream.cursor = null;
  stream.done = false;
  loadStream(true);
  if ("q" in changes || "showMuted" in changes) loadCounts();
}

export async function loadSaved(reset = false) {
  if (!reset && (saved.loading || saved.done)) return;
  saved.loading = true;
  saved.error = "";
  try {
    const r = await api("/articles" + qs({ view: "salvati", cursor: reset ? null : saved.cursor }));
    saved.items = reset ? r.items : [...saved.items, ...r.items];
    saved.cursor = r.next_cursor;
    saved.done = !r.next_cursor;
  } catch (err) {
    saved.error = err.message;
  } finally {
    saved.loading = false;
  }
}

let lastQuiet = 0;
async function refreshQuietly() {
  if (Date.now() - lastQuiet < 60000) return;
  lastQuiet = Date.now();
  await Promise.all([loadCounts(), loadSources()]);
}

export async function refreshAll() {
  if (ui.refreshing) return;
  ui.refreshing = true;
  try {
    const r = await api("/sources/refresh", { method: "POST" });
    const parts = [];
    parts.push(r.checked === 1 ? "1 fonte controllata" : `${r.checked} fonti controllate`);
    parts.push(r.new_articles === 0 ? "nessun articolo nuovo" : r.new_articles === 1 ? "1 articolo nuovo" : `${r.new_articles} articoli nuovi`);
    if (r.errors) parts.push(r.errors === 1 ? "1 con errori" : `${r.errors} con errori`);
    if (r.checked === 0 && r.skipped) toast("Fonti già controllate meno di un minuto fa");
    else toast(parts.join(" · "));
    await Promise.all([loadStream(true), loadCounts(), loadSources()]);
  } catch (err) {
    toast(err.message);
  } finally {
    ui.refreshing = false;
  }
}

// ---------- Lettore, letti e salvati ----------

export function openArticle(id) {
  const push = !ui.reader;
  ui.reader = id;
  writeLocation(push);
}

export function closeReader() {
  if (!ui.reader) return;
  ui.reader = null;
  writeLocation(false);
}

function patchItems(id, changes) {
  for (const list of allLists()) {
    for (const a of list) if (a.id === id) Object.assign(a, changes);
  }
}

export async function setRead(article, read) {
  if (article.read === read) return;
  patchItems(article.id, { read });
  data.counts.nonletti = Math.max(0, data.counts.nonletti + (read ? -1 : 1));
  try {
    await api(`/articles/${article.id}/read`, { method: read ? "PUT" : "DELETE" });
  } catch (err) {
    patchItems(article.id, { read: !read });
    if (err.status !== 0) toast(err.message);
  }
}

export async function setSaved(article, value) {
  patchItems(article.id, { saved: value });
  data.counts.salvati = Math.max(0, data.counts.salvati + (value ? 1 : -1));
  try {
    await api(`/articles/${article.id}/saved`, { method: value ? "PUT" : "DELETE" });
    toast(value ? "Salvato: lo trovi anche offline" : "Rimosso dai salvati");
    if (!value) saved.items = saved.items.filter((a) => a.id !== article.id);
    else if (!saved.items.some((a) => a.id === article.id)) saved.items = [{ ...article, saved: true }, ...saved.items];
  } catch (err) {
    patchItems(article.id, { saved: !value });
    data.counts.salvati += value ? -1 : 1;
    toast(err.message);
  }
}

export async function markAllRead() {
  try {
    const r = await api("/articles/mark-read", {
      method: "POST",
      body: { view: stream.view, folder: stream.folder ?? null, source: stream.source, q: stream.q, before: stream.serverTime },
    });
    toast(r.marked === 1 ? "1 articolo segnato come letto" : `${r.marked} articoli segnati come letti`);
    for (const a of stream.items) a.read = true;
    await Promise.all([loadCounts(), loadSources()]);
    if (stream.view === "nonletti") loadStream(true);
  } catch (err) {
    toast(err.message);
  }
}

// ---------- Schede ----------

export function openSheet(name, arg = null) {
  ui.sheet = name;
  ui.sheetArg = arg;
}

export function closeSheet() {
  ui.sheet = null;
  ui.sheetArg = null;
}

export function showSource(source) {
  closeSheet();
  ui.tab = "oggi";
  if (!isWide()) ui.reader = null;
  writeLocation(true);
  setFilter({ view: "tutti", folder: null, source: source.id, sourceTitle: source.title });
}
