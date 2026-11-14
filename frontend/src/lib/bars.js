// Barre a scomparsa sul telefono (#36): scorrendo verso il basso la barra in alto e la Dock
// escono dallo schermo, tornando su (anche di poco) rientrano.

export const BARS = {
  delta: 8, // spostamento minimo prima di cambiare stato: niente tremolii
  top: 56, // vicino alla cima le barre restano sempre visibili
  minScroll: 120, // pagine che scorrono meno di così: niente da nascondere
  bottom: 2, // arrivati in fondo ricompaiono, come in Safari: chi ha finito l'elenco trova la Dock
};

/**
 * Decide cosa fare delle barre dopo uno scorrimento.
 * `ref` è la posizione di riferimento dell'ultimo cambio; la funzione restituisce la nuova
 * e `hidden`: true (nascondi), false (mostra) o null (lascia com'è).
 * La posizione è limitata a [0, max] per ignorare il rimbalzo elastico di iOS.
 */
export function barsAfterScroll(ref, scrollTop, maxScroll) {
  const max = Math.max(maxScroll, 0);
  const y = Math.min(Math.max(scrollTop, 0), max);
  if (y < BARS.top || max < BARS.minScroll || y >= max - BARS.bottom) return { hidden: false, ref: y };
  if (Math.abs(y - ref) < BARS.delta) return { hidden: null, ref };
  return { hidden: y > ref, ref: y };
}
