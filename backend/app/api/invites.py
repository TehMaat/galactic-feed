"""Link d'invito e di reimpostazione della password (pubblici: si aprono senza account)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from ..db import iso, now
from ..deps import AppContext, get_ctx, get_db, user_from_row
from ..security import create_session, new_token, token_hash
from .common import NewAccount, check_password, set_session_cookie, user_agent, user_payload

router = APIRouter(prefix="/api/invites", tags=["inviti"])

INVALID = "Questo link non è valido, è già stato usato oppure è scaduto. Chiedi un nuovo link all'amministratore."
LINK_PATHS = {"invite": "invito", "reset": "reimposta"}


def create_invite(
    conn: sqlite3.Connection,
    ctx: AppContext,
    kind: str,
    created_by: int,
    note: str = "",
    target_user_id: int | None = None,
) -> dict:
    token = new_token()
    ts = now()
    expires = ts + ctx.settings.invite_hours * 3600
    with conn:
        if kind == "reset":
            # Un solo link di reset valido per utente: il nuovo sostituisce il vecchio.
            conn.execute(
                "DELETE FROM invites WHERE kind = 'reset' AND target_user_id = ? AND used_at IS NULL",
                (target_user_id,),
            )
        cur = conn.execute(
            "INSERT INTO invites (token_hash, kind, note, created_by, target_user_id, created_at, expires_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_hash(token), kind, note, created_by, target_user_id, ts, expires),
        )
    return {
        "id": cur.lastrowid,
        "kind": kind,
        "note": note,
        "url": f"{ctx.settings.public_url}/{LINK_PATHS[kind]}/{token}",
        "created_at": iso(ts),
        "expires_at": iso(expires),
    }


def _valid_invite(conn: sqlite3.Connection, token: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT i.*, c.display_name AS by_name, c.username AS by_username, t.username AS target_username"
        " FROM invites i LEFT JOIN users c ON c.id = i.created_by LEFT JOIN users t ON t.id = i.target_user_id"
        " WHERE i.token_hash = ? AND i.used_at IS NULL AND i.expires_at > ?",
        (token_hash(token), now()),
    ).fetchone()
    if row is None or (row["kind"] == "reset" and row["target_user_id"] is None):
        raise HTTPException(status_code=404, detail=INVALID)
    return row


@router.get("/{token}")
def describe(token: str, conn: sqlite3.Connection = Depends(get_db)):
    row = _valid_invite(conn, token)
    return {
        "kind": row["kind"],
        "invited_by": (row["by_name"] or row["by_username"]) if row["created_by"] else None,
        "username": row["target_username"],
        "expires_at": iso(row["expires_at"]),
    }


class AcceptInvite(NewAccount):
    pass


class AcceptReset(BaseModel):
    password: str

    _p = field_validator("password")(check_password)


def _consume(conn: sqlite3.Connection, invite_id: int, user_id: int) -> bool:
    """Segna il link come usato. Falso se qualcun altro l'ha usato un attimo prima."""
    cur = conn.execute(
        "UPDATE invites SET used_at = ?, used_by = ? WHERE id = ? AND used_at IS NULL",
        (now(), user_id, invite_id),
    )
    return cur.rowcount == 1


@router.post("/{token}/accept")
def accept(
    token: str,
    body: dict,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    """Con un invito crea l'account; con un link di reset imposta la nuova password.

    In entrambi i casi l'utente resta collegato su questo dispositivo.
    """
    row = _valid_invite(conn, token)
    if row["kind"] == "invite":
        data = AcceptInvite(**body)
        exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (data.username,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="Questo nome utente è già preso: scegline un altro.")
        try:
            with conn:
                cur = conn.execute(
                    "INSERT INTO users (username, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (data.username, data.display_name or data.username, ctx.passwords.hash(data.password), now()),
                )
                user_id = cur.lastrowid
                if not _consume(conn, row["id"], user_id):
                    raise HTTPException(status_code=404, detail=INVALID)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Questo nome utente è già preso: scegline un altro.")
    else:
        data = AcceptReset(**body)
        user_id = row["target_user_id"]
        with conn:
            if not _consume(conn, row["id"], user_id):
                raise HTTPException(status_code=404, detail=INVALID)
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (ctx.passwords.hash(data.password), user_id))
            # Con una nuova password si esce da tutti gli altri dispositivi.
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user_row["disabled"]:
        raise HTTPException(status_code=403, detail="Questo account è disattivato. Chiedi all'amministratore.")
    session = create_session(conn, user_id, user_agent(request), ctx.settings.session_days)
    set_session_cookie(request, response, session, ctx)
    return {"user": user_payload(user_from_row(user_row))}
