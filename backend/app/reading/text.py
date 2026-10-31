"""Normalizzazione del testo per confronti: minuscole, senza accenti né punteggiatura."""

from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^0-9a-z]+")

# Parole troppo comuni per dire qualcosa sul contenuto di un titolo.
STOPWORDS = set(
    """
    il lo la i gli le un uno una di a da in con su per tra fra e ed o od ma se che chi cui non piu più
    del dello della dei degli delle al allo alla ai agli alle dal dallo dalla dai dagli dalle nel nello
    nella nei negli nelle sul sullo sulla sui sugli sulle col coi come anche ecco questo questa questi
    queste quello quella sono e è ha hanno era essere avere fa fare cosa perche perché quando dove
    the a an of to in on for with and or but is are was were be by at from as it its this that these
    those how why what who new your you we our
    """.split()
)


def normalize(text: str) -> str:
    """«Perché la Luna?» → «perche la luna»."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(_NON_WORD.sub(" ", text.lower()).split())


def title_key(title: str) -> str:
    """Le parole significative del titolo, in ordine, senza doppioni."""
    seen: list[str] = []
    for word in normalize(title).split():
        if len(word) > 1 and word not in STOPWORDS and word not in seen:
            seen.append(word)
    return " ".join(seen)
