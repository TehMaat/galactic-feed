"""Pezzi in comune tra le API: validazione di nomi e password, cookie, preferenze."""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import Request, Response
from pydantic import BaseModel, Field, field_validator

from ..db import iso
from ..deps import AppContext, User
from ..security import SESSION_COOKIE

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$")
PASSWORD_MIN = 8
PASSWORD_MAX = 256


def check_username(value: str) -> str:
    value = (value or "").strip()
    if not USERNAME_RE.match(value):
        raise ValueError(
            "Il nome utente deve avere da 3 a 32 caratteri: lettere, numeri, punto, trattino o trattino basso."
        )
    return value


def check_password(value: str) -> str:
    if len(value or "") < PASSWORD_MIN:
        raise ValueError(f"La password deve avere almeno {PASSWORD_MIN} caratteri.")
    if len(value) > PASSWORD_MAX:
        raise ValueError(f"La password può avere al massimo {PASSWORD_MAX} caratteri.")
    return value


def clean_display_name(value: str | None) -> str:
    return " ".join((value or "").split())[:60]


class NewAccount(BaseModel):
    username: str
    password: str
    display_name: str = ""

    _u = field_validator("username")(check_username)
    _p = field_validator("password")(check_password)
    _d = field_validator("display_name")(clean_display_name)


class Prefs(BaseModel):
    """Preferenze personali. La v2 aggiungerà qui edizione, notifiche e AI."""

    theme: Literal["auto", "light", "dark"] = "auto"
    text_size: float = Field(default=1.0, ge=0.85, le=1.3)
    dedupe: bool = True


def prefs_with_defaults(stored: dict[str, Any]) -> dict[str, Any]:
    merged = Prefs().model_dump()
    for key in merged:
        if key in stored:
            merged[key] = stored[key]
    try:
        return Prefs(**merged).model_dump()
    except ValueError:
        return Prefs().model_dump()


def user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "prefs": prefs_with_defaults(user.prefs),
        "created_at": iso(user.created_at),
    }


def set_session_cookie(request: Request, response: Response, token: str, ctx: AppContext) -> None:
    # "Secure" quando la richiesta arriva in HTTPS (direttamente o tramite il reverse proxy,
    # che lo segnala con X-Forwarded-Proto). Così funziona anche l'accesso in HTTP dalla rete di casa.
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ctx.settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def clear_session_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax", secure=request.url.scheme == "https")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "sconosciuto"


def user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")
