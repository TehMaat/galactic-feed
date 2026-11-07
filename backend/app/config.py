"""Configurazione letta dalle variabili d'ambiente.

Tutte le impostazioni hanno un valore predefinito ragionevole: per partire basta
indicare PUBLIC_URL. L'elenco completo è in docs/ARCHITETTURA.md. Quelle dell'istanza
(durata delle sessioni, conservazione degli articoli, fuso orario…) si cambiano anche dal
pannello di amministrazione, che vale più della variabile d'ambiente (vedi instance.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


def _read_version() -> str:
    """Il numero di versione, dal file VERSION alla radice del repository.

    Nell'immagine Docker il file sta in /app/VERSION, accanto a /app/backend.
    """
    path = Path(__file__).resolve().parent.parent.parent / "VERSION"
    try:
        return path.read_text(encoding="utf-8").strip() or "0.0.0-sviluppo"
    except OSError:
        return "0.0.0-sviluppo"


VERSION = _read_version()

_TRUE = {"1", "true", "yes", "si", "sì", "on"}


def _env_opt_bool(name: str) -> bool | None:
    value = os.environ.get(name, "").strip()
    return value.lower() in _TRUE if value else None


def _env_opt_int(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    try:
        return max(1, int(value)) if value else None
    except ValueError:
        return None


def _env_timezone() -> str | None:
    """TZ, se è un fuso orario vero (Europe/Rome); altrimenti None."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    value = os.environ.get("TZ", "").strip().lstrip(":")
    if not value or "/" not in value and value != "UTC":
        return None
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return value


@dataclass
class Settings:
    public_url: str = "http://localhost:8080"
    data_dir: Path = Path("/data")
    # Impostazioni dell'istanza: None = variabile d'ambiente non indicata. Vale quella scelta
    # dall'amministratore nel pannello, oppure il valore predefinito (vedi instance.py).
    timezone: str | None = None
    retention_days: int | None = None
    block_private_networks: bool | None = None
    log_level: str = "info"
    frontend_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
    # Nei test lo scheduler resta spento e i feed si controllano a comando.
    scheduler_enabled: bool = True
    # Durata delle sessioni: con «Ricordami» (giorni) e senza (ore senza usare l'app).
    # None = non indicata nelle variabili d'ambiente: vale quella scelta dall'amministratore
    # o il valore predefinito (vedi instance.py).
    remember_days: int | None = None
    session_hours: int | None = None
    invite_hours: int | None = None
    # Parametri argon2: i test li abbassano per andare più veloci.
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4

    def __post_init__(self) -> None:
        self.public_url = self.public_url.strip().rstrip("/") or "http://localhost:8080"
        self.data_dir = Path(self.data_dir)
        self.frontend_dir = Path(self.frontend_dir)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "galactic-feed.db"

    @property
    def public_origin(self) -> str:
        parts = urlsplit(self.public_url)
        return f"{parts.scheme}://{parts.netloc}".lower()

    @property
    def user_agent(self) -> str:
        return f"GalacticFeed/{VERSION} (+{self.public_url})"

    @classmethod
    def from_env(cls) -> "Settings":
        kwargs = dict(
            public_url=os.environ.get("PUBLIC_URL", "http://localhost:8080"),
            data_dir=Path(os.environ.get("DATA_DIR", "/data")),
            timezone=_env_timezone(),
            retention_days=_env_opt_int("RETENTION_DAYS"),
            block_private_networks=_env_opt_bool("BLOCK_PRIVATE_NETWORKS"),
            log_level=os.environ.get("LOG_LEVEL", "info").lower(),
            remember_days=_env_opt_int("REMEMBER_DAYS"),
            session_hours=_env_opt_int("SESSION_HOURS"),
            invite_hours=_env_opt_int("INVITE_HOURS"),
        )
        if os.environ.get("FRONTEND_DIR"):
            kwargs["frontend_dir"] = Path(os.environ["FRONTEND_DIR"])
        return cls(**kwargs)
