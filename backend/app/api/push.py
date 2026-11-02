"""Notifiche push: chiave pubblica, iscrizione dei dispositivi, prova."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import now
from ..deps import AppContext, User, current_user, get_ctx, get_db
from ..push.webpush import allowed_endpoint, unb64u
from .common import user_agent

router = APIRouter(prefix="/api/push", tags=["notifiche"])

MAX_DEVICES = 20


@router.get("/key")
def public_key(_: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    return {"public_key": ctx.notifier.vapid.public_key}


class Keys(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class NewSubscription(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: Keys


class EndpointBody(BaseModel):
    endpoint: str = Field(max_length=1000)


def _devices(conn: sqlite3.Connection, user_id: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM push_subscriptions WHERE user_id = ?", (user_id,)).fetchone()[0]


@router.get("/subscriptions")
def subscriptions(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return {"devices": _devices(conn, user.id)}


@router.post("/subscriptions", status_code=201)
def subscribe(body: NewSubscription, request: Request, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    if not allowed_endpoint(body.endpoint):
        raise HTTPException(status_code=422, detail="Il servizio di notifiche di questo browser non è supportato.")
    try:
        ok = len(unb64u(body.keys.p256dh)) == 65 and len(unb64u(body.keys.auth)) == 16
    except ValueError:
        ok = False
    if not ok:
        raise HTTPException(status_code=422, detail="Chiavi di iscrizione non valide.")
    with conn:
        # Lo stesso dispositivo può passare a un altro account: l'iscrizione segue chi è entrato.
        conn.execute(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, user_agent, created_at) VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (endpoint) DO UPDATE SET user_id = excluded.user_id, p256dh = excluded.p256dh,"
            " auth = excluded.auth, user_agent = excluded.user_agent, failures = 0",
            (user.id, body.endpoint, body.keys.p256dh, body.keys.auth, user_agent(request)[:300], now()),
        )
        conn.execute(
            "DELETE FROM push_subscriptions WHERE user_id = ? AND id NOT IN"
            " (SELECT id FROM push_subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?)",
            (user.id, user.id, MAX_DEVICES),
        )
    return {"devices": _devices(conn, user.id)}


@router.delete("/subscriptions")
def unsubscribe(body: EndpointBody, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    with conn:
        conn.execute("DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?", (user.id, body.endpoint))
    return {"devices": _devices(conn, user.id)}


@router.post("/test")
async def test(user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    sent, errors = await ctx.notifier.send_to_user(
        user.id,
        {"title": "Galactic Feed", "body": "Le notifiche funzionano su questo dispositivo.", "url": "/", "tag": "prova"},
    )
    if not sent:
        detail = errors[0] if errors else "Nessun dispositivo iscritto alle notifiche."
        raise HTTPException(status_code=502 if errors else 404, detail=detail)
    return {"sent": sent}
