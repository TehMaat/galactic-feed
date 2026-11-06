"""Icone delle fonti: la favicon del sito o l'avatar del canale YouTube.

Si cerca in automatico quando una fonte viene aggiunta e poi ogni 7 giorni:
1. nella pagina del sito, i <link rel="icon"> e «apple-touch-icon» (prima le più grandi,
   che restano nitide sugli schermi ad alta densità);
2. /favicon.ico;
3. l'immagine di anteprima del sito (og:image), come ultima scelta: di solito è un banner.
Per i canali YouTube si usa l'avatar del canale (og:image della pagina del canale).
Ogni candidata viene scaricata per controllare che sia davvero un'immagine. L'icona passa
poi dal proxy /api/img, come le altre immagini. Le icone SVG si scartano: il proxy non le serve.
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urljoin, urlsplit

import lxml.html
from lxml import etree

from ..db import now
from . import youtube
from .net import MAX_PAGE_BYTES, PAGE_ACCEPT, FetchError, fetch, image_type

log = logging.getLogger("galactic_feed.icons")

REFRESH_DAYS = 7
BATCH = 8
CONCURRENCY = 3
MAX_ICON_BYTES = 1024 * 1024
MAX_TRIES = 5
IMAGE_ACCEPT = "image/avif,image/webp,image/png,image/x-icon,image/*;q=0.8"
# Dimensione «buona»: le icone si vedono fino a 36 px, cioè circa 108 pixel veri sui telefoni.
GOOD_SIZE = 96
_SIZE = re.compile(r"(\d+)\s*[xX]\s*(\d+)")
_YT_SIZE = re.compile(r"=s\d+(-)")


def _size(sizes: str, default: int) -> int:
    found = [min(int(w), int(h)) for w, h in _SIZE.findall(sizes or "")]
    return max(found) if found else default


def _is_svg(href: str, kind: str) -> bool:
    return "svg" in (kind or "").lower() or urlsplit(href).path.lower().endswith(".svg")


def icon_candidates(html: str, base_url: str) -> list[str]:
    """Le icone dichiarate nella pagina, dalla più adatta, poi /favicon.ico e og:image."""
    try:
        root = lxml.html.fromstring(html)
    except (etree.ParserError, ValueError):
        root = None
    links: list[tuple[int, int, str]] = []
    og = ""
    if root is not None:
        for i, link in enumerate(root.iter("link")):
            rel = (link.get("rel") or "").lower().split()
            href = (link.get("href") or "").strip()
            if not href or href.startswith("data:") or _is_svg(href, link.get("type", "")):
                continue
            if "apple-touch-icon" in rel or "apple-touch-icon-precomposed" in rel:
                size = _size(link.get("sizes", ""), 180)
            elif "icon" in rel:
                size = _size(link.get("sizes", ""), 32)
            else:
                continue
            links.append((size, i, urljoin(base_url, href)))
        for meta in root.iter("meta"):
            if (meta.get("property") or meta.get("name") or "").lower() == "og:image" and meta.get("content"):
                og = urljoin(base_url, meta.get("content").strip())
                break
    # Prima le icone grandi abbastanza (dalla più piccola tra queste), poi le altre dalla più grande.
    good = sorted((x for x in links if x[0] >= GOOD_SIZE), key=lambda x: (x[0], x[1]))
    small = sorted((x for x in links if x[0] < GOOD_SIZE), key=lambda x: (-x[0], x[1]))
    parts = urlsplit(base_url)
    out = [u for _, _, u in good + small]
    out.append(f"{parts.scheme}://{parts.netloc}/favicon.ico")
    if og:
        out.append(og)
    seen: set[str] = set()
    return [u for u in out if u.startswith(("http://", "https://")) and not (u in seen or seen.add(u))]


def youtube_avatar(html: str) -> str:
    """L'avatar del canale nella sua pagina, in una dimensione adatta a un'icona."""
    try:
        root = lxml.html.fromstring(html)
    except (etree.ParserError, ValueError):
        return ""
    for meta in root.iter("meta"):
        if (meta.get("property") or "").lower() == "og:image" and meta.get("content"):
            return _YT_SIZE.sub(r"=s176\1", meta.get("content").strip(), count=1)
    return ""


async def check_image(client, url: str) -> bool:
    """Vero se all'indirizzo c'è un'immagine che il proxy può servire."""
    try:
        got = await fetch(client, url, accept=IMAGE_ACCEPT, max_bytes=MAX_ICON_BYTES)
    except FetchError:
        return False
    return got.status == 200 and image_type(got.content, got.content_type) is not None


def _pages(feed) -> list[str]:
    """Le pagine in cui cercare: il sito del feed e la sua home."""
    pages = []
    site = feed["site_url"] or ""
    if site.startswith(("http://", "https://")):
        pages.append(site)
    base = site if pages else feed["url"]
    parts = urlsplit(base)
    home = f"{parts.scheme}://{parts.netloc}/"
    if home not in pages:
        pages.append(home)
    return pages


async def find_icon(client, feed) -> str:
    """L'indirizzo dell'icona del feed, oppure "" se non se ne trova nessuna."""
    if feed["kind"] == "youtube":
        page = feed["site_url"] or ""
        if not youtube.is_youtube(page):
            return ""
        try:
            got = await fetch(client, page, accept=PAGE_ACCEPT, max_bytes=MAX_PAGE_BYTES, cookies=youtube.CONSENT_COOKIES)
        except FetchError:
            return ""
        avatar = youtube_avatar(got.text())
        return avatar if avatar and await check_image(client, avatar) else ""

    candidates: list[str] = []
    for page in _pages(feed):
        try:
            got = await fetch(client, page, accept=PAGE_ACCEPT, max_bytes=MAX_PAGE_BYTES)
        except FetchError:
            continue
        for url in icon_candidates(got.text(), got.url):
            if url not in candidates:
                candidates.append(url)
        if len(candidates) > 1:  # la pagina dichiara almeno un'icona oltre a /favicon.ico
            break
    if not candidates:
        parts = urlsplit(feed["site_url"] or feed["url"])
        candidates = [f"{parts.scheme}://{parts.netloc}/favicon.ico"]
    for url in candidates[:MAX_TRIES]:
        if await check_image(client, url):
            return url
    return ""


class IconFinder:
    def __init__(self, ctx):
        self.ctx = ctx
        self._sem = asyncio.Semaphore(CONCURRENCY)

    def _due(self) -> list[int]:
        with self.ctx.db.session() as conn:
            rows = conn.execute(
                "SELECT id FROM feeds WHERE (icon_checked_at IS NULL OR icon_checked_at < ?)"
                " AND last_success_at IS NOT NULL"
                " AND EXISTS (SELECT 1 FROM subscriptions s WHERE s.feed_id = feeds.id)"
                " ORDER BY icon_checked_at IS NOT NULL, icon_checked_at LIMIT ?",
                (now() - REFRESH_DAYS * 86400, BATCH),
            ).fetchall()
        return [r["id"] for r in rows]

    async def run_due(self) -> int:
        """Cerca le icone dei feed nuovi e di quelli controllati più di 7 giorni fa."""
        due = await asyncio.to_thread(self._due)
        if due:
            await asyncio.gather(*(self.refresh(fid) for fid in due), return_exceptions=True)
        return len(due)

    async def refresh(self, feed_id: int) -> str:
        """Cerca subito l'icona del feed e la salva. Restituisce l'indirizzo trovato ("" se nessuno)."""

        def load():
            with self.ctx.db.session() as conn:
                return conn.execute("SELECT id, url, kind, site_url, icon_url FROM feeds WHERE id = ?", (feed_id,)).fetchone()

        feed = await asyncio.to_thread(load)
        if feed is None:
            return ""
        async with self._sem:
            try:
                url = await find_icon(self.ctx.http, feed)
            except Exception:
                log.exception("Errore cercando l'icona di %s", feed["url"])
                url = feed["icon_url"]

        def save():
            with self.ctx.db.session() as conn, conn:
                conn.execute("UPDATE feeds SET icon_url = ?, icon_checked_at = ? WHERE id = ?", (url, now(), feed_id))

        await asyncio.to_thread(save)
        return url
