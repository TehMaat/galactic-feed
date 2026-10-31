"""Lettura di feed RSS e Atom (compresi quelli dei canali YouTube) con feedparser."""

from __future__ import annotations

import calendar
import hashlib
import json
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import feedparser

from .sanitize import clean_html, excerpt, first_image, html_to_text, word_count

# Sotto questa lunghezza il contenuto del feed è considerato solo un estratto.
FULL_TEXT_MIN_CHARS = 1200


@dataclass
class Entry:
    guid: str
    url: str
    title: str
    author: str
    excerpt: str
    content_html: str
    categories: list[str]
    image_url: str
    video_id: str | None
    published_at: int | None
    word_count: int
    text_length: int

    @property
    def needs_full_text(self) -> bool:
        return not self.video_id and bool(self.url) and self.text_length < FULL_TEXT_MIN_CHARS

    @property
    def categories_json(self) -> str:
        return json.dumps(self.categories, ensure_ascii=False)


@dataclass
class ParsedFeed:
    title: str
    site_url: str
    kind: str
    entries: list[Entry] = field(default_factory=list)


class NotAFeed(Exception):
    pass


def _timestamp(entry) -> int | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            try:
                return calendar.timegm(value)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _image(entry, content_html: str, base: str) -> str:
    for thumb in entry.get("media_thumbnail") or []:
        if thumb.get("url"):
            return thumb["url"]
    for media in entry.get("media_content") or []:
        if media.get("url") and (media.get("medium") == "image" or str(media.get("type", "")).startswith("image/")):
            return media["url"]
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image/") and link.get("href"):
            return link["href"]
    return first_image(content_html, base)


def _video_id(entry) -> str | None:
    vid = entry.get("yt_videoid")
    return str(vid) if vid else None


def parse_feed(content: bytes, url: str, content_type: str = "") -> ParsedFeed:
    headers = {"content-location": url}
    if content_type:
        headers["content-type"] = content_type
    data = feedparser.parse(content, response_headers=headers, sanitize_html=False, resolve_relative_uris=True)
    if not data.get("version") and not data.entries:
        raise NotAFeed()

    meta = data.feed
    site_url = meta.get("link") or ""
    kind = "youtube" if "youtube.com/feeds/videos.xml" in url else "rss"
    feed_title = html_to_text(meta.get("title", "")) or ""

    entries = []
    for e in data.entries:
        link = e.get("link") or ""
        if link:
            link = urljoin(url, link)
        title = html_to_text(e.get("title", "")) or ""
        raw_content = ""
        for c in e.get("content") or []:
            if len(c.get("value", "")) > len(raw_content):
                raw_content = c.get("value", "")
        raw_summary = e.get("summary", "") or ""
        if not raw_content:
            raw_content = raw_summary
        base = link or url
        content_html = clean_html(raw_content, base, drop_heading=title)
        text = html_to_text(content_html)
        summary_text = html_to_text(raw_summary) or text
        video_id = _video_id(e)
        guid = e.get("id") or e.get("guid") or link
        if not guid:
            guid = "hash:" + hashlib.sha256((title + raw_summary).encode("utf-8")).hexdigest()[:32]
        if not title and not text:
            continue
        entries.append(
            Entry(
                guid=str(guid)[:500],
                url=link,
                title=title or excerpt(text, 90),
                author=html_to_text(e.get("author", "")),
                excerpt=excerpt(summary_text),
                content_html=content_html,
                categories=[t.get("term", "").strip() for t in e.get("tags") or [] if t.get("term", "").strip()][:20],
                image_url=_image(e, raw_content, base),
                video_id=video_id,
                published_at=_timestamp(e),
                word_count=word_count(text),
                text_length=len(text),
            )
        )
    return ParsedFeed(title=feed_title, site_url=site_url, kind=kind, entries=entries)


def estimate_per_week(entries: list[Entry]) -> float | None:
    """Quanti articoli a settimana pubblica il feed, a partire dalle date che contiene."""
    dates = sorted(e.published_at for e in entries if e.published_at)
    if len(dates) < 2:
        return None
    span_days = max((dates[-1] - dates[0]) / 86400, (time.time() - dates[-1]) / 86400 + 0.5, 1)
    return round(len(dates) / span_days * 7, 1)
