"""Password, token, sessioni e protezioni di base.

- Le password sono salvate solo come hash argon2.
- Token di sessione e di invito sono stringhe casuali: nel database finisce solo
  il loro hash SHA-256, così una copia del database non permette di entrare.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import Settings
from .db import now

SESSION_COOKIE = "gf_session"
# Il cookie si rinnova al massimo una volta l'ora, per non scrivere a ogni richiesta.
SESSION_TOUCH_SECONDS = 3600


class Passwords:
    def __init__(self, settings: Settings):
        self._hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
        )
        # Usato quando l'utente non esiste, per non rivelarlo con i tempi di risposta.
        self._dummy = self._hasher.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, stored_hash: str | None, password: str) -> bool:
        try:
            return self._hasher.verify(stored_hash or self._dummy, password) and stored_hash is not None
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(stored_hash)
        except InvalidHashError:
            return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_setup_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_session(conn: sqlite3.Connection, user_id: int, user_agent: str, days: int) -> str:
    token = new_token()
    ts = now()
    with conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at, user_agent)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (token_hash(token), user_id, ts, ts, ts + days * 86400, (user_agent or "")[:300]),
        )
        conn.execute("UPDATE users SET last_seen_at = ? WHERE id = ?", (ts, user_id))
    return token


class RateLimiter:
    """Conta i tentativi falliti per chiave (indirizzo IP, nome utente…).

    Tiene tutto in memoria: dopo un riavvio i contatori ripartono da zero, che per
    un server di casa va benissimo.
    """

    def __init__(self, max_failures: int, window_seconds: int):
        self.max_failures = max_failures
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, at: float) -> deque[float]:
        hits = self._hits[key]
        while hits and hits[0] <= at - self.window:
            hits.popleft()
        return hits

    def blocked(self, *keys: str) -> bool:
        at = time.monotonic()
        with self._lock:
            return any(len(self._trim(k, at)) >= self.max_failures for k in keys)

    def fail(self, *keys: str) -> None:
        at = time.monotonic()
        with self._lock:
            for k in keys:
                self._trim(k, at).append(at)

    def reset(self, *keys: str) -> None:
        with self._lock:
            for k in keys:
                self._hits.pop(k, None)


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def same_origin_request(method: str, headers, settings: Settings, request_origin: str) -> bool:
    """Protezione CSRF: le richieste che modificano dati devono venire dalla PWA stessa.

    I browser moderni mandano Sec-Fetch-Site; quelli più vecchi almeno Origin.
    Le richieste senza nessuno dei due vengono da programmi (curl, test), che non
    hanno i cookie del browser e quindi non sono un rischio CSRF.
    """
    if method.upper() in SAFE_METHODS:
        return True
    site = headers.get("sec-fetch-site")
    if site:
        return site in ("same-origin", "none")
    origin = headers.get("origin")
    if not origin or origin == "null":
        return origin is None
    origin = origin.rstrip("/").lower()
    return origin in (settings.public_origin, request_origin.lower())
