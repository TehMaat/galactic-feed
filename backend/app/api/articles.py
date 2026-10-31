"""Articoli: Flusso con filtri e ricerca, lettura, letti e salvati, azioni fatte offline."""

from __future__ import annotations

import json
import math
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import iso, now
from ..deps import AppContext, User, current_user, get_ctx, get_db
from ..reading import query
from ..reading.query import VIEWS, ArticleFilter
from .common import prefs_with_defaults
from .images import proxied, proxy_images_in_html

router = APIRouter(prefix="/api/articles", tags=["articoli"])

PAGE_SIZE = 30
WORDS_PER_MINUTE = 220
NOT_FOUND = "Articolo non trovato."


def make_filter(
    user: User,
    view: str = "tutti",
    folder: str | None = None,
    source: int | None = None,
    q: str = "",
    show_muted: bool = False,
) -> ArticleFilter:
    if view not in VIEWS:
        raise HTTPException(status_code=422, detail="Filtro sconosciuto.")
    f = ArticleFilter(view=view, source=source, q=q or "", show_muted=show_muted)
    if folder == "none":
        f.no_folder = True
    elif folder:
        if not folder.isdigit():
            raise HTTPException(status_code=422, detail="Cartella non valida.")
        f.folder = int(folder)
    f.dedupe = bool(prefs_with_defaults(user.prefs)["dedupe"])
    return f


def filter_params(
    view: str = Query("tutti", description="tutti · perte · nonletti · video · salvati"),
    folder: str | None = Query(None, description="id della cartella, oppure «none» per le fonti senza cartella"),
    source: int | None = Query(None, description="id della fonte"),
    q: str = Query("", max_length=200, description="ricerca full-text"),
    show_muted: bool = Query(False, description="mostra anche gli articoli nascosti dalle parole silenziate"),
    user: User = Depends(current_user),
) -> ArticleFilter:
    return make_filter(user, view, folder, source, q, show_muted)


def _cursor(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    try:
        a, b = raw.split(":")
        return int(a), int(b)
    except ValueError:
        raise HTTPException(status_code=422, detail="Cursore non valido.")


def item_payload(row: sqlite3.Row, secret: bytes, others: list[dict] | None = None) -> dict:
    source_title = row["sub_title"] or row["feed_title"] or ""
    minutes = None if row["video_id"] else max(1, math.ceil((row["word_count"] or 0) / WORDS_PER_MINUTE))
    return {
        "id": row["id"],
        "title": row["title"],
        "excerpt": row["excerpt"],
        "url": row["url"],
        "author": row["author"],
        "image": proxied(secret, row["image_url"]),
        "published_at": iso(row["published_at"]),
        "source": {"id": row["sub_id"], "title": source_title, "kind": row["kind"], "folder_id": row["folder_id"]},
        "video": bool(row["video_id"]),
        "video_id": row["video_id"],
        "reading_minutes": minutes,
        "read": row["read_at"] is not None,
        "saved": row["saved_at"] is not None,
        "saved_at": iso(row["saved_at"]),
        "match": {"keyword": row["keyword"], "level": row["level"]} if row["level"] else None,
        "muted": bool(row["muted"]),
        "also_on": others or [],
    }


@router.get("")
def list_articles(
    f: ArticleFilter = Depends(filter_params),
    cursor: str | None = None,
    limit: int = Query(PAGE_SIZE, ge=1, le=100),
    user: User = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    rows, next_cursor = query.list_page(conn, user.id, f, _cursor(cursor), limit)
    ids = [r["id"] for r in rows]
    details = query.article_rows(conn, user.id, ids)
    clusters = {r["cluster_id"]: r["id"] for r in rows if r["dup"] > 1}
    others = query.also_on(conn, user.id, clusters)
    items = [item_payload(details[r["id"]], ctx.secret, others.get(r["cluster_id"])) for r in rows if r["id"] in details]
    hidden = 0 if (f.show_muted or f.view == "salvati" or cursor) else query.count(conn, user.id, f, muted=True)
    return {
        "items": items,
        "next_cursor": f"{next_cursor[0]}:{next_cursor[1]}" if next_cursor else None,
        "hidden": hidden,
        "server_time": iso(now()),
    }


@router.get("/counts")
def article_counts(
    f: ArticleFilter = Depends(filter_params), user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)
):
    return query.counts(conn, user.id, f)


def _visible_or_404(conn: sqlite3.Connection, user_id: int, article_id: int) -> None:
    if not query.is_visible(conn, user_id, article_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)


@router.get("/{article_id}")
def article(
    article_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    _visible_or_404(conn, user.id, article_id)
    row = query.article_rows(conn, user.id, [article_id], full=True)[article_id]
    others = query.also_on(conn, user.id, {row["cluster_id"]: row["id"]}).get(row["cluster_id"])
    payload = item_payload(row, ctx.secret, others)
    full = row["full_status"] == "ok" and row["full_html"]
    payload["content_html"] = proxy_images_in_html(ctx.secret, row["full_html"] if full else row["content_html"])
    payload["full_text"] = bool(full) or row["full_status"] == "none"
    payload["full_text_status"] = row["full_status"]
    payload["categories"] = json.loads(row["categories"] or "[]")
    payload["site_url"] = row["site_url"]
    return {"article": payload}


# ---------- Letti e salvati ----------


def set_read(conn: sqlite3.Connection, user_id: int, article_id: int, read: bool, ts: int | None = None) -> None:
    """Letto/non letto vale per tutta la notizia: anche i suoi doppioni da altre fonti."""
    ts = ts or now()
    cluster = "SELECT id FROM articles WHERE cluster_id = (SELECT cluster_id FROM articles WHERE id = ?) OR id = ?"
    if read:
        conn.execute(
            "INSERT INTO user_articles (user_id, article_id, read_at)"
            f" SELECT ?, id, ? FROM ({cluster}) WHERE true"
            " ON CONFLICT (user_id, article_id) DO UPDATE SET read_at = COALESCE(user_articles.read_at, excluded.read_at)",
            (user_id, ts, article_id, article_id),
        )
    else:
        conn.execute(
            f"UPDATE user_articles SET read_at = NULL WHERE user_id = ? AND article_id IN ({cluster})",
            (user_id, article_id, article_id),
        )
        conn.execute("DELETE FROM user_articles WHERE user_id = ? AND read_at IS NULL AND saved_at IS NULL", (user_id,))


def set_saved(conn: sqlite3.Connection, user_id: int, article_id: int, saved: bool, ts: int | None = None) -> None:
    ts = ts or now()
    if saved:
        conn.execute(
            "INSERT INTO user_articles (user_id, article_id, saved_at) VALUES (?, ?, ?)"
            " ON CONFLICT (user_id, article_id) DO UPDATE SET saved_at = COALESCE(user_articles.saved_at, excluded.saved_at)",
            (user_id, article_id, ts),
        )
    else:
        conn.execute("UPDATE user_articles SET saved_at = NULL WHERE user_id = ? AND article_id = ?", (user_id, article_id))
        conn.execute(
            "DELETE FROM user_articles WHERE user_id = ? AND article_id = ? AND read_at IS NULL AND saved_at IS NULL",
            (user_id, article_id),
        )


def _state(conn: sqlite3.Connection, user_id: int, article_id: int) -> dict:
    row = conn.execute(
        "SELECT read_at, saved_at FROM user_articles WHERE user_id = ? AND article_id = ?", (user_id, article_id)
    ).fetchone()
    return {
        "id": article_id,
        "read": bool(row and row["read_at"]),
        "saved": bool(row and row["saved_at"]),
    }


def _toggle(kind: str, value: bool):
    def endpoint(article_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
        _visible_or_404(conn, user.id, article_id)
        with conn:
            (set_read if kind == "read" else set_saved)(conn, user.id, article_id, value)
        return _state(conn, user.id, article_id)

    return endpoint


router.put("/{article_id}/read", summary="Segna come letto")(_toggle("read", True))
router.delete("/{article_id}/read", summary="Segna come non letto")(_toggle("read", False))
router.put("/{article_id}/saved", summary="Salva")(_toggle("saved", True))
router.delete("/{article_id}/saved", summary="Togli dai salvati")(_toggle("saved", False))


class MarkRead(BaseModel):
    view: str = "tutti"
    folder: str | None = None
    source: int | None = None
    q: str = ""
    # Solo gli articoli arrivati fino a questo momento (quello in cui l'elenco è stato caricato).
    before: str | None = None


@router.post("/mark-read")
def mark_read(body: MarkRead, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """«Segna tutti come letti» sugli articoli del filtro in uso."""
    f = make_filter(user, body.view, body.folder, body.source, body.q)
    f.dedupe = False
    if body.before:
        from datetime import datetime

        try:
            f.before = int(datetime.fromisoformat(body.before.replace("Z", "+00:00")).timestamp())
        except ValueError:
            raise HTTPException(status_code=422, detail="Data non valida.")
    f.view = "nonletti" if f.view == "tutti" else f.view
    cte, params = query.visible_cte(user.id, f)
    ts = now()
    with conn:
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS to_mark (id INTEGER PRIMARY KEY)")
        conn.execute("DELETE FROM to_mark")
        conn.execute(f"WITH {cte} INSERT INTO to_mark (id) SELECT id FROM vis WHERE read_at IS NULL", params)
        marked = conn.execute("SELECT COUNT(*) FROM to_mark").fetchone()[0]
        # Anche i doppioni delle notizie segnate, come per il singolo articolo.
        conn.execute(
            "INSERT INTO user_articles (user_id, article_id, read_at)"
            " SELECT ?, a.id, ? FROM articles a"
            " WHERE a.id IN (SELECT id FROM to_mark)"
            " OR a.cluster_id IN (SELECT cluster_id FROM articles WHERE id IN (SELECT id FROM to_mark))"
            " ON CONFLICT (user_id, article_id) DO UPDATE SET read_at = COALESCE(user_articles.read_at, excluded.read_at)",
            (user.id, ts),
        )
        conn.execute("DELETE FROM to_mark")
    return {"marked": marked}


class SyncAction(BaseModel):
    id: int
    read: bool | None = None
    saved: bool | None = None


class SyncBody(BaseModel):
    actions: list[SyncAction] = Field(default_factory=list, max_length=500)


@router.post("/sync")
def sync(body: SyncBody, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """Le azioni fatte senza rete (letto, salvato), applicate in ordine quando torna la connessione."""
    applied = skipped = 0
    with conn:
        for action in body.actions:
            if not query.is_visible(conn, user.id, action.id):
                # Articolo cancellato nel frattempo, o di una fonte che l'utente non segue più.
                skipped += 1
                continue
            if action.read is not None:
                set_read(conn, user.id, action.id, action.read)
            if action.saved is not None:
                set_saved(conn, user.id, action.id, action.saved)
            applied += 1
    return {"applied": applied, "skipped": skipped}
