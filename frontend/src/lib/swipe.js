// Swipe orizzontale in Oggi tra Edizione e Flusso (#29). Qui solo le decisioni, senza DOM,
// così si provano con vitest; i gestori dei Pointer Events stanno in Oggi.svelte.
//
// - Gli swipe che partono vicino ai bordi sono del sistema (gesto «indietro» di Android e di
//   Safari): li ignoriamo.
// - Si decide l'asse dopo qualche pixel: se il dito va soprattutto in verticale la pagina scorre
//   e lo swipe non parte più.
// - Verso sinistra si va al Flusso, verso destra all'Edizione: lo stesso ordine del selettore.
// - Agli estremi (Edizione e swipe a destra, Flusso e swipe a sinistra) il contenuto si sposta
//   solo un po', come un elastico, e non cambia niente.

export const SWIPE = {
  edge: 28, // px dai bordi riservati ai gesti di sistema
  lock: 10, // px prima di decidere l'asse
  ratio: 1.5, // |dx| deve superare ratio·|dy| per essere orizzontale
  distance: 0.3, // frazione della larghezza oltre la quale si cambia modalità
  velocity: 0.45, // px/ms: uno swipe veloce cambia anche se è corto
  minDistance: 40, // px: ma non se è un tocco appena mosso
  rubber: 0.25, // quanto segue il dito agli estremi
};

export const MODES = ["edizione", "flusso"];

/** Elementi da cui lo swipe non parte: campi, chip che scorrono, o chi lo chiede con data-no-swipe. */
export const NO_SWIPE = "input, textarea, select, [contenteditable], .chips, [data-no-swipe]";

/** Lo swipe può cominciare da qui? `x` è la posizione del dito, `width` quella dello schermo. */
export function canStart(x, width, { edge = SWIPE.edge } = {}) {
  return x >= edge && x <= width - edge;
}

/**
 * Asse del gesto dopo uno spostamento (dx, dy): "x" (swipe), "y" (scorrimento) o null (ancora presto).
 */
export function lockAxis(dx, dy) {
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (Math.max(ax, ay) < SWIPE.lock) return null;
  return ax > SWIPE.ratio * ay ? "x" : "y";
}

/** La modalità verso cui porta uno spostamento dx partendo da `mode`, o null agli estremi. */
export function target(mode, dx) {
  const i = MODES.indexOf(mode);
  if (i < 0 || dx === 0) return null;
  const j = dx < 0 ? i + 1 : i - 1;
  return MODES[j] ?? null;
}

/** Quanto spostare il contenuto mentre il dito si muove: pieno verso l'altra modalità, elastico agli estremi. */
export function offset(mode, dx) {
  return target(mode, dx) ? dx : dx * SWIPE.rubber;
}

/**
 * Al rilascio: la nuova modalità, o null se si resta dove si è.
 * `vx` è la velocità orizzontale in px/ms (negativa verso sinistra).
 */
export function release(mode, dx, vx, width) {
  const next = target(mode, dx);
  if (!next) return null;
  const far = Math.abs(dx) >= width * SWIPE.distance;
  const fast = Math.abs(dx) >= SWIPE.minDistance && Math.abs(vx) >= SWIPE.velocity && Math.sign(vx) === Math.sign(dx);
  return far || fast ? next : null;
}
