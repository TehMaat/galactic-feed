// Scorciatoie da tastiera (#94). Qui solo la parte senza stato, che si prova con i test:
// quale scorciatoia è un tasto premuto e quale articolo viene prima o dopo in un elenco.

/** Le scorciatoie, nell'ordine in cui le mostra l'elenco («?»). */
export const SHORTCUTS = [
  ["j", "Notizia successiva"],
  ["k", "Notizia precedente"],
  ["s", "Salva o togli dai salvati l'articolo aperto"],
  ["m", "Segna l'articolo aperto come letto o da leggere"],
  ["o", "Apri l'originale in una nuova scheda"],
  ["r", "Controlla subito le fonti"],
  ["/", "Cerca"],
  ["?", "Mostra questo elenco"],
  ["Esc", "Chiudi l'articolo o la finestra"],
];

const KEYS = new Set(["j", "k", "s", "m", "o", "v", "r", "/", "?"]);
const ALIASES = { v: "o" };

/** Si sta scrivendo in un campo: i tasti sono lettere, non scorciatoie. */
export function isTyping(target) {
  if (!target || typeof target !== "object") return false;
  if (target.isContentEditable) return true;
  const tag = (target.tagName || "").toLowerCase();
  if (tag === "textarea" || tag === "select") return true;
  if (tag !== "input") return false;
  const type = (target.type || "text").toLowerCase();
  return !["checkbox", "radio", "button", "submit", "reset", "range", "color", "file"].includes(type);
}

/** La scorciatoia del tasto premuto («j», «o»…), oppure null. Ctrl, Alt e ⌘ lasciano il tasto al browser. */
export function shortcutFor(event) {
  if (!event || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return null;
  if (isTyping(event.target)) return null;
  const key = event.key?.length === 1 ? event.key.toLowerCase() : "";
  if (!KEYS.has(key)) return null;
  return ALIASES[key] || key;
}

/**
 * L'articolo dopo (step 1) o prima (step -1) di quello aperto. Senza un articolo aperto, o se
 * non è nell'elenco, «j» parte dal primo e «k» non fa niente. null in fondo e in cima.
 */
export function neighbour(items, currentId, step) {
  if (!items?.length) return null;
  const at = currentId == null ? -1 : items.findIndex((a) => a.id === currentId);
  if (at === -1) return step > 0 ? items[0].id : null;
  const next = items[at + step];
  return next ? next.id : null;
}
