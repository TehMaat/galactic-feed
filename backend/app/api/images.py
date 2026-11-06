"""Proxy delle immagini degli articoli.

Le immagini passano dal server invece di essere caricate direttamente dai siti:
- il service worker le può conservare per la lettura offline (stessa origine);
- i siti non vedono l'indirizzo IP e il browser di chi legge.
Gli indirizzi sono firmati dal server, quindi il proxy non scarica nient'altro che le
immagini degli articoli. Si accettano solo immagini raster (niente SVG).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..deps import AppContext, User, current_user, get_ctx
from ..feeds.net import FetchError, fetch, image_type

router = APIRouter(prefix="/api", tags=["immagini"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024
_IMG_SRC = re.compile(r'(<img\b[^>]*?\ssrc=")([^"]+)(")', re.I)


def sign(secret: bytes, url: str) -> str:
    digest = hmac.new(secret, url.encode("utf-8"), hashlib.sha256).digest()[:18]
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def proxied(secret: bytes, url: str | None) -> str | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    return f"/api/img?u={quote(url, safe='')}&s={sign(secret, url)}"


def proxied_icon(secret: bytes, url: str | None) -> str | None:
    """Come proxied, con un segno in più (k=icon) per il service worker, che tiene le icone a parte."""
    base = proxied(secret, url)
    return base + "&k=icon" if base else None


def source_icon(secret: bytes, mode: str | None, custom: str | None, auto: str | None) -> str | None:
    """L'icona da mostrare per una fonte, secondo la scelta dell'utente: auto, custom o none (iniziali)."""
    if mode == "none":
        return None
    if mode == "custom" and custom:
        return proxied_icon(secret, custom)
    return proxied_icon(secret, auto)


def proxy_images_in_html(secret: bytes, content: str) -> str:
    def repl(m: re.Match) -> str:
        url = html.unescape(m.group(2))
        new = proxied(secret, url)
        return m.group(1) + html.escape(new or url, quote=True) + m.group(3)

    return _IMG_SRC.sub(repl, content or "")


@router.get("/img")
async def image(u: str, s: str, _: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    # Il parametro k=icon (icone delle fonti) serve solo al service worker: qui non cambia nulla.
    if not hmac.compare_digest(sign(ctx.secret, u), s):
        raise HTTPException(status_code=403, detail="Indirizzo dell'immagine non valido.")
    try:
        got = await fetch(ctx.http, u, accept="image/avif,image/webp,image/*;q=0.8", max_bytes=MAX_IMAGE_BYTES)
    except FetchError as exc:
        raise HTTPException(status_code=502, detail=exc.message)
    kind = image_type(got.content, got.content_type)
    if kind is None:
        raise HTTPException(status_code=415, detail="Il file non è un'immagine supportata.")
    return Response(
        content=got.content,
        media_type=kind,
        headers={
            # Le immagini di un articolo non cambiano: il browser le tiene una settimana.
            "Cache-Control": "private, max-age=604800, immutable",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
