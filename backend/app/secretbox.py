"""Segreti salvati nel database (chiave dell'AI, in futuro il client secret OIDC).

Si cifrano con una chiave ricavata da data/secret.key, che resta fuori dal database:
una copia del solo file galactic-feed.db non rivela i segreti. Le API non li restituiscono mai.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("galactic_feed.secretbox")

PREFIX = "enc1:"
_PURPOSE = b"galactic-feed/app-settings"


def _fernet(secret: bytes) -> Fernet:
    if not secret:
        raise RuntimeError("La chiave del server (secret.key) non è ancora stata caricata.")
    key = hmac.new(secret, _PURPOSE, hashlib.sha256).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def is_encrypted(stored: str) -> bool:
    return bool(stored) and stored.startswith(PREFIX)


def encrypt(secret: bytes, text: str) -> str:
    """Il testo cifrato da salvare ("" resta "")."""
    if not text:
        return ""
    return PREFIX + _fernet(secret).encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(secret: bytes, stored: str) -> str:
    """Il testo in chiaro. I valori salvati prima della cifratura passano così come sono.

    Se secret.key è cambiata (per esempio è stata cancellata) il segreto non si può più
    leggere: risulta vuoto e l'amministratore lo deve inserire di nuovo.
    """
    if not stored:
        return ""
    if not is_encrypted(stored):
        return stored
    try:
        return _fernet(secret).decrypt(stored[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        log.warning("Un segreto salvato non si può decifrare (secret.key è cambiata?): va inserito di nuovo.")
        return ""
