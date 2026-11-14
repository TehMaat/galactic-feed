// Notifiche push e numero sull'icona dell'app.
// Su iPhone e iPad le notifiche funzionano solo nell'app aggiunta alla schermata Home
// (iOS 16.4 o successivo); in Safari normale il browser non le offre.

import { api } from "./api.js";

export function pushSupported() {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function isIos() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

export function isStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone === true;
}

function keyBytes(base64url) {
  const pad = "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob((base64url + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function registration() {
  return navigator.serviceWorker.ready;
}

/** Questo dispositivo è iscritto? */
export async function currentSubscription() {
  if (!pushSupported()) return null;
  try {
    return await (await registration()).pushManager.getSubscription();
  } catch {
    return null;
  }
}

function sameKey(sub, publicKey) {
  const current = sub.options?.applicationServerKey;
  if (!current) return true; // il browser non la dice: si dà per buona
  const a = new Uint8Array(current);
  const b = keyBytes(publicKey);
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

/**
 * Iscrive il dispositivo (o riusa l'iscrizione che ha) e la comunica al server.
 * Un'iscrizione fatta con un'altra chiave del server (per esempio dopo aver ricreato il
 * volume dei dati) non riceverebbe più nulla: si rifà.
 */
async function subscribeAndRegister() {
  const { public_key } = await api("/push/key");
  const reg = await registration();
  let sub = await reg.pushManager.getSubscription();
  if (sub && !sameKey(sub, public_key)) {
    await sub.unsubscribe().catch(() => {});
    sub = null;
  }
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) });
  await api("/push/subscriptions", { method: "POST", body: sub.toJSON() });
  return sub;
}

const BLOCKED = "Le notifiche sono bloccate: permettile nelle impostazioni del browser o del sistema.";

/** Chiede il permesso e iscrive il dispositivo. Restituisce un messaggio d'errore o "". */
export async function enablePush() {
  if (!pushSupported()) {
    return isIos() && !isStandalone()
      ? "Su iPhone le notifiche arrivano solo nell'app aggiunta alla schermata Home: aprila da lì e riprova."
      : "Questo browser non supporta le notifiche.";
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return BLOCKED;
  try {
    await subscribeAndRegister();
    return "";
  } catch (err) {
    return err.message || "Iscrizione alle notifiche non riuscita.";
  }
}

/**
 * All'apertura delle Impostazioni: se il dispositivo è iscritto, controlla che l'iscrizione
 * sia ancora valida e che il server la conosca (il server dimentica i dispositivi dopo
 * qualche invio fallito). Restituisce { on, error }.
 */
export async function syncPush() {
  const sub = await currentSubscription();
  if (!sub) return { on: false, error: "" };
  if (Notification.permission !== "granted") return { on: false, error: BLOCKED };
  try {
    await subscribeAndRegister();
  } catch {
    /* senza rete: l'iscrizione resta quella che c'è */
  }
  return { on: true, error: "" };
}

/** Manda la notifica di prova a questo dispositivo. Restituisce un messaggio d'errore o "". */
export async function testPush() {
  if (pushSupported() && Notification.permission !== "granted") return BLOCKED;
  const sub = await currentSubscription();
  if (!sub) return "Questo dispositivo non è iscritto: spegni e riaccendi le notifiche.";
  try {
    await api("/push/test", { method: "POST", body: { endpoint: sub.endpoint } });
    return "";
  } catch (err) {
    return err.message || "Invio della notifica di prova non riuscito.";
  }
}

export async function disablePush() {
  const sub = await currentSubscription();
  if (!sub) return;
  try {
    await api("/push/subscriptions", { method: "DELETE", body: { endpoint: sub.endpoint } });
  } catch {
    /* il server la dimentica comunque al primo invio fallito */
  }
  await sub.unsubscribe();
}

/** Numero di non letti sull'icona dell'app installata (dove il sistema lo permette). */
export function setBadge(count) {
  if (!("setAppBadge" in navigator)) return;
  const op = count > 0 ? navigator.setAppBadge(count) : navigator.clearAppBadge();
  op.catch(() => {});
}
