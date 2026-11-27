"""Pezzi in comune tra le API: validazione di nomi e password, cookie, preferenze."""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import Request, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from .. import instance
from ..db import iso
from ..deps import AppContext, User
from ..security import SESSION_COOKIE, create_session

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


TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
MAX_EDITION_TIMES = 6


def check_times(values: list[str]) -> list[str]:
    """Orari dell'Edizione: «HH:MM», da 1 a 6, senza doppioni, in ordine."""
    times = sorted({(v or "").strip() for v in values})
    if not times:
        raise ValueError("Serve almeno un orario, oppure spegni l'Edizione.")
    if len(times) > MAX_EDITION_TIMES:
        raise ValueError(f"Al massimo {MAX_EDITION_TIMES} edizioni al giorno.")
    for t in times:
        if not TIME_RE.match(t):
            raise ValueError("Orario non valido: scrivilo come 07:30.")
    return times


# Colori principali: una tavolozza con contrasto AA verificato in chiaro e in scuro
# (frontend/src/styles/base.css), oppure «system», il colore di sistema dove il browser lo dà.
ACCENTS = ("galassia", "indaco", "blu", "viola", "rosa", "arancio", "ambra", "verde", "system", "custom")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
PRESET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
# Preset pronti del Notiziario (#68): non si salvano, li conosce l'app.
BUILTIN_PRESETS = ("perte", "tutte", "nonletti")
MAX_PRESETS = 20


class FilterSpec(BaseModel):
    """Un filtro del Notiziario: da dove partire, solo non letti, chiavi incluse ed escluse (#68)."""

    scope: Literal["perte", "tutte"] = "perte"
    unread: bool = False
    inc: list[str] = Field(default_factory=list)
    exc: list[str] = Field(default_factory=list)

    @field_validator("inc", "exc")
    @classmethod
    def _keys(cls, values: list[str]) -> list[str]:
        from ..reading.query import check_filter_keys

        return check_filter_keys(values)


class Preset(BaseModel):
    id: str
    name: str
    filter: FilterSpec = Field(default_factory=FilterSpec)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not PRESET_ID_RE.match(v) or v in BUILTIN_PRESETS or v == "last":
            raise ValueError("Preset non valido.")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join((v or "").split())
        if not v:
            raise ValueError("Dai un nome al preset.")
        if len(v) > 24:
            raise ValueError("Il nome del preset può avere al massimo 24 caratteri.")
        return v


class Prefs(BaseModel):
    """Preferenze personali: aspetto, doppioni, Edizione, AI e notifiche."""

    theme: Literal["auto", "light", "dark"] = "auto"
    # Varianti dei due temi: scuro blu notte, grigio o nero (schermi OLED); chiaro neutro o carta.
    # Solarized (#73) in tutti e due i temi.
    dark_style: Literal["notte", "grigio", "nero", "solarized"] = "notte"
    light_style: Literal["neutro", "carta", "solarized"] = "neutro"
    accent: Literal[ACCENTS] = "galassia"
    # Colore scelto con il selettore, quando accent è «custom» (#74).
    accent_custom: str = "#4F8CFF"
    # Un solo font per interfaccia e articoli (#75): galactic (titoli Plus Jakarta Sans, articoli
    # Newsreader), classico (serif), sistema, inter, leggibile. font_read resta per compatibilità.
    font: Literal["galactic", "classico", "sistema", "inter", "leggibile"] = "galactic"
    font_read: Literal["serif", "sans", "sistema"] = "serif"
    text_size: float = Field(default=1.0, ge=0.85, le=1.3)
    # Sul computer: articolo nella colonna accanto all'elenco o a tutta pagina sopra di esso (#9).
    reader_layout: Literal["colonne", "pagina"] = "colonne"
    dedupe: bool = True
    # Nasconde gli articoli di cui il sito non lascia leggere il testo completo (solo l'estratto).
    hide_partial: bool = False
    # Nel Notiziario solo le notizie da leggere, con qualsiasi preset (#95).
    hide_read: bool = False
    # Tag proposti in automatico per le fonti nuove.
    auto_tags: bool = True
    # Edizione: accesa o spenta e orari (nel fuso dell'istanza).
    edition: bool = False
    edition_times: list[str] = Field(default_factory=lambda: ["07:30"])
    # AI: come scegliere le notizie «per te», descrizione per il modello, riassunti.
    ai_mode: Literal["parole", "ai", "entrambi"] = "parole"
    ai_text: str = Field(default="", max_length=1500)
    summaries: bool = True
    # Notifiche: cartelle importanti (id, oppure «none» per le fonti senza cartella) ed Edizione.
    notify_folders: list[str] = Field(default_factory=list, max_length=200)
    notify_edition: bool = True
    # Fuso orario dell'utente per le Edizioni ("" = quello dell'istanza).
    timezone: str = ""
    # Notiziario (#68, #69): preset dell'utente, quale usare all'apertura (uno pronto, uno dei
    # suoi o «last») e l'ultimo filtro usato, esclusioni comprese.
    presets: list[Preset] = Field(default_factory=list, max_length=MAX_PRESETS)
    start_preset: str = "perte"
    last_filter: FilterSpec | None = None

    _t = field_validator("edition_times")(check_times)

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str) -> str:
        from ..instance import valid_timezone

        value = (value or "").strip()
        if value and not valid_timezone(value):
            raise ValueError("Fuso orario sconosciuto: scrivilo come Europe/Rome.")
        return value

    @field_validator("accent_custom")
    @classmethod
    def _accent_custom(cls, value: str) -> str:
        value = (value or "").strip()
        if not HEX_RE.match(value):
            raise ValueError("Colore non valido: scrivilo come #4F8CFF.")
        return value.upper()

    @field_validator("presets")
    @classmethod
    def _presets(cls, values: list[Preset]) -> list[Preset]:
        seen = set()
        for p in values:
            if p.id in seen:
                raise ValueError("Due preset con lo stesso id.")
            seen.add(p.id)
        return values

    @model_validator(mode="after")
    def _start(self) -> "Prefs":
        # Se il preset all'apertura non c'è più (cancellato), si torna a «Per te».
        ids = {*BUILTIN_PRESETS, "last", *(p.id for p in self.presets)}
        if self.start_preset not in ids:
            self.start_preset = "perte"
        return self

    @field_validator("notify_folders")
    @classmethod
    def _folders(cls, values: list[str]) -> list[str]:
        out = []
        for v in values:
            v = str(v).strip()
            if v != "none" and not v.isdigit():
                raise ValueError("Cartella non valida.")
            if v not in out:
                out.append(v)
        return out


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
        # Avatar (#76): la foto, se c'è, oppure le iniziali su uno dei colori proposti.
        "avatar": f"/api/avatars/{user.id}?v={user.avatar_v}" if user.avatar_v else None,
        "avatar_color": user.avatar_color,
        "prefs": prefs_with_defaults(user.prefs),
        "created_at": iso(user.created_at),
    }


def start_session(
    request: Request, response: Response, conn, ctx: AppContext, user_id: int, remember: bool = True, via: str = "password"
) -> None:
    """Crea la sessione e manda il cookie. Senza «Ricordami» il cookie sparisce chiudendo il browser."""
    seconds = instance.session_seconds(ctx, remember, conn)
    token = create_session(conn, user_id, user_agent(request), seconds, remember, via)
    set_session_cookie(request, response, token, seconds if remember else None)


def set_session_cookie(request: Request, response: Response, token: str, max_age: int | None) -> None:
    """max_age None = cookie di sessione, che il browser cancella quando si chiude."""
    # "Secure" quando la richiesta arriva in HTTPS (direttamente o tramite il reverse proxy,
    # che lo segnala con X-Forwarded-Proto). Così funziona anche l'accesso in HTTP dalla rete di casa.
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
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
