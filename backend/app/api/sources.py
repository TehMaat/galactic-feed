"""Fonti dell'utente: ricerca dei feed, aggiunta, modifica, rimozione e aggiornamento."""

from __future__ import annotations

import asyncio
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import iso, now
from ..deps import AppContext, User, current_user, get_ctx, get_db
from ..feeds.discovery import NothingFound, discover
from ..feeds.net import FetchError, normalize_input_url
from ..feeds.sanitize import normalize_feed_url
from .folders import check_folder

router = APIRouter(prefix="/api/sources", tags=["fonti"])

INTERVALS = [15, 30, 60, 180, 360, 720, 1440]
DEFAULT_INTERVAL = 30
# Un aggiornamento manuale non riscarica i feed controllati nell'ultimo minuto.
REFRESH_MIN_SECONDS = 60
REFRESH_WAIT_SECONDS = 25


def check_interval(value: int | None) -> int:
    if value is None:
        return DEFAULT_INTERVAL
    if value not in INTERVALS:
        raise HTTPException(status_code=422, detail="Intervallo non valido: scegli tra 15 minuti e 24 ore.")
    return value


def feed_kind(url: str) -> str:
    return "youtube" if "youtube.com/feeds/videos.xml" in url else "rss"


def ensure_feed(conn: sqlite3.Connection, url: str, title: str = "") -> tuple[int, bool]:
    """Id del feed con questo indirizzo, creandolo se nessuno lo segue ancora."""
    row = conn.execute("SELECT id FROM feeds WHERE url = ?", (url,)).fetchone()
    if row:
        return row["id"], False
    cur = conn.execute(
        "INSERT INTO feeds (url, kind, title, next_fetch_at, created_at) VALUES (?, ?, ?, 0, ?)",
        (url, feed_kind(url), title, now()),
    )
    return cur.lastrowid, True


def recompute_interval(conn: sqlite3.Connection, feed_id: int) -> None:
    """L'intervallo del feed è il più breve tra quelli scelti da chi lo segue."""
    conn.execute(
        "UPDATE feeds SET interval_min = COALESCE((SELECT MIN(interval_min) FROM subscriptions WHERE feed_id = ?), interval_min)"
        " WHERE id = ?",
        (feed_id, feed_id),
    )
    conn.execute(
        "UPDATE feeds SET next_fetch_at = MIN(next_fetch_at, last_fetch_at + interval_min * 60)"
        " WHERE id = ? AND last_fetch_at IS NOT NULL AND error_count = 0",
        (feed_id,),
    )


def subscribe(conn: sqlite3.Connection, user_id: int, feed_id: int, folder_id: int | None, title: str, interval: int) -> int | None:
    cur = conn.execute(
        "INSERT OR IGNORE INTO subscriptions (user_id, feed_id, folder_id, title, interval_min, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, feed_id, folder_id, title, interval, now()),
    )
    if cur.rowcount == 0:
        return None
    recompute_interval(conn, feed_id)
    return cur.lastrowid


def remove_feed_if_orphan(conn: sqlite3.Connection, feed_id: int) -> None:
    conn.execute(
        "DELETE FROM feeds WHERE id = ? AND NOT EXISTS (SELECT 1 FROM subscriptions WHERE feed_id = ?)", (feed_id, feed_id)
    )


def source_status(row: sqlite3.Row) -> str:
    """ok · warn (problema passeggero) · err (non funziona) · pending (mai controllata)."""
    if row["last_fetch_at"] is None:
        return "pending"
    if row["error_message"]:
        return "err" if row["last_success_at"] is None or row["error_count"] >= 3 else "warn"
    return "ok"


SOURCE_SELECT = (
    "SELECT s.id, s.feed_id, s.folder_id, s.title AS custom_title, s.interval_min, s.created_at,"
    " f.url, f.kind, f.title AS feed_title, f.site_url, f.last_fetch_at, f.last_success_at, f.next_fetch_at,"
    " f.error_message, f.error_since, f.error_count, f.last_status,"
    " (SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id) AS articles"
    " FROM subscriptions s JOIN feeds f ON f.id = s.feed_id"
)


def source_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "feed_id": row["feed_id"],
        "title": row["custom_title"] or row["feed_title"] or row["url"],
        "custom_title": row["custom_title"],
        "feed_title": row["feed_title"],
        "url": row["url"],
        "site_url": row["site_url"],
        "kind": row["kind"],
        "folder_id": row["folder_id"],
        "interval_min": row["interval_min"],
        "status": source_status(row),
        "error": row["error_message"],
        "error_since": iso(row["error_since"]),
        "last_status": row["last_status"],
        "last_fetch_at": iso(row["last_fetch_at"]),
        "last_success_at": iso(row["last_success_at"]),
        "next_fetch_at": iso(row["next_fetch_at"]) if row["next_fetch_at"] else None,
        "articles": row["articles"],
        "created_at": iso(row["created_at"]),
    }


def get_source(conn: sqlite3.Connection, user_id: int, source_id: int) -> sqlite3.Row:
    row = conn.execute(SOURCE_SELECT + " WHERE s.id = ? AND s.user_id = ?", (source_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Fonte non trovata.")
    return row


def list_sources(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        SOURCE_SELECT + " WHERE s.user_id = ? ORDER BY COALESCE(NULLIF(s.title, ''), NULLIF(f.title, ''), f.url) COLLATE NOCASE",
        (user_id,),
    ).fetchall()
    return [source_payload(r) for r in rows]


# ---------- Endpoint ----------


class DiscoverBody(BaseModel):
    url: str


@router.post("/discover")
async def discover_feeds(
    body: DiscoverBody, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    """Dall'indirizzo di un sito (o di un canale YouTube) ai feed che si possono seguire."""
    try:
        candidates = await discover(ctx.http, body.url)
    except NothingFound as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=exc.message)
    followed = {
        r["url"]
        for r in conn.execute(
            "SELECT f.url FROM subscriptions s JOIN feeds f ON f.id = s.feed_id WHERE s.user_id = ?", (user.id,)
        )
    }
    items = []
    for c in candidates:
        d = c.as_dict()
        d["last_published"] = iso(c.last_published)
        d["already_followed"] = c.url in followed
        items.append(d)
    return {"candidates": items}


@router.get("")
def sources(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return {"sources": list_sources(conn, user.id), "intervals": INTERVALS}


class NewSource(BaseModel):
    url: str
    title: str = ""
    folder_id: int | None = None
    interval_min: int | None = None


@router.post("", status_code=201)
async def add_source(
    body: NewSource, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    try:
        url = normalize_feed_url(normalize_input_url(body.url))
    except FetchError as exc:
        raise HTTPException(status_code=422, detail=exc.message)
    interval = check_interval(body.interval_min)
    check_folder(conn, user.id, body.folder_id)
    title = " ".join(body.title.split())[:120]

    existing = conn.execute(
        "SELECT s.id FROM subscriptions s JOIN feeds f ON f.id = s.feed_id WHERE s.user_id = ? AND f.url = ?",
        (user.id, url),
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Segui già questa fonte.")

    with conn:
        feed_id, created = ensure_feed(conn, url)
    if created:
        # Primo controllo subito: se l'indirizzo non è un feed lo si dice adesso.
        outcome = await ctx.fetcher.fetch_feed(feed_id)
        if not outcome.ok:
            with conn:
                remove_feed_if_orphan(conn, feed_id)
            raise HTTPException(status_code=422, detail=f"Non riesco ad aggiungere questa fonte. {outcome.error}")
    with conn:
        source_id = subscribe(conn, user.id, feed_id, body.folder_id, title, interval)
    if source_id is None:
        raise HTTPException(status_code=409, detail="Segui già questa fonte.")
    ctx.scheduler.wake()
    return {"source": source_payload(get_source(conn, user.id, source_id))}


class SourcePatch(BaseModel):
    title: str | None = None
    folder_id: int | None = None
    interval_min: int | None = None


@router.patch("/{source_id}")
def update_source(
    source_id: int, body: SourcePatch, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)
):
    row = get_source(conn, user.id, source_id)
    fields = body.model_fields_set
    title = row["custom_title"] if "title" not in fields else " ".join((body.title or "").split())[:120]
    folder_id = row["folder_id"]
    if "folder_id" in fields:
        check_folder(conn, user.id, body.folder_id)
        folder_id = body.folder_id
    interval = row["interval_min"] if body.interval_min is None else check_interval(body.interval_min)
    with conn:
        conn.execute(
            "UPDATE subscriptions SET title = ?, folder_id = ?, interval_min = ? WHERE id = ?",
            (title, folder_id, interval, source_id),
        )
        recompute_interval(conn, row["feed_id"])
    return {"source": source_payload(get_source(conn, user.id, source_id))}


@router.delete("/{source_id}")
def delete_source(source_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    row = get_source(conn, user.id, source_id)
    with conn:
        conn.execute("DELETE FROM subscriptions WHERE id = ?", (source_id,))
        recompute_interval(conn, row["feed_id"])
        # Se nessun altro la segue, il feed e i suoi articoli spariscono.
        remove_feed_if_orphan(conn, row["feed_id"])
    return {"ok": True}


@router.post("/{source_id}/refresh")
async def refresh_source(
    source_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    row = get_source(conn, user.id, source_id)
    outcome = await ctx.fetcher.fetch_feed(row["feed_id"])
    ctx.scheduler.wake()
    return {"source": source_payload(get_source(conn, user.id, source_id)), "new_articles": outcome.new}


@router.post("/refresh")
async def refresh_all(
    user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    """Il pulsante «Aggiorna»: controlla subito le fonti dell'utente.

    Aspetta al massimo 25 secondi; i feed più lenti finiscono in sottofondo.
    """
    recent = now() - REFRESH_MIN_SECONDS
    rows = conn.execute(
        "SELECT f.id, f.last_fetch_at FROM subscriptions s JOIN feeds f ON f.id = s.feed_id WHERE s.user_id = ?",
        (user.id,),
    ).fetchall()
    to_fetch = [r["id"] for r in rows if r["last_fetch_at"] is None or r["last_fetch_at"] < recent]
    tasks = [ctx.fetcher.fetch_feed(fid) for fid in to_fetch]
    done, pending = (await asyncio.wait(tasks, timeout=REFRESH_WAIT_SECONDS)) if tasks else (set(), set())
    outcomes = [t.result() for t in done if not t.cancelled() and t.exception() is None]
    ctx.scheduler.wake()
    return {
        "sources": len(rows),
        "checked": len(outcomes),
        "skipped": len(rows) - len(to_fetch),
        "in_progress": len(pending),
        "new_articles": sum(o.new for o in outcomes),
        "errors": sum(1 for o in outcomes if not o.ok),
    }
