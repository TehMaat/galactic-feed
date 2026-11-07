"""Accesso con un provider OpenID Connect (issue #22): configurazione e protocollo.

- Configurazione fatta dall'amministratore nell'app (tabella app_settings, chiavi «oidc.*»);
  il client secret è cifrato con data/secret.key e le API non lo restituiscono mai.
- Flusso Authorization Code con PKCE (S256), state e nonce.
- L'ID token si verifica con le chiavi del provider (JWKS) oppure, per HS256, con il client
  secret: firma, iss, aud, exp, iat, nonce. L'algoritmo «none» non è mai accettato.
- Il login con password si può spegnere, ma resta sempre un accesso d'emergenza: la
  variabile EMERGENCY_PASSWORD_LOGIN=true, oppure «python -m app.emergency» nel container.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import asdict, dataclass

import httpx
import jwt

from . import secretbox
from .db import get_setting, set_setting

PREFIX = "oidc."
CALLBACK_PATH = "/api/auth/oidc/callback"
STATE_SECONDS = 600
DISCOVERY_SECONDS = 3600
TIMEOUT = 15
ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA", "HS256", "HS384", "HS512"]
_TRUE = {"1", "true", "yes", "si", "sì", "on"}


class OIDCError(Exception):
    """Errore da mostrare all'utente (in italiano)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class OIDCConfig:
    enabled: bool = False
    issuer: str = ""
    client_id: str = ""
    client_secret: str = ""
    scopes: str = "openid profile email"
    label: str = "Entra con il tuo account"
    auto_create: bool = False  # crea l'utente al primo accesso (altrimenti serve un invito)
    link_email: bool = True  # collega un utente esistente con la stessa email verificata
    link_username: bool = False  # collega un utente esistente con lo stesso nome utente
    admin_claim: str = ""  # per esempio «groups»
    admin_value: str = ""  # per esempio «galactic-admin»
    password_login: bool = True
    rp_logout: bool = False  # all'uscita, esci anche dal provider

    @property
    def ready(self) -> bool:
        return self.enabled and bool(self.issuer) and bool(self.client_id)


_BOOLS = {"enabled", "auto_create", "link_email", "link_username", "password_login", "rp_logout"}


def load(conn: sqlite3.Connection, secret: bytes) -> OIDCConfig:
    cfg = OIDCConfig()
    for key in asdict(cfg):
        raw = get_setting(conn, PREFIX + key, None)
        if raw is None:
            continue
        if key == "client_secret":
            cfg.client_secret = secretbox.decrypt(secret, raw)
        elif key in _BOOLS:
            setattr(cfg, key, raw == "1")
        else:
            setattr(cfg, key, raw)
    return cfg


def save(conn: sqlite3.Connection, cfg: OIDCConfig, secret: bytes) -> None:
    with conn:
        for key, value in asdict(cfg).items():
            if key == "client_secret":
                value = secretbox.encrypt(secret, value)
            elif key in _BOOLS:
                value = "1" if value else "0"
            set_setting(conn, PREFIX + key, value)


def emergency_env() -> bool:
    return os.environ.get("EMERGENCY_PASSWORD_LOGIN", "").strip().lower() in _TRUE


def password_login_allowed(cfg: OIDCConfig) -> bool:
    """Il login con password resta sempre possibile se l'OIDC non è pronto, o in emergenza."""
    return cfg.password_login or not cfg.ready or emergency_env()


def redirect_uri(public_url: str) -> str:
    return public_url.rstrip("/") + CALLBACK_PATH


# ---------- Discovery e chiavi ----------

_cache: dict[str, tuple[float, dict]] = {}


def _client() -> httpx.AsyncClient:
    # Client a parte: il provider è scelto dall'amministratore e spesso sta nella rete di casa,
    # quindi non vale il blocco della rete locale pensato per le fonti.
    return httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT), follow_redirects=True, headers={"Accept": "application/json"})


async def _get_json(url: str, what: str) -> dict:
    try:
        async with _client() as client:
            resp = await client.get(url)
    except httpx.HTTPError:
        raise OIDCError(f"Il provider non risponde ({what}). Controlla l'indirizzo e che il server lo possa raggiungere.")
    if resp.status_code != 200:
        raise OIDCError(f"Il provider ha risposto con un errore ({resp.status_code}) chiedendo {what}.")
    try:
        data = resp.json()
    except ValueError:
        raise OIDCError(f"La risposta del provider ({what}) non è JSON.")
    if not isinstance(data, dict):
        raise OIDCError(f"La risposta del provider ({what}) non è valida.")
    return data


async def discover(issuer: str, fresh: bool = False) -> dict:
    """Il documento /.well-known/openid-configuration del provider, controllato."""
    issuer = issuer.rstrip("/")
    cached = _cache.get("d:" + issuer)
    if cached and not fresh and time.time() - cached[0] < DISCOVERY_SECONDS:
        return cached[1]
    doc = await _get_json(issuer + "/.well-known/openid-configuration", "la configurazione")
    if (doc.get("issuer") or "").rstrip("/") != issuer:
        raise OIDCError(f"L'issuer dichiarato dal provider ({doc.get('issuer')}) non coincide con quello configurato ({issuer}).")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not doc.get(key):
            raise OIDCError(f"Nella configurazione del provider manca «{key}».")
    _cache["d:" + issuer] = (time.time(), doc)
    return doc


async def jwks(doc: dict, fresh: bool = False) -> list[dict]:
    url = doc["jwks_uri"]
    cached = _cache.get("k:" + url)
    if cached and not fresh and time.time() - cached[0] < DISCOVERY_SECONDS:
        return cached[1]["keys"]
    data = await _get_json(url, "le chiavi (JWKS)")
    keys = data.get("keys")
    if not isinstance(keys, list):
        raise OIDCError("Le chiavi del provider (JWKS) non sono valide.")
    _cache["k:" + url] = (time.time(), {"keys": keys})
    return keys


def forget_cache() -> None:
    _cache.clear()


# ---------- PKCE, state, nonce ----------


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


def state_hash(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


# ---------- Token ----------


async def exchange_code(doc: dict, cfg: OIDCConfig, code: str, verifier: str, redirect: str) -> dict:
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect, "code_verifier": verifier, "client_id": cfg.client_id}
    methods = doc.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    auth = None
    if cfg.client_secret:
        if "client_secret_basic" in methods:
            auth = httpx.BasicAuth(cfg.client_id, cfg.client_secret)
        else:
            data["client_secret"] = cfg.client_secret
    try:
        async with _client() as client:
            resp = await client.post(doc["token_endpoint"], data=data, auth=auth)
    except httpx.HTTPError:
        raise OIDCError("Il provider non risponde: riprova tra poco.")
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code != 200 or "id_token" not in body:
        detail = body.get("error_description") or body.get("error") or f"errore {resp.status_code}"
        raise OIDCError(f"Il provider non ha accettato l'accesso ({detail}). Controlla client ID, client secret e indirizzo di ritorno.")
    return body


async def verify_id_token(token: str, doc: dict, cfg: OIDCConfig, nonce: str) -> dict:
    """Le informazioni dell'ID token, dopo aver controllato firma, emittente, destinatario, scadenza e nonce."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise OIDCError("Il provider ha mandato un token non valido.")
    alg = header.get("alg", "")
    allowed = [a for a in (doc.get("id_token_signing_alg_values_supported") or ["RS256"]) if a in ALGORITHMS]
    if alg not in allowed:
        raise OIDCError(f"Algoritmo di firma del token non accettato ({alg or 'nessuno'}).")
    if alg.startswith("HS"):
        if not cfg.client_secret:
            raise OIDCError("Il provider firma i token con il client secret, ma il client secret non è configurato.")
        key = cfg.client_secret
    else:
        key = None
        for fresh in (False, True):  # chiave nuova del provider: si rileggono le chiavi una volta
            for jwk in await jwks(doc, fresh=fresh):
                if header.get("kid") in (None, jwk.get("kid")) and jwk.get("use", "sig") == "sig":
                    try:
                        key = jwt.PyJWK(jwk, algorithm=alg).key
                        break
                    except jwt.PyJWTError:
                        continue
            if key is not None:
                break
        if key is None:
            raise OIDCError("Non trovo la chiave del provider con cui è firmato il token.")
    try:
        claims = jwt.decode(
            token, key, algorithms=[alg], audience=cfg.client_id, issuer=doc["issuer"], leeway=60,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise OIDCError("Il token del provider è scaduto: riprova.")
    except jwt.PyJWTError as exc:
        raise OIDCError(f"Il token del provider non è valido ({exc}).")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise OIDCError("Il token del provider non corrisponde a questo accesso (nonce): riprova.")
    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != cfg.client_id:
        raise OIDCError("Il token del provider è destinato a un'altra applicazione.")
    return claims


async def userinfo(doc: dict, access_token: str) -> dict:
    if not doc.get("userinfo_endpoint") or not access_token:
        return {}
    try:
        async with _client() as client:
            resp = await client.get(doc["userinfo_endpoint"], headers={"Authorization": f"Bearer {access_token}"})
        return resp.json() if resp.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        return {}


def claim_values(claims: dict, name: str) -> list[str]:
    """I valori di un claim (lista, stringa separata da spazi o virgole), per il gruppo degli amministratori."""
    value = claims.get(name)
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [v for v in value.replace(",", " ").split() if v]
    if isinstance(value, bool):
        return ["true"] if value else []
    return []


def is_verified(claims: dict) -> bool:
    value = claims.get("email_verified")
    return value is True or (isinstance(value, str) and value.lower() == "true")


def describe(cfg: OIDCConfig, public_url: str) -> dict:
    """La configurazione per il pannello, senza il client secret."""
    data = asdict(cfg)
    data.pop("client_secret")
    data["has_secret"] = bool(cfg.client_secret)
    data["redirect_uri"] = redirect_uri(public_url)
    data["ready"] = cfg.ready
    data["emergency"] = emergency_env()
    return data


def dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
