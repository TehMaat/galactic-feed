"""Controllo di un feed: download, lettura, salvataggio dei nuovi articoli.

- Manda ETag e Last-Modified: se il feed non è cambiato il sito risponde 304 e non
  si riscarica niente.
- Dopo un errore i controlli si diradano (doppio dell'intervallo a ogni errore, fino
  a una volta al giorno) e si rispetta l'header Retry-After.
- Un feed seguito da più utenti si scarica una volta sola.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass, field

from ..db import now
from ..reading.dedupe import find_cluster
from ..reading.matching import apply_new_articles
from ..reading.text import title_key
from .extract import initial_full_status
from .net import FetchError, fetch
from .parser import Entry, NotAFeed, parse_feed
from .sanitize import canonical_url, html_to_text, normalize_feed_url

log = logging.getLogger("galactic_feed.fetcher")

CONCURRENCY = 4
MAX_ENTRIES = 200
MAX_BACKOFF_MIN = 24 * 60
NOT_A_FEED = "L'indirizzo non contiene un feed RSS o Atom valido."


@dataclass
class FetchOutcome:
    feed_id: int
    ok: bool
    new: int = 0
    not_modified: bool = False
    error: str | None = None
    new_ids: list[int] = field(default_factory=list)


def next_delay_minutes(interval: int, error_count: int, retry_after: int | None = None) -> int:
    delay = interval if error_count == 0 else min(interval * 2 ** min(error_count, 8), MAX_BACKOFF_MIN)
    if retry_after:
        delay = max(delay, min(-(-retry_after // 60), MAX_BACKOFF_MIN))
    return max(1, delay)


def store_entries(conn: sqlite3.Connection, feed_id: int, entries: list[Entry]) -> list[int]:
    """Salva gli articoli nuovi e aggiorna quelli modificati. Restituisce gli id dei nuovi."""
    ts = now()
    new_ids: list[int] = []
    with conn:
        for e in entries[:MAX_ENTRIES]:
            published = min(e.published_at or ts, ts)
            canon = f"youtube:{e.video_id}" if e.video_id else canonical_url(e.url)
            text = html_to_text(e.content_html)
            existing = conn.execute(
                "SELECT id, title, content_html FROM articles WHERE feed_id = ? AND guid = ?", (feed_id, e.guid)
            ).fetchone()
            if existing is None:
                key = title_key(e.title)
                cur = conn.execute(
                    "INSERT INTO articles (feed_id, guid, url, canonical_url, title, title_key, author, excerpt, categories,"
                    " content_html, full_status, image_url, video_id, word_count, published_at, fetched_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        feed_id, e.guid, e.url, canon, e.title, key, e.author, e.excerpt, e.categories_json,
                        e.content_html, initial_full_status(e.needs_full_text, published), e.image_url,
                        e.video_id, e.word_count, published, ts,
                    ),
                )
                cluster = find_cluster(conn, cur.lastrowid, feed_id, canon, key, published)
                conn.execute("UPDATE articles SET cluster_id = ? WHERE id = ?", (cluster, cur.lastrowid))
                conn.execute(
                    "INSERT INTO articles_fts (rowid, title, author, body) VALUES (?, ?, ?, ?)",
                    (cur.lastrowid, e.title, e.author, text or e.excerpt),
                )
                new_ids.append(cur.lastrowid)
            elif existing["title"] != e.title or existing["content_html"] != e.content_html:
                conn.execute(
                    "UPDATE articles SET title = ?, title_key = ?, author = ?, excerpt = ?, categories = ?, content_html = ?,"
                    " image_url = CASE WHEN ? != '' THEN ? ELSE image_url END WHERE id = ?",
                    (e.title, title_key(e.title), e.author, e.excerpt, e.categories_json, e.content_html,
                     e.image_url, e.image_url, existing["id"]),
                )
                conn.execute(
                    "UPDATE articles_fts SET title = ?, author = ? WHERE rowid = ?", (e.title, e.author, existing["id"])
                )
    return new_ids


class Fetcher:
    def __init__(self, ctx):
        self.ctx = ctx
        self._sem = asyncio.Semaphore(CONCURRENCY)
        self._running: dict[int, asyncio.Task] = {}

    def fetch_feed(self, feed_id: int) -> asyncio.Task:
        """Avvia il controllo (o riusa quello già in corso per lo stesso feed)."""
        task = self._running.get(feed_id)
        if task is None or task.done():
            task = asyncio.ensure_future(self._fetch(feed_id))
            self._running[feed_id] = task
            task.add_done_callback(lambda t, fid=feed_id: self._running.pop(fid, None) if self._running.get(fid) is t else None)
        return task

    def _load(self, feed_id: int):
        with self.ctx.db.session() as conn:
            return conn.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,)).fetchone()

    async def _fetch(self, feed_id: int) -> FetchOutcome:
        feed = await asyncio.to_thread(self._load, feed_id)
        if feed is None:
            return FetchOutcome(feed_id, ok=False, error="Fonte non trovata.")
        async with self._sem:
            try:
                got = await fetch(self.ctx.http, feed["url"], etag=feed["etag"], last_modified=feed["last_modified"])
            except FetchError as exc:
                return await asyncio.to_thread(self._record_error, feed, exc.message, exc.status, exc.retry_after)
            except Exception:
                log.exception("Errore inatteso scaricando %s", feed["url"])
                return await asyncio.to_thread(self._record_error, feed, "Errore inatteso durante il download.", None, None)

        if got.status == 304:
            return await asyncio.to_thread(self._record_success, feed, got, None, [])
        try:
            parsed = await asyncio.to_thread(parse_feed, got.content, got.url, got.content_type)
        except NotAFeed:
            return await asyncio.to_thread(self._record_error, feed, NOT_A_FEED, got.status, None)
        except Exception:
            log.exception("Errore leggendo il feed %s", feed["url"])
            return await asyncio.to_thread(self._record_error, feed, NOT_A_FEED, got.status, None)

        def save():
            with self.ctx.db.session() as conn:
                new_ids = store_entries(conn, feed_id, parsed.entries)
                # Interessi e parole silenziate di chi segue il feed, subito.
                apply_new_articles(conn, feed_id, new_ids)
            return self._record_success(feed, got, parsed, new_ids)

        outcome = await asyncio.to_thread(save)
        if outcome.new:
            await self.ctx.hooks.emit_new_articles(feed_id, outcome.new_ids)
        return outcome

    def _record_success(self, feed, got, parsed, new_ids: list[int]) -> FetchOutcome:
        ts = now()
        delay = next_delay_minutes(feed["interval_min"], 0)
        with self.ctx.db.session() as conn, conn:
            conn.execute(
                "UPDATE feeds SET last_fetch_at = ?, last_success_at = ?, last_status = ?, error_message = NULL,"
                " error_since = NULL, error_count = 0, next_fetch_at = ?,"
                " etag = COALESCE(?, etag), last_modified = COALESCE(?, last_modified),"
                " title = CASE WHEN ? != '' THEN ? ELSE title END,"
                " site_url = CASE WHEN ? != '' THEN ? ELSE site_url END,"
                " kind = COALESCE(?, kind) WHERE id = ?",
                (
                    ts, ts, got.status, ts + delay * 60,
                    got.headers.get("etag"), got.headers.get("last-modified"),
                    parsed.title if parsed else "", parsed.title if parsed else "",
                    parsed.site_url if parsed else "", parsed.site_url if parsed else "",
                    parsed.kind if parsed else None, feed["id"],
                ),
            )
            if got.permanent_redirect:
                new_url = normalize_feed_url(got.permanent_redirect)
                taken = conn.execute("SELECT 1 FROM feeds WHERE url = ? AND id != ?", (new_url, feed["id"])).fetchone()
                if not taken:
                    log.info("Il feed %s si è spostato in %s", feed["url"], new_url)
                    conn.execute("UPDATE feeds SET url = ?, etag = NULL, last_modified = NULL WHERE id = ?", (new_url, feed["id"]))
        return FetchOutcome(feed["id"], ok=True, new=len(new_ids), not_modified=got.status == 304, new_ids=new_ids)

    def _record_error(self, feed, message: str, status: int | None, retry_after: int | None) -> FetchOutcome:
        ts = now()
        errors = feed["error_count"] + 1
        delay = next_delay_minutes(feed["interval_min"], errors, retry_after)
        with self.ctx.db.session() as conn, conn:
            conn.execute(
                "UPDATE feeds SET last_fetch_at = ?, last_status = ?, error_message = ?,"
                " error_since = COALESCE(error_since, ?), error_count = ?, next_fetch_at = ? WHERE id = ?",
                (ts, status, message, ts, errors, ts + delay * 60, feed["id"]),
            )
        log.info("Errore sul feed %s: %s", feed["url"], message)
        return FetchOutcome(feed["id"], ok=False, error=message)
