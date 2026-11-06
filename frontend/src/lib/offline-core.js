// Lettura offline: parti comuni al service worker (src/sw.js) e all'app (lib/offline.js).
//
// Cosa resta sul dispositivo:
// - la copia di ogni articolo aperto o salvato, nella cache «gf-articles»;
// - le sue immagini, nella cache «gf-img-offline»;
// - un indice in IndexedDB (store «articles») con id, salvato sì/no, quando è stato letto e
//   le immagini: serve a tenere tutti i salvati più gli ultimi 300 letti e a buttare il resto;
// - la coda delle azioni fatte senza rete (store «queue»), inviata al server quando torna.

export const CACHE = {
  articles: "gf-articles", // copie degli articoli (GET /api/articles/{id})
  images: "gf-img-offline", // immagini degli articoli disponibili offline
  imagesRecent: "gf-img", // immagini viste di recente (elenchi, copertine), a scadenza
  icons: "gf-icons", // icone delle fonti, tenute a lungo per vederle anche offline
  api: "gf-api", // stato dell'account, fonti, cartelle, interessi, contatori
  lists: "gf-lists", // elenchi di articoli (Flusso, Salvati)
};

export const KEEP_READ = 300; // articoli letti (non salvati) da tenere offline
export const MAX_IMAGES_PER_ARTICLE = 12;
export const PREFETCH_HEADER = "X-GF-Prefetch"; // richiesta fatta per preparare l'offline, non lettura

const DB_NAME = "galactic-feed";
const DB_VERSION = 1;

// ---------- Regole (funzioni pure, provate in tests/offline.test.js) ----------

/** Gli articoli da togliere: si tengono tutti i salvati e i `keep` letti più di recente. */
export function selectEvictions(metas, keep = KEEP_READ) {
  const read = metas.filter((m) => !m.saved).sort((a, b) => (b.readAt || 0) - (a.readAt || 0));
  return read.slice(keep).map((m) => m.id);
}

/** Indirizzi (assoluti) delle immagini di un articolo che passano dal proxy del server. */
export function imageUrls(article, origin, max = MAX_IMAGES_PER_ARTICLE) {
  const found = [];
  if (article.image) found.push(article.image);
  const re = /<img\b[^>]*?\ssrc="([^"]+)"/gi;
  let m;
  while ((m = re.exec(article.content_html || ""))) found.push(m[1].replace(/&amp;/g, "&"));
  const out = [];
  for (const raw of found) {
    let url;
    try {
      url = new URL(raw, origin);
    } catch {
      continue;
    }
    if (url.origin !== origin || url.pathname !== "/api/img") continue;
    if (!out.includes(url.href)) out.push(url.href);
    if (out.length >= max) break;
  }
  return out;
}

/** Unisce una nuova azione a quella già in coda per lo stesso articolo: vale l'ultima. */
export function mergeAction(existing, id, changes) {
  const next = { id, v: (existing?.v || 0) + 1 };
  for (const key of ["read", "saved"]) {
    const value = key in changes ? changes[key] : existing?.[key];
    if (value !== undefined) next[key] = value;
  }
  return next;
}

/** Applica le azioni in coda agli articoli di un elenco (che possono venire dalla cache). */
export function applyPending(items, pending) {
  if (!pending.size) return items;
  for (const item of items) {
    const p = pending.get(item.id);
    if (!p) continue;
    if (p.read !== undefined) item.read = p.read;
    if (p.saved !== undefined) item.saved = p.saved;
  }
  return items;
}

export function articleKey(id, origin) {
  return `${origin}/api/articles/${id}`;
}

// ---------- IndexedDB ----------

let dbPromise = null;

function openDb() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("articles")) db.createObjectStore("articles", { keyPath: "id" });
      if (!db.objectStoreNames.contains("queue")) db.createObjectStore("queue", { keyPath: "id" });
    };
    req.onsuccess = () => {
      const db = req.result;
      // Se un'altra scheda aggiorna il database, questa chiude e riapre alla prossima richiesta.
      db.onversionchange = () => {
        db.close();
        dbPromise = null;
      };
      resolve(db);
    };
    req.onerror = () => {
      dbPromise = null;
      reject(req.error);
    };
  });
  return dbPromise;
}

function done(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore(name, mode, fn) {
  const db = await openDb();
  const tx = db.transaction(name, mode);
  const result = await fn(tx.objectStore(name));
  await new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
  return result;
}

export const meta = {
  get: (id) => withStore("articles", "readonly", (s) => done(s.get(id))),
  all: () => withStore("articles", "readonly", (s) => done(s.getAll())),
  put: (record) => withStore("articles", "readwrite", (s) => done(s.put(record))),
  delete: (ids) => withStore("articles", "readwrite", (s) => Promise.all(ids.map((id) => done(s.delete(id))))),
  /** Cambia solo «salvato», se l'articolo è già sul dispositivo. */
  setSaved: (id, saved) =>
    withStore("articles", "readwrite", async (s) => {
      const record = await done(s.get(id));
      if (record && record.saved !== saved) await done(s.put({ ...record, saved }));
      return Boolean(record);
    }),
};

export const queue = {
  all: () => withStore("queue", "readonly", (s) => done(s.getAll())),
  add: (id, changes) =>
    withStore("queue", "readwrite", async (s) => {
      const next = mergeAction(await done(s.get(id)), id, changes);
      await done(s.put(next));
      return next;
    }),
  /** Toglie le azioni inviate, ma non quelle cambiate nel frattempo (versione diversa). */
  remove: (sent) =>
    withStore("queue", "readwrite", async (s) => {
      for (const a of sent) {
        const current = await done(s.get(a.id));
        if (current && current.v === a.v) await done(s.delete(a.id));
      }
    }),
};

export async function clearDb() {
  for (const name of ["articles", "queue"]) await withStore(name, "readwrite", (s) => done(s.clear()));
}

// ---------- Cache ----------

/** Toglie gli articoli in più e le immagini che nessun articolo usa più. */
export async function prune(keep = KEEP_READ) {
  const metas = await meta.all();
  const drop = new Set(selectEvictions(metas, keep));
  const articles = await caches.open(CACHE.articles);
  const origin = self.location.origin;
  if (drop.size) {
    await Promise.all([...drop].map((id) => articles.delete(articleKey(id, origin))));
    await meta.delete([...drop]);
  }
  const used = new Set(metas.filter((m) => !drop.has(m.id)).flatMap((m) => m.images || []));
  const images = await caches.open(CACHE.images);
  for (const req of await images.keys()) if (!used.has(req.url)) await images.delete(req);
}

/** Cancella tutto quello che l'app ha messo da parte per l'offline (uscita, cambio account). */
export async function clearOfflineData() {
  const names = await caches.keys();
  await Promise.all(names.filter((n) => n.startsWith("gf-")).map((n) => caches.delete(n)));
  await clearDb();
}
