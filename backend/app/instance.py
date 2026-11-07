"""Impostazioni dell'istanza, scelte dall'amministratore dall'interfaccia (pannello Amministrazione).

Per ogni impostazione vale, in quest'ordine:
1. il valore salvato dall'amministratore (tabella app_settings, chiave «instance.<nome>»);
2. la variabile d'ambiente, se è indicata;
3. il valore predefinito.
Le modifiche valgono subito, senza riavviare il server.

Restano solo variabili d'ambiente, perché servono prima dell'avvio o riguardano
l'infrastruttura: PUBLIC_URL, DATA_DIR, LOG_LEVEL, FORWARDED_ALLOW_IPS (ENV_ONLY qui sotto).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .db import get_setting, set_setting

PREFIX = "instance."
DEFAULTS_KEY = PREFIX + "user_defaults"


def valid_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return False
    return "/" in value or value == "UTC"


@dataclass(frozen=True)
class Option:
    kind: str  # «int», «bool» oppure «timezone»
    default: Any
    group: str  # sezione del pannello: access, users, sources, system
    env: str | None = None  # variabile d'ambiente che la imposta, se c'è
    unit: str = ""  # «giorni», «ore», «minuti»
    choices: tuple = ()

    def check(self, value: Any) -> Any:
        """Il valore validato, oppure ValueError con un messaggio in italiano."""
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise ValueError("Valore non valido: serve sì o no.")
            return value
        if self.kind == "timezone":
            if not isinstance(value, str) or not valid_timezone(value.strip()):
                raise ValueError("Fuso orario sconosciuto: scrivilo come Europe/Rome.")
            return value.strip()
        if isinstance(value, bool) or not isinstance(value, int) or value not in self.choices:
            choices = ", ".join(str(c) for c in self.choices)
            raise ValueError(f"Valore non valido: scegli tra {choices} {self.unit}.")
        return value

    def parse(self, stored: str) -> Any:
        """Il valore salvato nel database (testo), oppure None se non è più valido."""
        try:
            value = json.loads(stored)
            return self.check(value)
        except (ValueError, TypeError):
            return None


OPTIONS: dict[str, Option] = {
    # Accesso con «Ricordami»: la sessione dura questi giorni dall'ultimo utilizzo.
    "remember_days": Option("int", 90, "access", "REMEMBER_DAYS", "giorni", (7, 30, 90, 180, 365)),
    # Accesso senza «Ricordami»: finisce chiudendo il browser, e comunque dopo queste ore senza usare l'app.
    "session_hours": Option("int", 12, "access", "SESSION_HOURS", "ore", (1, 4, 12, 24, 72)),
    # Validità dei link d'invito e di quelli per una nuova password.
    "invite_hours": Option("int", 48, "users", "INVITE_HOURS", "ore", (24, 48, 72, 168)),
    # Articoli non salvati più vecchi di così vengono cancellati.
    "retention_days": Option("int", 90, "sources", "RETENTION_DAYS", "giorni", (14, 30, 60, 90, 180, 365, 730)),
    # Intervallo proposto per le fonti nuove (anche quelle importate da OPML).
    "default_interval": Option("int", 30, "sources", None, "minuti", (15, 30, 60, 180, 360, 720, 1440)),
    # Vieta le fonti sulla rete locale (indirizzi privati).
    "block_private_networks": Option("bool", False, "sources", "BLOCK_PRIVATE_NETWORKS"),
    # Fuso orario dell'istanza: orari dell'Edizione.
    "timezone": Option("timezone", "Europe/Rome", "system", "TZ"),
}

# Variabili d'ambiente che restano tali: servono prima dell'avvio o riguardano l'infrastruttura.
ENV_ONLY = {
    "PUBLIC_URL": lambda s: s.public_url,
    "DATA_DIR": lambda s: str(s.data_dir),
    "LOG_LEVEL": lambda s: s.log_level,
    "FORWARDED_ALLOW_IPS": lambda s: os.environ.get("FORWARDED_ALLOW_IPS", "*"),
}

# Preferenze che l'amministratore può impostare per i nuovi utenti.
DEFAULT_PREFS = ("theme", "dark_style", "light_style", "accent", "font", "font_read", "text_size", "dedupe", "edition", "edition_times", "summaries")


def _env_value(settings: Settings, key: str) -> Any:
    return getattr(settings, key, None)


class Instance:
    """Le impostazioni dell'istanza di un server, con una copia in memoria.

    Solo questo processo le cambia (con save), quindi la copia resta sempre giusta.
    """

    def __init__(self, settings: Settings, db):
        self.settings = settings
        self.db = db
        self._stored: dict[str, str] | None = None
        self._lock = threading.Lock()

    def _load(self, conn: sqlite3.Connection | None = None) -> dict[str, str]:
        with self._lock:
            if self._stored is not None:
                return self._stored
        if conn is None:
            with self.db.session() as own:
                rows = own.execute("SELECT key, value FROM app_settings WHERE key LIKE 'instance.%'").fetchall()
        else:
            rows = conn.execute("SELECT key, value FROM app_settings WHERE key LIKE 'instance.%'").fetchall()
        stored = {r["key"]: r["value"] for r in rows}
        with self._lock:
            self._stored = stored
        return stored

    def forget(self) -> None:
        with self._lock:
            self._stored = None

    def resolve(self, key: str, conn: sqlite3.Connection | None = None) -> tuple[Any, str]:
        """(valore, origine): origine è «gui», «env» oppure «default»."""
        option = OPTIONS[key]
        stored = self._load(conn).get(PREFIX + key)
        if stored is not None:
            value = option.parse(stored)
            if value is not None:
                return value, "gui"
        env = _env_value(self.settings, key)
        if env is not None:
            return env, "env"
        return option.default, "default"

    def get(self, key: str, conn: sqlite3.Connection | None = None) -> Any:
        return self.resolve(key, conn)[0]

    def describe(self, conn: sqlite3.Connection | None = None) -> dict:
        """Tutte le impostazioni, con da dove arriva il valore attuale: per il pannello."""
        out = {}
        for key, option in OPTIONS.items():
            current, origin = self.resolve(key, conn)
            out[key] = {
                "value": current,
                "origin": origin,
                "group": option.group,
                "kind": option.kind,
                "default": option.default,
                "env": option.env,
                "env_value": _env_value(self.settings, key),
                "choices": list(option.choices),
                "unit": option.unit,
            }
        return out

    def save(self, conn: sqlite3.Connection, changes: dict[str, Any]) -> None:
        """Salva i valori scelti dall'amministratore (tutti o nessuno). None torna a variabile d'ambiente o predefinito."""
        unknown = [k for k in changes if k not in OPTIONS]
        if unknown:
            raise ValueError(f"Impostazione sconosciuta: {unknown[0]}.")
        checked = {k: None if v is None else OPTIONS[k].check(v) for k, v in changes.items()}
        with conn:
            for key, value in checked.items():
                set_setting(conn, PREFIX + key, None if value is None else json.dumps(value))
        self.forget()

    # ---- Preferenze per i nuovi utenti ----

    def user_defaults(self, conn: sqlite3.Connection | None = None) -> dict:
        """Le preferenze iniziali dei nuovi account (solo quelle scelte dall'amministratore)."""
        stored = self._load(conn).get(DEFAULTS_KEY)
        try:
            data = json.loads(stored) if stored else {}
        except ValueError:
            data = {}
        return {k: v for k, v in data.items() if k in DEFAULT_PREFS} if isinstance(data, dict) else {}

    def save_user_defaults(self, conn: sqlite3.Connection, prefs: dict) -> None:
        with conn:
            set_setting(conn, DEFAULTS_KEY, json.dumps({k: v for k, v in prefs.items() if k in DEFAULT_PREFS}) if prefs else None)
        self.forget()


def session_seconds(ctx, remember: bool, conn: sqlite3.Connection | None = None) -> int:
    """Durata di una sessione dall'ultimo utilizzo, con o senza «Ricordami»."""
    if remember:
        return ctx.instance.get("remember_days", conn) * 86400
    return ctx.instance.get("session_hours", conn) * 3600


# Usate dai test e dagli script: leggono senza copia in memoria.
def resolve(conn: sqlite3.Connection, settings: Settings, key: str) -> tuple[Any, str]:
    option = OPTIONS[key]
    stored = get_setting(conn, PREFIX + key, None)
    if stored is not None:
        value = option.parse(stored)
        if value is not None:
            return value, "gui"
    env = _env_value(settings, key)
    return (env, "env") if env is not None else (option.default, "default")
