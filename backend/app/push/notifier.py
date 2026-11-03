"""Quando mandare le notifiche, e a chi.

- Notizie importanti: ogni giro dello scheduler (dopo il download dei feed e il filtro AI),
  per ogni utente con almeno un dispositivo iscritto, le notizie «per te» arrivate da poco
  nelle cartelle che ha scelto come importanti, non lette e mai notificate. Più notizie
  insieme diventano una notifica sola; al massimo una ogni THROTTLE secondi per utente.
- Edizione pronta: se l'utente lo vuole, appena il server la compone.
Ogni notifica porta il numero di non letti, che il service worker mette sull'icona.
"""

from __future__ import annotations

import json
import logging
import sqlite3

import httpx

from ..api.common import prefs_with_defaults
from ..db import now
from ..reading import query
from ..reading.query import ArticleFilter
from .webpush import Subscription, Vapid, send

log = logging.getLogger("galactic_feed.push")

THROTTLE = 10 * 60
RECENT = 3 * 3600
MAX_FAILURES = 5


def unread_count(conn: sqlite3.Connection, user_id: int, dedupe: bool = True) -> int:
    return query.count(conn, user_id, ArticleFilter(view="nonletti", dedupe=dedupe))


class Notifier:
    def __init__(self, ctx):
        self.ctx = ctx
        self.vapid: Vapid | None = None
        self.client: httpx.AsyncClient | None = None
        self.last_sent: dict[int, int] = {}

    def start(self) -> None:
        settings = self.ctx.settings
        subject = settings.public_url if settings.public_url.startswith("https://") else "mailto:admin@galactic-feed.invalid"
        self.vapid = Vapid.load_or_create(settings.data_dir / "vapid.pem", subject)
        self.client = httpx.AsyncClient(timeout=15, follow_redirects=False)

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    # ---- invio ----

    async def send_to_user(self, user_id: int, data: dict, urgency: str = "normal") -> tuple[int, list[str]]:
        with self.ctx.db.session() as conn:
            subs = [
                Subscription(r["id"], r["endpoint"], r["p256dh"], r["auth"])
                for r in conn.execute("SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE user_id = ?", (user_id,))
            ]
        sent, errors = 0, []
        for sub in subs:
            outcome = await send(self.client, self.vapid, sub, data, urgency)
            with self.ctx.db.session() as conn, conn:
                if outcome.ok:
                    sent += 1
                    conn.execute("UPDATE push_subscriptions SET last_ok_at = ?, failures = 0 WHERE id = ?", (now(), sub.id))
                elif outcome.gone:
                    conn.execute("DELETE FROM push_subscriptions WHERE id = ?", (sub.id,))
                else:
                    errors.append(outcome.message)
                    conn.execute("UPDATE push_subscriptions SET failures = failures + 1 WHERE id = ?", (sub.id,))
                    conn.execute("DELETE FROM push_subscriptions WHERE id = ? AND failures >= ?", (sub.id, MAX_FAILURES))
        if sent:
            self.last_sent[user_id] = now()
        return sent, errors

    # ---- notizie importanti ----

    def _users(self, conn: sqlite3.Connection) -> list[tuple[int, dict, int]]:
        rows = conn.execute(
            "SELECT u.id, u.prefs, MIN(p.created_at) AS since FROM users u"
            " JOIN push_subscriptions p ON p.user_id = u.id WHERE u.disabled = 0 GROUP BY u.id"
        ).fetchall()
        out = []
        for r in rows:
            try:
                prefs = prefs_with_defaults(json.loads(r["prefs"] or "{}"))
            except ValueError:
                continue
            if prefs["notify_folders"]:
                out.append((r["id"], prefs, r["since"]))
        return out

    def pending_news(self, conn: sqlite3.Connection, user_id: int, folders: list[str], since: int, ts: int) -> list[sqlite3.Row]:
        ids = [int(f) for f in folders if f.isdigit()]
        clause = []
        params: list = []
        if ids:
            clause.append(f"s.folder_id IN ({','.join('?' * len(ids))})")
            params += ids
        if "none" in folders:
            clause.append("s.folder_id IS NULL")
        if not clause:
            return []
        return conn.execute(
            "SELECT a.id, a.title, COALESCE(NULLIF(s.title, ''), NULLIF(f.title, ''), f.url) AS source, m.level"
            " FROM articles a JOIN feeds f ON f.id = a.feed_id"
            " JOIN subscriptions s ON s.feed_id = a.feed_id AND s.user_id = ?"
            " JOIN user_matches m ON m.article_id = a.id AND m.user_id = ? AND m.level IS NOT NULL AND m.muted = 0"
            " LEFT JOIN user_articles ua ON ua.article_id = a.id AND ua.user_id = ?"
            " LEFT JOIN push_sent p ON p.article_id = a.id AND p.user_id = ?"
            " WHERE a.fetched_at >= ? AND a.published_at >= ? AND ua.read_at IS NULL AND p.article_id IS NULL"
            " AND (a.cluster_id IS NULL OR a.cluster_id = a.id)"
            f" AND ({' OR '.join(clause)})"
            " ORDER BY m.level = 'alta' DESC, a.published_at DESC LIMIT 20",
            [user_id, user_id, user_id, user_id, max(since, ts - RECENT), ts - 24 * 3600, *params],
        ).fetchall()

    async def notify_news(self, ts: int | None = None) -> int:
        """Un giro: restituisce quante notifiche ha mandato."""
        if not self.vapid:
            return 0
        ts = ts or now()
        sent_total = 0
        with self.ctx.db.session() as conn:
            users = self._users(conn)
        for user_id, prefs, since in users:
            if ts - self.last_sent.get(user_id, 0) < THROTTLE:
                continue
            with self.ctx.db.session() as conn:
                rows = self.pending_news(conn, user_id, prefs["notify_folders"], since, ts)
                if not rows:
                    continue
                badge = unread_count(conn, user_id, prefs["dedupe"])
            if len(rows) == 1:
                r = rows[0]
                data = {"title": r["source"], "body": r["title"], "url": f"/?a={r['id']}", "tag": f"art-{r['id']}"}
            else:
                lines = [f"• {r['title']}" for r in rows[:3]]
                if len(rows) > 3:
                    lines.append(f"e altre {len(rows) - 3}")
                data = {"title": f"{len(rows)} notizie per te", "body": "\n".join(lines), "url": "/", "tag": "notizie"}
            data["badge"] = badge
            urgency = "high" if any(r["level"] == "alta" for r in rows) else "normal"
            sent, _ = await self.send_to_user(user_id, data, urgency)
            if sent:
                sent_total += 1
                with self.ctx.db.session() as conn, conn:
                    conn.executemany(
                        "INSERT OR IGNORE INTO push_sent (user_id, article_id, sent_at) VALUES (?, ?, ?)",
                        [(user_id, r["id"], ts) for r in rows],
                    )
        return sent_total

    # ---- Edizione ----

    async def edition_ready(self, user_id: int, edition_id: int) -> None:
        if not self.vapid:
            return
        with self.ctx.db.session() as conn:
            row = conn.execute("SELECT u.prefs, e.slot, e.stats FROM editions e JOIN users u ON u.id = e.user_id WHERE e.id = ?", (edition_id,)).fetchone()
            has_device = conn.execute("SELECT 1 FROM push_subscriptions WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
            if not row or not has_device:
                return
            prefs = prefs_with_defaults(json.loads(row["prefs"] or "{}"))
            if not prefs["notify_edition"]:
                return
            selected = json.loads(row["stats"] or "{}").get("selected", 0)
            badge = unread_count(conn, user_id, prefs["dedupe"])
        body = f"{selected} notizie scelte per te." if selected != 1 else "1 notizia scelta per te."
        await self.send_to_user(
            user_id,
            {"title": f"L'Edizione delle {row['slot']} è pronta", "body": body, "url": "/", "tag": "edizione", "badge": badge},
        )
