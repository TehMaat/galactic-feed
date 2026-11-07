// Stato dell'app e azioni. I componenti leggono da qui e chiamano queste funzioni.

import { api, qs, setUnauthorizedHandler } from "./api.js";
import { disablePush, setBadge } from "./push.js";
import { clearAll, enqueue, flushQueue, hasPending, overlay, prepareForUser, refreshCopy, syncSaved } from "./offline.js";

// Le Impostazioni e l'Amministrazione sono pagine come le altre sezioni (non finestre sopra l'app).
const TABS = {
  "/": "oggi", "/fonti": "fonti", "/interessi": "interessi", "/salvati": "salvati",
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
  readerFromHistory: false,
  sheet: null, // add · source · folder · tags · edition-config
  sheetArg: null,
  pageArg: null, // sottopagina da aprire nelle Impostazioni o nell'Amministrazione (per esempio «ai»)
  pageTick: 0, // cresce a ogni apertura di una pagina: si torna alla sua prima schermata
  toast: "",
  toastOn: false,
  refreshing: false,
  oggiMode: "edizione", // edizione · flusso (con l'Edizione accesa)
  online: typeof navigator === "undefined" ? true : navigator.onLine,
  homeTick: 0, // cresce a ogni tocco sul logo: Oggi torna in cima
});

// ---------- Flusso ----------

export const stream = $state({
  view: "tutti", // tutti · perte · nonletti · video
  folder: null, // id cartella, «none» o null
  source: null, // id fonte o null
  sourceTitle: "",
  tag: null, // id del tag o null
  country: null, // nazione delle fonti («IT») o null
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
  return [stream.items, saved.items, fromEdition];
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
  ui.tab = "oggi";
  writeLocation(tabChanged);
  ui.homeTick += 1;
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
  window.addEventListener("online", () => {
    ui.online = true;
    if (session.phase === "ready") backOnline();
  });
  window.addEventListener("offline", () => (ui.online = false));
  // Una notifica push arrivata mentre l'app è aperta: contatori e Edizione si aggiornano.
  navigator.serviceWorker?.addEventListener("message", (event) => {
    if (event.data?.type !== "gf-push" || session.phase !== "ready") return;
    loadCounts();
    if (event.data.data?.tag === "edizione") loadEdition();
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
  if (goHome) {
    ui.tab = "oggi";
    ui.reader = null;
    history.replaceState({ gf: true }, "", "/");
  }
  startData(user);
}

async function startData(user) {
  // Prima la coda delle azioni fatte offline, così gli elenchi arrivano già aggiornati.
  await prepareForUser(user.id);
  if (ui.online) await flushQueue();
  await loadAll();
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
  ui.sheet = null;
  ui.reader = null;
  history.replaceState({ gf: true }, "", "/");
  // Uscita anche dal provider, se l'amministratore l'ha scelta.
  if (redirect) location.assign(redirect);
}

// ---------- Preferenze ----------

export function applyPrefs(prefs) {
  if (!prefs) return;
  applyTheme(prefs.theme, prefs.dark_style, prefs.light_style);
  applyLook({ accent: prefs.accent, font: prefs.font, font_read: prefs.font_read });
}

// Colore della barra del browser (meta theme-color): segue lo sfondo del tema e della variante in uso.
export const BAR_COLORS = {
  light: { neutro: "#F4F5F9", carta: "#F8F5EE" },
  dark: { notte: "#0C0F1C", grigio: "#18181B", nero: "#000000" },
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
  font_read: ["read", "gf-read", "serif"],
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
  if ("edition" in changes || "edition_times" in changes) {
    if (changes.edition) ui.oggiMode = "edizione";
    if (editionOn()) loadEdition();
  }
  return true;
}

// ---------- Caricamento ----------

export async function loadAll() {
  await Promise.all([loadSources(), loadInterests(), loadStream(true), loadCounts(), editionOn() ? loadEdition() : null]);
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
    data.counts = await api("/articles/counts" + qs({ q: stream.q, show_muted: stream.showMuted }));
    if (!stream.q) setBadge(data.counts.nonletti);
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
          tag: stream.tag,
          country: stream.country,
          q: stream.q,
          show_muted: stream.showMuted,
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
  if (active) loadEdition();
}

let lastQuiet = 0;
async function refreshQuietly() {
  if (Date.now() - lastQuiet < 60000) return;
  lastQuiet = Date.now();
  await Promise.all([loadCounts(), loadSources(), editionOn() ? loadEdition() : null]);
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
  sendQueued();
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

export async function setRead(article, read) {
  if (article.read === read) return;
  patchItems(article.id, { read });
  data.counts.nonletti = Math.max(0, data.counts.nonletti + (read ? -1 : 1));
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
    const r = await api("/articles/mark-read", {
      method: "POST",
      body: { view: stream.view, folder: stream.folder ?? null, source: stream.source, tag: stream.tag, country: stream.country, q: stream.q, before: stream.serverTime },
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
  setFilter({ view: "tutti", folder: null, tag: null, country: null, source: source.id, sourceTitle: source.title });
}

// ---------- Conferme ----------
// Al posto di window.confirm(), che alcuni browser e alcune app installate bloccano o non
// mostrano (e allora «Elimina» sembrava non fare niente): una finestra dell'app.

export const confirmation = $state({ open: false, title: "", message: "", action: "Conferma", danger: true });
let confirmResolve = null;

/** Chiede conferma. Restituisce una promessa: true se la persona conferma. */
export function ask(message, { title = "Sei sicuro?", action = "Elimina", danger = true } = {}) {
  confirmResolve?.(false);
  Object.assign(confirmation, { open: true, title, message, action, danger });
  return new Promise((resolve) => (confirmResolve = resolve));
}

export function answer(yes) {
  confirmation.open = false;
  const resolve = confirmResolve;
  confirmResolve = null;
  resolve?.(yes);
}
