"""Tag delle fonti (issue #17): proposti in automatico, modificabili, usati come filtri.

Ogni utente ha i propri tag, anche sulle fonti che altri seguono. Una fonte può averne
più di uno (a differenza delle cartelle).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..db import now
from ..deps import User, current_user, get_db
from ..reading import tagging
from .folders import COLORS

router = APIRouter(prefix="/api/tags", tags=["tag"])

MAX_TAGS = 100


def clean_tag(value: str) -> str:
    value = " ".join((value or "").split())
    if not value:
        raise ValueError("Dai un nome al tag.")
    if len(value) > 30:
        raise ValueError("Il nome del tag può avere al massimo 30 caratteri.")
    return value


def list_tags(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT t.*, (SELECT COUNT(*) FROM source_tags st WHERE st.tag_id = t.id AND st.origin != 'rejected') AS sources"
        " FROM tags t WHERE t.user_id = ? ORDER BY t.position, t.name COLLATE NOCASE",
        (user_id,),
    ).fetchall()
    return [
        {"id": r["id"], "name": r["name"], "color": r["color"], "position": r["position"], "in_feed": bool(r["in_feed"]), "sources": r["sources"]}
        for r in rows
    ]


def tags_by_source(conn: sqlite3.Connection, user_id: int, subscription_ids: list[int] | None = None) -> dict[int, list[dict]]:
    """I tag di ogni fonte dell'utente (senza quelli tolti), nell'ordine dei tag."""
    sql = (
        "SELECT st.subscription_id, st.origin, t.id, t.name, t.color FROM source_tags st"
        " JOIN tags t ON t.id = st.tag_id WHERE t.user_id = ? AND st.origin != 'rejected'"
    )
    params: list = [user_id]
    if subscription_ids is not None:
        if not subscription_ids:
            return {}
        sql += f" AND st.subscription_id IN ({','.join('?' * len(subscription_ids))})"
        params += subscription_ids
    out: dict[int, list[dict]] = {}
    for r in conn.execute(sql + " ORDER BY t.position, t.name COLLATE NOCASE", params):
        out.setdefault(r["subscription_id"], []).append({"id": r["id"], "name": r["name"], "color": r["color"], "origin": r["origin"]})
    return out


def _get_tag(conn: sqlite3.Connection, user_id: int, tag_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tags WHERE id = ? AND user_id = ?", (tag_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Tag non trovato.")
    return row


def _payload(conn: sqlite3.Connection, user_id: int) -> dict:
    return {"tags": list_tags(conn, user_id), "colors": COLORS}


@router.get("")
def tags(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return _payload(conn, user.id)


class NewTag(BaseModel):
    name: str
    color: str | None = None

    _n = field_validator("name")(clean_tag)


@router.post("", status_code=201)
def create_tag(body: NewTag, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM tags WHERE user_id = ?", (user.id,)).fetchone()[0] >= MAX_TAGS:
        raise HTTPException(status_code=422, detail=f"Puoi avere al massimo {MAX_TAGS} tag.")
    if conn.execute("SELECT 1 FROM tags WHERE user_id = ? AND name = ?", (user.id, body.name)).fetchone():
        raise HTTPException(status_code=409, detail="Hai già un tag con questo nome.")
    with conn:
        tag_id = tagging.tag_id_for(conn, user.id, body.name)
        if body.color in COLORS:
            conn.execute("UPDATE tags SET color = ? WHERE id = ?", (body.color, tag_id))
    return _payload(conn, user.id)


class TagPatch(BaseModel):
    name: str | None = None
    color: str | None = None
    in_feed: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return clean_tag(v) if v is not None else None

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if v is not None and v not in COLORS:
            raise ValueError("Colore non valido.")
        return v


@router.patch("/{tag_id}")
def update_tag(tag_id: int, body: TagPatch, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    row = _get_tag(conn, user.id, tag_id)
    in_feed = row["in_feed"] if body.in_feed is None else int(body.in_feed)
    try:
        with conn:
            conn.execute(
                "UPDATE tags SET name = ?, color = ?, in_feed = ? WHERE id = ?",
                (body.name or row["name"], body.color or row["color"], in_feed, tag_id),
            )
            if body.name and body.name != row["name"]:
                # Un tag rinominato è una scelta dell'utente: le fonti che lo hanno lo tengono.
                conn.execute("UPDATE source_tags SET origin = 'user' WHERE tag_id = ? AND origin = 'auto'", (tag_id,))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Hai già un tag con questo nome: per metterli insieme usa «Unisci».")
    return _payload(conn, user.id)


class Order(BaseModel):
    ids: list[int] = Field(max_length=MAX_TAGS)


@router.put("/order")
def reorder(body: Order, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """Ordine dei tag (anche delle chip nel Flusso)."""
    with conn:
        for position, tag_id in enumerate(body.ids):
            conn.execute("UPDATE tags SET position = ? WHERE id = ? AND user_id = ?", (position, tag_id, user.id))
    return _payload(conn, user.id)


class Merge(BaseModel):
    into: int


@router.post("/{tag_id}/merge")
def merge(tag_id: int, body: Merge, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """Unisce due tag: le fonti del primo passano al secondo, poi il primo sparisce."""
    if tag_id == body.into:
        raise HTTPException(status_code=422, detail="Scegli un tag diverso.")
    _get_tag(conn, user.id, tag_id)
    _get_tag(conn, user.id, body.into)
    with conn:
        conn.execute(
            "INSERT INTO source_tags (subscription_id, tag_id, origin, created_at)"
            " SELECT subscription_id, ?, 'user', ? FROM source_tags WHERE tag_id = ? AND origin != 'rejected'"
            " ON CONFLICT (subscription_id, tag_id) DO UPDATE SET origin = 'user'",
            (body.into, now(), tag_id),
        )
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    return _payload(conn, user.id)


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    _get_tag(conn, user.id, tag_id)
    with conn:
        conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    return _payload(conn, user.id)


def set_source_tags(conn: sqlite3.Connection, user_id: int, subscription_id: int, names: list[str]) -> None:
    """I tag della fonte diventano esattamente questi (scelta dell'utente).

    Quelli proposti che l'utente tiene diventano suoi («user»); quelli che toglie restano
    come «rejected», così la proposta automatica non li rimette.
    """
    wanted = []
    for name in names:
        name = clean_tag(name)
        tag_id = tagging.tag_id_for(conn, user_id, name)
        if tag_id not in wanted:
            wanted.append(tag_id)
    ts = now()
    current = {
        r["tag_id"]: r["origin"]
        for r in conn.execute("SELECT tag_id, origin FROM source_tags WHERE subscription_id = ?", (subscription_id,))
    }
    for tag_id, origin in current.items():
        if tag_id in wanted:
            continue
        if origin == "auto":
            conn.execute("UPDATE source_tags SET origin = 'rejected' WHERE subscription_id = ? AND tag_id = ?", (subscription_id, tag_id))
        elif origin == "user":
            conn.execute("DELETE FROM source_tags WHERE subscription_id = ? AND tag_id = ?", (subscription_id, tag_id))
    for tag_id in wanted:
        if current.get(tag_id) != "user":
            conn.execute(
                "INSERT INTO source_tags (subscription_id, tag_id, origin, created_at) VALUES (?, ?, 'user', ?)"
                " ON CONFLICT (subscription_id, tag_id) DO UPDATE SET origin = 'user'",
                (subscription_id, tag_id, ts),
            )
