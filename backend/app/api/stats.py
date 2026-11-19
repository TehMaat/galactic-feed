"""Statistiche di lettura nel Profilo (#78).

Si ricavano dagli articoli aperti (tabella reading_log: uno per articolo, quando lo si apre la
prima volta), dai salvati e dalle uscite delle Edizioni aperte. Niente tempi di lettura: non si
misura quanto resti su un articolo. Giorni e ore sono nel fuso dell'utente.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from ..db import now
from ..deps import AppContext, User, current_user, get_ctx, get_db
from ..reading import edition, schedule
from .common import prefs_with_defaults

router = APIRouter(prefix="/api/me", tags=["profilo"])

TOP = 5


def _streaks(days: set, today) -> tuple[int, int]:
    """Giorni di fila con almeno un articolo aperto: quelli in corso (fino a oggi o ieri) e il record."""
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    current = 0
    d = today if today in days else today - timedelta(days=1)
    while d in days:
        current += 1
        d -= timedelta(days=1)
    return current, best


@router.get("/stats")
def stats(
    days: int = Query(7, description="periodo: 7 o 30 giorni"),
    user: User = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    days = 30 if days >= 30 else 7
    tz = schedule.zone(edition.user_timezone(ctx, prefs_with_defaults(user.prefs), conn))
    ts = now()
    today = datetime.fromtimestamp(ts, tz).date()
    first = today - timedelta(days=days - 1)
    start = int(datetime(first.year, first.month, first.day, tzinfo=tz).timestamp())
    prev_start = int(datetime.combine(first - timedelta(days=days), datetime.min.time(), tz).timestamp())

    reads = [r[0] for r in conn.execute("SELECT read_at FROM reading_log WHERE user_id = ?", (user.id,))]
    local = [datetime.fromtimestamp(t, tz) for t in reads]
    in_period = [d for d, t in zip(local, reads) if t >= start]
    per_day = Counter(d.date() for d in in_period)
    hours = Counter(d.hour for d in in_period)
    current, best = _streaks({d.date() for d in local}, today)

    interests = conn.execute(
        "SELECT name, COUNT(*) AS n FROM ("
        "  SELECT DISTINCT rl.article_id, t.name FROM reading_log rl"
        "  JOIN subscriptions s ON s.feed_id = rl.feed_id AND s.user_id = rl.user_id"
        "  JOIN source_tags st ON st.subscription_id = s.id AND st.origin != 'rejected'"
        "  JOIN tags t ON t.id = st.tag_id"
        "  WHERE rl.user_id = ? AND rl.read_at >= ?"
        "  UNION"
        "  SELECT DISTINCT rl.article_id, g.name FROM reading_log rl"
        "  JOIN user_matches m ON m.article_id = rl.article_id AND m.user_id = rl.user_id"
        "  JOIN word_groups g ON g.id = m.group_id"
        "  WHERE rl.user_id = ? AND rl.read_at >= ?"
        ") GROUP BY name COLLATE NOCASE ORDER BY n DESC, name LIMIT 20",
        (user.id, start, user.id, start),
    ).fetchall()
    tagged = sum(r["n"] for r in interests) or 1
    sources = conn.execute(
        "SELECT s.id, COALESCE(NULLIF(s.title, ''), NULLIF(f.title, ''), f.url) AS title, COUNT(*) AS n"
        " FROM reading_log rl JOIN subscriptions s ON s.feed_id = rl.feed_id AND s.user_id = rl.user_id"
        " JOIN feeds f ON f.id = s.feed_id"
        " WHERE rl.user_id = ? AND rl.read_at >= ? GROUP BY s.id ORDER BY n DESC, title LIMIT ?",
        (user.id, start, TOP),
    ).fetchall()
    eds = conn.execute(
        "SELECT COUNT(*) AS issued, COALESCE(SUM(opened_at IS NOT NULL), 0) AS opened FROM editions WHERE user_id = ? AND created_at >= ?",
        (user.id, start),
    ).fetchone()
    saved = conn.execute("SELECT COUNT(*) FROM user_articles WHERE user_id = ? AND saved_at >= ?", (user.id, start)).fetchone()[0]
    return {
        "days": days,
        "read": len(in_period),
        "read_prev": sum(1 for t in reads if prev_start <= t < start),
        "saved": saved,
        "streak": current,
        "best_streak": best,
        "per_day": [{"date": (first + timedelta(days=i)).isoformat(), "n": per_day.get(first + timedelta(days=i), 0)} for i in range(days)],
        "hours": [hours.get(h, 0) for h in range(24)],
        "interests": [{"name": r["name"], "n": r["n"], "share": round(r["n"] * 100 / tagged)} for r in interests[:TOP]],
        "sources": [{"id": r["id"], "title": r["title"], "n": r["n"]} for r in sources],
        "editions": {"issued": eds["issued"], "opened": eds["opened"]},
    }
