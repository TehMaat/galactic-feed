"""Edizione: a ogni orario scelto dall'utente, una selezione delle notizie arrivate.

Come si compone:
- si prendono le notizie pubblicate dopo l'edizione precedente (al massimo 48 ore, 24 per
  la prima), senza quelle silenziate e con i doppioni uniti come nel Flusso;
- entrano quelle «per te» (interessi o AI), prima le priorità alte, poi le più recenti,
  fino a MAX_ITEMS; la prima diventa la notizia in primo piano;
- se quelle per te sono meno di MIN_MATCHES, si aggiungono le ultime notizie, una per
  fonte, nella sezione «Dalle tue fonti»;
- le altre si raggruppano per cartella, nell'ordine delle cartelle.

Gli orari sono nel fuso del server (TZ). Se il server era spento all'ora giusta, l'edizione
si compone appena riparte, purché non sia già passato l'orario successivo.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..db import now
from . import query
from .query import ArticleFilter

log = logging.getLogger("galactic_feed.edition")

MAX_ITEMS = 30
MIN_MATCHES = 3
FILLER_ITEMS = 8
KEEP_EDITIONS = 60
FIRST_WINDOW = 24 * 3600
MAX_WINDOW = 48 * 3600


def zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except Exception:
        return ZoneInfo("UTC")


def _slot_datetimes(times: list[str], tz: str, ts: int) -> list[tuple[datetime, str]]:
    """Gli orari di ieri, oggi e domani come date vere, in ordine."""
    zone_ = zone(tz)
    today = datetime.fromtimestamp(ts, zone_).date()
    out = []
    for delta in (-1, 0, 1):
        day = today + timedelta(days=delta)
        for t in times:
            h, m = (int(x) for x in t.split(":"))
            out.append((datetime(day.year, day.month, day.day, h, m, tzinfo=zone_), t))
    return sorted(out)


def last_slot(times: list[str], tz: str, ts: int) -> tuple[int, str]:
    """L'orario più recente già passato: (momento, «HH:MM»)."""
    past = [(d, t) for d, t in _slot_datetimes(times, tz, ts) if d.timestamp() <= ts]
    d, t = past[-1]
    return int(d.timestamp()), t


def next_slot(times: list[str], tz: str, ts: int) -> tuple[int, str]:
    d, t = next((d, t) for d, t in _slot_datetimes(times, tz, ts) if d.timestamp() > ts)
    return int(d.timestamp()), t


def is_due(times: list[str], tz: str, ts: int, last_created: int | None) -> str | None:
    """L'orario dell'edizione da comporre adesso, oppure None se è già fatta."""
    slot_ts, slot = last_slot(times, tz, ts)
    if last_created is not None and last_created >= slot_ts:
        return None
    return slot


def _candidates(conn: sqlite3.Connection, user_id: int, since: int, dedupe: bool) -> list[sqlite3.Row]:
    f = ArticleFilter(since=since, dedupe=dedupe)
    cte, params = query.visible_cte(user_id, f)
    return conn.execute(
        f"WITH {cte}, {query.ranked_sql(f)}"
        " SELECT r.id, r.level, r.folder_id, r.published_at, s.id AS sub_id"
        " FROM ranked r JOIN articles a ON a.id = r.id"
        " LEFT JOIN subscriptions s ON s.feed_id = a.feed_id AND s.user_id = ?"
        " WHERE r.rn = 1 ORDER BY r.published_at DESC, r.id DESC",
        [*params, user_id],
    ).fetchall()


def select(rows: list[sqlite3.Row]) -> list[tuple[int, str, object]]:
    """Sceglie le notizie: [(id, sezione provvisoria, cartella)], la prima è quella in primo piano."""
    level_rank = {"alta": 0, "media": 1}
    matches = sorted((r for r in rows if r["level"]), key=lambda r: (level_rank[r["level"]], -r["published_at"]))
    chosen = [(r["id"], "match", r["folder_id"]) for r in matches[:MAX_ITEMS]]
    if len(chosen) < MIN_MATCHES:
        taken = {c[0] for c in chosen}
        seen_sources: set = set()
        for r in rows:
            if len(chosen) >= FILLER_ITEMS:
                break
            if r["id"] in taken or r["sub_id"] in seen_sources:
                continue
            seen_sources.add(r["sub_id"])
            chosen.append((r["id"], "fonti", r["folder_id"]))
    return chosen


def compose(conn: sqlite3.Connection, user_id: int, slot: str, ts: int | None = None, dedupe: bool = True) -> int:
    """Compone e salva un'edizione. Restituisce il suo id."""
    ts = ts or now()
    prev = conn.execute(
        "SELECT created_at FROM editions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)
    ).fetchone()
    since = max(prev["created_at"], ts - MAX_WINDOW) if prev else ts - FIRST_WINDOW
    rows = _candidates(conn, user_id, since, dedupe)
    chosen = select(rows)
    hidden = query.count(conn, user_id, ArticleFilter(since=since, dedupe=dedupe), muted=True)
    sources = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id = ?", (user_id,)).fetchone()[0]
    stats = {
        "sources": sources,
        "new": len(rows),
        "selected": sum(1 for c in chosen if c[1] == "match"),
        "hidden": hidden,
    }
    with conn:
        number = conn.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM editions WHERE user_id = ?", (user_id,)).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO editions (user_id, number, slot, since, stats, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, number, slot, since, json.dumps(stats), ts),
        )
        edition_id = cur.lastrowid
        items = []
        for pos, (article_id, kind, folder_id) in enumerate(chosen):
            if pos == 0 and kind == "match":
                section = "hero"
            elif kind == "fonti":
                section = "fonti"
            else:
                section = str(folder_id) if folder_id is not None else "none"
            items.append((edition_id, article_id, pos, section))
        conn.executemany("INSERT INTO edition_items (edition_id, article_id, position, section) VALUES (?, ?, ?, ?)", items)
        # Si tengono le ultime KEEP_EDITIONS edizioni.
        conn.execute(
            "DELETE FROM editions WHERE user_id = ? AND id NOT IN"
            " (SELECT id FROM editions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?)",
            (user_id, user_id, KEEP_EDITIONS),
        )
    log.info("Edizione n. %s per l'utente %s: %s notizie", number, user_id, len(chosen))
    return edition_id


def users_with_edition(conn: sqlite3.Connection) -> list[tuple[int, dict]]:
    out = []
    for r in conn.execute("SELECT id, prefs FROM users"):
        try:
            prefs = json.loads(r["prefs"] or "{}")
        except ValueError:
            continue
        if prefs.get("edition"):
            out.append((r["id"], prefs))
    return out


def run_due(ctx, ts: int | None = None) -> list[tuple[int, int]]:
    """Compone le edizioni arrivate all'orario. Restituisce [(utente, edizione)]."""
    from ..api.common import prefs_with_defaults

    ts = ts or now()
    made = []
    with ctx.db.session() as conn:
        for user_id, stored in users_with_edition(conn):
            prefs = prefs_with_defaults(stored)
            last = conn.execute("SELECT MAX(created_at) FROM editions WHERE user_id = ?", (user_id,)).fetchone()[0]
            slot = is_due(prefs["edition_times"], ctx.settings.timezone, ts, last)
            if slot:
                try:
                    made.append((user_id, compose(conn, user_id, slot, ts, prefs["dedupe"])))
                except Exception:
                    log.exception("Edizione non composta per l'utente %s", user_id)
    return made
