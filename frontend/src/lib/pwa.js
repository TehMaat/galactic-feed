// Registrazione del service worker: rende l'app installabile e la fa aprire anche offline.

export function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || import.meta.env.DEV) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      /* senza service worker l'app funziona lo stesso, solo non offline */
    });
  });
}
