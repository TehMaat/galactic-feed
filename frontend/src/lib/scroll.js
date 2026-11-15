// Chi scorre (#38). Su telefono e tablet scorre il documento, così nel browser la barra degli
// indirizzi si riduce come sui normali siti; sul computer ogni sezione (.view) ha il suo scroll,
// perché lista e lettore stanno affiancati. Il limite è lo stesso del CSS (app.css, «Telefono e
// tablet») e di isWide() in store.svelte.js.

export const COMPACT_QUERY = "(max-width: 1099.98px)";

/** true quando scorre il documento (telefono e tablet). */
export function docScroll() {
  return typeof window !== "undefined" && window.matchMedia(COMPACT_QUERY).matches;
}

/** Posizione verticale di una sezione, chiunque la faccia scorrere. */
export function viewScrollTop(view) {
  return docScroll() ? window.scrollY : view.scrollTop;
}

/** Fa scorrere una sezione (window.scrollTo su telefono e tablet). */
export function scrollViewTo(view, options) {
  (docScroll() ? window : view).scrollTo(options);
}
