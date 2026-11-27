"""Il proprio profilo: nome, preferenze, password e dispositivi collegati."""

from __future__ import annotations

import json
import sqlite3

import base64

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from ..db import iso
from ..deps import AppContext, User, current_user, get_ctx, get_db, user_from_row
from ..reading import edition
from ..reading.matching import recompute_user
from .common import Prefs, check_password, clean_display_name, prefs_with_defaults, user_payload

router = APIRouter(prefix="/api/me", tags=["profilo"])
avatars = APIRouter(prefix="/api/avatars", tags=["profilo"])

# Avatar (#76): l'app riduce la foto (256 px) prima di mandarla; qui si controlla solo che sia
# un'immagine vera e piccola. I colori sono quelli proposti dall'app per le iniziali.
AVATAR_MAX_BYTES = 200_000
AVATAR_COLORS = 8
_IMAGE_TYPES = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"))


def _image_type(data: bytes) -> str | None:
    for magic, kind in _IMAGE_TYPES:
        if data.startswith(magic):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.get("")
def me(user: User = Depends(current_user)):
    return {"user": user_payload(user)}


class PrefsPatch(BaseModel):
    theme: str | None = None
    dark_style: str | None = None
    light_style: str | None = None
    accent: str | None = None
    font: str | None = None
    font_read: str | None = None
    text_size: float | None = None
    reader_layout: str | None = None
    dedupe: bool | None = None
    hide_partial: bool | None = None
    hide_read: bool | None = None
    auto_tags: bool | None = None
    edition: bool | None = None
    edition_times: list[str] | None = None
    ai_mode: str | None = None
    ai_text: str | None = None
    summaries: bool | None = None
    notify_folders: list[str] | None = None
    notify_edition: bool | None = None
    timezone: str | None = None
    accent_custom: str | None = None
    presets: list[dict] | None = None
    start_preset: str | None = None
    last_filter: dict | None = None


class MePatch(BaseModel):
    display_name: str | None = None
    avatar_color: int | None = Field(default=None, ge=0, le=AVATAR_COLORS - 1)
    prefs: PrefsPatch | None = None

    _d = field_validator("display_name")(lambda v: clean_display_name(v) if v is not None else None)


@router.patch("")
def update_me(
    body: MePatch,
    user: User = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    # Le modifiche si applicano ai valori salvati adesso, non a quelli letti all'inizio della
    # richiesta: due PATCH quasi insieme (per esempio «AI» e poi «Salva la descrizione» negli
    # Interessi) altrimenti si sovrascrivono, e la seconda riporta indietro la prima.
    conn.execute("BEGIN IMMEDIATE")
    try:
        saved = user_from_row(conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone())
        display_name = saved.display_name
        if body.display_name is not None:
            display_name = body.display_name or saved.username
        before = prefs_with_defaults(saved.prefs)
        prefs = before
        changes: dict = {}
        if body.prefs is not None:
            changes = body.prefs.model_dump(exclude_none=True)
            prefs = Prefs(**{**prefs, **changes}).model_dump()
    except BaseException:
        conn.rollback()
        raise
    with conn:
        conn.execute(
            "UPDATE users SET display_name = ?, prefs = ? WHERE id = ?",
            (display_name, json.dumps(prefs), user.id),
        )
        if body.avatar_color is not None:
            conn.execute("UPDATE users SET avatar_color = ? WHERE id = ?", (body.avatar_color, user.id))
        if prefs["ai_text"].strip() != before["ai_text"].strip():
            # Descrizione nuova: l'AI rivaluta gli articoli recenti.
            conn.execute("DELETE FROM ai_matches WHERE user_id = ?", (user.id,))
    if body.prefs is not None and {"edition", "edition_times"} & changes.keys():
        # Accendere l'Edizione o cambiarne gli orari vale per la prima Edizione (vedi reading/edition.py).
        edition.apply_legacy_prefs(conn, user.id, prefs, set(changes))
        edition.sync_edition_pref(conn, user.id)
    if prefs["ai_mode"] != before["ai_mode"] or prefs["ai_text"].strip() != before["ai_text"].strip():
        recompute_user(conn, user.id)
        if ctx.scheduler:
            ctx.scheduler.wake()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    return {"user": user_payload(user_from_row(row))}


class PasswordChange(BaseModel):
    current: str = ""
    new: str

    _p = field_validator("new")(check_password)


@router.post("/password")
def change_password(
    body: PasswordChange,
    user: User = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()
    # Chi è stato creato dal provider OIDC non ha ancora una password: la sceglie senza quella attuale.
    no_password = row["password_hash"] == "!oidc"
    if not no_password and not ctx.passwords.verify(row["password_hash"], body.current):
        raise HTTPException(status_code=403, detail="La password attuale non è corretta.")
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (ctx.passwords.hash(body.new), user.id))
        # Gli altri dispositivi devono rientrare con la nuova password; questo resta collegato.
        conn.execute("DELETE FROM sessions WHERE user_id = ? AND id != ?", (user.id, user.session_id))
    return {"ok": True}


@router.get("/sessions")
def sessions(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT id, created_at, last_seen_at, expires_at, remember, user_agent FROM sessions"
        " WHERE user_id = ? AND expires_at > strftime('%s', 'now') ORDER BY last_seen_at DESC",
        (user.id,),
    ).fetchall()
    return {
        "sessions": [
            {
                "id": r["id"],
                "created_at": iso(r["created_at"]),
                "last_seen_at": iso(r["last_seen_at"]),
                # Scade a quest'ora se non si usa l'app; senza «Ricordami» anche chiudendo il browser.
                "expires_at": iso(r["expires_at"]),
                "remember": bool(r["remember"]),
                "user_agent": r["user_agent"],
                "current": r["id"] == user.session_id,
            }
            for r in rows
        ]
    }


@router.delete("/sessions/{session_id}")
def end_session(session_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    with conn:
        cur = conn.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user.id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Dispositivo non trovato.")
    return {"ok": True}


class AvatarBody(BaseModel):
    data: str = Field(..., max_length=AVATAR_MAX_BYTES * 2, description="immagine in base64 (anche come data: URL)")


@router.put("/avatar")
def set_avatar(body: AvatarBody, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    raw = body.data.split(",", 1)[1] if body.data.startswith("data:") else body.data
    try:
        data = base64.b64decode(raw, validate=True)
    except ValueError:
        raise HTTPException(status_code=422, detail="La foto non è leggibile.")
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="La foto è troppo grande: scegline una più piccola.")
    kind = _image_type(data)
    if kind is None:
        raise HTTPException(status_code=422, detail="Usa una foto JPEG, PNG o WebP.")
    with conn:
        conn.execute(
            "UPDATE users SET avatar = ?, avatar_type = ?, avatar_v = avatar_v + 1 WHERE id = ?", (data, kind, user.id)
        )
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    return {"user": user_payload(user_from_row(row))}


@router.delete("/avatar")
def delete_avatar(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    with conn:
        conn.execute("UPDATE users SET avatar = NULL, avatar_type = '' WHERE id = ?", (user.id,))
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    return {"user": user_payload(user_from_row(row))}


@avatars.get("/{user_id}")
def get_avatar(user_id: int, _: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """La foto di un utente dell'istanza (per esempio in Amministrazione). L'indirizzo cambia a ogni foto nuova."""
    row = conn.execute("SELECT avatar, avatar_type FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or row["avatar"] is None:
        raise HTTPException(status_code=404, detail="Nessuna foto.")
    return Response(
        content=bytes(row["avatar"]),
        media_type=row["avatar_type"] or "image/jpeg",
        headers={"Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )
