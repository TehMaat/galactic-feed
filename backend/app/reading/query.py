"""Le query degli articoli visti da un utente: filtri, ricerca, doppioni, paginazione.

Un utente vede gli articoli dei feed che segue, più quelli che ha salvato (anche se nel
frattempo ha smesso di seguire la fonte). Per i doppioni, prima si applicano i filtri e
poi, per ogni notizia, si tiene l'articolo pubblicato per primo.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .text import normalize

VIEWS = ("tutti", "perte", "nonletti", "video", "salvati")
MAX_SEARCH_WORDS = 8


@dataclass
class ArticleFilter:
    view: str = "tutti"
    folder: int | None = None
    no_folder: bool = False
    source: int | None = None
    q: str = ""
    show_muted: bool = False
    dedupe: bool = True
    before: int | None = None
    since: int | None = None

    @property
    def sort_column(self) -> str:
        return "saved_at" if self.view == "salvati" else "published_at"


def fts_query(text: str) -> str | None:
    """Ogni parola cercata deve comparire, anche come inizio di parola: «galass» trova «galassie»."""
    words = normalize(text).split()[:MAX_SEARCH_WORDS]
    if not words:
        return None
    return " ".join(f'"{w}"*' for w in words)


def visible_cte(user_id: int, f: ArticleFilter, muted: bool | None = False) -> tuple[str, list]:
    """CTE «vis»: gli articoli che passano i filtri. muted=None li prende tutti, True solo i silenziati."""
    where = ["(s.id IS NOT NULL OR ua.saved_at IS NOT NULL)"]
    params: list = [user_id, user_id, user_id]
    if f.view == "perte":
        where.append("m.level IS NOT NULL")
    elif f.view == "nonletti":
        where.append("ua.read_at IS NULL")
    elif f.view == "video":
        where.append("a.video_id IS NOT NULL")
    elif f.view == "salvati":
        where.append("ua.saved_at IS NOT NULL")
    if f.folder is not None:
        where.append("s.folder_id = ?")
        params.append(f.folder)
    elif f.no_folder:
        where.append("s.id IS NOT NULL AND s.folder_id IS NULL")
    if f.source is not None:
        where.append("s.id = ?")
        params.append(f.source)
    if f.q.strip():
        like = "%" + f.q.strip().replace("%", "").replace("_", "") + "%"
        match = fts_query(f.q)
        clause = "s.title LIKE ? OR f.title LIKE ?"
        params += [like, like]
        if match:
            clause = "a.id IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?) OR " + clause
            params.insert(len(params) - 2, match)
        where.append(f"({clause})")
    if f.before is not None:
        where.append("a.published_at <= ?")
        params.append(f.before)
    if f.since is not None:
        where.append("a.published_at >= ?")
        params.append(f.since)
    if muted is True:
        where.append("COALESCE(m.muted, 0) = 1")
    elif muted is False and not f.show_muted and f.view != "salvati":
        where.append("COALESCE(m.muted, 0) = 0")

    sql = (
        "vis AS (SELECT a.id, a.cluster_id, a.published_at, a.video_id, ua.saved_at, ua.read_at,"
        " m.level, s.folder_id"
        " FROM articles a JOIN feeds f ON f.id = a.feed_id"
        " LEFT JOIN subscriptions s ON s.feed_id = a.feed_id AND s.user_id = ?"
        " LEFT JOIN user_articles ua ON ua.article_id = a.id AND ua.user_id = ?"
        " LEFT JOIN user_matches m ON m.article_id = a.id AND m.user_id = ?"
        " WHERE " + " AND ".join(where) + ")"
    )
    return sql, params


def ranked_sql(f: ArticleFilter) -> str:
    """CTE «ranked»: con i doppioni uniti, rn = 1 indica l'articolo da mostrare per ogni notizia."""
    if f.dedupe and f.view != "salvati":
        return (
            "ranked AS (SELECT vis.*, ROW_NUMBER() OVER (PARTITION BY cluster_id ORDER BY published_at, id) AS rn,"
            " COUNT(*) OVER (PARTITION BY cluster_id) AS dup FROM vis)"
        )
    return "ranked AS (SELECT vis.*, 1 AS rn, 1 AS dup FROM vis)"


def list_page(
    conn: sqlite3.Connection, user_id: int, f: ArticleFilter, cursor: tuple[int, int] | None, limit: int
) -> tuple[list[sqlite3.Row], tuple[int, int] | None]:
    cte, params = visible_cte(user_id, f)
    col = f.sort_column
    sql = f"WITH {cte}, {ranked_sql(f)} SELECT id, cluster_id, dup, {col} AS sort FROM ranked WHERE rn = 1"
    if cursor:
        sql += f" AND ({col} < ? OR ({col} = ? AND id < ?))"
        params += [cursor[0], cursor[0], cursor[1]]
    sql += f" ORDER BY {col} DESC, id DESC LIMIT ?"
    params.append(limit + 1)
    rows = conn.execute(sql, params).fetchall()
    more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (rows[-1]["sort"], rows[-1]["id"]) if more and rows else None
    return rows, next_cursor


def count(conn: sqlite3.Connection, user_id: int, f: ArticleFilter, muted: bool | None = False) -> int:
    cte, params = visible_cte(user_id, f, muted)
    return conn.execute(f"WITH {cte}, {ranked_sql(f)} SELECT COUNT(*) FROM ranked WHERE rn = 1", params).fetchone()[0]


def counts(conn: sqlite3.Connection, user_id: int, f: ArticleFilter) -> dict:
    """I numeri sui filtri del Flusso, per la ricerca in corso."""
    base = ArticleFilter(q=f.q, dedupe=f.dedupe, show_muted=f.show_muted)
    cte, params = visible_cte(user_id, base)
    row = conn.execute(
        f"WITH {cte}, {ranked_sql(base)} SELECT COUNT(*) AS tutti,"
        " COALESCE(SUM(level IS NOT NULL), 0) AS perte,"
        " COALESCE(SUM(read_at IS NULL), 0) AS nonletti,"
        " COALESCE(SUM(video_id IS NOT NULL), 0) AS video"
        " FROM ranked WHERE rn = 1",
        params,
    ).fetchone()
    folders = conn.execute(
        f"WITH {cte}, {ranked_sql(base)} SELECT folder_id, COUNT(*) AS n FROM ranked WHERE rn = 1 GROUP BY folder_id",
        params,
    ).fetchall()
    saved = count(conn, user_id, ArticleFilter(view="salvati", q=f.q))
    return {
        "tutti": row["tutti"],
        "perte": row["perte"],
        "nonletti": row["nonletti"],
        "video": row["video"],
        "salvati": saved,
        "folders": {str(r["folder_id"]): r["n"] for r in folders if r["folder_id"] is not None},
        "no_folder": next((r["n"] for r in folders if r["folder_id"] is None), 0),
        "hidden": count(conn, user_id, base, muted=True) if not f.show_muted else 0,
    }


def is_visible(conn: sqlite3.Connection, user_id: int, article_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM articles a"
            " LEFT JOIN subscriptions s ON s.feed_id = a.feed_id AND s.user_id = ?"
            " LEFT JOIN user_articles ua ON ua.article_id = a.id AND ua.user_id = ?"
            " WHERE a.id = ? AND (s.id IS NOT NULL OR ua.saved_at IS NOT NULL)",
            (user_id, user_id, article_id),
        ).fetchone()
        is not None
    )


def article_rows(conn: sqlite3.Connection, user_id: int, ids: list[int], full: bool = False) -> dict[int, sqlite3.Row]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    content = ", a.content_html, a.full_html, a.full_status, a.categories" if full else ""
    rows = conn.execute(
        "SELECT a.id, a.cluster_id, a.url, a.title, a.author, a.excerpt, a.image_url, a.video_id, a.word_count,"
        " a.published_at, f.kind, f.title AS feed_title, f.site_url, s.id AS sub_id, s.title AS sub_title, s.folder_id,"
        f" ua.read_at, ua.saved_at, m.keyword, m.level, COALESCE(m.muted, 0) AS muted{content}"
        " FROM articles a JOIN feeds f ON f.id = a.feed_id"
        " LEFT JOIN subscriptions s ON s.feed_id = a.feed_id AND s.user_id = ?"
        " LEFT JOIN user_articles ua ON ua.article_id = a.id AND ua.user_id = ?"
        " LEFT JOIN user_matches m ON m.article_id = a.id AND m.user_id = ?"
        f" WHERE a.id IN ({marks})",
        [user_id, user_id, user_id, *ids],
    ).fetchall()
    return {r["id"]: r for r in rows}


def also_on(conn: sqlite3.Connection, user_id: int, clusters: dict[int, int]) -> dict[int, list[dict]]:
    """Per ogni notizia unita (cluster → articolo mostrato), le altre fonti che la riportano."""
    if not clusters:
        return {}
    marks = ",".join("?" * len(clusters))
    rows = conn.execute(
        "SELECT a.id, a.cluster_id, s.id AS sub_id, COALESCE(NULLIF(s.title, ''), NULLIF(f.title, ''), f.url) AS title, a.url"
        " FROM articles a JOIN feeds f ON f.id = a.feed_id"
        " JOIN subscriptions s ON s.feed_id = a.feed_id AND s.user_id = ?"
        f" WHERE a.cluster_id IN ({marks}) ORDER BY a.published_at",
        [user_id, *clusters.keys()],
    ).fetchall()
    out: dict[int, list[dict]] = {}
    for r in rows:
        if clusters.get(r["cluster_id"]) == r["id"]:
            continue
        out.setdefault(r["cluster_id"], []).append({"article_id": r["id"], "source_id": r["sub_id"], "title": r["title"], "url": r["url"]})
    return out
