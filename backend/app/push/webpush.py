"""Web Push standard, senza servizi esterni oltre a quelli dei browser.

- Chiavi VAPID (RFC 8292): una coppia di chiavi P-256 creata al primo avvio e salvata in
  data/vapid.pem. La chiave pubblica va al browser quando si iscrive; con quella privata il
  server firma ogni invio.
- Contenuto cifrato con «aes128gcm» (RFC 8291 e RFC 8188): solo il browser che si è iscritto
  può leggerlo, il servizio push del browser (Google, Mozilla, Apple…) no.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096
TTL = 24 * 3600
# Servizi push dei browser: solo questi indirizzi ricevono richieste dal server.
PUSH_HOSTS = (
    "fcm.googleapis.com",  # Chrome, Edge su Android, Samsung Internet
    "push.services.mozilla.com",  # Firefox
    "push.apple.com",  # Safari e PWA su iPhone, iPad e Mac
    "notify.windows.com",  # Edge su Windows
)


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def unb64u(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def allowed_endpoint(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return False
    return any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def _raw_public(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


class Vapid:
    def __init__(self, private_key: ec.EllipticCurvePrivateKey, subject: str):
        self.private_key = private_key
        self.subject = subject
        self.public_key = b64u(_raw_public(private_key.public_key()))

    @classmethod
    def load_or_create(cls, path: Path, subject: str) -> "Vapid":
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        else:
            key = ec.generate_private_key(ec.SECP256R1())
            path.write_bytes(
                key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
            )
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        return cls(key, subject)

    def authorization(self, endpoint: str, now: int | None = None) -> str:
        parts = urlsplit(endpoint)
        claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int(now or time.time()) + 12 * 3600, "sub": self.subject}
        header = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
        body = b64u(json.dumps(claims, separators=(",", ":")).encode())
        signing_input = f"{header}.{body}".encode()
        r, s = decode_dss_signature(self.private_key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return f"vapid t={header}.{body}.{b64u(signature)}, k={self.public_key}"


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(payload: bytes, p256dh: str, auth: str, salt: bytes | None = None, server_key=None) -> bytes:
    """Cifra il contenuto per un dispositivo (RFC 8291, un solo record aes128gcm)."""
    ua_public = unb64u(p256dh)
    auth_secret = unb64u(auth)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    server_key = server_key or ec.generate_private_key(ec.SECP256R1())
    as_public = _raw_public(server_key.public_key())
    shared = server_key.exchange(ec.ECDH(), ua_key)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack("!IB", RECORD_SIZE, len(as_public)) + as_public + ciphertext


@dataclass
class Subscription:
    id: int
    endpoint: str
    p256dh: str
    auth: str


@dataclass
class Outcome:
    ok: bool
    gone: bool = False  # il dispositivo non è più iscritto: va tolto
    status: int | None = None
    message: str = ""


async def send(client: httpx.AsyncClient, vapid: Vapid, sub: Subscription, data: dict, urgency: str = "normal") -> Outcome:
    if not allowed_endpoint(sub.endpoint):
        return Outcome(False, gone=True, message="Servizio push non riconosciuto.")
    payload = json.dumps(data, ensure_ascii=False).encode()
    try:
        body = encrypt(payload, sub.p256dh, sub.auth)
    except (ValueError, TypeError):
        return Outcome(False, gone=True, message="Chiavi del dispositivo non valide.")
    headers = {
        "Authorization": vapid.authorization(sub.endpoint),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(TTL),
        "Urgency": urgency,
    }
    try:
        res = await client.post(sub.endpoint, content=body, headers=headers)
    except httpx.HTTPError:
        return Outcome(False, message="Il servizio push non risponde.")
    if res.status_code in (200, 201, 202):
        return Outcome(True, status=res.status_code)
    if res.status_code in (404, 410):
        return Outcome(False, gone=True, status=res.status_code, message="Il dispositivo non è più iscritto.")
    return Outcome(False, status=res.status_code, message=f"Il servizio push ha risposto {res.status_code}.")
