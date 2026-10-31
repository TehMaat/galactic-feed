"""Accesso a SQLite e migrazioni dello schema.

Il database è un solo file in DATA_DIR, in modalità WAL: chi legge non blocca chi
scrive. Lo schema cresce con i file numerati in migrations/ (001_*.sql, 002_*.sql…);
il numero dell'ultima migrazione applicata è salvato in PRAGMA user_version.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

log = logging.getLogger("galactic_feed.db")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_MIGRATION_RE = re.compile(r"^(\d{3})_[\w-]+\.sql$")


def now() -> int:
    """Orario attuale in secondi UTC: è il formato usato in tutto il database."""
    return int(time.time())


def iso(ts: int | None) -> str | None:
    """Converte i secondi UTC del database in una data ISO 8601 per l'API."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    def init(self) -> None:
        """Crea il file se manca, attiva WAL e applica le migrazioni mancanti."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.session() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            migrate(conn)


def _migrations() -> list[tuple[int, Path]]:
    found = []
    for path in MIGRATIONS_DIR.iterdir():
        match = _MIGRATION_RE.match(path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


def migrate(conn: sqlite3.Connection) -> int:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for number, path in _migrations():
        if number <= current:
            continue
        log.info("Applico la migrazione %s", path.name)
        script = path.read_text(encoding="utf-8")
        conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {number};\nCOMMIT;")
        current = number
    return current
