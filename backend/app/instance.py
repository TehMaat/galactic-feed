"""Impostazioni dell'istanza, scelte dall'amministratore dall'interfaccia.

Per ogni impostazione vale, in quest'ordine:
1. il valore salvato dall'amministratore (tabella app_settings, chiave «instance.<nome>»);
2. la variabile d'ambiente, se è indicata;
3. il valore predefinito.
Le modifiche valgono subito, senza riavviare il server.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .config import Settings
from .db import get_setting, set_setting

PREFIX = "instance."


@dataclass(frozen=True)
class Option:
    default: int
    choices: tuple[int, ...]
    env: str  # nome della variabile d'ambiente
    unit: str  # «giorni», «ore»


OPTIONS: dict[str, Option] = {
    # Accesso con «Ricordami»: la sessione dura questi giorni dall'ultimo utilizzo.
    "remember_days": Option(default=90, choices=(7, 30, 90, 180, 365), env="REMEMBER_DAYS", unit="giorni"),
    # Accesso senza «Ricordami»: finisce chiudendo il browser, e comunque dopo queste ore senza usare l'app.
    "session_hours": Option(default=12, choices=(1, 4, 12, 24, 72), env="SESSION_HOURS", unit="ore"),
}


def _env_value(settings: Settings, key: str) -> int | None:
    return getattr(settings, key, None)


def resolve(conn: sqlite3.Connection, settings: Settings, key: str) -> tuple[int, str]:
    """(valore, origine): origine è «gui», «env» oppure «default»."""
    option = OPTIONS[key]
    stored = get_setting(conn, PREFIX + key)
    if stored.isdigit() and int(stored) in option.choices:
        return int(stored), "gui"
    env = _env_value(settings, key)
    if env:
        return env, "env"
    return option.default, "default"


def value(conn: sqlite3.Connection, settings: Settings, key: str) -> int:
    return resolve(conn, settings, key)[0]


def describe(conn: sqlite3.Connection, settings: Settings) -> dict:
    """Tutte le impostazioni, con da dove arriva il valore attuale: per il pannello dell'amministratore."""
    out = {}
    for key, option in OPTIONS.items():
        current, origin = resolve(conn, settings, key)
        out[key] = {
            "value": current,
            "origin": origin,
            "default": option.default,
            "env": option.env,
            "env_value": _env_value(settings, key),
            "choices": list(option.choices),
            "unit": option.unit,
        }
    return out


def save(conn: sqlite3.Connection, key: str, new: int | None) -> None:
    """Salva il valore scelto dall'amministratore; None torna alla variabile d'ambiente o al predefinito."""
    option = OPTIONS[key]
    if new is not None and new not in option.choices:
        choices = ", ".join(str(c) for c in option.choices)
        raise ValueError(f"Valore non valido: scegli tra {choices} {option.unit}.")
    set_setting(conn, PREFIX + key, None if new is None else str(new))


def session_seconds(conn: sqlite3.Connection, settings: Settings, remember: bool) -> int:
    """Durata di una sessione dall'ultimo utilizzo, con o senza «Ricordami»."""
    if remember:
        return value(conn, settings, "remember_days") * 86400
    return value(conn, settings, "session_hours") * 3600
