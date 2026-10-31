"""Interessi e parole silenziate: quali articoli sono «per te» e quali vanno nascosti.

Il confronto avviene su titolo, estratto e categorie del feed, per parole intere e
senza badare a maiuscole e accenti. Per l'italiano riconosce anche singolare e
plurale: «razzo» trova «razzi», «galassia» trova «galassie», «amica» trova «amiche».

Il risultato viene salvato in user_matches, così elenchi, filtri e contatori sono
semplici query SQL. Si ricalcola:
- per gli articoli nuovi, appena arrivano (apply_new_articles);
- per tutti gli articoli di un utente, quando cambia le sue regole (recompute_user).

Punto di aggancio per la v2: `evaluate` è il calcolo della pertinenza. Il filtro AI
aggiungerà un secondo calcolo accanto a questo e scriverà nella stessa tabella.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field

from .text import normalize

LEVEL_ORDER = {"alta": 0, "media": 1}
VOWELS = "aeiou"


def word_pattern(phrase: str) -> re.Pattern | None:
    words = normalize(phrase).split()
    if not words:
        return None
    parts = [re.escape(w) for w in words[:-1]]
    last = words[-1]
    if len(last) >= 4 and last[-1] in VOWELS:
        # Singolare/plurale: cambia l'ultima vocale, con l'eventuale «h» (amica → amiche).
        parts.append(re.escape(last[:-1]) + "h?[" + VOWELS + "]")
    else:
        parts.append(re.escape(last))
    return re.compile(r"(?<![0-9a-z])" + r"\s+".join(parts) + r"(?![0-9a-z])")


@dataclass
class Rules:
    interests: list[tuple[str, str, re.Pattern]] = field(default_factory=list)  # (parola, livello, regex)
    muted: list[re.Pattern] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.interests and not self.muted


@dataclass
class Match:
    keyword: str | None
    level: str | None
    muted: bool


def load_rules(conn: sqlite3.Connection, user_id: int) -> Rules:
    rules = Rules()
    rows = conn.execute(
        "SELECT keyword, level FROM interests WHERE user_id = ? AND level != 'spento' ORDER BY created_at, id",
        (user_id,),
    ).fetchall()
    for r in sorted(rows, key=lambda r: LEVEL_ORDER[r["level"]]):
        pattern = word_pattern(r["keyword"])
        if pattern:
            rules.interests.append((r["keyword"], r["level"], pattern))
    for r in conn.execute("SELECT word FROM muted_words WHERE user_id = ?", (user_id,)):
        pattern = word_pattern(r["word"])
        if pattern:
            rules.muted.append(pattern)
    return rules


def haystack(title: str, excerpt: str, categories: str | list[str]) -> str:
    if isinstance(categories, str):
        try:
            categories = json.loads(categories or "[]")
        except ValueError:
            categories = []
    return normalize(" ".join([title or "", excerpt or "", " ".join(categories or [])]))


def evaluate(rules: Rules, text: str) -> Match | None:
    """Esito delle regole su un testo già normalizzato con haystack()."""
    muted = any(p.search(text) for p in rules.muted)
    for keyword, level, pattern in rules.interests:
        if pattern.search(text):
            return Match(keyword, level, muted)
    return Match(None, None, True) if muted else None


def _store(conn: sqlite3.Connection, user_id: int, rows, rules: Rules) -> int:
    values = []
    for r in rows:
        m = evaluate(rules, haystack(r["title"], r["excerpt"], r["categories"]))
        if m:
            values.append((user_id, r["id"], m.keyword, m.level, int(m.muted)))
    conn.executemany(
        "INSERT OR REPLACE INTO user_matches (user_id, article_id, keyword, level, muted) VALUES (?, ?, ?, ?, ?)",
        values,
    )
    return len(values)


def recompute_user(conn: sqlite3.Connection, user_id: int) -> None:
    """Ricalcola tutto per un utente (dopo che ha cambiato interessi o parole silenziate)."""
    rules = load_rules(conn, user_id)
    with conn:
        conn.execute("DELETE FROM user_matches WHERE user_id = ?", (user_id,))
        if rules.empty:
            return
        cur = conn.execute(
            "SELECT a.id, a.title, a.excerpt, a.categories FROM articles a"
            " WHERE a.feed_id IN (SELECT feed_id FROM subscriptions WHERE user_id = ?)"
            " OR a.id IN (SELECT article_id FROM user_articles WHERE user_id = ? AND saved_at IS NOT NULL)",
            (user_id, user_id),
        )
        while batch := cur.fetchmany(1000):
            _store(conn, user_id, batch, rules)


def recompute_feed_for_user(conn: sqlite3.Connection, user_id: int, feed_id: int) -> None:
    """Quando un utente inizia a seguire un feed che altri seguivano già."""
    rules = load_rules(conn, user_id)
    if rules.empty:
        return
    rows = conn.execute("SELECT id, title, excerpt, categories FROM articles WHERE feed_id = ?", (feed_id,)).fetchall()
    with conn:
        _store(conn, user_id, rows, rules)


def apply_new_articles(conn: sqlite3.Connection, feed_id: int, article_ids: list[int]) -> None:
    """Applica le regole di tutti gli iscritti del feed agli articoli appena arrivati."""
    if not article_ids:
        return
    marks = ",".join("?" * len(article_ids))
    rows = conn.execute(f"SELECT id, title, excerpt, categories FROM articles WHERE id IN ({marks})", article_ids).fetchall()
    users = [r["user_id"] for r in conn.execute("SELECT user_id FROM subscriptions WHERE feed_id = ?", (feed_id,))]
    with conn:
        for user_id in users:
            rules = load_rules(conn, user_id)
            if not rules.empty:
                _store(conn, user_id, rows, rules)
