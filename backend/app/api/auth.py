"""Primo avvio, accesso e uscita."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..config import VERSION
from ..db import now
from ..deps import AppContext, get_ctx, get_db, load_session_user, user_from_row
from ..security import SESSION_COOKIE, create_session, token_hash
from .common import NewAccount, clear_session_cookie, client_ip, set_session_cookie, user_agent, user_payload

router = APIRouter(prefix="/api/auth", tags=["accesso"])

TOO_MANY = "Troppi tentativi sbagliati. Riprova tra qualche minuto."


def users_exist(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


@router.get("/state")
def state(request: Request, conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    """Cosa deve mostrare la PWA all'apertura: primo avvio, accesso o app."""
    user = load_session_user(request, conn, ctx)
    return {
        "setup_needed": not users_exist(conn),
        "user": user_payload(user) if user else None,
        "version": VERSION,
    }


class SetupBody(NewAccount):
    code: str


@router.post("/setup")
def setup(
    body: SetupBody,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    """Crea il primo account, che è l'amministratore. Serve il codice scritto nel log."""
    if users_exist(conn):
        raise HTTPException(status_code=409, detail="L'amministratore esiste già: entra con il tuo account.")
    ip_key = "setup:" + client_ip(request)
    if ctx.login_limiter.blocked(ip_key):
        raise HTTPException(status_code=429, detail=TOO_MANY)
    if not ctx.check_setup_code(body.code):
        ctx.login_limiter.fail(ip_key)
        raise HTTPException(
            status_code=403,
            detail="Codice di primo avvio non corretto. Lo trovi nel log del server (docker compose logs galactic-feed).",
        )
    ts = now()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users (username, display_name, password_hash, is_admin, created_at)"
                " SELECT ?, ?, ?, 1, ? WHERE NOT EXISTS (SELECT 1 FROM users)",
                (body.username, body.display_name or body.username, ctx.passwords.hash(body.password), ts),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="L'amministratore esiste già: entra con il tuo account.")
    if cur.rowcount == 0:
        raise HTTPException(status_code=409, detail="L'amministratore esiste già: entra con il tuo account.")
    ctx.clear_setup_code()
    token = create_session(conn, cur.lastrowid, user_agent(request), ctx.settings.session_days)
    set_session_cookie(request, response, token, ctx)
    row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"user": user_payload(user_from_row(row))}


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    username = body.username.strip()
    keys = ("login-ip:" + client_ip(request), "login-user:" + username.lower())
    if ctx.login_limiter.blocked(*keys):
        raise HTTPException(status_code=429, detail=TOO_MANY)
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not ctx.passwords.verify(row["password_hash"] if row else None, body.password):
        ctx.login_limiter.fail(*keys)
        raise HTTPException(status_code=401, detail="Nome utente o password non corretti.")
    if row["disabled"]:
        raise HTTPException(status_code=403, detail="Questo account è disattivato. Chiedi all'amministratore.")
    ctx.login_limiter.reset(keys[1])
    if ctx.passwords.needs_rehash(row["password_hash"]):
        with conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (ctx.passwords.hash(body.password), row["id"]))
    token = create_session(conn, row["id"], user_agent(request), ctx.settings.session_days)
    set_session_cookie(request, response, token, ctx)
    return {"user": user_payload(user_from_row(row))}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
    clear_session_cookie(request, response)
    return {"ok": True}
