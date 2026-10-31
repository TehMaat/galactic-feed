"""Ricerca automatica dei feed a partire dall'indirizzo di un sito.

1. Se l'indirizzo è già un feed, si usa quello.
2. Se è una pagina, si leggono i <link rel="alternate"> che i siti mettono per i lettori RSS.
3. Se la pagina non ne indica, si provano gli indirizzi più comuni (/feed, /rss.xml…).
Ogni candidato viene scaricato e letto, così l'utente vede titolo, frequenza e se
il feed contiene il testo completo. I feed dei commenti vengono scartati: l'app è
di sola lettura.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
import lxml.html
from lxml import etree

from . import youtube
from .net import FEED_ACCEPT, MAX_PAGE_BYTES, PAGE_ACCEPT, FetchError, fetch, normalize_input_url
from .parser import FULL_TEXT_MIN_CHARS, NotAFeed, ParsedFeed, estimate_per_week, parse_feed
from .sanitize import normalize_feed_url

FEED_TYPES = {"application/rss+xml", "application/atom+xml", "application/rdf+xml", "application/xml", "text/xml"}
COMMON_PATHS = ["/feed", "/rss", "/feed.xml", "/rss.xml", "/atom.xml", "/index.xml", "/feed/"]
COMMENTS = re.compile(r"comment|commenti", re.I)
MAX_CANDIDATES = 8


@dataclass
class Candidate:
    url: str
    title: str
    kind: str
    site_url: str
    items: int
    per_week: float | None
    full_text: bool
    last_published: int | None

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "kind": self.kind,
            "site_url": self.site_url,
            "items": self.items,
            "per_week": self.per_week,
            "full_text": self.full_text,
            "last_published": self.last_published,
        }


class NothingFound(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _candidate(url: str, parsed: ParsedFeed, fallback_title: str = "") -> Candidate:
    entries = parsed.entries
    with_text = [e for e in entries if not e.video_id]
    full = bool(with_text) and sum(e.text_length >= FULL_TEXT_MIN_CHARS for e in with_text) >= len(with_text) / 2
    dates = [e.published_at for e in entries if e.published_at]
    host = (urlsplit(parsed.site_url or url).hostname or "").removeprefix("www.")
    return Candidate(
        url=normalize_feed_url(url),
        title=parsed.title or fallback_title or host,
        kind=parsed.kind,
        site_url=parsed.site_url,
        items=len(entries),
        per_week=estimate_per_week(entries),
        full_text=full or parsed.kind == "youtube",
        last_published=max(dates) if dates else None,
    )


def _try_parse(fetched_url: str, content: bytes, content_type: str) -> ParsedFeed | None:
    if content_type in ("text/html", "application/xhtml+xml"):
        return None
    try:
        return parse_feed(content, fetched_url, content_type)
    except NotAFeed:
        return None


def links_in_page(html: str, base_url: str) -> list[tuple[str, str]]:
    """(indirizzo, titolo) dei feed dichiarati nella pagina."""
    try:
        root = lxml.html.fromstring(html)
    except (etree.ParserError, ValueError):
        return []
    found = []
    for link in root.iter("link", "a"):
        rel = (link.get("rel") or "").lower().split()
        kind = (link.get("type") or "").lower().split(";")[0].strip()
        href = link.get("href")
        if not href or "alternate" not in rel or kind not in FEED_TYPES:
            continue
        found.append((urljoin(base_url, href), (link.get("title") or "").strip()))
    return found


async def _check(client: httpx.AsyncClient, url: str, title: str) -> Candidate | None:
    try:
        got = await fetch(client, url, accept=FEED_ACCEPT)
    except FetchError:
        return None
    parsed = _try_parse(got.url, got.content, got.content_type)
    if parsed is None:
        return None
    return _candidate(got.url, parsed, title)


def _is_comments(c: Candidate, declared_title: str = "") -> bool:
    return bool(COMMENTS.search(c.url) or COMMENTS.search(c.title) or COMMENTS.search(declared_title))


async def discover(client: httpx.AsyncClient, raw_url: str) -> list[Candidate]:
    url = normalize_input_url(raw_url)
    cookies = None

    if youtube.is_youtube(url):
        direct = youtube.direct_feed(url)
        if direct:
            c = await _check(client, direct, "")
            if c:
                return [c]
            raise NothingFound("Non riesco a leggere il feed di questo canale YouTube. Controlla il link.")
        cookies = youtube.CONSENT_COOKIES

    got = await fetch(client, url, accept=PAGE_ACCEPT + ", " + FEED_ACCEPT, max_bytes=MAX_PAGE_BYTES, cookies=cookies)
    parsed = _try_parse(got.url, got.content, got.content_type)
    if parsed is not None:
        return [_candidate(got.url, parsed)]

    html = got.text()
    if youtube.is_youtube(got.url):
        feed_url = youtube.feed_from_page(html)
        c = await _check(client, feed_url, "") if feed_url else None
        if c:
            return [c]
        raise NothingFound("Non trovo il canale. Incolla il link della pagina del canale, per esempio youtube.com/@nome.")

    declared = links_in_page(html, got.url)
    seen: set[str] = set()
    to_check: list[tuple[str, str]] = []
    for href, title in declared:
        key = normalize_feed_url(href)
        if key not in seen:
            seen.add(key)
            to_check.append((href, title))
    if not to_check:
        root = f"{urlsplit(got.url).scheme}://{urlsplit(got.url).netloc}"
        to_check = [(root + p, "") for p in COMMON_PATHS]

    results = await asyncio.gather(*(_check(client, u, t) for u, t in to_check[:MAX_CANDIDATES]))
    titles = dict((normalize_feed_url(u), t) for u, t in to_check)
    candidates: list[Candidate] = []
    urls: set[str] = set()
    for c in results:
        if c is None or c.url in urls or _is_comments(c, titles.get(c.url, "")):
            continue
        urls.add(c.url)
        if titles.get(c.url):
            c.title = c.title or titles[c.url]
        candidates.append(c)
    if not candidates:
        raise NothingFound(
            "In questa pagina non ho trovato nessun feed RSS o Atom. "
            "Prova con la pagina principale del sito, oppure cerca sul sito un link «RSS» o «Feed»."
        )
    return candidates
