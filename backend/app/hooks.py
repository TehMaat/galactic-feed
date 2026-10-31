"""Punti di aggancio per la seconda versione.

La prima versione non li usa, ma il codice li chiama già nei momenti giusti:

- `new_articles`: dopo ogni controllo di un feed, con gli articoli appena arrivati.
  Qui si collegheranno la composizione dell'Edizione e le notifiche push
  ("è arrivata una notizia importante per Anna").
- la pertinenza di un articolo per un utente è calcolata in
  `reading/matching.py:evaluate` e salvata nella tabella `user_matches`. Oggi usa le
  parole chiave; il filtro AI aggiungerà un secondo calcolo accanto a questo e
  scriverà il suo esito nella stessa tabella, così elenchi e filtri non cambiano.

Ogni funzione registrata riceve dati semplici (numeri e liste) e non deve bloccare:
gli errori vengono scritti nel log e non fermano il download dei feed.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

log = logging.getLogger("galactic_feed.hooks")

NewArticlesHook = Callable[[int, list[int]], Awaitable[None]]


class Hooks:
    def __init__(self) -> None:
        self.new_articles: list[NewArticlesHook] = []

    async def emit_new_articles(self, feed_id: int, article_ids: list[int]) -> None:
        if not article_ids:
            return
        for hook in self.new_articles:
            try:
                await hook(feed_id, article_ids)
            except Exception:  # un aggancio difettoso non deve fermare il fetcher
                log.exception("Errore nell'aggancio new_articles")
