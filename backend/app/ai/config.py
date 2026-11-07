"""Configurazione dell'AI (la sceglie l'amministratore) e consumi del giorno.

Fornitori:
- «ollama»: un modello locale (Ollama o un altro server compatibile con l'API di OpenAI);
- «openai»: OpenAI o un servizio cloud compatibile, con la sua chiave;
- «anthropic»: Claude di Anthropic, con la sua chiave.

La chiave API resta nel database del server, cifrata con data/secret.key (secretbox.py),
e non torna mai indietro dalle API.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .. import secretbox
from ..db import get_setting, set_setting  # noqa: F401 (usate anche da api/ai.py)

PROVIDERS = {
    "ollama": {"kind": "locale", "label": "Ollama (locale)", "base_url": "http://ollama:11434/v1", "model": "", "needs_key": False},
    "openai": {"kind": "cloud", "label": "OpenAI o compatibile", "base_url": "https://api.openai.com/v1", "model": "", "needs_key": True},
    "anthropic": {"kind": "cloud", "label": "Anthropic (Claude)", "base_url": "", "model": "claude-opus-5-5", "needs_key": True},
}
DEFAULT_DAILY_LIMIT = 500
PREFIX = "ai."


@dataclass
class AIConfig:
    provider: str = ""
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    daily_limit: int = DEFAULT_DAILY_LIMIT

    @property
    def enabled(self) -> bool:
        info = PROVIDERS.get(self.provider)
        if not info or not self.model:
            return False
        if info["needs_key"] and not self.api_key:
            return False
        return self.provider == "anthropic" or bool(self.base_url)

    @property
    def kind(self) -> str | None:
        return PROVIDERS[self.provider]["kind"] if self.provider in PROVIDERS else None

    @property
    def label(self) -> str:
        return PROVIDERS[self.provider]["label"] if self.provider in PROVIDERS else ""


def load(conn: sqlite3.Connection, secret: bytes) -> AIConfig:
    try:
        limit = int(get_setting(conn, PREFIX + "daily_limit", str(DEFAULT_DAILY_LIMIT)))
    except ValueError:
        limit = DEFAULT_DAILY_LIMIT
    return AIConfig(
        provider=get_setting(conn, PREFIX + "provider"),
        base_url=get_setting(conn, PREFIX + "base_url"),
        model=get_setting(conn, PREFIX + "model"),
        api_key=secretbox.decrypt(secret, get_setting(conn, PREFIX + "api_key")),
        daily_limit=limit,
    )


def save(conn: sqlite3.Connection, cfg: AIConfig, secret: bytes) -> None:
    with conn:
        set_setting(conn, PREFIX + "provider", cfg.provider)
        set_setting(conn, PREFIX + "base_url", cfg.base_url)
        set_setting(conn, PREFIX + "model", cfg.model)
        set_setting(conn, PREFIX + "api_key", secretbox.encrypt(secret, cfg.api_key))
        set_setting(conn, PREFIX + "daily_limit", str(cfg.daily_limit))


def encrypt_stored_key(conn: sqlite3.Connection, secret: bytes) -> bool:
    """All'avvio: cifra la chiave salvata in chiaro dalle versioni precedenti. Vero se l'ha fatto."""
    stored = get_setting(conn, PREFIX + "api_key")
    if not stored or secretbox.is_encrypted(stored):
        return False
    with conn:
        set_setting(conn, PREFIX + "api_key", secretbox.encrypt(secret, stored))
    return True


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def usage_today(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT requests, input_tokens, output_tokens FROM ai_usage WHERE day = ?", (today(),)).fetchone()
    return dict(row) if row else {"requests": 0, "input_tokens": 0, "output_tokens": 0}


def under_limit(conn: sqlite3.Connection, cfg: AIConfig) -> bool:
    return usage_today(conn)["requests"] < cfg.daily_limit


def record_usage(conn: sqlite3.Connection, input_tokens: int, output_tokens: int) -> None:
    with conn:
        conn.execute(
            "INSERT INTO ai_usage (day, requests, input_tokens, output_tokens) VALUES (?, 1, ?, ?)"
            " ON CONFLICT (day) DO UPDATE SET requests = requests + 1,"
            " input_tokens = input_tokens + excluded.input_tokens, output_tokens = output_tokens + excluded.output_tokens",
            (today(), input_tokens, output_tokens),
        )
        # Si tengono 90 giorni di consumi.
        conn.execute("DELETE FROM ai_usage WHERE day < date('now', '-90 days')")


def set_error(conn: sqlite3.Connection, message: str | None, ts: int | None = None) -> None:
    with conn:
        set_setting(conn, PREFIX + "last_error", message)
        set_setting(conn, PREFIX + "last_error_at", str(ts) if message and ts else None)
