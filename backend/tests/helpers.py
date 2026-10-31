"""Aiuti per preparare fonti e articoli nel database senza passare dalla rete."""

from __future__ import annotations

import itertools
import time

from app.api.sources import ensure_feed, subscribe
from app.feeds.fetcher import store_entries
from app.feeds.parser import Entry
from app.reading.matching import apply_new_articles

_guid = itertools.count(1)
HOUR = 3600


def entry(title, url=None, excerpt="", hours_ago=1, categories=(), video_id=None, content="", image="", words=440):
    n = next(_guid)
    return Entry(
        guid=f"g{n}",
        url=url or f"https://news.example/{n}",
        title=title,
        author="",
        excerpt=excerpt,
        content_html=content or f"<p>{excerpt}</p>",
        categories=list(categories),
        image_url=image,
        video_id=video_id,
        published_at=int(time.time()) - int(hours_ago * HOUR),
        word_count=words,
        text_length=len(content or excerpt),
    )


def user_id(client) -> int:
    return client.get("/api/me").json()["user"]["id"]


def feed(app, client, url, entries, title="Fonte", folder_id=None, kind_title=None):
    """Crea (o riusa) il feed, iscrive l'utente del client e salva gli articoli. Restituisce gli id."""
    uid = user_id(client)
    with app.state.ctx.db.session() as conn:
        with conn:
            feed_id, _ = ensure_feed(conn, url, kind_title or title)
            subscribe(conn, uid, feed_id, folder_id, "", 30)
        ids = store_entries(conn, feed_id, entries)
        apply_new_articles(conn, feed_id, ids)
    return ids


def source_id(client, title):
    return next(s["id"] for s in client.get("/api/sources").json()["sources"] if s["title"] == title)
