"""Oggetti condivisi dalle API: contesto dell'app, database e utente collegato."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Iterator

from fastapi import Depends, HTTPException, Request

from .config import Settings
from .db import Database, now
from .hooks import Hooks
from .security import SESSION_COOKIE, SESSION_TOUCH_SECONDS, Passwords, RateLimiter, new_setup_code, token_hash

log = logging.getLogger("galactic_feed")

# Quanti codici di primo avvio sbagliati, in tutto, prima di generarne uno nuovo.
SETUP_MAX_FAILURES = 20


class AppContext:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.db_path)
        self.passwords = Passwords(settings)
        # 10 tentativi sbagliati in 15 minuti per indirizzo o per nome utente.
        self.login_limiter = RateLimiter(max_failures=10, window_seconds=15 * 60)
        self.hooks = Hooks()
        # Creati all'avvio del server (vedi main.lifespan).
        self.http = None
        self.fetcher = None
        self.extractor = None
        self.scheduler = None
        self._setup_code: str | None = None
        self._setup_failures = 0
        self._lock = threading.Lock()

    # ---- Codice di primo avvio ----
    def refresh_setup_code(self, needed: bool) -> None:
        with self._lock:
            self._setup_failures = 0
            self._setup_code = new_setup_code() if needed else None
            code = self._setup_code
        if code:
            log.warning(
                "\n\n  ── Galactic Feed · primo avvio ──\n"
                "  Apri %s e crea l'amministratore.\n"
                "  Codice di primo avvio: %s\n",
                self.settings.public_url,
                code,
            )

    @property
    def setup_code(self) -> str | None:
        return self._setup_code

    def check_setup_code(self, code: str) -> bool:
        with self._lock:
            ok = self._setup_code is not None and code.strip() == self._setup_code
            if not ok:
                self._setup_failures += 1
                regenerate = self._setup_failures >= SETUP_MAX_FAILURES
            else:
                regenerate = False
        if regenerate:
            log.warning("Troppi codici di primo avvio sbagliati: ne genero uno nuovo.")
            self.refresh_setup_code(True)
        return ok

    def clear_setup_code(self) -> None:
        with self._lock:
            self._setup_code = None


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_db(ctx: AppContext = Depends(get_ctx)) -> Iterator[sqlite3.Connection]:
    conn = ctx.db.connect()
    try:
        yield conn
    finally:
        conn.close()


@dataclass
class User:
    id: int
    username: str
    display_name: str
    is_admin: bool
    prefs: dict[str, Any] = field(default_factory=dict)
    session_id: int | None = None
    created_at: int | None = None


def user_from_row(row: sqlite3.Row, session_id: int | None = None) -> User:
    try:
        prefs = json.loads(row["prefs"] or "{}")
    except (TypeError, ValueError):
        prefs = {}
    return User(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"] or row["username"],
        is_admin=bool(row["is_admin"]),
        prefs=prefs if isinstance(prefs, dict) else {},
        session_id=session_id,
        created_at=row["created_at"],
    )


def load_session_user(request: Request, conn: sqlite3.Connection, ctx: AppContext) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    ts = now()
    row = conn.execute(
        "SELECT s.id AS sid, s.last_seen_at AS s_seen, u.* FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token_hash = ? AND s.expires_at > ? AND u.disabled = 0",
        (token_hash(token), ts),
    ).fetchone()
    if row is None:
        return None
    if ts - row["s_seen"] > SESSION_TOUCH_SECONDS:
        with conn:
            conn.execute(
                "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE id = ?",
                (ts, ts + ctx.settings.session_days * 86400, row["sid"]),
            )
            conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (ts, row["id"]))
    return user_from_row(row, session_id=row["sid"])


def current_user(
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
) -> User:
    user = load_session_user(request, conn, ctx)
    if user is None:
        raise HTTPException(status_code=401, detail="Accesso richiesto: entra con il tuo account.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Solo l'amministratore può farlo.")
    return user
