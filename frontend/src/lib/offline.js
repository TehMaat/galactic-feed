// Offline dal lato dell'app: coda delle azioni fatte senza rete, copie dei salvati,
// pulizia all'uscita. Le regole comuni con il service worker sono in offline-core.js.

import { api, qs } from "./api.js";
import { CACHE, PREFETCH_HEADER, applyPending, articleKey, clearOfflineData, meta, queue } from "./offline-core.js";

const supported = typeof indexedDB !== "undefined" && typeof caches !== "undefined";

// Copia in memoria della coda, per applicarla subito agli elenchi.
const pending = new Map();

export function hasPending() {
  return pending.size > 0;
}

export function overlay(items) {
  return applyPending(items, pending);
}

export async function loadPending() {
  if (!supported) return;
  try {
    pending.clear();
    for (const a of await queue.all()) pending.set(a.id, a);
  } catch {
    /* IndexedDB non disponibile (navigazione privata): niente coda */
  }
}

/** Mette in coda un'azione (letto, salvato) da inviare al ritorno della rete. */
export async function enqueue(id, changes) {
  const local = { ...pending.get(id), ...changes, id };
  pending.set(id, local);
  if (!supported) return;
  try {
    const stored = await queue.add(id, changes);
    pending.set(id, stored);
    if ("saved" in changes) await meta.setSaved(id, changes.saved);
  } catch {
    /* resta solo in memoria fino alla chiusura dell'app */
  }
}

let flushing = null;

/**
 * Invia la coda al server. Restituisce gli id degli articoli aggiornati, oppure null se
 * non c'era niente da inviare o la rete non c'è ancora.
 */
export function flushQueue() {
  if (!pending.size) return Promise.resolve(null);
  if (!flushing) flushing = doFlush().finally(() => (flushing = null));
  return flushing;
}

async function doFlush() {
  const sent = [...pending.values()];
  try {
    await api("/articles/sync", {
      method: "POST",
      body: { actions: sent.map(({ id, read, saved }) => ({ id, read, saved })) },
    });
  } catch (err) {
    // Senza rete o senza accesso si riprova più tardi; altri errori non si risolvono riprovando.
    if (err.status === 0 || err.status === 401) return null;
  }
  for (const a of sent) if (pending.get(a.id) === a) pending.delete(a.id);
  if (supported) {
    try {
      await queue.remove(sent.filter((a) => a.v));
    } catch {
      /* la coda si ripulisce al prossimo invio */
    }
  }
  // Le copie offline degli articoli salvati o tolti si aggiornano con lo stato nuovo.
  for (const a of sent) if (a.saved !== undefined) refreshCopy(a.id);
  return sent.map((a) => a.id);
}

function offlineReady() {
  return supported && typeof navigator !== "undefined" && Boolean(navigator.serviceWorker?.controller);
}

/** Scarica di nuovo la copia offline di un articolo (passa dal service worker). */
export async function refreshCopy(id) {
  if (!offlineReady()) return false;
  try {
    await api(`/articles/${id}`, { headers: { [PREFETCH_HEADER]: "1" } });
    return true;
  } catch {
    return false;
  }
}

/** L'articolo è già sul dispositivo e si può leggere senza rete? */
export async function isAvailableOffline(id) {
  if (!supported) return false;
  try {
    const cache = await caches.open(CACHE.articles);
    return Boolean(await cache.match(articleKey(id, location.origin)));
  } catch {
    return false;
  }
}

let lastSavedSync = 0;

/**
 * Tiene sul dispositivo una copia di tutti i salvati, anche quelli salvati da un altro
 * dispositivo e mai aperti qui.
 */
export async function syncSaved({ force = false } = {}) {
  if (!offlineReady() || !navigator.onLine) return;
  if (!force && Date.now() - lastSavedSync < 5 * 60e3) return;
  lastSavedSync = Date.now();
  try {
    const ids = new Set();
    let cursor = null;
    // Stesso indirizzo della schermata Salvati: così anche il suo elenco resta in cache.
    for (let page = 0; page < 40; page++) {
      const r = await api("/articles" + qs({ view: "salvati", cursor }));
      for (const a of r.items) ids.add(a.id);
      cursor = r.next_cursor;
      if (!cursor) break;
    }
    const known = new Map((await meta.all()).map((m) => [m.id, m]));
    for (const m of known.values()) if (m.saved && !ids.has(m.id) && !pending.has(m.id)) await meta.setSaved(m.id, false);
    for (const id of ids) {
      const m = known.get(id);
      if (m?.saved && (await isAvailableOffline(id))) continue;
      if (!(await refreshCopy(id))) break; // rete caduta: si riprova la prossima volta
    }
  } catch {
    lastSavedSync = 0;
  }
}

/** All'ingresso: se sul dispositivo ci sono dati di un altro account, si cancellano. */
export async function prepareForUser(userId) {
  let previous = null;
  try {
    previous = localStorage.getItem("gf-offline-user");
  } catch {
    /* archivio non disponibile */
  }
  if (previous && previous !== String(userId)) await clearAll();
  try {
    localStorage.setItem("gf-offline-user", String(userId));
  } catch {
    /* archivio non disponibile */
  }
  await loadPending();
}

/** All'uscita non resta niente dell'account sul dispositivo. */
export async function clearAll() {
  pending.clear();
  lastSavedSync = 0;
  try {
    localStorage.removeItem("gf-offline-user");
  } catch {
    /* archivio non disponibile */
  }
  if (!supported) return;
  try {
    await clearOfflineData();
  } catch {
    /* niente da cancellare */
  }
}
