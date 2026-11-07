"""Gestione degli utenti e degli inviti (solo amministratore)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .. import instance, oidc
from ..config import VERSION
from ..db import get_setting, iso, now
from ..deps import AppContext, User, get_ctx, get_db, require_admin
from .common import Prefs, prefs_with_defaults
from .invites import create_invite
from .oidc import UNUSABLE_PASSWORD

router = APIRouter(prefix="/api/admin", tags=["amministrazione"])


def _user_row(row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
    linked = conn.execute("SELECT COUNT(*) FROM user_identities WHERE user_id = ?", (row["id"],)).fetchone()[0]
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"] or row["username"],
        "is_admin": bool(row["is_admin"]),
        "disabled": bool(row["disabled"]),
        "created_at": iso(row["created_at"]),
        "last_seen_at": iso(row["last_seen_at"]),
        # Come entra: con la password (account locale), con il provider OIDC, o in entrambi i modi.
        "has_password": row["password_hash"] != UNUSABLE_PASSWORD,
        "linked_identities": linked,
        "admin_via_group": bool(row["admin_via_group"]),
    }


def _get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Utente non trovato.")
    return row


@router.get("/users")
def list_users(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT * FROM users ORDER BY created_at, id").fetchall()
    return {"users": [_user_row(r, conn) for r in rows]}


class UserPatch(BaseModel):
    is_admin: bool | None = None
    disabled: bool | None = None


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserPatch,
    admin: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
):
    row = _get_user(conn, user_id)
    if user_id == admin.id and (body.is_admin is False or body.disabled is True):
        raise HTTPException(
            status_code=400,
            detail="Non puoi togliere i permessi a te stesso né disattivarti: chiedilo a un altro amministratore.",
        )
    is_admin = row["is_admin"] if body.is_admin is None else int(body.is_admin)
    disabled = row["disabled"] if body.disabled is None else int(body.disabled)
    with conn:
        conn.execute("UPDATE users SET is_admin = ?, disabled = ? WHERE id = ?", (is_admin, disabled, user_id))
        if body.is_admin is not None:
            # Scelta fatta a mano: il gruppo del provider non la annulla più (vedi api/oidc.py).
            conn.execute("UPDATE users SET admin_via_group = 0 WHERE id = ?", (user_id,))
        if disabled:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return {"user": _user_row(_get_user(conn, user_id), conn)}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Non puoi eliminare il tuo stesso account.")
    _get_user(conn, user_id)
    with conn:
        # Fonti, interessi, letti e salvati dell'utente spariscono con lui (ON DELETE CASCADE).
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"ok": True}


@router.post("/users/{user_id}/reset")
def reset_link(
    user_id: int,
    admin: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    row = _get_user(conn, user_id)
    link = create_invite(conn, ctx, "reset", admin.id, note=f"Nuova password per {row['username']}", target_user_id=user_id)
    return {"invite": link}


def _invite_row(row: sqlite3.Row, ts: int) -> dict:
    if row["used_at"]:
        status = "usato"
    elif row["expires_at"] <= ts:
        status = "scaduto"
    else:
        status = "valido"
    return {
        "id": row["id"],
        "kind": row["kind"],
        "note": row["note"],
        "status": status,
        "created_at": iso(row["created_at"]),
        "expires_at": iso(row["expires_at"]),
        "used_at": iso(row["used_at"]),
        "used_by": row["used_by_name"],
        "target_user": row["target_name"],
    }


@router.get("/invites")
def list_invites(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    ts = now()
    # I link usati o scaduti da più di una settimana non servono più.
    with conn:
        conn.execute(
            "DELETE FROM invites WHERE (used_at IS NOT NULL AND used_at < ?) OR expires_at < ?",
            (ts - 7 * 86400, ts - 7 * 86400),
        )
    rows = conn.execute(
        "SELECT i.*, u.username AS used_by_name, t.username AS target_name FROM invites i"
        " LEFT JOIN users u ON u.id = i.used_by LEFT JOIN users t ON t.id = i.target_user_id"
        " ORDER BY i.created_at DESC, i.id DESC"
    ).fetchall()
    return {"invites": [_invite_row(r, ts) for r in rows]}


class InviteBody(BaseModel):
    note: str = ""


@router.post("/invites")
def new_invite(
    body: InviteBody | None = None,
    admin: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    note = " ".join(((body.note if body else "") or "").split())[:80]
    return {"invite": create_invite(conn, ctx, "invite", admin.id, note=note)}


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: int, _: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    with conn:
        cur = conn.execute("DELETE FROM invites WHERE id = ?", (invite_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Invito non trovato.")
    return {"ok": True}


@router.get("/status")
def status(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    """Stato del sistema per il pannello: versione, spazio, feed, errori recenti, variabili d'avvio."""
    path = ctx.settings.db_path
    size = sum(p.stat().st_size for p in path.parent.glob(path.name + "*") if p.is_file())
    counts = conn.execute(
        "SELECT (SELECT COUNT(*) FROM users) AS users, (SELECT COUNT(*) FROM feeds) AS feeds,"
        " (SELECT COUNT(*) FROM articles) AS articles, (SELECT MAX(last_fetch_at) FROM feeds) AS last_fetch,"
        " (SELECT COUNT(*) FROM feeds WHERE error_message IS NOT NULL) AS feeds_with_errors"
    ).fetchone()
    errors = conn.execute(
        "SELECT f.url, f.title, f.error_message, f.error_since, f.last_fetch_at, COUNT(s.id) AS followers"
        " FROM feeds f LEFT JOIN subscriptions s ON s.feed_id = f.id"
        " WHERE f.error_message IS NOT NULL GROUP BY f.id ORDER BY f.last_fetch_at DESC LIMIT 10"
    ).fetchall()
    ai_error = get_setting(conn, "ai.last_error") or None
    ai_error_at = get_setting(conn, "ai.last_error_at")
    scheduler = ctx.scheduler
    return {
        "version": VERSION,
        "public_url": ctx.settings.public_url,
        "timezone": ctx.instance.get("timezone", conn),
        "users": counts["users"],
        "feeds": counts["feeds"],
        "articles": counts["articles"],
        "database_bytes": size,
        "retention_days": ctx.instance.get("retention_days", conn),
        "last_fetch_at": iso(counts["last_fetch"]),
        "scheduler_last_run_at": iso(scheduler.last_run_at) if scheduler and scheduler.last_run_at else None,
        "feeds_with_errors": counts["feeds_with_errors"],
        "recent_errors": [
            {
                "title": r["title"] or r["url"],
                "url": r["url"],
                "error": r["error_message"],
                "since": iso(r["error_since"]),
                "followers": r["followers"],
            }
            for r in errors
        ],
        "ai_error": {"message": ai_error, "at": iso(int(ai_error_at)) if ai_error_at.isdigit() else None} if ai_error else None,
        # Restano variabili d'ambiente: si leggono all'avvio, non si cambiano dal pannello.
        "environment": {name: read(ctx.settings) for name, read in instance.ENV_ONLY.items()},
    }


# ---------- Impostazioni dell'istanza ----------


@router.get("/settings")
def get_settings(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    return {"settings": ctx.instance.describe(conn)}


@router.patch("/settings")
def update_settings(
    body: dict,
    _: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    """Cambia una o più impostazioni (tutte o nessuna). null torna alla variabile d'ambiente o al predefinito."""
    try:
        ctx.instance.save(conn, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if ctx.scheduler:
        ctx.scheduler.wake()
    return {"settings": ctx.instance.describe(conn)}


# ---------- Preferenze per i nuovi utenti ----------


def _defaults_payload(ctx: AppContext, conn: sqlite3.Connection) -> dict:
    chosen = ctx.instance.user_defaults(conn)
    full = prefs_with_defaults(chosen)
    return {"prefs": {k: full[k] for k in instance.DEFAULT_PREFS}, "chosen": sorted(chosen)}


@router.get("/defaults")
def get_defaults(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    """Le preferenze con cui partono i nuovi account. chosen: quelle scelte dall'amministratore."""
    return _defaults_payload(ctx, conn)


@router.put("/defaults")
def put_defaults(
    body: dict,
    _: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    """Sostituisce le preferenze iniziali dei nuovi account. Valgono per chi si iscrive da adesso."""
    unknown = [k for k in body if k not in instance.DEFAULT_PREFS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Preferenza sconosciuta: {unknown[0]}.")
    checked = Prefs(**{**Prefs().model_dump(), **body}).model_dump()
    ctx.instance.save_user_defaults(conn, {k: checked[k] for k in body})
    return _defaults_payload(ctx, conn)


# ---------- Nazione delle fonti condivise (#20) ----------


@router.get("/feeds")
def list_feeds(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    """I feed seguiti, con la nazione proposta e quella corretta dall'amministratore."""
    rows = conn.execute(
        "SELECT f.id, f.url, f.title, f.site_url, f.language, f.country, f.country_admin, COUNT(s.id) AS followers"
        " FROM feeds f JOIN subscriptions s ON s.feed_id = f.id GROUP BY f.id ORDER BY f.title COLLATE NOCASE"
    ).fetchall()
    return {
        "feeds": [
            {
                "id": r["id"], "title": r["title"] or r["url"], "url": r["url"], "site_url": r["site_url"],
                "language": r["language"] or None, "country_auto": r["country"] or None, "country_admin": r["country_admin"],
                "country": (r["country_admin"] if r["country_admin"] is not None else r["country"]) or None,
                "followers": r["followers"],
            }
            for r in rows
        ]
    }


class FeedPatch(BaseModel):
    # «IT», "" (nessuna nazione) oppure null (torna a quella proposta in automatico).
    country: str | None = None


@router.patch("/feeds/{feed_id}")
def update_feed(feed_id: int, body: FeedPatch, _: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    """Corregge la nazione di un feed per tutti (chi l'ha scelta per sé tiene la sua)."""
    from .sources import check_country

    try:
        country = check_country(body.country)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    with conn:
        cur = conn.execute("UPDATE feeds SET country_admin = ? WHERE id = ?", (country, feed_id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Feed non trovato.")
    return list_feeds(_, conn)


# ---------- Accesso con un provider OIDC (#22) ----------


def _oidc_payload(conn: sqlite3.Connection, ctx: AppContext) -> dict:
    cfg = oidc.load(conn, ctx.secret)
    data = oidc.describe(cfg, ctx.settings.public_url)
    data["linked_admins"] = conn.execute(
        "SELECT COUNT(DISTINCT u.id) FROM users u JOIN user_identities i ON i.user_id = u.id WHERE u.is_admin = 1 AND u.disabled = 0"
    ).fetchone()[0]
    data["linked_users"] = conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_identities").fetchone()[0]
    return data


@router.get("/oidc")
def get_oidc(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    return _oidc_payload(conn, ctx)


class OIDCBody(BaseModel):
    enabled: bool | None = None
    issuer: str | None = None
    client_id: str | None = None
    # None: resta quello salvato; "": si cancella.
    client_secret: str | None = None
    scopes: str | None = None
    label: str | None = None
    auto_create: bool | None = None
    link_email: bool | None = None
    link_username: bool | None = None
    admin_claim: str | None = None
    admin_value: str | None = None
    password_login: bool | None = None
    rp_logout: bool | None = None


@router.put("/oidc")
def put_oidc(
    body: OIDCBody, _: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    cfg = oidc.load(conn, ctx.secret)
    for key, value in body.model_dump(exclude_none=True).items():
        if isinstance(value, str):
            value = value.strip()
        setattr(cfg, key, value)
    cfg.issuer = cfg.issuer.rstrip("/")
    if cfg.issuer and not cfg.issuer.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="L'issuer deve iniziare con https:// (o http:// nella rete di casa).")
    if "openid" not in cfg.scopes.split():
        cfg.scopes = ("openid " + cfg.scopes).strip()
    cfg.label = " ".join(cfg.label.split())[:40] or "Entra con il tuo account"
    if cfg.enabled and (not cfg.issuer or not cfg.client_id):
        raise HTTPException(status_code=422, detail="Per accendere l'accesso servono issuer e client ID.")
    if not cfg.password_login:
        linked = conn.execute(
            "SELECT 1 FROM users u JOIN user_identities i ON i.user_id = u.id WHERE u.is_admin = 1 AND u.disabled = 0 LIMIT 1"
        ).fetchone()
        if not cfg.ready or not linked:
            raise HTTPException(
                status_code=422,
                detail="Prima di spegnere l'accesso con password, accendi il provider e collega l'account di almeno un amministratore.",
            )
    oidc.save(conn, cfg, ctx.secret)
    oidc.forget_cache()
    return _oidc_payload(conn, ctx)


@router.post("/oidc/test")
async def test_oidc(_: User = Depends(require_admin), ctx: AppContext = Depends(get_ctx)):
    """«Prova la configurazione»: legge la configurazione del provider e le sue chiavi."""
    with ctx.db.session() as conn:
        cfg = oidc.load(conn, ctx.secret)
    if not cfg.issuer or not cfg.client_id:
        raise HTTPException(status_code=422, detail="Scrivi almeno issuer e client ID.")
    try:
        doc = await oidc.discover(cfg.issuer, fresh=True)
        keys = await oidc.jwks(doc, fresh=True)
    except oidc.OIDCError as exc:
        raise HTTPException(status_code=502, detail=exc.message)
    algs = doc.get("id_token_signing_alg_values_supported") or ["RS256"]
    if any(a.startswith("HS") for a in algs) and not any(not a.startswith("HS") for a in algs) and not cfg.client_secret:
        raise HTTPException(status_code=422, detail="Il provider firma i token con il client secret: inseriscilo.")
    return {
        "ok": True,
        "issuer": doc["issuer"],
        "keys": len(keys),
        "algorithms": algs,
        "end_session": bool(doc.get("end_session_endpoint")),
        "message": f"Il provider risponde: {len(keys)} chiavi, firma {', '.join(algs)}. Ora prova a entrare con «{cfg.label}».",
    }
