"""Notifiche push: cifratura e firma secondo gli standard, iscrizioni, quando si notifica."""

from __future__ import annotations

import asyncio
import json
import os
import struct

import httpx
import respx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.push import webpush
from app.push.webpush import b64u, unb64u
from app.reading import edition

from helpers import entry, feed

FCM = "https://fcm.googleapis.com/fcm/send/abc123"


class Device:
    """Un browser finto: le sue chiavi e la decifratura (come farebbe il browser vero)."""

    def __init__(self, endpoint=FCM):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        self.endpoint = endpoint
        raw = self.key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.p256dh = b64u(raw)

    def subscription(self):
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": b64u(self.auth)}}

    def decrypt(self, body: bytes) -> dict:
        salt, rs, idlen = body[:16], struct.unpack("!I", body[16:20])[0], body[20]
        assert rs == 4096 and idlen == 65
        as_public = body[21:86]
        server = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
        shared = self.key.exchange(ec.ECDH(), server)

        def hkdf(salt_, ikm, info, n):
            return HKDF(algorithm=hashes.SHA256(), length=n, salt=salt_, info=info).derive(ikm)

        ua_public = unb64u(self.p256dh)
        ikm = hkdf(self.auth, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
        cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        plain = AESGCM(cek).decrypt(nonce, body[86:], None)
        assert plain.endswith(b"\x02")
        return json.loads(plain[:-1])


def test_encryption_and_vapid(app, client):
    device = Device()
    body = webpush.encrypt(b'{"title": "ciao"}', device.p256dh, b64u(device.auth))
    assert device.decrypt(body) == {"title": "ciao"}

    vapid = app.state.ctx.notifier.vapid
    header = vapid.authorization(FCM, now=1_800_000_000)
    token, key = header.removeprefix("vapid t=").split(", k=")
    assert key == vapid.public_key
    h, c, sig = token.split(".")
    claims = json.loads(unb64u(c))
    assert claims == {"aud": "https://fcm.googleapis.com", "exp": 1_800_000_000 + 12 * 3600, "sub": "https://feed.example.org"}
    raw = unb64u(sig)
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64u(key))
    public.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")), f"{h}.{c}".encode(), ec.ECDSA(hashes.SHA256()))
    # La chiave resta la stessa tra un avvio e l'altro.
    assert (app.state.ctx.settings.data_dir / "vapid.pem").exists()

    assert webpush.allowed_endpoint("https://web.push.apple.com/QGuQ") is True
    assert webpush.allowed_endpoint("https://wns2-par02p.notify.windows.com/w/?token=x") is True
    assert webpush.allowed_endpoint("http://fcm.googleapis.com/x") is False
    assert webpush.allowed_endpoint("https://evil.example/fcm.googleapis.com") is False
    assert webpush.allowed_endpoint("https://192.168.1.1/") is False


def test_subscriptions_api(admin):
    assert admin.get("/api/push/key").json()["public_key"]
    device = Device()
    bad = admin.post("/api/push/subscriptions", json={**device.subscription(), "endpoint": "https://192.168.1.10/push"})
    assert bad.status_code == 422 and "non è supportato" in bad.json()["detail"]
    wrong_keys = device.subscription()
    wrong_keys["keys"]["auth"] = "abc"
    assert admin.post("/api/push/subscriptions", json=wrong_keys).status_code == 422

    assert admin.post("/api/push/subscriptions", json=device.subscription()).json() == {"devices": 1}
    assert admin.post("/api/push/subscriptions", json=device.subscription()).json() == {"devices": 1}  # stesso dispositivo
    assert admin.request("DELETE", "/api/push/subscriptions", json={"endpoint": FCM}).json() == {"devices": 0}
    assert admin.post("/api/push/test").status_code == 404


@respx.mock
def test_news_notifications(admin, app):
    device = Device()
    admin.post("/api/push/subscriptions", json=device.subscription())
    received = []
    route = respx.post(FCM).mock(side_effect=lambda r: received.append(r) or httpx.Response(201))

    # Prova dalle Impostazioni.
    assert admin.post("/api/push/test").json() == {"sent": 1}
    req = received[-1]
    assert req.headers["content-encoding"] == "aes128gcm" and req.headers["authorization"].startswith("vapid t=")
    assert device.decrypt(req.content)["body"] == "Le notifiche funzionano su questo dispositivo."

    spazio = admin.post("/api/folders", json={"name": "Spazio", "color": "blu"}).json()["folder"]["id"]
    admin.post("/api/interests/keywords", json={"keyword": "razzo", "level": "alta"})
    admin.post("/api/interests/keywords", json={"keyword": "ricetta"})
    [razzo, _] = feed(app, admin, "https://orbita.example/feed", [
        entry("Il razzo europeo vola", hours_ago=1), entry("Senza interessi", hours_ago=1),
    ], title="Orbita", folder_id=spazio)
    feed(app, admin, "https://cucina.example/feed", [entry("Una ricetta nuova", hours_ago=1)], title="Cucina")

    notifier = app.state.ctx.notifier
    notifier.last_sent.clear()
    # Nessuna cartella importante: nessuna notifica.
    assert asyncio.run(notifier.notify_news()) == 0
    admin.patch("/api/me", json={"prefs": {"notify_folders": [str(spazio)]}})
    assert asyncio.run(notifier.notify_news()) == 1
    data = device.decrypt(received[-1].content)
    assert data["title"] == "Orbita" and data["body"] == "Il razzo europeo vola"
    assert data["url"] == f"/?a={razzo}" and data["badge"] == 3
    assert received[-1].headers["urgency"] == "high"

    # Già notificata: non si ripete; e c'è il limite di una ogni 10 minuti.
    notifier.last_sent.clear()
    assert asyncio.run(notifier.notify_news()) == 0
    admin.patch("/api/me", json={"prefs": {"notify_folders": [str(spazio), "none"]}})
    assert asyncio.run(notifier.notify_news()) == 1  # la ricetta, dalle fonti senza cartella
    feed(app, admin, "https://cucina.example/feed", [entry("Ricetta dei biscotti", hours_ago=1), entry("Ricetta del pane", hours_ago=1)], title="Cucina")
    assert asyncio.run(notifier.notify_news()) == 0  # troppo presto
    notifier.last_sent.clear()
    assert asyncio.run(notifier.notify_news()) == 1
    data = device.decrypt(received[-1].content)
    assert data["title"] == "2 notizie per te" and "Ricetta del pane" in data["body"]

    # Edizione pronta.
    admin.patch("/api/me", json={"prefs": {"edition": True}})
    [(uid, ed)] = edition.run_due(app.state.ctx)
    asyncio.run(app.state.ctx.hooks.emit_edition_ready(uid, ed))
    assert device.decrypt(received[-1].content)["title"].startswith("L'Edizione delle")
    admin.patch("/api/me", json={"prefs": {"notify_edition": False}})
    count = route.call_count
    asyncio.run(notifier.edition_ready(uid, ed))
    assert route.call_count == count

    # Il browser ha tolto l'iscrizione: il server la dimentica.
    route.mock(return_value=httpx.Response(410))
    assert admin.post("/api/push/test").status_code == 404
    assert admin.get("/api/push/subscriptions").json() == {"devices": 0}

    bad = admin.patch("/api/me", json={"prefs": {"notify_folders": ["../etc"]}})
    assert bad.status_code == 422
