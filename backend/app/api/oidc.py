"""Accesso con un provider OpenID Connect (issue #22): avvio, ritorno dal provider, account collegati.

Il browser va su /api/auth/oidc/start, che lo manda al provider; il provider lo rimanda su
/api/auth/oidc/callback con un codice, che il server scambia con i token. Alla fine si apre
la normale sessione di Galactic Feed (con «Ricordami» e le durate scelte dall'amministratore)
e si torna all'app. Gli errori tornano all'app come ?oidc_error=… da mostrare nella pagina di accesso.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import sqlite3
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import oidc
from ..db import now
from ..deps import AppContext, User, current_user, get_ctx, get_db, load_session_user
from .common import start_session

log = logging.getLogger("galactic_feed.oidc")
router = APIRouter(prefix="/api", tags=["accesso con provider"])

STATE_COOKIE = "gf_oidc"
UNUSABLE_PASSWORD = "!oidc"  # gli utenti creati dal provider non hanno una password


def _cookie_args(request: Request) -> dict:
    return {"httponly": True, "samesite": "lax", "secure": request.url.scheme == "https", "path": "/api/auth/oidc"}


def _back(request: Request, ctx: AppContext, **params) -> RedirectResponse:
    """Torna all'app; senza parametri all'inizio, altrimenti con l'esito (?oidc_error=… o ?oidc_linked=1)."""
    url = "/" + ("?" + urlencode(params, quote_via=quote) if params else "")
    resp = RedirectResponse(url, status_code=303)
    resp.delete_cookie(STATE_COOKIE, **_cookie_args(request))
    return resp


@router.get("/auth/oidc/start")
async def start(
    request: Request, remember: bool = False, link: bool = False,
    conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx),
):
    """Manda il browser al provider. Con link=1 collega l'account del provider all'utente collegato."""
    cfg = oidc.load(conn, ctx.secret)
    if not cfg.ready:
        raise HTTPException(status_code=404, detail="L'accesso con il provider non è configurato.")
    link_user = None
    if link:
        user = load_session_user(request, conn, ctx)
        if user is None:
            return _back(request, ctx, oidc_error="Per collegare un account devi prima entrare.")
        link_user = user.id
    try:
        doc = await oidc.discover(cfg.issuer)
    except oidc.OIDCError as exc:
        return _back(request, ctx, oidc_error=exc.message)
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, challenge = oidc.pkce_pair()
    ts = now()
    with conn:
        conn.execute("DELETE FROM oidc_states WHERE created_at < ?", (ts - oidc.STATE_SECONDS,))
        conn.execute(
            "INSERT INTO oidc_states (state_hash, verifier, nonce, remember, link_user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (oidc.state_hash(state), verifier, nonce, int(remember), link_user, ts),
        )
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": oidc.redirect_uri(ctx.settings.public_url),
        "scope": cfg.scopes or "openid",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    sep = "&" if "?" in doc["authorization_endpoint"] else "?"
    resp = RedirectResponse(doc["authorization_endpoint"] + sep + urlencode(params), status_code=303)
    # Lo state anche in un cookie: il ritorno vale solo nel browser che ha iniziato l'accesso.
    resp.set_cookie(STATE_COOKIE, state, max_age=oidc.STATE_SECONDS, **_cookie_args(request))
    return resp


def _username_from(claims: dict, conn: sqlite3.Connection) -> str:
    """Un nome utente libero, dal provider: preferred_username, poi l'email, poi il nome."""
    raw = claims.get("preferred_username") or (claims.get("email") or "").split("@")[0] or claims.get("name") or "utente"
    base = re.sub(r"[^A-Za-z0-9._-]+", "", str(raw).replace(" ", "."))[:28].strip("._-") or "utente"
    if len(base) < 3:
        base = (base + "user")[:3]
    if not base[0].isalnum():
        base = "u" + base
    candidate, n = base, 1
    while conn.execute("SELECT 1 FROM users WHERE username = ?", (candidate,)).fetchone():
        n += 1
        candidate = f"{base}{n}"
    return candidate


def _sync_admin(conn: sqlite3.Connection, cfg: oidc.OIDCConfig, user_id: int, claims: dict) -> None:
    """Amministratore secondo il gruppo del provider.

    Il gruppo dà i permessi e toglie solo quelli che ha dato lui: chi è stato reso amministratore
    da un altro amministratore nell'app (o è l'amministratore locale del primo avvio) lo resta.
    Mai lasciare l'istanza senza amministratori.
    """
    if not cfg.admin_claim or not cfg.admin_value:
        return
    should = cfg.admin_value in oidc.claim_values(claims, cfg.admin_claim)
    row = conn.execute("SELECT is_admin, admin_via_group FROM users WHERE id = ?", (user_id,)).fetchone()
    if should:
        if not row["is_admin"]:
            with conn:
                conn.execute("UPDATE users SET is_admin = 1, admin_via_group = 1 WHERE id = ?", (user_id,))
        return
    if not row["is_admin"] or not row["admin_via_group"]:
        return
    others = conn.execute(
        "SELECT COUNT(*) FROM users WHERE is_admin = 1 AND disabled = 0 AND id != ?", (user_id,)
    ).fetchone()[0]
    if others == 0:
        log.warning("L'utente %s non è più nel gruppo degli amministratori, ma è l'unico: resta amministratore.", user_id)
        return
    with conn:
        conn.execute("UPDATE users SET is_admin = 0, admin_via_group = 0 WHERE id = ?", (user_id,))


def _find_user(conn: sqlite3.Connection, cfg: oidc.OIDCConfig, ctx: AppContext, issuer: str, claims: dict) -> int:
    sub = str(claims["sub"])
    # Il collegamento automatico (stessa email o stesso nome utente) non tocca mai gli amministratori:
    # l'amministratore locale resta un account a parte, che entra con la sua password. Chi vuole
    # usare il provider anche per quell'account lo collega a mano dalle Impostazioni.
    row = conn.execute("SELECT user_id FROM user_identities WHERE issuer = ? AND subject = ?", (issuer, sub)).fetchone()
    if row:
        return row["user_id"]
    email = (claims.get("email") or "").strip().lower()
    user_id = None
    if cfg.link_email and email and oidc.is_verified(claims):
        found = conn.execute("SELECT id FROM users WHERE lower(email) = ? AND is_admin = 0", (email,)).fetchone()
        user_id = found["id"] if found else None
    if user_id is None and cfg.link_username and claims.get("preferred_username"):
        found = conn.execute(
            "SELECT id FROM users WHERE username = ? AND is_admin = 0", (str(claims["preferred_username"]),)
        ).fetchone()
        user_id = found["id"] if found else None
    if user_id is None:
        if not cfg.auto_create:
            raise oidc.OIDCError(
                "Il tuo account del provider non è collegato a nessun utente di Galactic Feed. "
                "Chiedi un invito all'amministratore, poi collega l'account dalle Impostazioni."
            )
        username = _username_from(claims, conn)
        display = " ".join(str(claims.get("name") or username).split())[:60] or username
        with conn:
            cur = conn.execute(
                "INSERT INTO users (username, display_name, password_hash, prefs, email, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (username, display, UNUSABLE_PASSWORD, json.dumps(ctx.instance.user_defaults(conn)),
                 email if oidc.is_verified(claims) else "", now()),
            )
        user_id = cur.lastrowid
        log.info("Nuovo utente %s creato dall'accesso con il provider", username)
    _add_identity(conn, user_id, issuer, claims)
    return user_id


def _add_identity(conn: sqlite3.Connection, user_id: int, issuer: str, claims: dict) -> None:
    with conn:
        conn.execute(
            "INSERT INTO user_identities (user_id, issuer, subject, email, username, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, issuer, str(claims["sub"]), str(claims.get("email") or ""), str(claims.get("preferred_username") or ""), now()),
        )
        if oidc.is_verified(claims) and claims.get("email"):
            conn.execute("UPDATE users SET email = ? WHERE id = ? AND email = ''", (str(claims["email"]).lower(), user_id))


@router.get("/auth/oidc/callback")
async def callback(
    request: Request, code: str = "", state: str = "", error: str = "", error_description: str = "",
    conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx),
):
    if error:
        return _back(request, ctx, oidc_error=f"Il provider non ha concesso l'accesso: {error_description or error}.")
    cookie = request.cookies.get(STATE_COOKIE, "")
    if not state or not cookie or not secrets.compare_digest(state, cookie):
        return _back(request, ctx, oidc_error="Accesso non valido o scaduto: riprova dall'inizio.")
    with conn:
        row = conn.execute("SELECT * FROM oidc_states WHERE state_hash = ?", (oidc.state_hash(state),)).fetchone()
        conn.execute("DELETE FROM oidc_states WHERE state_hash = ?", (oidc.state_hash(state),))
    if row is None or now() - row["created_at"] > oidc.STATE_SECONDS or not code:
        return _back(request, ctx, oidc_error="Accesso non valido o scaduto: riprova dall'inizio.")
    cfg = oidc.load(conn, ctx.secret)
    if not cfg.ready:
        return _back(request, ctx, oidc_error="L'accesso con il provider è stato spento.")
    try:
        doc = await oidc.discover(cfg.issuer)
        tokens = await oidc.exchange_code(doc, cfg, code, row["verifier"], oidc.redirect_uri(ctx.settings.public_url))
        claims = await oidc.verify_id_token(tokens["id_token"], doc, cfg, row["nonce"])
        # Email e gruppi a volte arrivano solo da userinfo.
        if cfg.admin_claim not in claims or "email" not in claims or "preferred_username" not in claims:
            extra = await oidc.userinfo(doc, tokens.get("access_token", ""))
            if extra.get("sub") == claims["sub"]:
                claims = {**extra, **claims}
        issuer = doc["issuer"]
        if row["link_user_id"]:
            taken = conn.execute(
                "SELECT user_id FROM user_identities WHERE issuer = ? AND subject = ?", (issuer, str(claims["sub"]))
            ).fetchone()
            if taken and taken["user_id"] != row["link_user_id"]:
                raise oidc.OIDCError("Questo account del provider è già collegato a un altro utente.")
            if not taken:
                _add_identity(conn, row["link_user_id"], issuer, claims)
            return _back(request, ctx, oidc_linked="1")
        user_id = _find_user(conn, cfg, ctx, issuer, claims)
    except oidc.OIDCError as exc:
        log.info("Accesso con il provider non riuscito: %s", exc.message)
        return _back(request, ctx, oidc_error=exc.message)
    user = conn.execute("SELECT disabled FROM users WHERE id = ?", (user_id,)).fetchone()
    if user["disabled"]:
        return _back(request, ctx, oidc_error="Questo account è disattivato. Chiedi all'amministratore.")
    _sync_admin(conn, cfg, user_id, claims)
    with conn:
        conn.execute(
            "UPDATE user_identities SET last_login_at = ? WHERE issuer = ? AND subject = ?", (now(), issuer, str(claims["sub"]))
        )
    resp = _back(request, ctx)
    start_session(request, resp, conn, ctx, user_id, remember=bool(row["remember"]), via="oidc")
    return resp


# ---------- Account collegati (Impostazioni personali) ----------


@router.get("/me/identities")
def my_identities(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT id, issuer, email, username, created_at, last_login_at FROM user_identities WHERE user_id = ? ORDER BY id",
        (user.id,),
    ).fetchall()
    has_password = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()["password_hash"] != UNUSABLE_PASSWORD
    return {
        "identities": [
            {"id": r["id"], "issuer": r["issuer"], "email": r["email"] or None, "username": r["username"] or None,
             "created_at": r["created_at"], "last_login_at": r["last_login_at"]}
            for r in rows
        ],
        "has_password": has_password,
    }


@router.delete("/me/identities/{identity_id}")
def unlink(identity_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    rows = conn.execute("SELECT id FROM user_identities WHERE user_id = ?", (user.id,)).fetchall()
    if identity_id not in {r["id"] for r in rows}:
        raise HTTPException(status_code=404, detail="Account collegato non trovato.")
    has_password = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()["password_hash"] != UNUSABLE_PASSWORD
    cfg = oidc.load(conn, ctx.secret)
    if len(rows) == 1 and (not has_password or not oidc.password_login_allowed(cfg)):
        raise HTTPException(status_code=409, detail="È il tuo unico modo per entrare: scollegandolo non potresti più accedere.")
    with conn:
        conn.execute("DELETE FROM user_identities WHERE id = ?", (identity_id,))
    return my_identities(user, conn)
