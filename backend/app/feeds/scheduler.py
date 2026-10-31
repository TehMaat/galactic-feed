"""Scheduler interno: ogni minuto controlla i feed in scadenza e completa i testi.

Non serve cron né un altro container: è un ciclo asincrono che parte con il server.
Le azioni dell'utente (aggiungi fonte, aggiorna) lo svegliano subito con wake().
"""

from __future__ import annotations

import asyncio
import logging

from ..db import now

log = logging.getLogger("galactic_feed.scheduler")

TICK_SECONDS = 60
DUE_BATCH = 100
CLEANUP_EVERY = 6 * 3600


class Scheduler:
    def __init__(self, ctx, tick: int = TICK_SECONDS):
        self.ctx = ctx
        self.tick = tick
        self._event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._last_cleanup = 0
        self.last_run_at: int | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="scheduler")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def wake(self) -> None:
        self._event.set()

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Errore nello scheduler")
            try:
                await asyncio.wait_for(self._event.wait(), self.tick)
            except TimeoutError:
                pass
            self._event.clear()

    def _due_feeds(self) -> list[int]:
        with self.ctx.db.session() as conn:
            rows = conn.execute(
                "SELECT id FROM feeds WHERE next_fetch_at <= ?"
                " AND EXISTS (SELECT 1 FROM subscriptions s WHERE s.feed_id = feeds.id)"
                " ORDER BY next_fetch_at LIMIT ?",
                (now(), DUE_BATCH),
            ).fetchall()
        return [r["id"] for r in rows]

    async def run_once(self) -> None:
        self.last_run_at = now()
        due = await asyncio.to_thread(self._due_feeds)
        if due:
            await asyncio.gather(*(self.ctx.fetcher.fetch_feed(fid) for fid in due), return_exceptions=True)
        # Testi completi a piccoli lotti, finché ce ne sono.
        for _ in range(5):
            if not await self.ctx.extractor.extract_pending():
                break
        if now() - self._last_cleanup > CLEANUP_EVERY:
            self._last_cleanup = now()
            await asyncio.to_thread(cleanup, self.ctx)


SAVED = "EXISTS (SELECT 1 FROM user_articles ua WHERE ua.article_id = articles.id AND ua.saved_at IS NOT NULL)"


def cleanup(ctx) -> None:
    """Toglie gli articoli troppo vecchi e i feed che nessuno segue più. I salvati restano sempre."""
    limit = now() - ctx.settings.retention_days * 86400
    with ctx.db.session() as conn, conn:
        conn.execute(f"DELETE FROM articles WHERE published_at < ? AND fetched_at < ? AND NOT {SAVED}", (limit, limit))
        orphan = "NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.feed_id = articles.feed_id)"
        conn.execute(f"DELETE FROM articles WHERE {orphan} AND NOT {SAVED}")
        conn.execute(
            "DELETE FROM feeds WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.feed_id = feeds.id)"
            " AND NOT EXISTS (SELECT 1 FROM articles a WHERE a.feed_id = feeds.id)"
        )
