// Chi scorre (#38). Sul telefono scorre il documento, così nel browser la barra degli indirizzi
// si riduce come sui normali siti; su tablet e computer ogni sezione (.view) ha il suo scroll,
// perché le colonne stanno affiancate. Il limite è lo stesso del CSS (app.css, «Telefono»).

export const PHONE_QUERY = "(max-width: 699.98px)";

/** true quando scorre il documento (telefono). */
export function docScroll() {
  return typeof window !== "undefined" && window.matchMedia(PHONE_QUERY).matches;
}

/** Posizione verticale di una sezione, chiunque la faccia scorrere. */
export function viewScrollTop(view) {
  return docScroll() ? window.scrollY : view.scrollTop;
}

/** Fa scorrere una sezione (window.scrollTo sul telefono). */
export function scrollViewTo(view, options) {
  (docScroll() ? window : view).scrollTo(options);
}
