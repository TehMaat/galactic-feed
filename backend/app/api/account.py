"""Il proprio profilo: nome, preferenze, password e dispositivi collegati."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..db import iso
from ..deps import AppContext, User, current_user, get_ctx, get_db, user_from_row
from .common import Prefs, check_password, clean_display_name, prefs_with_defaults, user_payload

router = APIRouter(prefix="/api/me", tags=["profilo"])


@router.get("")
def me(user: User = Depends(current_user)):
    return {"user": user_payload(user)}


class PrefsPatch(BaseModel):
    theme: str | None = None
    text_size: float | None = None
    dedupe: bool | None = None


class MePatch(BaseModel):
    display_name: str | None = None
    prefs: PrefsPatch | None = None

    _d = field_validator("display_name")(lambda v: clean_display_name(v) if v is not None else None)


@router.patch("")
def update_me(body: MePatch, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    display_name = user.display_name
    if body.display_name is not None:
        display_name = body.display_name or user.username
    prefs = prefs_with_defaults(user.prefs)
    if body.prefs is not None:
        changes = body.prefs.model_dump(exclude_none=True)
        prefs = Prefs(**{**prefs, **changes}).model_dump()
    with conn:
        conn.execute(
            "UPDATE users SET display_name = ?, prefs = ? WHERE id = ?",
            (display_name, json.dumps(prefs), user.id),
        )
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    return {"user": user_payload(user_from_row(row))}


class PasswordChange(BaseModel):
    current: str
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
    if not ctx.passwords.verify(row["password_hash"], body.current):
        raise HTTPException(status_code=403, detail="La password attuale non è corretta.")
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (ctx.passwords.hash(body.new), user.id))
        # Gli altri dispositivi devono rientrare con la nuova password; questo resta collegato.
        conn.execute("DELETE FROM sessions WHERE user_id = ? AND id != ?", (user.id, user.session_id))
    return {"ok": True}


@router.get("/sessions")
def sessions(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT id, created_at, last_seen_at, user_agent FROM sessions WHERE user_id = ? ORDER BY last_seen_at DESC",
        (user.id,),
    ).fetchall()
    return {
        "sessions": [
            {
                "id": r["id"],
                "created_at": iso(r["created_at"]),
                "last_seen_at": iso(r["last_seen_at"]),
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
