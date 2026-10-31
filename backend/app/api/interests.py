"""Interessi (parole chiave con priorità) e parole silenziate."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..db import now
from ..deps import User, current_user, get_db
from ..reading import query
from ..reading.matching import recompute_user
from ..reading.query import ArticleFilter
from ..reading.text import normalize
from .common import prefs_with_defaults

router = APIRouter(prefix="/api/interests", tags=["interessi"])

Level = Literal["alta", "media", "spento"]
MAX_ITEMS = 200


def clean_word(value: str) -> str:
    value = " ".join((value or "").split())
    if not normalize(value):
        raise ValueError("Scrivi una parola o un argomento.")
    if len(value) > 60:
        raise ValueError("Al massimo 60 caratteri.")
    return value


def _payload(conn: sqlite3.Connection, user: User) -> dict:
    keywords = conn.execute(
        "SELECT id, keyword, level FROM interests WHERE user_id = ? ORDER BY created_at, id", (user.id,)
    ).fetchall()
    muted = conn.execute("SELECT id, word FROM muted_words WHERE user_id = ? ORDER BY created_at, id", (user.id,)).fetchall()
    return {
        "keywords": [dict(r) for r in keywords],
        "muted": [dict(r) for r in muted],
        "rules": {"dedupe": prefs_with_defaults(user.prefs)["dedupe"]},
    }


@router.get("")
def interests(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return _payload(conn, user)


class NewKeyword(BaseModel):
    keyword: str
    level: Level = "media"

    _k = field_validator("keyword")(clean_word)


@router.post("/keywords", status_code=201)
def add_keyword(body: NewKeyword, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM interests WHERE user_id = ?", (user.id,)).fetchone()[0] >= MAX_ITEMS:
        raise HTTPException(status_code=422, detail=f"Puoi avere al massimo {MAX_ITEMS} interessi.")
    try:
        with conn:
            conn.execute(
                "INSERT INTO interests (user_id, keyword, level, created_at) VALUES (?, ?, ?, ?)",
                (user.id, body.keyword, body.level, now()),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Questo interesse c'è già.")
    recompute_user(conn, user.id)
    return _payload(conn, user)


class KeywordPatch(BaseModel):
    level: Level


@router.patch("/keywords/{keyword_id}")
def update_keyword(
    keyword_id: int, body: KeywordPatch, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)
):
    with conn:
        cur = conn.execute("UPDATE interests SET level = ? WHERE id = ? AND user_id = ?", (body.level, keyword_id, user.id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Interesse non trovato.")
    recompute_user(conn, user.id)
    return _payload(conn, user)


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    with conn:
        cur = conn.execute("DELETE FROM interests WHERE id = ? AND user_id = ?", (keyword_id, user.id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Interesse non trovato.")
    recompute_user(conn, user.id)
    return _payload(conn, user)


class NewMuted(BaseModel):
    word: str

    _w = field_validator("word")(clean_word)


@router.post("/muted", status_code=201)
def add_muted(body: NewMuted, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT COUNT(*) FROM muted_words WHERE user_id = ?", (user.id,)).fetchone()[0] >= MAX_ITEMS:
        raise HTTPException(status_code=422, detail=f"Puoi avere al massimo {MAX_ITEMS} parole silenziate.")
    try:
        with conn:
            conn.execute(
                "INSERT INTO muted_words (user_id, word, created_at) VALUES (?, ?, ?)", (user.id, body.word.lower(), now())
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Questa parola è già silenziata.")
    recompute_user(conn, user.id)
    return _payload(conn, user)


@router.delete("/muted/{word_id}")
def delete_muted(word_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    with conn:
        cur = conn.execute("DELETE FROM muted_words WHERE id = ? AND user_id = ?", (word_id, user.id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Parola non trovata.")
    recompute_user(conn, user.id)
    return _payload(conn, user)


@router.get("/preview")
def preview(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """«N notizie delle ultime 24 ore sono per te, su M arrivate.» Il riquadro in cima agli Interessi."""
    dedupe = prefs_with_defaults(user.prefs)["dedupe"]
    since = now() - 86400
    total = query.count(conn, user.id, ArticleFilter(since=since, dedupe=dedupe))
    matching = query.count(conn, user.id, ArticleFilter(view="perte", since=since, dedupe=dedupe))
    hidden = query.count(conn, user.id, ArticleFilter(since=since, dedupe=dedupe), muted=True)
    return {"matching": matching, "total": total, "hidden": hidden, "hours": 24}
