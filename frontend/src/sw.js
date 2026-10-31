// Service worker di Galactic Feed.
// Tappa (d): tiene in cache l'interfaccia, così l'app si apre subito e si può installare.
// La lettura offline di articoli e salvati arriva nella tappa (e).

import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

self.skipWaiting();
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Tutti gli indirizzi dell'app (/, /fonti, /invito/…) aprono la stessa pagina; l'API no.
registerRoute(new NavigationRoute(createHandlerBoundToURL("/index.html"), { denylist: [/^\/api\//] }));
