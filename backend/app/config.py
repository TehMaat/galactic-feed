"""Configurazione letta dalle variabili d'ambiente.

Tutte le impostazioni hanno un valore predefinito ragionevole: per partire basta
indicare PUBLIC_URL. L'elenco completo è in docs/ARCHITETTURA.md.
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


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in _TRUE


def _env_opt_int(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    try:
        return max(1, int(value)) if value else None
    except ValueError:
        return None


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name, "").strip()
    try:
        return int(value) if value else default
    except ValueError:
        return default


@dataclass
class Settings:
    public_url: str = "http://localhost:8080"
    data_dir: Path = Path("/data")
    timezone: str = "Europe/Rome"
    retention_days: int = 90
    block_private_networks: bool = False
    log_level: str = "info"
    frontend_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "frontend" / "dist")
    # Nei test lo scheduler resta spento e i feed si controllano a comando.
    scheduler_enabled: bool = True
    # Durata delle sessioni: con «Ricordami» (giorni) e senza (ore senza usare l'app).
    # None = non indicata nelle variabili d'ambiente: vale quella scelta dall'amministratore
    # o il valore predefinito (vedi instance.py).
    remember_days: int | None = None
    session_hours: int | None = None
    invite_hours: int = 48
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
            timezone=os.environ.get("TZ", "Europe/Rome") or "Europe/Rome",
            retention_days=max(1, _env_int("RETENTION_DAYS", 90)),
            block_private_networks=_env_bool("BLOCK_PRIVATE_NETWORKS", False),
            log_level=os.environ.get("LOG_LEVEL", "info").lower(),
            remember_days=_env_opt_int("REMEMBER_DAYS"),
            session_hours=_env_opt_int("SESSION_HOURS"),
        )
        if os.environ.get("FRONTEND_DIR"):
            kwargs["frontend_dir"] = Path(os.environ["FRONTEND_DIR"])
        return cls(**kwargs)
