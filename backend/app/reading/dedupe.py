"""Doppioni: la stessa notizia pubblicata da più fonti.

Quando arriva un articolo lo si confronta con quelli dei 3 giorni intorno:
- stesso link ripulito (senza utm_, www, #…) → stessa notizia, anche nello stesso feed;
- titolo quasi uguale in un altro feed → stessa notizia. «Quasi uguale» vuol dire
  almeno 4 parole significative e il 75% in comune; con 3 parole devono coincidere tutte.
Gli articoli della stessa notizia condividono cluster_id. Nell'elenco l'utente ne vede
uno solo, con l'indicazione «anche su: …».
"""

from __future__ import annotations

import sqlite3

WINDOW_SECONDS = 3 * 86400
SIMILARITY = 0.75
MIN_WORDS = 4


def similar(a: str, b: str) -> bool:
    wa, wb = set(a.split()), set(b.split())
    if len(wa) < 3 or len(wb) < 3:
        return False
    if len(wa) < MIN_WORDS or len(wb) < MIN_WORDS:
        return wa == wb
    return len(wa & wb) / len(wa | wb) >= SIMILARITY


def find_cluster(
    conn: sqlite3.Connection, article_id: int, feed_id: int, canonical: str, key: str, published: int
) -> int:
    lo, hi = published - WINDOW_SECONDS, published + WINDOW_SECONDS
    if canonical:
        row = conn.execute(
            "SELECT cluster_id FROM articles WHERE canonical_url = ? AND id != ? AND published_at BETWEEN ? AND ?"
            " ORDER BY published_at LIMIT 1",
            (canonical, article_id, lo, hi),
        ).fetchone()
        if row and row["cluster_id"]:
            return row["cluster_id"]
    if key and len(key.split()) >= 3:
        rows = conn.execute(
            "SELECT cluster_id, title_key FROM articles WHERE feed_id != ? AND id != ? AND published_at BETWEEN ? AND ?"
            " AND title_key != '' ORDER BY published_at",
            (feed_id, article_id, lo, hi),
        )
        for row in rows:
            if row["cluster_id"] and similar(key, row["title_key"]):
                return row["cluster_id"]
    return article_id
