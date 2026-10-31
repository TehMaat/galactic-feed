"""Canali YouTube: dal link del canale (o da @nome) al feed pubblico degli ultimi video."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

FEED_BASE = "https://www.youtube.com/feeds/videos.xml"
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
CHANNEL_ID = re.compile(r"^UC[\w-]{22}$")
# YouTube in Europa mostra una pagina di consenso ai cookie: questi cookie la saltano.
CONSENT_COOKIES = {"SOCS": "CAI", "CONSENT": "YES+1"}

_PAGE_PATTERNS = [
    re.compile(r'<link[^>]+rel="alternate"[^>]+type="application/rss\+xml"[^>]+href="([^"]+)"'),
    re.compile(r'"externalId"\s*:\s*"(UC[\w-]{22})"'),
    re.compile(r'<meta[^>]+itemprop="(?:identifier|channelId)"[^>]+content="(UC[\w-]{22})"'),
    re.compile(r'"channelId"\s*:\s*"(UC[\w-]{22})"'),
    re.compile(r'youtube\.com/channel/(UC[\w-]{22})'),
]


def is_youtube(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() in YOUTUBE_HOSTS


def channel_feed(channel_id: str) -> str:
    return f"{FEED_BASE}?channel_id={channel_id}"


def direct_feed(url: str) -> str | None:
    """Il feed, se si ricava dal link senza scaricare la pagina."""
    parts = urlsplit(url)
    if parts.path.startswith("/feeds/videos.xml"):
        return url
    query = parse_qs(parts.query)
    if "list" in query and query["list"][0]:
        return f"{FEED_BASE}?playlist_id={query['list'][0]}"
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) >= 2 and segments[0] == "channel" and CHANNEL_ID.match(segments[1]):
        return channel_feed(segments[1])
    return None


def feed_from_page(html: str) -> str | None:
    """Cerca nella pagina del canale l'identificativo che serve per il feed."""
    for pattern in _PAGE_PATTERNS:
        match = pattern.search(html)
        if not match:
            continue
        value = match.group(1).replace("&amp;", "&")
        if value.startswith("http"):
            if "/feeds/videos.xml" in value:
                return value
            continue
        return channel_feed(value)
    return None
