"""Edizione: l'ultima composta, una precedente, oppure una nuova adesso."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..db import iso, now
from ..deps import AppContext, User, current_user, get_ctx, get_db
from ..reading import edition, query
from .articles import item_payload
from .common import prefs_with_defaults

router = APIRouter(prefix="/api/editions", tags=["edizione"])

NONE_TITLE = "Senza cartella"
FONTI_TITLE = "Dalle tue fonti"


def _schedule(user: User, ctx: AppContext) -> dict:
    prefs = prefs_with_defaults(user.prefs)
    times = prefs["edition_times"]
    next_ts, next_time = edition.next_slot(times, ctx.instance.get("timezone"), now())
    return {"enabled": prefs["edition"], "times": times, "next_at": iso(next_ts), "next_time": next_time}


def edition_payload(conn: sqlite3.Connection, user: User, ctx: AppContext, row: sqlite3.Row) -> dict:
    items = conn.execute(
        "SELECT article_id, section FROM edition_items WHERE edition_id = ? ORDER BY position", (row["id"],)
    ).fetchall()
    details = query.article_rows(conn, user.id, [i["article_id"] for i in items])
    folders = {
        str(f["id"]): f
        for f in conn.execute("SELECT id, name, color, position FROM folders WHERE user_id = ? ORDER BY position, name", (user.id,))
    }
    order = list(folders)
    hero = None
    groups: dict[str, list[dict]] = {}
    for it in items:
        r = details.get(it["article_id"])
        if r is None or (r["sub_id"] is None and r["saved_at"] is None):
            continue  # fonte non più seguita
        payload = item_payload(r, ctx.secret)
        if it["section"] == "hero":
            hero = payload
            continue
        key = it["section"]
        if key not in ("none", "fonti") and key not in folders:
            key = "none"  # cartella cancellata nel frattempo
        groups.setdefault(key, []).append(payload)
    sections = []
    for key in [*order, "none", "fonti"]:
        if key not in groups:
            continue
        if key in folders:
            title, color = folders[key]["name"], folders[key]["color"]
        else:
            title, color = (NONE_TITLE if key == "none" else FONTI_TITLE), "grigio"
        sections.append({"key": key, "title": title, "color": color, "items": groups[key]})
    return {
        "id": row["id"],
        "number": row["number"],
        "slot": row["slot"],
        "created_at": iso(row["created_at"]),
        "since": iso(row["since"]),
        "stats": json.loads(row["stats"] or "{}"),
        "hero": hero,
        "sections": sections,
    }


@router.get("/latest")
def latest(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    row = conn.execute("SELECT * FROM editions WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1", (user.id,)).fetchone()
    return {
        "edition": edition_payload(conn, user, ctx, row) if row else None,
        "schedule": _schedule(user, ctx),
    }


@router.get("/{edition_id}")
def get_edition(
    edition_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    row = conn.execute("SELECT * FROM editions WHERE id = ? AND user_id = ?", (edition_id, user.id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Edizione non trovata.")
    return {"edition": edition_payload(conn, user, ctx, row), "schedule": _schedule(user, ctx)}


@router.post("", status_code=201)
def compose_now(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    """«Componi adesso»: un'edizione con le notizie arrivate dall'ultima."""
    prefs = prefs_with_defaults(user.prefs)
    last = conn.execute("SELECT MAX(created_at) FROM editions WHERE user_id = ?", (user.id,)).fetchone()[0]
    if last and now() - last < 60:
        raise HTTPException(status_code=429, detail="Hai appena composto un'edizione: riprova tra un minuto.")
    slot = datetime.fromtimestamp(now(), edition.zone(ctx.instance.get("timezone"))).strftime("%H:%M")
    edition_id = edition.compose(conn, user.id, slot, dedupe=prefs["dedupe"])
    row = conn.execute("SELECT * FROM editions WHERE id = ?", (edition_id,)).fetchone()
    return {"edition": edition_payload(conn, user, ctx, row), "schedule": _schedule(user, ctx)}
