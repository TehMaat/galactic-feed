"""Gestione degli utenti e degli inviti (solo amministratore)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..config import VERSION
from ..db import iso, now
from ..deps import AppContext, User, get_ctx, get_db, require_admin
from .invites import create_invite

router = APIRouter(prefix="/api/admin", tags=["amministrazione"])


def _user_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"],
        "is_admin": bool(row["is_admin"]),
        "disabled": bool(row["disabled"]),
        "created_at": iso(row["created_at"]),
        "last_seen_at": iso(row["last_seen_at"]),
    }


def _get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Utente non trovato.")
    return row


@router.get("/users")
def list_users(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM users ORDER BY created_at, id").fetchall()
    return {"users": [_user_row(r) for r in rows]}


class UserPatch(BaseModel):
    is_admin: bool | None = None
    disabled: bool | None = None


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserPatch,
    admin: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
):
    row = _get_user(conn, user_id)
    if user_id == admin.id and (body.is_admin is False or body.disabled is True):
        raise HTTPException(
            status_code=400,
            detail="Non puoi togliere i permessi a te stesso né disattivarti: chiedilo a un altro amministratore.",
        )
    is_admin = row["is_admin"] if body.is_admin is None else int(body.is_admin)
    disabled = row["disabled"] if body.disabled is None else int(body.disabled)
    with conn:
        conn.execute("UPDATE users SET is_admin = ?, disabled = ? WHERE id = ?", (is_admin, disabled, user_id))
        if disabled:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return {"user": _user_row(_get_user(conn, user_id))}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Non puoi eliminare il tuo stesso account.")
    _get_user(conn, user_id)
    with conn:
        # Fonti, interessi, letti e salvati dell'utente spariscono con lui (ON DELETE CASCADE).
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"ok": True}


@router.post("/users/{user_id}/reset")
def reset_link(
    user_id: int,
    admin: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    row = _get_user(conn, user_id)
    link = create_invite(conn, ctx, "reset", admin.id, note=f"Nuova password per {row['username']}", target_user_id=user_id)
    return {"invite": link}


def _invite_row(row: sqlite3.Row, ts: int) -> dict:
    if row["used_at"]:
        status = "usato"
    elif row["expires_at"] <= ts:
        status = "scaduto"
    else:
        status = "valido"
    return {
        "id": row["id"],
        "kind": row["kind"],
        "note": row["note"],
        "status": status,
        "created_at": iso(row["created_at"]),
        "expires_at": iso(row["expires_at"]),
        "used_at": iso(row["used_at"]),
        "used_by": row["used_by_name"],
        "target_user": row["target_name"],
    }


@router.get("/invites")
def list_invites(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    ts = now()
    # I link usati o scaduti da più di una settimana non servono più.
    with conn:
        conn.execute(
            "DELETE FROM invites WHERE (used_at IS NOT NULL AND used_at < ?) OR expires_at < ?",
            (ts - 7 * 86400, ts - 7 * 86400),
        )
    rows = conn.execute(
        "SELECT i.*, u.username AS used_by_name, t.username AS target_name FROM invites i"
        " LEFT JOIN users u ON u.id = i.used_by LEFT JOIN users t ON t.id = i.target_user_id"
        " ORDER BY i.created_at DESC, i.id DESC"
    ).fetchall()
    return {"invites": [_invite_row(r, ts) for r in rows]}


class InviteBody(BaseModel):
    note: str = ""


@router.post("/invites")
def new_invite(
    body: InviteBody | None = None,
    admin: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    note = " ".join(((body.note if body else "") or "").split())[:80]
    return {"invite": create_invite(conn, ctx, "invite", admin.id, note=note)}


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: int, _: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    with conn:
        cur = conn.execute("DELETE FROM invites WHERE id = ?", (invite_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Invito non trovato.")
    return {"ok": True}


@router.get("/status")
def status(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    path = ctx.settings.db_path
    size = sum(p.stat().st_size for p in path.parent.glob(path.name + "*") if p.is_file())
    return {
        "version": VERSION,
        "public_url": ctx.settings.public_url,
        "timezone": ctx.settings.timezone,
        "users": users,
        "database_bytes": size,
        "retention_days": ctx.settings.retention_days,
    }
