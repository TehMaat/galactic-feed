"""Tag proposti in automatico per le fonti (issue #17).

Per una fonte appena seguita si guardano gli articoli recenti del feed:
1. i gruppi di parole pronti (presets.py): se le loro parole compaiono in molti titoli,
   il nome del gruppo («Tecnologia», «Calcio»…) diventa un tag;
2. le categorie scritte dal sito nel feed, se ricorrono in molti articoli.
Al massimo tre tag. I tag proposti hanno origin «auto»; quelli tolti dall'utente restano
come «rejected», così la proposta non li rimette. Le scelte dell'utente non si toccano mai.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter

from ..db import now
from .matching import haystack, word_pattern
from .text import normalize

MAX_TAGS = 3
SAMPLE = 60
# Categorie che non dicono niente sull'argomento della fonte.
GENERIC = {
    "uncategorized", "senza categoria", "news", "notizie", "ultime notizie", "home", "homepage", "blog", "articoli",
    "articolo", "general", "generale", "varie", "misc", "featured", "in evidenza", "top", "primo piano", "post",
}
COLORS = ["indaco", "blu", "verde", "viola", "rosa", "ambra", "azzurro", "grigio"]


def suggest(conn: sqlite3.Connection, feed_id: int) -> list[str]:
    """Fino a tre nomi di tag per il feed, dal più adatto."""
    feed = conn.execute("SELECT title FROM feeds WHERE id = ?", (feed_id,)).fetchone()
    rows = conn.execute(
        "SELECT title, excerpt, categories FROM articles WHERE feed_id = ? ORDER BY published_at DESC LIMIT ?",
        (feed_id, SAMPLE),
    ).fetchall()
    if not rows:
        return []
    n = len(rows)
    texts = [haystack(r["title"], r["excerpt"], r["categories"]) for r in rows]
    feed_title = normalize(feed["title"] if feed else "")
    scores: dict[str, float] = {}

    # 1. Gruppi di parole pronti.
    for p in conn.execute("SELECT name, words FROM preset_groups WHERE hidden = 0"):
        patterns = [pt for pt in (word_pattern(w) for w in json.loads(p["words"])) if pt]
        hits = sum(1 for t in texts if any(pt.search(t) for pt in patterns))
        in_title = any(pt.search(feed_title) for pt in patterns)
        share = hits / n
        if (hits >= 2 and share >= 0.25) or in_title:
            scores[p["name"]] = share + (0.5 if in_title else 0)

    # 2. Categorie del feed.
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for r in rows:
        try:
            cats = json.loads(r["categories"] or "[]")
        except ValueError:
            cats = []
        for c in {(c or "").strip() for c in cats}:
            key = normalize(c)
            if not key or key in GENERIC or len(c) > 30:
                continue
            counts[key] += 1
            labels.setdefault(key, c[:1].upper() + c[1:])
    for key, hits in counts.items():
        if hits >= 3 and hits / n >= 0.3:
            name = labels[key]
            if not any(normalize(existing) == key for existing in scores):
                scores[name] = hits / n

    return [name for name, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:MAX_TAGS]]


def tag_id_for(conn: sqlite3.Connection, user_id: int, name: str) -> int:
    """Id del tag dell'utente con quel nome (maiuscole a parte), creandolo se manca."""
    row = conn.execute("SELECT id FROM tags WHERE user_id = ? AND name = ?", (user_id, name)).fetchone()
    if row:
        return row["id"]
    used = conn.execute("SELECT COUNT(*) FROM tags WHERE user_id = ?", (user_id,)).fetchone()[0]
    position = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tags WHERE user_id = ?", (user_id,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO tags (user_id, name, color, position, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, COLORS[used % len(COLORS)], position, now()),
    )
    return cur.lastrowid


def apply_suggestions(conn: sqlite3.Connection, subscription_id: int) -> list[str]:
    """Propone i tag per la fonte dell'utente. Non tocca i tag scelti né quelli tolti. Restituisce quelli aggiunti."""
    sub = conn.execute("SELECT id, user_id, feed_id FROM subscriptions WHERE id = ?", (subscription_id,)).fetchone()
    if sub is None:
        return []
    names = suggest(conn, sub["feed_id"])
    added = []
    with conn:
        for name in names:
            tag_id = tag_id_for(conn, sub["user_id"], name)
            cur = conn.execute(
                "INSERT OR IGNORE INTO source_tags (subscription_id, tag_id, origin, created_at) VALUES (?, ?, 'auto', ?)",
                (subscription_id, tag_id, now()),
            )
            if cur.rowcount:
                added.append(name)
        conn.execute("UPDATE subscriptions SET tags_suggested_at = ? WHERE id = ?", (now(), subscription_id))
    return added


def wants_auto_tags(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute("SELECT prefs FROM users WHERE id = ?", (user_id,)).fetchone()
    try:
        return bool(json.loads(row["prefs"] or "{}").get("auto_tags", True)) if row else False
    except ValueError:
        return True


def run_due(conn: sqlite3.Connection, limit: int = 20) -> int:
    """Le fonti a cui non sono ancora stati proposti i tag (per esempio importate con l'OPML)."""
    rows = conn.execute(
        "SELECT s.id, s.user_id FROM subscriptions s JOIN feeds f ON f.id = s.feed_id"
        " WHERE s.tags_suggested_at IS NULL AND f.last_success_at IS NOT NULL"
        " AND EXISTS (SELECT 1 FROM articles a WHERE a.feed_id = f.id) LIMIT ?",
        (limit,),
    ).fetchall()
    done = 0
    for r in rows:
        if wants_auto_tags(conn, r["user_id"]):
            apply_suggestions(conn, r["id"])
        else:
            with conn:
                conn.execute("UPDATE subscriptions SET tags_suggested_at = ? WHERE id = ?", (now(), r["id"]))
        done += 1
    return done
