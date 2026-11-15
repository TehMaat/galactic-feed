// Le spiegazioni aperte dal cerchio con la «i».
import { inform } from "./store.svelte.js";

export function explainDedupe() {
  return inform(
    [
      "Quando la stessa notizia arriva da più fonti, la vedi una volta sola. Due articoli sono la stessa notizia se hanno lo stesso link, oppure se escono da fonti diverse a meno di 3 giorni di distanza con un titolo quasi uguale.",
      "Di ogni notizia vedi l'articolo pubblicato per primo tra quelli che passano i filtri: se filtri su una fonte, vedi la versione di quella fonte. Le altre fonti sono elencate in «Anche su».",
      "Letto e non letto valgono per tutta la notizia: se ne leggi una versione, anche le altre risultano lette e non ti ricompaiono tra i non letti.",
      "Nei Salvati i doppioni restano separati. Puoi spegnere l'unione in Interessi, nelle Regole.",
    ],
    { title: "Come funzionano i doppioni" },
  );
}
