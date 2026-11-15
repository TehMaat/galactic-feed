// Service worker e aggiornamenti dell'app (#41).
//
// Il service worker rende l'app installabile e la fa aprire anche offline, ma tiene in cache
// l'interfaccia: senza un controllo esplicito l'app installata su iPhone può restare alla
// versione vecchia per giorni, perché iOS la riporta in primo piano dalla memoria senza
// ricaricarla (e quindi senza ricontrollare sw.js). Per questo:
// - si cerca una versione nuova quando l'app torna in primo piano e ogni ora mentre è aperta;
// - la versione nuova aspetta («waiting») finché non la si attiva: così la pagina aperta non
//   perde i suoi file a metà (il service worker nuovo cancella quelli vecchi dalla cache);
// - si attiva con «Aggiorna», oppure da sola se arriva appena riaperta l'app e non stai
//   leggendo né scrivendo: la pagina si ricarica e mostra la versione nuova.
// Icona e nome dell'app sulla Home, invece, iOS li fissa all'installazione: per quelli bisogna
// togliere e riaggiungere l'app (vedi README).

import { confirmation, ui } from "./store.svelte.js";

/** Versione dell'interfaccia in uso (quella compilata in questo file JS). */
export const APP_VERSION = typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "";

export const pwa = $state({
  ready: false, // c'è una versione nuova pronta: basta attivarla
  checking: false, // controllo chiesto a mano in corso
  checked: 0, // ora dell'ultimo controllo finito
  dismissed: false, // avviso chiuso con «Più tardi» (resta in Impostazioni → Informazioni)
});

const HOUR = 3600e3;
const MIN_GAP = 60e3; // non più di un controllo al minuto tornando in primo piano
const AUTO_WINDOW = 15e3; // dopo il ritorno in primo piano, per quanto si può ricaricare da soli

let registration = null;
let lastCheck = 0;
let visibleAt = Date.now();
let wantReload = false;
let manual = false; // l'ultimo controllo l'ha chiesto chi usa l'app: si mostra l'avviso, senza ricaricare da soli

/** Si può ricaricare la pagina senza disturbare? Niente articolo, schede o campi aperti. */
export function idle() {
  if (ui.reader || ui.sheet || confirmation.open) return false;
  const el = document.activeElement;
  return !(el && (el.matches?.("input, textarea, select") || el.isContentEditable));
}

function markReady() {
  pwa.ready = true;
  if (!manual && document.visibilityState === "visible" && Date.now() - visibleAt < AUTO_WINDOW && idle()) applyUpdate();
}

function watch(worker) {
  if (!worker) return;
  const check = () => {
    // «installed» con un controller attivo: è un aggiornamento, non la prima installazione.
    if (worker.state === "installed" && navigator.serviceWorker.controller) markReady();
  };
  worker.addEventListener("statechange", check);
  check();
}

/** Cerca una versione nuova. `force`: anche se il controllo precedente è recente. */
export async function checkForUpdate(force = false) {
  if (!registration || (!force && Date.now() - lastCheck < MIN_GAP)) return;
  lastCheck = Date.now();
  manual = force;
  if (force) pwa.checking = true;
  try {
    await registration.update();
  } catch {
    /* offline o server irraggiungibile: si riprova più tardi */
  } finally {
    pwa.checking = false;
    pwa.checked = Date.now();
  }
}

/** Attiva la versione nuova e ricarica la pagina. */
export function applyUpdate() {
  const waiting = registration?.waiting;
  wantReload = true;
  if (waiting) waiting.postMessage({ type: "SKIP_WAITING" });
  else location.reload(); // già attiva (service worker di una versione precedente): basta ricaricare
}

export function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || import.meta.env.DEV) return;
  const hadController = Boolean(navigator.serviceWorker.controller);

  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (wantReload) {
      wantReload = false;
      location.reload();
    } else if (hadController) {
      // Un service worker di una versione precedente si è attivato da solo: la pagina ha ancora
      // il JS vecchio, quindi si propone di ricaricare.
      pwa.ready = true;
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    visibleAt = Date.now();
    if (pwa.ready && idle()) applyUpdate();
    else checkForUpdate();
  });
  setInterval(() => checkForUpdate(), HOUR);

  window.addEventListener("load", async () => {
    try {
      registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    } catch {
      return; // senza service worker l'app funziona lo stesso, solo non offline
    }
    lastCheck = Date.now(); // register() ha appena controllato
    if (registration.waiting && navigator.serviceWorker.controller) markReady();
    watch(registration.installing);
    registration.addEventListener("updatefound", () => watch(registration.installing));
  });
}
