// Service worker di Galactic Feed.
// - Tiene in cache l'interfaccia, così l'app si apre subito, si installa e parte anche offline.
// - Conserva gli articoli aperti o salvati e le loro immagini: tutti i salvati più gli ultimi
//   300 letti restano leggibili senza rete (le regole sono in lib/offline-core.js).
// - Tiene l'ultima risposta di account, fonti, contatori ed elenchi, per aprire l'app offline.
// Le azioni fatte senza rete (letto, salvato) le gestisce l'app con una coda in IndexedDB:
// iPhone e iPad non hanno la sincronizzazione in background dei service worker.

import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { CacheFirst, NetworkFirst } from "workbox-strategies";
import { ExpirationPlugin } from "workbox-expiration";
import { CacheableResponsePlugin } from "workbox-cacheable-response";
import { CACHE, PREFETCH_HEADER, articleKey, imageUrls, meta, prune } from "./lib/offline-core.js";

self.skipWaiting();
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Tutti gli indirizzi dell'app (/, /fonti, /invito/…) aprono la stessa pagina; l'API no.
registerRoute(new NavigationRoute(createHandlerBoundToURL("/index.html"), { denylist: [/^\/api\//] }));

const ORIGIN = self.location.origin;
const sameOrigin = (url) => url.origin === ORIGIN;
const onlyOk = new CacheableResponsePlugin({ statuses: [200] });

// ---------- Articoli ----------

const ARTICLE = /^\/api\/articles\/(\d+)$/;
const NETWORK_TIMEOUT = 8000;

async function cachedArticle(id) {
  const cache = await caches.open(CACHE.articles);
  return cache.match(articleKey(id, ORIGIN));
}

async function keepImages(urls) {
  const keep = await caches.open(CACHE.images);
  const recent = await caches.open(CACHE.imagesRecent);
  for (const url of urls) {
    if (await keep.match(url)) continue;
    try {
      let res = await recent.match(url);
      if (!res) {
        res = await fetch(url, { credentials: "same-origin" });
        if (!res.ok) continue;
      }
      await keep.put(url, res);
    } catch {
      /* senza rete o spazio: l'articolo resta leggibile, senza quell'immagine */
    }
  }
}

async function storeArticle(id, response, prefetch) {
  const { article } = await response.clone().json();
  const cache = await caches.open(CACHE.articles);
  await cache.put(articleKey(id, ORIGIN), response);
  const before = await meta.get(id);
  const images = imageUrls(article, ORIGIN);
  // Una copia preparata in anticipo (per i salvati) non conta come lettura.
  const readAt = prefetch ? before?.readAt || 0 : Date.now();
  await meta.put({ id, saved: Boolean(article.saved), readAt, images });
  return images;
}

async function articleHandler({ request, url, event }) {
  const id = Number(url.pathname.match(ARTICLE)[1]);
  const network = fetch(request).then(async (res) => {
    if (res.ok) {
      try {
        // La copia va in cache prima di rispondere: così il lettore la trova subito.
        const images = await storeArticle(id, res.clone(), request.headers.has(PREFETCH_HEADER));
        event.waitUntil(keepImages(images).then(() => prune()).catch(() => {}));
      } catch {
        /* spazio esaurito o risposta inattesa: si legge lo stesso, solo non offline */
      }
    }
    return res;
  });
  network.catch(() => {}); // l'errore si gestisce sotto; qui si evita l'avviso «non gestito»
  // Rete lenta: dopo qualche secondo si usa la copia offline, se c'è.
  const timeout = new Promise((resolve) => setTimeout(resolve, NETWORK_TIMEOUT));
  try {
    const first = await Promise.race([network, timeout.then(() => cachedArticle(id))]);
    if (first) return first;
    return await network;
  } catch (err) {
    const cached = await cachedArticle(id);
    if (cached) return cached;
    throw err;
  }
}

registerRoute(({ url, request }) => sameOrigin(url) && request.method === "GET" && ARTICLE.test(url.pathname), articleHandler);

// ---------- Immagini ----------

const recentImages = new CacheFirst({
  cacheName: CACHE.imagesRecent,
  plugins: [onlyOk, new ExpirationPlugin({ maxEntries: 400, maxAgeSeconds: 14 * 24 * 3600, purgeOnQuotaError: true })],
});

// Icone delle fonti (k=icon): poche e usate ovunque, restano 60 giorni anche senza rete.
const icons = new CacheFirst({
  cacheName: CACHE.icons,
  plugins: [onlyOk, new ExpirationPlugin({ maxEntries: 500, maxAgeSeconds: 60 * 24 * 3600, purgeOnQuotaError: true })],
});

registerRoute(
  ({ url, request }) => sameOrigin(url) && request.method === "GET" && url.pathname === "/api/img" && url.searchParams.get("k") === "icon",
  icons,
);

registerRoute(
  ({ url, request }) => sameOrigin(url) && request.method === "GET" && url.pathname === "/api/img",
  async (options) => {
    const kept = await caches.open(CACHE.images).then((c) => c.match(options.request));
    return kept || recentImages.handle(options);
  },
);

// ---------- Account, fonti, contatori ed elenchi ----------
// Prima la rete; senza rete (o se non risponde in pochi secondi) l'ultima risposta avuta.

const STATE = /^\/api\/(auth\/state|me|sources|folders|tags|interests|interests\/preview|articles\/counts)$/;

registerRoute(
  ({ url, request }) => sameOrigin(url) && request.method === "GET" && STATE.test(url.pathname),
  new NetworkFirst({
    cacheName: CACHE.api,
    networkTimeoutSeconds: 5,
    plugins: [onlyOk, new ExpirationPlugin({ maxEntries: 40 })],
  }),
);

registerRoute(
  ({ url, request }) => sameOrigin(url) && request.method === "GET" && url.pathname === "/api/articles",
  new NetworkFirst({
    cacheName: CACHE.lists,
    networkTimeoutSeconds: 5,
    plugins: [onlyOk, new ExpirationPlugin({ maxEntries: 40 })],
  }),
);

// ---------- Notifiche push ----------
// Il server manda { title, body, url, tag, badge }: la notifica e il numero sull'icona.

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data?.text() };
  }
  const shown = self.registration.showNotification(data.title || "Galactic Feed", {
    body: data.body || "",
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    tag: data.tag,
    data: { url: data.url || "/" },
  });
  // Il numero sull'icona: con l'app aperta lo aggiorna la pagina (che ricarica i contatori),
  // con l'app chiusa lo mette il service worker.
  const tell = self.clients.matchAll({ type: "window" }).then((list) => {
    list.forEach((c) => c.postMessage({ type: "gf-push", data }));
    if (!list.length && typeof data.badge === "number" && "setAppBadge" in self.navigator) {
      return (data.badge > 0 ? self.navigator.setAppBadge(data.badge) : self.navigator.clearAppBadge()).catch(() => {});
    }
  });
  event.waitUntil(Promise.allSettled([tell, shown]));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of windows) {
        if (new URL(client.url).origin === self.location.origin && "focus" in client) {
          await client.focus();
          return client.navigate ? client.navigate(url) : undefined;
        }
      }
      return self.clients.openWindow(url);
    })(),
  );
});
