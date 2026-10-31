"""Testo completo: quando il feed dà solo un estratto, lo si prende dalla pagina dell'articolo.

trafilatura riconosce la parte della pagina che contiene l'articolo e scarta menu,
pubblicità e commenti. Sui siti a pagamento di solito trova poco: in quel caso si
tiene il contenuto del feed.
"""

from __future__ import annotations

import asyncio
import logging

import trafilatura

from ..db import now
from .net import MAX_PAGE_BYTES, PAGE_ACCEPT, FetchError, fetch
from .sanitize import clean_html, html_to_text, word_count

log = logging.getLogger("galactic_feed.extract")

CONCURRENCY = 2
BATCH = 10
# Solo gli articoli recenti: estrarre quelli vecchi di un feed appena aggiunto sarebbe lento.
MAX_AGE_DAYS = 14


def extract_from_html(html: str, url: str, title: str) -> tuple[str, str]:
    """(HTML pulito dell'articolo, immagine principale) a partire dalla pagina."""
    body = trafilatura.extract(
        html,
        url=url,
        output_format="html",
        include_images=True,
        include_links=True,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    ) or ""
    image = ""
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        image = (meta.image or "") if meta else ""
    except Exception:  # i metadati sono un di più
        image = ""
    if body.startswith("<html>"):
        body = body.replace("<html>", "").replace("</html>", "").replace("<body>", "").replace("</body>", "")
    return clean_html(body, url, drop_heading=title), image


class Extractor:
    def __init__(self, ctx):
        self.ctx = ctx
        self._sem = asyncio.Semaphore(CONCURRENCY)

    async def extract_pending(self, limit: int = BATCH) -> int:
        def pending():
            with self.ctx.db.session() as conn:
                return conn.execute(
                    "SELECT id, url, title, content_html, image_url FROM articles"
                    " WHERE full_status = 'pending' ORDER BY published_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        rows = await asyncio.to_thread(pending)
        results = await asyncio.gather(*(self._one(r) for r in rows))
        return sum(results)

    async def _one(self, row) -> bool:
        async with self._sem:
            try:
                got = await fetch(self.ctx.http, row["url"], accept=PAGE_ACCEPT, max_bytes=MAX_PAGE_BYTES)
                html, image = await asyncio.to_thread(extract_from_html, got.text(), got.url, row["title"])
            except FetchError as exc:
                log.info("Testo completo non disponibile per %s: %s", row["url"], exc.message)
                html, image = "", ""
            except Exception:
                log.exception("Errore nell'estrazione di %s", row["url"])
                html, image = "", ""
        text = html_to_text(html)
        feed_text = html_to_text(row["content_html"])
        good = len(text) >= max(400, int(len(feed_text) * 1.3))
        await asyncio.to_thread(self._save, row["id"], row["title"], html if good else None, text, image, row["image_url"])
        return good

    def _save(self, article_id: int, title: str, html: str | None, text: str, image: str, old_image: str) -> None:
        with self.ctx.db.session() as conn, conn:
            if html is None:
                conn.execute("UPDATE articles SET full_status = 'failed' WHERE id = ?", (article_id,))
                return
            conn.execute(
                "UPDATE articles SET full_html = ?, full_status = 'ok', word_count = ?, image_url = ? WHERE id = ?",
                (html, word_count(text), old_image or image or "", article_id),
            )
            conn.execute("UPDATE articles_fts SET body = ? WHERE rowid = ?", (text, article_id))


def initial_full_status(needs_full_text: bool, published_at: int) -> str:
    if not needs_full_text:
        return "none"
    return "pending" if published_at >= now() - MAX_AGE_DAYS * 86400 else "skipped"
