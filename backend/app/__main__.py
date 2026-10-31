"""Avvio del server: `python -m app` (è il comando usato nel container)."""

from __future__ import annotations

import logging
import os

import uvicorn

from .config import Settings
from .main import create_app


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s · %(message)s",
    )
    uvicorn.run(
        create_app(settings),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        # Il reverse proxy comunica con X-Forwarded-Proto e X-Forwarded-For
        # se il visitatore usa HTTPS e qual è il suo indirizzo.
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "*"),
        log_level=settings.log_level,
        access_log=settings.log_level == "debug",
    )


if __name__ == "__main__":
    main()
