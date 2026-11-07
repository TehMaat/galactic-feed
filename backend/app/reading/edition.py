"""Edizioni: selezioni delle notizie composte per ogni utente quando lo sceglie lui.

Un utente può avere più Edizioni (edition_configs, issue #18), ognuna con:
- un nome («La mia Edizione», «Politica · Italia», «Videogiochi del venerdì»);
- regole facoltative su tag delle fonti, cartelle, nazioni e gruppi di parole (tra tipi
  diversi valgono tutte, dentro lo stesso tipo ne basta una; nessuna regola = tutto);
- una pianificazione giornaliera, settimanale o mensile (schedule.py, issue #19);
- un numero massimo di notizie e il periodo coperto.

Come si compone un'uscita:
- si prendono le notizie pubblicate dopo l'uscita precedente della stessa Edizione (con un
  limite che dipende dalla pianificazione: 2 giorni, 8 giorni, 32 giorni), senza quelle
  silenziate e con i doppioni uniti come nel Flusso;
- senza regole: entrano quelle «per te» (interessi o AI), prima le priorità alte, poi le più
  recenti; se sono meno di MIN_MATCHES si aggiungono le ultime notizie, una per fonte;
- con le regole: entrano le notizie che le rispettano, prima quelle «per te», poi le più recenti;
- la prima diventa la notizia in primo piano, le altre si raggruppano per cartella.

Gli orari sono nel fuso dell'utente (Impostazioni), o in quello dell'istanza. Se il server era
spento all'ora giusta, l'uscita si compone appena riparte.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from ..db import now
from . import query, schedule
from .matching import haystack, word_pattern
from .query import ArticleFilter
from .schedule import zone  # noqa: F401 (usata dalle API)

log = logging.getLogger("galactic_feed.edition")

MAX_ITEMS = 30
MIN_MATCHES = 3
FILLER_ITEMS = 8
KEEP_EDITIONS = 60
DEFAULT_NAME = "La mia Edizione"
RULE_TYPES = ("tags", "folders", "countries", "groups")


# ---------- Compatibilità con gli orari della versione precedente ----------


def last_slot(times: list[str], tz: str, ts: int) -> tuple[int, str]:
    return schedule.last_occurrence({"kind": "daily", "times": sorted(times)}, tz, ts)


def next_slot(times: list[str], tz: str, ts: int) -> tuple[int, str]:
    return schedule.next_occurrences({"kind": "daily", "times": sorted(times)}, tz, ts, 1)[0]


def is_due(times: list[str], tz: str, ts: int, last_created: int | None) -> str | None:
    return schedule.is_due({"kind": "daily", "times": sorted(times)}, tz, ts, last_created)


# ---------- Configurazioni ----------


def load_config(row: sqlite3.Row) -> dict:
    try:
        rules = json.loads(row["rules"] or "{}")
    except ValueError:
        rules = {}
    try:
        sched = schedule.check(json.loads(row["schedule"] or "{}"))
    except (ValueError, TypeError):
        sched = {"kind": "daily", "times": ["07:30"]}
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "active": bool(row["active"]),
        "rules": {k: list(rules.get(k) or []) for k in RULE_TYPES},
        "schedule": sched,
        "max_items": row["max_items"],
        "period": row["period"],
        "notify": bool(row["notify"]),
        "position": row["position"],
    }


def ensure_configs(conn: sqlite3.Connection, user_id: int) -> None:
    """Al primo uso trasforma l'Edizione delle preferenze (accesa sì/no e orari) in «La mia Edizione».

    Le Edizioni già composte passano a lei, con gli stessi numeri: per chi la usava non cambia nulla.
    Vale anche per i nuovi utenti con l'Edizione accesa dai predefiniti dell'amministratore.
    """
    from ..api.common import prefs_with_defaults

    row = conn.execute("SELECT editions_ready, prefs FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or row["editions_ready"]:
        return
    try:
        prefs = prefs_with_defaults(json.loads(row["prefs"] or "{}"))
    except ValueError:
        prefs = prefs_with_defaults({})
    had_editions = conn.execute("SELECT 1 FROM editions WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
    with conn:
        if prefs["edition"] or had_editions:
            cur = conn.execute(
                "INSERT INTO edition_configs (user_id, name, active, rules, schedule, max_items, created_at)"
                " VALUES (?, ?, ?, '{}', ?, ?, ?)",
                (user_id, DEFAULT_NAME, int(prefs["edition"]), json.dumps({"kind": "daily", "times": prefs["edition_times"]}), MAX_ITEMS, now()),
            )
            conn.execute(
                "UPDATE editions SET config_id = ?, config_number = number WHERE user_id = ? AND config_id IS NULL",
                (cur.lastrowid, user_id),
            )
        conn.execute("UPDATE users SET editions_ready = 1 WHERE id = ?", (user_id,))


def user_configs(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    ensure_configs(conn, user_id)
    rows = conn.execute("SELECT * FROM edition_configs WHERE user_id = ? ORDER BY position, id", (user_id,)).fetchall()
    return [load_config(r) for r in rows]


def sync_edition_pref(conn: sqlite3.Connection, user_id: int) -> None:
    """prefs.edition dice se c'è almeno un'Edizione attiva: la PWA la usa per mostrare Oggi → Edizione."""
    active = conn.execute("SELECT 1 FROM edition_configs WHERE user_id = ? AND active = 1 LIMIT 1", (user_id,)).fetchone()
    row = conn.execute("SELECT prefs FROM users WHERE id = ?", (user_id,)).fetchone()
    try:
        prefs = json.loads(row["prefs"] or "{}") if row else {}
    except ValueError:
        prefs = {}
    if bool(prefs.get("edition")) != bool(active):
        prefs["edition"] = bool(active)
        with conn:
            conn.execute("UPDATE users SET prefs = ? WHERE id = ?", (json.dumps(prefs), user_id))


def apply_legacy_prefs(conn: sqlite3.Connection, user_id: int, prefs: dict, changed: set[str]) -> None:
    """Le preferenze «Edizione accesa» e «orari» (API precedenti) valgono per la prima Edizione."""
    configs = user_configs(conn, user_id)
    with conn:
        if not configs:
            if prefs.get("edition"):
                conn.execute(
                    "INSERT INTO edition_configs (user_id, name, active, rules, schedule, max_items, created_at)"
                    " VALUES (?, ?, 1, '{}', ?, ?, ?)",
                    (user_id, DEFAULT_NAME, json.dumps({"kind": "daily", "times": prefs["edition_times"]}), MAX_ITEMS, now()),
                )
            return
        first = configs[0]
        sched = first["schedule"]
        if "edition_times" in changed and sched["kind"] == "daily":
            sched = {"kind": "daily", "times": prefs["edition_times"]}
        active = bool(prefs["edition"]) if "edition" in changed else first["active"]
        conn.execute(
            "UPDATE edition_configs SET active = ?, schedule = ? WHERE id = ?", (int(active), json.dumps(sched), first["id"])
        )


def user_timezone(ctx, prefs: dict, conn: sqlite3.Connection | None = None) -> str:
    """Il fuso dell'utente, oppure quello dell'istanza."""
    tz = (prefs or {}).get("timezone") or ""
    return tz if tz else ctx.instance.get("timezone", conn)


# ---------- Scelta delle notizie ----------


def _candidates(conn: sqlite3.Connection, user_id: int, since: int, dedupe: bool) -> list[sqlite3.Row]:
    f = ArticleFilter(since=since, dedupe=dedupe)
    cte, params = query.visible_cte(user_id, f)
    return conn.execute(
        f"WITH {cte}, {query.ranked_sql(f)}"
        " SELECT r.id, r.level, r.folder_id, r.published_at, s.id AS sub_id, a.title, a.excerpt, a.categories,"
        " COALESCE(s.country, fd.country_admin, fd.country) AS country"
        " FROM ranked r JOIN articles a ON a.id = r.id JOIN feeds fd ON fd.id = a.feed_id"
        " LEFT JOIN subscriptions s ON s.feed_id = a.feed_id AND s.user_id = ?"
        " WHERE r.rn = 1 ORDER BY r.published_at DESC, r.id DESC",
        [*params, user_id],
    ).fetchall()


def has_rules(rules: dict) -> bool:
    return any(rules.get(k) for k in RULE_TYPES)


def apply_rules(conn: sqlite3.Connection, user_id: int, rows: list[sqlite3.Row], rules: dict) -> list[sqlite3.Row]:
    """Le notizie che rispettano le regole: tutte le regole presenti, una qualsiasi per tipo."""
    if not has_rules(rules):
        return rows
    out = rows
    if rules.get("folders"):
        wanted = {str(f) for f in rules["folders"]}
        out = [r for r in out if (str(r["folder_id"]) if r["folder_id"] is not None else "none") in wanted]
    if rules.get("tags"):
        marks = ",".join("?" * len(rules["tags"]))
        subs = {
            r["subscription_id"]
            for r in conn.execute(
                f"SELECT st.subscription_id FROM source_tags st JOIN tags t ON t.id = st.tag_id"
                f" WHERE t.user_id = ? AND st.origin != 'rejected' AND st.tag_id IN ({marks})",
                [user_id, *rules["tags"]],
            )
        }
        out = [r for r in out if r["sub_id"] in subs]
    if rules.get("countries"):
        wanted = {c.upper() for c in rules["countries"]}
        out = [r for r in out if (r["country"] or "").upper() in wanted]
    if rules.get("groups"):
        marks = ",".join("?" * len(rules["groups"]))
        words = [
            r["word"]
            for r in conn.execute(
                f"SELECT w.word FROM word_group_words w JOIN word_groups g ON g.id = w.group_id"
                f" WHERE g.user_id = ? AND g.id IN ({marks})",
                [user_id, *rules["groups"]],
            )
        ]
        patterns = [p for p in (word_pattern(w) for w in words) if p]
        out = [r for r in out if any(p.search(haystack(r["title"], r["excerpt"], r["categories"])) for p in patterns)]
    return out


def select(rows: list[sqlite3.Row], max_items: int = MAX_ITEMS, restricted: bool = False) -> list[tuple[int, str, object]]:
    """Sceglie le notizie: [(id, tipo, cartella)], la prima va in primo piano.

    tipo: «match» (per te), «rule» (rispetta le regole dell'Edizione), «fonti» (aggiunta
    quando quelle per te sono poche).
    """
    level_rank = {"alta": 0, "media": 1}
    if restricted:
        ordered = sorted(rows, key=lambda r: (level_rank.get(r["level"], 2), -r["published_at"]))
        return [(r["id"], "match" if r["level"] else "rule", r["folder_id"]) for r in ordered[:max_items]]
    matches = sorted((r for r in rows if r["level"]), key=lambda r: (level_rank[r["level"]], -r["published_at"]))
    chosen = [(r["id"], "match", r["folder_id"]) for r in matches[:max_items]]
    if len(chosen) < MIN_MATCHES:
        taken = {c[0] for c in chosen}
        seen_sources: set = set()
        for r in rows:
            if len(chosen) >= min(FILLER_ITEMS, max_items):
                break
            if r["id"] in taken or r["sub_id"] in seen_sources:
                continue
            seen_sources.add(r["sub_id"])
            chosen.append((r["id"], "fonti", r["folder_id"]))
    return chosen


def window(conn: sqlite3.Connection, config: dict, ts: int) -> int:
    """Da quando prendere le notizie per la prossima uscita di questa Edizione."""
    first, cap = schedule.window_seconds(config["schedule"], config["period"])
    if config["period"] != "auto":
        return ts - first
    prev = conn.execute(
        "SELECT created_at FROM editions WHERE config_id = ? ORDER BY created_at DESC LIMIT 1", (config["id"],)
    ).fetchone()
    return max(prev["created_at"], ts - cap) if prev else ts - first


def preview(conn: sqlite3.Connection, user_id: int, config: dict, dedupe: bool, ts: int | None = None) -> dict:
    """Quante notizie avrebbe l'Edizione con queste regole, adesso (per l'anteprima nelle Impostazioni)."""
    ts = ts or now()
    first, _ = schedule.window_seconds(config["schedule"], config["period"])
    rows = apply_rules(conn, user_id, _candidates(conn, user_id, ts - first, dedupe), config["rules"])
    chosen = select(rows, config["max_items"], has_rules(config["rules"]))
    return {"available": len(rows), "selected": len(chosen), "hours": first // 3600}


def compose(
    conn: sqlite3.Connection, user_id: int, config: dict, slot: str, ts: int | None = None, dedupe: bool = True
) -> int:
    """Compone e salva un'uscita dell'Edizione. Restituisce il suo id."""
    ts = ts or now()
    since = window(conn, config, ts)
    restricted = has_rules(config["rules"])
    all_rows = _candidates(conn, user_id, since, dedupe)
    rows = apply_rules(conn, user_id, all_rows, config["rules"])
    chosen = select(rows, config["max_items"], restricted)
    hidden = query.count(conn, user_id, ArticleFilter(since=since, dedupe=dedupe), muted=True)
    sources = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE user_id = ?", (user_id,)).fetchone()[0]
    stats = {
        "sources": sources,
        "new": len(rows),
        "selected": sum(1 for c in chosen if c[1] in ("match", "rule")),
        "hidden": hidden,
    }
    with conn:
        number = conn.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM editions WHERE user_id = ?", (user_id,)).fetchone()[0]
        config_number = conn.execute(
            "SELECT COALESCE(MAX(config_number), 0) + 1 FROM editions WHERE config_id = ?", (config["id"],)
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO editions (user_id, number, slot, since, stats, created_at, config_id, config_number)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, number, slot, since, json.dumps(stats), ts, config["id"], config_number),
        )
        edition_id = cur.lastrowid
        items = []
        for pos, (article_id, kind, folder_id) in enumerate(chosen):
            if pos == 0 and kind in ("match", "rule"):
                section = "hero"
            elif kind == "fonti":
                section = "fonti"
            else:
                section = str(folder_id) if folder_id is not None else "none"
            items.append((edition_id, article_id, pos, section))
        conn.executemany("INSERT INTO edition_items (edition_id, article_id, position, section) VALUES (?, ?, ?, ?)", items)
        # Si tengono le ultime KEEP_EDITIONS uscite di ogni Edizione.
        conn.execute(
            "DELETE FROM editions WHERE config_id = ? AND id NOT IN"
            " (SELECT id FROM editions WHERE config_id = ? ORDER BY created_at DESC LIMIT ?)",
            (config["id"], config["id"], KEEP_EDITIONS),
        )
    log.info("«%s» n. %s per l'utente %s: %s notizie", config["name"], config_number, user_id, len(chosen))
    return edition_id


def run_due(ctx, ts: int | None = None) -> list[tuple[int, int]]:
    """Compone le uscite arrivate all'orario. Restituisce [(utente, edizione)]."""
    from ..api.common import prefs_with_defaults

    ts = ts or now()
    made = []
    with ctx.db.session() as conn:
        for r in conn.execute("SELECT id FROM users WHERE editions_ready = 0").fetchall():
            ensure_configs(conn, r["id"])
        rows = conn.execute(
            "SELECT c.*, u.prefs AS user_prefs FROM edition_configs c JOIN users u ON u.id = c.user_id"
            " WHERE c.active = 1 AND u.disabled = 0 ORDER BY c.user_id, c.position, c.id"
        ).fetchall()
        for row in rows:
            config = load_config(row)
            try:
                prefs = prefs_with_defaults(json.loads(row["user_prefs"] or "{}"))
            except ValueError:
                prefs = prefs_with_defaults({})
            last = conn.execute("SELECT MAX(created_at) FROM editions WHERE config_id = ?", (config["id"],)).fetchone()[0]
            slot = schedule.is_due(config["schedule"], user_timezone(ctx, prefs, conn), ts, last)
            if slot:
                try:
                    made.append((config["user_id"], compose(conn, config["user_id"], config, slot, ts, prefs["dedupe"])))
                except Exception:
                    log.exception("Edizione «%s» non composta per l'utente %s", config["name"], config["user_id"])
    return made
