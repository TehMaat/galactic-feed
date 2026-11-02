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

/** Chiede il permesso e iscrive il dispositivo. Restituisce un messaggio d'errore o "". */
export async function enablePush() {
  if (!pushSupported()) {
    return isIos() && !isStandalone()
      ? "Su iPhone le notifiche arrivano solo nell'app aggiunta alla schermata Home: aprila da lì e riprova."
      : "Questo browser non supporta le notifiche.";
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return "Le notifiche sono bloccate: permettile nelle impostazioni del browser o del telefono.";
  }
  try {
    const { public_key } = await api("/push/key");
    const reg = await registration();
    let sub = await reg.pushManager.getSubscription();
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) });
    await api("/push/subscriptions", { method: "POST", body: sub.toJSON() });
    return "";
  } catch (err) {
    return err.message || "Iscrizione alle notifiche non riuscita.";
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
