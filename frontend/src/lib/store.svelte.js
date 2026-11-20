// Stato dell'app e azioni. I componenti leggono da qui e chiamano queste funzioni.

import { api, qs, setUnauthorizedHandler } from "./api.js";
import { disablePush, setBadge } from "./push.js";
import { clearAll, enqueue, flushQueue, hasPending, overlay, prepareForUser, refreshCopy, syncSaved } from "./offline.js";
import { accentVars, applyCustomAccent } from "./color.js";

// Le Impostazioni e l'Amministrazione sono pagine come le altre sezioni (non finestre sopra l'app).
const TABS = {
  "/": "oggi", "/fonti": "fonti", "/interessi": "interessi", "/salvati": "salvati",
  "/cerca": "cerca", "/profilo": "profilo",
  "/impostazioni": "impostazioni", "/amministrazione": "amministrazione",
};
const PATHS = Object.fromEntries(Object.entries(TABS).map(([path, tab]) => [tab, path]));
export const TEXT_SIZES = [1, 1.12, 0.92];

// ---------- Sessione ----------

export const session = $state({
  phase: "loading", // loading · setup · login · invite · reset · ready
  user: null,
  version: "",
  token: null, // token dell'invito o del reset, preso dall'indirizzo
  invite: null, // { kind, invited_by, username }
  inviteError: "",
  // Accesso con il provider OIDC (#22): { enabled, label, password_login }.
  oidc: { enabled: false, label: "", password_login: true },
  oidcError: "", // errore tornato dal provider (?oidc_error=…)
});

// ---------- Dati ----------

export const data = $state({
  sources: [],
  folders: [],
  tags: [], // tag delle fonti (#17)
  colors: [],
  intervals: [],
  counts: { tutti: 0, perte: 0, nonletti: 0, video: 0, salvati: 0, folders: {}, no_folder: 0, tags: {}, countries: {}, hidden: 0 },
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
  edition: null, // id dell'uscita dell'Edizione aperta (#64): si legge come un articolo
  readerFromHistory: false,
  sheet: null, // add · source · folder · tags · edition-config
  sheetArg: null,
  pageArg: null, // sottopagina da aprire nelle Impostazioni o nell'Amministrazione (per esempio «ai»)
  pageTick: 0, // cresce a ogni apertura di una pagina: si torna alla sua prima schermata
  toast: "",
  toastOn: false,
  refreshing: false,
  newsTick: 0, // cresce a ogni tocco su «Notiziario» nella Dock: Oggi scorre fino alla sezione
  atNews: false, // in Oggi il Notiziario è arrivato in vista (la Dock lo accende)
  settingsQuery: "", // ricerca nelle Impostazioni (#67)
  settingsFocus: false, // dal Profilo «Cerca nelle impostazioni»: il campo prende il cursore (una volta)
  online: typeof navigator === "undefined" ? true : navigator.onLine,
  homeTick: 0, // cresce a ogni tocco sul logo: Oggi torna in cima
});

// ---------- Notiziario ----------

// Il filtro del Notiziario (#68): da dove si parte (per te o tutte), solo non letti, chiavi
// incluse ed escluse («t:3» tag, «g:5» gruppo di parole, «f:2» cartella, «s:12» fonte, «c:IT»
// nazione, «v» video). I preset sono filtri con un nome; tre sono pronti.
export const BUILTIN_PRESETS = [
  { id: "perte", name: "Per te", icon: "spark", builtin: true, filter: { scope: "perte", unread: false, inc: [], exc: [] } },
  { id: "tutte", name: "Tutte", builtin: true, filter: { scope: "tutte", unread: false, inc: [], exc: [] } },
  { id: "nonletti", name: "Non letti", icon: "eye", builtin: true, filter: { scope: "tutte", unread: true, inc: [], exc: [] } },
];

export const stream = $state({
  filter: { scope: "perte", unread: false, inc: [], exc: [] },
  tally: null, // { total, unread } del filtro in uso (#66)
  presetTally: {}, // id del preset → { total, unread }
  showMuted: false,
  showPartial: false, // mostra anche gli articoli senza testo completo nascosti dalla preferenza
  items: [],
  cursor: null,
  loading: false,
  error: "",
  hidden: 0,
  hiddenPartial: 0,
  serverTime: null,
  done: false,
});

export const saved = $state({ items: [], cursor: null, loading: false, error: "", done: false });

// Ricerca (sezione Cerca): negli articoli e nelle fonti.
export const search = $state({ q: "", items: [], cursor: null, loading: false, error: "", done: false, tally: null });

// Edizioni in Oggi (#64): l'ultima uscita di ogni Edizione accesa.
export const today = $state({ editions: [], loaded: false });

// Statistiche nel Profilo (#78). Periodo (#83): settimana, mese, anno o sempre.
export const stats = $state({ period: "settimana", data: null, loading: false, error: "" });

// ---------- Edizione ----------

// configs: le Edizioni dell'utente (per il selettore in Oggi); config: quella mostrata (null = l'ultima uscita).
export const edition = $state({ data: null, schedule: null, configs: [], config: null, loading: false, loaded: false, error: "" });
// Le Edizioni con regole e pianificazione, per le Impostazioni (#18, #19).
export const editionConfigs = $state({ list: [], timezone: "", loaded: false });

export function editionOn() {
  return Boolean(session.user?.prefs?.edition);
}

// Tutti gli articoli caricati, per aggiornare lo stato (letto/salvato) ovunque compaiano.
function allLists() {
  const ed = edition.data;
  const fromEdition = ed ? [...(ed.hero ? [ed.hero] : []), ...ed.sections.flatMap((s) => s.items)] : [];
  return [stream.items, saved.items, search.items, fromEdition];
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
  const ed = Number(params.get("e"));
  return { path, tab: TABS[path] || "oggi", article: Number.isFinite(id) && id > 0 ? id : null, edition: Number.isFinite(ed) && ed > 0 ? ed : null };
}

function writeLocation(push) {
  const query = [ui.edition ? `e=${ui.edition}` : "", ui.reader ? `a=${ui.reader}` : ""].filter(Boolean).join("&");
  const url = PATHS[ui.tab] + (query ? `?${query}` : "");
  if (url === location.pathname + location.search) return;
  history[push ? "pushState" : "replaceState"]({ gf: true }, "", url);
}

export function switchTab(tab) {
  ui.tab = tab;
  ui.sheet = null;
  if (!readerBeside()) {
    ui.reader = null;
    ui.edition = null;
  }
  writeLocation(true);
}

/** Apre le Impostazioni o l'Amministrazione, facoltativamente su una sottopagina. */
export function openPage(tab, arg = null) {
  ui.pageArg = arg;
  ui.pageTick += 1;
  if (ui.tab === tab) {
    ui.sheet = null;
    return;
  }
  switchTab(tab);
}

/** Il logo «galactic feed»: torna a Oggi, chiude lettore e schede, scorre in cima. */
export function goHome() {
  const tabChanged = ui.tab !== "oggi";
  ui.sheet = null;
  ui.sheetArg = null;
  ui.reader = null;
  ui.edition = null;
  ui.tab = "oggi";
  writeLocation(tabChanged);
  ui.homeTick += 1;
}

export function isWide() {
  return typeof window !== "undefined" && window.innerWidth >= 1100;
}

/** Sul computer l'articolo sta nella colonna accanto all'elenco (e resta aperto cambiando sezione)? (#9) */
export function readerBeside() {
  return isWide() && (session.user?.prefs?.reader_layout || "colonne") === "colonne";
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
    if (loc.edition !== ui.edition) {
      ui.edition = loc.edition;
      if (loc.edition) loadEditionIssue(loc.edition);
    }
    ui.sheet = null;
  });
  window.addEventListener("online", () => {
    ui.online = true;
    if (session.phase === "ready") backOnline();
  });
  window.addEventListener("offline", () => (ui.online = false));
  // Una notifica push arrivata mentre l'app è aperta: contatori e Edizione si aggiornano.
  navigator.serviceWorker?.addEventListener("message", (event) => {
    if (event.data?.type !== "gf-push" || session.phase !== "ready") return;
    loadCounts();
    loadTally();
    if (event.data.data?.tag === "edizione") loadToday();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && session.phase === "ready") {
      sendQueued();
      refreshQuietly();
    }
  });
  // Se il telefono dice di essere online ma la rete non c'era, la coda riparte da sola.
  setInterval(() => {
    if (session.phase === "ready" && ui.online && hasPending()) sendQueued();
  }, 60000);

  // Ritorno dal provider OIDC: l'esito è nell'indirizzo, che poi si ripulisce.
  const params = new URLSearchParams(location.search);
  const oidcLinked = params.get("oidc_linked") === "1";
  if (params.has("oidc_error") || oidcLinked) {
    session.oidcError = params.get("oidc_error") || "";
    history.replaceState({ gf: true }, "", location.pathname);
  }

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
  ui.edition = loc.edition;
  await checkSession();
  if (session.phase === "ready" && session.oidcError) toast(session.oidcError);
  else if (session.phase === "ready" && oidcLinked) toast("Account del provider collegato: ora puoi entrare anche con quello");
}

export async function checkSession() {
  try {
    const st = await api("/auth/state", { quiet401: true });
    session.version = st.version;
    if (st.oidc) session.oidc = st.oidc;
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
  stream.filter = startFilter(user.prefs);
  if (goHome) {
    ui.tab = "oggi";
    ui.reader = null;
    ui.edition = null;
    history.replaceState({ gf: true }, "", "/");
  }
  startData(user);
}

async function startData(user) {
  // Prima la coda delle azioni fatte offline, così gli elenchi arrivano già aggiornati.
  await prepareForUser(user.id);
  if (ui.online) await flushQueue();
  await loadAll();
  if (ui.edition) loadEditionIssue(ui.edition);
  syncSaved();
}

export async function logout() {
  // Le azioni fatte offline partono prima di uscire, se c'è la rete.
  if (ui.online) await flushQueue();
  // Dopo l'uscita questo dispositivo non riceve più notifiche dell'account, né il numero sull'icona.
  await disablePush().catch(() => {});
  setBadge(0);
  let redirect = null;
  try {
    redirect = (await api("/auth/logout", { method: "POST" })).redirect;
  } catch {
    /* si esce comunque */
  }
  await clearAll();
  session.user = null;
  session.phase = "login";
  data.loaded = false;
  stream.items = [];
  saved.items = [];
  search.items = [];
  today.editions = [];
  stats.data = null;
  ui.sheet = null;
  ui.reader = null;
  ui.edition = null;
  history.replaceState({ gf: true }, "", "/");
  // Uscita anche dal provider, se l'amministratore l'ha scelta.
  if (redirect) location.assign(redirect);
}

// ---------- Preferenze ----------

export function applyPrefs(prefs) {
  if (!prefs) return;
  applyTheme(prefs.theme, prefs.dark_style, prefs.light_style);
  applyLook({ accent: prefs.accent, font: prefs.font });
  const custom = prefs.accent === "custom" ? accentVars(prefs.accent_custom) : null;
  applyCustomAccent(custom);
  remember("gf-accent-vars", JSON.stringify(custom || {}));
}

// Colore della barra del browser (meta theme-color): segue lo sfondo del tema e della variante in uso.
export const BAR_COLORS = {
  light: { neutro: "#F4F5F9", carta: "#F8F5EE", solarized: "#FDF6E3" },
  dark: { notte: "#0C0F1C", grigio: "#18181B", nero: "#000000", solarized: "#002B36" },
};

/** Tema (auto, light, dark) e varianti: scuro notte, grigio o nero; chiaro neutro o carta. */
export function applyTheme(theme, dark = "notte", light = "neutro") {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.dataset.theme = theme;
  else delete root.dataset.theme;
  dark = dark in BAR_COLORS.dark ? dark : "notte";
  light = light in BAR_COLORS.light ? light : "neutro";
  if (dark === "notte") delete root.dataset.dark;
  else root.dataset.dark = dark;
  if (light === "neutro") delete root.dataset.light;
  else root.dataset.light = light;
  const bars = { light: BAR_COLORS.light[light], dark: BAR_COLORS.dark[dark] };
  for (const meta of document.querySelectorAll('meta[name="theme-color"]')) {
    const own = meta.media.includes("dark") ? bars.dark : bars.light;
    meta.content = theme === "light" || theme === "dark" ? bars[theme] : own;
  }
  remember("gf-theme", theme || "auto");
  remember("gf-dark", dark);
  remember("gf-light", light);
}

// Aspetto (data-* su <html>, letti dal CSS in base.css). Il valore predefinito toglie l'attributo.
const LOOK = {
  accent: ["accent", "gf-accent", "galassia"],
  font: ["font", "gf-font", "galactic"],
};

export function applyLook(values) {
  const root = document.documentElement;
  for (const [key, value] of Object.entries(values)) {
    if (!(key in LOOK) || value === undefined) continue;
    const [attr, storageKey, fallback] = LOOK[key];
    if (!value || value === fallback) delete root.dataset[attr];
    else root.dataset[attr] = value;
    remember(storageKey, value || fallback);
  }
}

// Colore del sistema (#46): CSS.supports dice solo se il browser conosce AccentColor, non se dà
// il colore vero. Chrome, Edge e Android lo conoscono ma danno sempre il loro blu (#0075FF).
// Le stesse condizioni di base.css: senza colori relativi resta il colore predefinito.
export const SYSTEM_ACCENT_TEST = "oklch(from AccentColor min(l, 0.45) min(c, 0.15) h)";
export const CHROMIUM_ACCENT = "rgb(0, 117, 255)";

/** "vero" se il browser dà un colore di sistema, "fisso" se dà sempre il blu di Chromium, "no" se non si può usare. */
export function systemAccentState() {
  if (typeof CSS === "undefined" || !CSS.supports?.("color", SYSTEM_ACCENT_TEST)) return "no";
  const probe = document.createElement("i");
  probe.style.color = "AccentColor";
  document.body.append(probe);
  const color = getComputedStyle(probe).color;
  probe.remove();
  return color === CHROMIUM_ACCENT ? "fisso" : "vero";
}

// Copia sul dispositivo, per applicare l'aspetto prima di disegnare la pagina (vedi index.html).
function remember(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* archivio non disponibile */
  }
}

/** Salva le preferenze. Restituisce false se il server le rifiuta (e le rimette come prima). */
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
    return false;
  }
  if ("edition" in changes || "edition_times" in changes) loadToday();
  return true;
}

// ---------- Caricamento ----------

export async function loadAll() {
  await Promise.all([loadSources(), loadInterests(), loadStream(true), loadCounts(), loadTally(), loadToday()]);
  data.loaded = true;
}

export async function loadSources() {
  try {
    // I tag non sono essenziali: se mancano (per esempio offline senza copia) le fonti arrivano lo stesso.
    const [s, f, t] = await Promise.all([api("/sources"), api("/folders"), api("/tags").catch(() => ({ tags: data.tags }))]);
    data.sources = s.sources;
    data.intervals = s.intervals;
    data.folders = f.folders;
    data.colors = f.colors;
    data.tags = t.tags;
  } catch (err) {
    if (err.status !== 401 && ui.online) toast(err.message);
  }
}

export async function loadInterests() {
  try {
    const [i, p] = await Promise.all([api("/interests"), api("/interests/preview")]);
    data.interests = i;
    data.preview = p;
  } catch (err) {
    if (err.status !== 401 && ui.online) toast(err.message);
  }
}

export async function loadCounts() {
  try {
    data.counts = await api("/articles/counts" + qs({ show_muted: stream.showMuted, show_partial: stream.showPartial }));
    setBadge(data.counts.nonletti);
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
          ...filterQuery(stream.filter),
          show_muted: stream.showMuted,
          show_partial: stream.showPartial,
          cursor: reset ? null : stream.cursor,
        }),
    );
    if (ticket !== streamRequest) return;
    overlay(r.items);
    stream.items = reset ? r.items : [...stream.items, ...r.items];
    stream.cursor = r.next_cursor;
    stream.done = !r.next_cursor;
    if (reset) {
      stream.hidden = r.hidden;
      stream.hiddenPartial = r.hidden_partial || 0;
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
  loadTally();
  if ("showMuted" in changes || "showPartial" in changes) loadCounts();
}

// ---------- Filtri e preset del Notiziario (#68, #69) ----------

const emptyFilter = () => ({ scope: "perte", unread: false, inc: [], exc: [] });
const sorted = (list) => [...(list || [])].sort();
const filterKey = (f) => JSON.stringify([f.scope, !!f.unread, sorted(f.inc), sorted(f.exc)]);

/** I parametri dell'API per un filtro. */
export function filterQuery(f) {
  return { view: f.scope === "perte" ? "perte" : "tutti", unread: f.unread || null, inc: f.inc.join(",") || null, exc: f.exc.join(",") || null };
}

/** I preset: i tre pronti e quelli dell'utente. */
export function allPresets() {
  return [...BUILTIN_PRESETS, ...(session.user?.prefs?.presets || [])];
}

/** Il preset che corrisponde al filtro in uso, se c'è. */
export function currentPreset(f = stream.filter) {
  const key = filterKey(f);
  return allPresets().find((p) => filterKey(p.filter) === key) || null;
}

/** Il filtro all'apertura: il preset scelto (predefinito «Per te») o l'ultimo usato. */
export function startFilter(prefs) {
  if (prefs?.start_preset === "last" && prefs.last_filter) return { ...emptyFilter(), ...prefs.last_filter };
  const p = [...BUILTIN_PRESETS, ...(prefs?.presets || [])].find((x) => x.id === prefs?.start_preset) || BUILTIN_PRESETS[0];
  return structuredClone($state.snapshot(p.filter));
}

let lastTimer;
/** Cambia il filtro del Notiziario. Il filtro, esclusioni comprese, resta salvato anche chiudendo l'app. */
export function changeFilter(f) {
  stream.filter = { ...emptyFilter(), ...f, inc: [...(f.inc || [])], exc: [...(f.exc || [])] };
  setFilter({});
  clearTimeout(lastTimer);
  lastTimer = setTimeout(() => {
    if (session.user) savePrefs({ last_filter: $state.snapshot(stream.filter) });
  }, 800);
}

/** Toglie dal filtro in uso una voce che non c'è più (per esempio un tag eliminato). */
export function dropFilterKey(key) {
  const f = $state.snapshot(stream.filter);
  if (f.inc.includes(key) || f.exc.includes(key)) changeFilter({ ...f, inc: f.inc.filter((k) => k !== key), exc: f.exc.filter((k) => k !== key) });
}

export function applyPreset(id) {
  const p = allPresets().find((x) => x.id === id);
  if (p) changeFilter(structuredClone($state.snapshot(p.filter)));
}

/** Stato di una chiave nel filtro in uso: «inc», «exc» o "". */
export function keyState(key, f = stream.filter) {
  return f.inc.includes(key) ? "inc" : f.exc.includes(key) ? "exc" : "";
}

/** Mette una chiave tra le incluse, le escluse o in nessuna delle due. */
export function setKey(key, state) {
  const f = $state.snapshot(stream.filter);
  f.inc = f.inc.filter((k) => k !== key);
  f.exc = f.exc.filter((k) => k !== key);
  if (state === "inc") f.inc.push(key);
  if (state === "exc") f.exc.push(key);
  changeFilter(f);
}

function presetId(name) {
  const base = name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 18) || "preset";
  const used = new Set(allPresets().map((p) => p.id).concat("last"));
  let id = base;
  for (let n = 2; used.has(id); n++) id = `${base}-${n}`;
  return id;
}

export async function savePreset(name) {
  name = name.trim();
  if (!name) return false;
  const presets = [...(session.user.prefs.presets || []), { id: presetId(name), name, filter: $state.snapshot(stream.filter) }];
  const ok = await savePrefs({ presets });
  if (ok) {
    toast(`Preset «${name}» salvato`);
    loadTally();
  }
  return ok;
}

export async function deletePreset(id) {
  const p = (session.user.prefs.presets || []).find((x) => x.id === id);
  if (!p || !(await ask("Il preset sparisce dalla riga del Notiziario. I filtri in uso non cambiano.", { title: `Eliminare «${p.name}»?` }))) return;
  if (await savePrefs({ presets: session.user.prefs.presets.filter((x) => x.id !== id) })) toast(`«${p.name}» eliminato`);
}

let tallyRequest = 0;
/** «X notizie · X da leggere» per il filtro in uso e il numero di ogni preset (#66). */
export async function loadTally() {
  const ticket = ++tallyRequest;
  const presets = allPresets();
  const asBody = (f) => ({ view: f.scope === "perte" ? "perte" : "tutti", unread: !!f.unread, inc: f.inc, exc: f.exc });
  try {
    const r = await api("/articles/tally", { method: "POST", body: { filters: [asBody(stream.filter), ...presets.map((p) => asBody(p.filter))] } });
    if (ticket !== tallyRequest) return;
    stream.tally = r.results[0];
    stream.presetTally = Object.fromEntries(presets.map((p, i) => [p.id, r.results[i + 1]]));
  } catch {
    /* i numeri non sono essenziali */
  }
}

// ---------- Ricerca ----------

let searchRequest = 0;
export async function loadSearch(reset = false) {
  if (!search.q.trim()) {
    search.items = [];
    search.tally = null;
    search.done = true;
    return;
  }
  if (!reset && (search.loading || search.done)) return;
  const ticket = ++searchRequest;
  search.loading = true;
  search.error = "";
  try {
    const [r, t] = await Promise.all([
      api("/articles" + qs({ view: "tutti", q: search.q.trim(), cursor: reset ? null : search.cursor })),
      reset ? api("/articles/tally", { method: "POST", body: { q: search.q.trim(), filters: [{ view: "tutti" }] } }) : null,
    ]);
    if (ticket !== searchRequest) return;
    overlay(r.items);
    search.items = reset ? r.items : [...search.items, ...r.items];
    search.cursor = r.next_cursor;
    search.done = !r.next_cursor;
    if (t) search.tally = t.results[0];
  } catch (err) {
    if (ticket === searchRequest) search.error = err.message;
  } finally {
    if (ticket === searchRequest) search.loading = false;
  }
}

// ---------- Profilo e statistiche (#76, #78) ----------

export async function loadStats(period = stats.period) {
  stats.period = period;
  stats.loading = true;
  stats.error = "";
  try {
    stats.data = await api("/me/stats" + qs({ period }));
  } catch (err) {
    stats.error = err.message;
  } finally {
    stats.loading = false;
  }
}

/** Nome e colore dell'avatar. */
export async function saveProfile(changes) {
  try {
    session.user = (await api("/me", { method: "PATCH", body: changes })).user;
    return true;
  } catch (err) {
    toast(err.message);
    return false;
  }
}

/** Foto del profilo (data: URL già ridotta), oppure null per tornare alle iniziali. */
export async function setAvatar(dataUrl) {
  try {
    const r = dataUrl ? await api("/me/avatar", { method: "PUT", body: { data: dataUrl } }) : await api("/me/avatar", { method: "DELETE" });
    session.user = r.user;
    return true;
  } catch (err) {
    toast(err.message);
    return false;
  }
}

export async function loadSaved(reset = false) {
  if (!reset && (saved.loading || saved.done)) return;
  saved.loading = true;
  saved.error = "";
  try {
    const r = await api("/articles" + qs({ view: "salvati", cursor: reset ? null : saved.cursor }));
    // Senza rete l'elenco può venire dalla cache: valgono le azioni ancora in coda.
    const items = overlay(r.items).filter((a) => a.saved);
    saved.items = reset ? items : [...saved.items, ...items];
    saved.cursor = r.next_cursor;
    saved.done = !r.next_cursor;
  } catch (err) {
    saved.error = err.message;
  } finally {
    saved.loading = false;
  }
}

/** Le Edizioni per Oggi: l'ultima uscita di ognuna, con quante notizie ha e quante da leggere. */
export async function loadToday() {
  try {
    today.editions = (await api("/editions/today")).editions;
  } catch {
    /* senza rete resta quello che c'era */
  } finally {
    today.loaded = true;
  }
}

/** Apre un'uscita dell'Edizione: su telefono sopra Oggi, sul computer nella colonna di destra. */
export function openEdition(id) {
  const push = !ui.edition && !ui.reader;
  ui.reader = null;
  ui.edition = id;
  writeLocation(push);
  loadEditionIssue(id);
}

export function closeEdition() {
  if (!ui.edition) return;
  ui.edition = null;
  ui.reader = null;
  writeLocation(false);
}

async function loadEditionIssue(id) {
  if (edition.data?.id !== id) edition.data = null;
  edition.loading = true;
  edition.error = "";
  try {
    const r = await api(`/editions/${id}`);
    if (ui.edition !== id) return;
    edition.data = overlayEdition(r.edition);
    edition.schedule = r.schedule;
  } catch (err) {
    edition.error = err.message;
  } finally {
    edition.loading = false;
    edition.loaded = true;
  }
}

export async function loadEdition() {
  edition.loading = true;
  edition.error = "";
  try {
    const r = await api("/editions/latest" + qs({ config: edition.config }));
    edition.data = r.edition ? overlayEdition(r.edition) : null;
    edition.schedule = r.schedule;
    edition.configs = r.configs || [];
  } catch (err) {
    edition.error = err.message;
  } finally {
    edition.loading = false;
    edition.loaded = true;
  }
}

function overlayEdition(ed) {
  overlay([...(ed.hero ? [ed.hero] : []), ...ed.sections.flatMap((s) => s.items)]);
  return ed;
}

export async function composeEdition() {
  edition.loading = true;
  try {
    const config_id = edition.config ?? edition.data?.config_id ?? null;
    const r = await api("/editions", { method: "POST", body: { config_id } });
    edition.data = overlayEdition(r.edition);
    edition.schedule = r.schedule;
    edition.configs = r.configs || [];
    edition.config = r.edition.config_id;
    loadToday();
  } catch (err) {
    toast(err.message);
  } finally {
    edition.loading = false;
    edition.loaded = true;
  }
}

export function showEdition(configId) {
  edition.config = configId;
  loadEdition();
}

export async function loadEditionConfigs() {
  try {
    const r = await api("/edition-configs");
    editionConfigs.list = r.configs;
    editionConfigs.timezone = r.timezone;
    editionConfigs.loaded = true;
  } catch (err) {
    toast(err.message);
  }
}

/** Elimina un'uscita (per esempio una composta per prova): si vede quella precedente della stessa Edizione. */
export async function deleteEditionIssue(ed) {
  const label = ed.name ? `«${ed.name}» n. ${ed.number}` : `l'Edizione n. ${ed.number}`;
  if (!(await ask("L'Edizione resta, con le sue regole e i suoi orari: si cancella solo questa uscita.", { title: `Eliminare ${label}?` }))) return;
  try {
    const r = await api(`/editions/${ed.id}`, { method: "DELETE" });
    edition.data = r.edition ? overlayEdition(r.edition) : null;
    edition.schedule = r.schedule;
    edition.configs = r.configs || [];
    if (ui.edition === ed.id) {
      ui.edition = r.edition ? r.edition.id : null;
      writeLocation(false);
    }
    loadToday();
    toast("Uscita eliminata");
  } catch (err) {
    toast(err.message);
  }
}

/** Apre la scheda di un'Edizione (regole, orari, elimina) partendo dal suo id. */
export async function editEditionConfig(id) {
  if (!editionConfigs.loaded) await loadEditionConfigs();
  const config = editionConfigs.list.find((c) => c.id === id);
  if (config) openSheet("edition-config", config);
}

/** Applica la risposta delle API delle Edizioni (elenco aggiornato) e ricarica quello che dipende da lì. */
export async function setEditionConfigs(r) {
  editionConfigs.list = r.configs;
  editionConfigs.timezone = r.timezone;
  // L'Edizione mostrata in Oggi non c'è più (eliminata): si torna all'ultima uscita di tutte.
  if (edition.config && !r.configs.some((c) => c.id === edition.config)) edition.config = null;
  const active = r.configs.some((c) => c.active);
  if (session.user && Boolean(session.user.prefs.edition) !== active) session.user.prefs = { ...session.user.prefs, edition: active };
  loadToday();
}

let lastQuiet = 0;
async function refreshQuietly() {
  if (Date.now() - lastQuiet < 60000) return;
  lastQuiet = Date.now();
  await Promise.all([loadCounts(), loadTally(), loadSources(), loadToday()]);
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
    await Promise.all([loadStream(true), loadCounts(), loadTally(), loadSources(), loadToday()]);
  } catch (err) {
    toast(err.message);
  } finally {
    ui.refreshing = false;
  }
  sendQueued();
}

// ---------- Lettore, letti e salvati ----------

export function openArticle(id) {
  const push = !ui.reader;
  ui.reader = id;
  writeLocation(push);
}

/** Indietro dal lettore: dall'articolo all'Edizione da cui lo si è aperto, poi a Oggi. */
export function closeReader() {
  if (ui.reader) {
    ui.reader = null;
    writeLocation(false);
  } else closeEdition();
}

/** Aggiorna i dati della fonte (per esempio l'icona) negli articoli già caricati. */
export function patchSourceInLists(sourceId, changes) {
  for (const list of allLists()) {
    for (const a of list) if (a.source?.id === sourceId) Object.assign(a.source, changes);
  }
}

function patchItems(id, changes) {
  for (const list of allLists()) {
    for (const a of list) if (a.id === id) Object.assign(a, changes);
  }
}

// Senza rete (o con altre azioni ancora in coda) l'azione va nella coda offline;
// con la rete parte subito. Restituisce «sent» o «queued»; gli errori del server passano.
async function sendAction(id, key, value) {
  if (!ui.online || hasPending()) {
    await enqueue(id, { [key]: value });
    if (ui.online) sendQueued();
    return "queued";
  }
  try {
    await api(`/articles/${id}/${key}`, { method: value ? "PUT" : "DELETE" });
    return "sent";
  } catch (err) {
    if (err.status !== 0) throw err;
    await enqueue(id, { [key]: value });
    return "queued";
  }
}

let readTimer;
export async function setRead(article, read) {
  if (article.read === read) return;
  patchItems(article.id, { read });
  data.counts.nonletti = Math.max(0, data.counts.nonletti + (read ? -1 : 1));
  clearTimeout(readTimer);
  readTimer = setTimeout(() => Promise.all([loadTally(), loadToday()]), 600);
  try {
    await sendAction(article.id, "read", read);
  } catch (err) {
    patchItems(article.id, { read: !read });
    data.counts.nonletti = Math.max(0, data.counts.nonletti + (read ? 1 : -1));
    toast(err.message);
  }
}

/** Salva o toglie dai salvati. Finisce quando anche la copia offline è aggiornata; false se non riesce. */
export async function setSaved(article, value) {
  patchItems(article.id, { saved: value });
  data.counts.salvati = Math.max(0, data.counts.salvati + (value ? 1 : -1));
  let how;
  try {
    how = await sendAction(article.id, "saved", value);
  } catch (err) {
    patchItems(article.id, { saved: !value });
    data.counts.salvati = Math.max(0, data.counts.salvati + (value ? -1 : 1));
    toast(err.message);
    return false;
  }
  if (how === "queued") toast(value ? "Salvato: lo invio al server appena torna la rete" : "Tolto dai salvati: lo invio al server appena torna la rete");
  else toast(value ? "Salvato: lo trovi anche offline" : "Rimosso dai salvati");
  if (!value) saved.items = saved.items.filter((a) => a.id !== article.id);
  else if (!saved.items.some((a) => a.id === article.id)) saved.items = [{ ...article, saved: true }, ...saved.items];
  // La copia sul dispositivo prende lo stato nuovo (e, se salvato, anche le immagini).
  if (how === "sent") await refreshCopy(article.id);
  return true;
}

// ---------- Offline ----------

async function sendQueued() {
  const ids = await flushQueue();
  if (ids?.length) await Promise.all([loadCounts(), loadSaved(true)]);
}

async function backOnline() {
  await sendQueued();
  await Promise.all([loadCounts(), stream.error ? loadStream(true) : null]);
  syncSaved({ force: true });
}

export async function markAllRead() {
  try {
    const f = stream.filter;
    const r = await api("/articles/mark-read", {
      method: "POST",
      body: { view: f.scope === "perte" ? "perte" : "tutti", inc: f.inc, exc: f.exc, before: stream.serverTime },
    });
    toast(r.marked === 1 ? "1 articolo segnato come letto" : `${r.marked} articoli segnati come letti`);
    for (const a of stream.items) a.read = true;
    await Promise.all([loadCounts(), loadTally(), loadSources(), loadToday()]);
    if (f.unread) loadStream(true);
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
  if (!readerBeside()) ui.reader = null;
  writeLocation(true);
  // Un filtro con solo questa fonte: «Salva come preset» o «Azzera» compaiono sotto la riga.
  changeFilter({ scope: "tutte", unread: false, inc: [`s:${source.id}`], exc: [] });
}

// ---------- Conferme ----------
// Al posto di window.confirm(), che alcuni browser e alcune app installate bloccano o non
// mostrano (e allora «Elimina» sembrava non fare niente): una finestra dell'app.

export const confirmation = $state({ open: false, title: "", message: "", action: "Conferma", danger: true, info: false });
let confirmResolve = null;

/** Chiede conferma. Restituisce una promessa: true se la persona conferma. */
export function ask(message, { title = "Sei sicuro?", action = "Elimina", danger = true } = {}) {
  confirmResolve?.(false);
  Object.assign(confirmation, { open: true, title, message, action, danger, info: false });
  return new Promise((resolve) => (confirmResolve = resolve));
}

/** Spiega qualcosa (il cerchio con la «i»): stessa finestra, un solo pulsante. message può essere un elenco di paragrafi. */
export function inform(message, { title = "Come funziona", action = "Ho capito" } = {}) {
  confirmResolve?.(false);
  Object.assign(confirmation, { open: true, title, message, action, danger: false, info: true });
  return new Promise((resolve) => (confirmResolve = resolve));
}

export function answer(yes) {
  confirmation.open = false;
  const resolve = confirmResolve;
  confirmResolve = null;
  resolve?.(yes);
}
