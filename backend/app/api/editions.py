"""Edizioni (#18, #19): le configurazioni dell'utente e le loro uscite.

- /api/edition-configs: crea, modifica, duplica, elimina le Edizioni; anteprima delle regole
  e delle prossime uscite.
- /api/editions: l'ultima uscita (di tutte o di un'Edizione), una precedente, oppure una nuova adesso.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..db import iso, now
from ..deps import AppContext, User, current_user, get_ctx, get_db
from ..reading import edition, query, schedule
from .articles import item_payload
from .common import prefs_with_defaults

router = APIRouter(prefix="/api", tags=["edizione"])

NONE_TITLE = "Senza cartella"
FONTI_TITLE = "Dalle tue fonti"
MAX_CONFIGS = 20
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


# ---------- Configurazioni ----------


class Rules(BaseModel):
    tags: list[int] = Field(default_factory=list, max_length=50)
    folders: list[str] = Field(default_factory=list, max_length=50)
    countries: list[str] = Field(default_factory=list, max_length=50)
    groups: list[int] = Field(default_factory=list, max_length=50)

    @field_validator("countries")
    @classmethod
    def _countries(cls, values: list[str]) -> list[str]:
        out = []
        for v in values:
            v = (v or "").strip().upper()
            if not COUNTRY_RE.match(v):
                raise ValueError("Nazione non valida: usa il codice di due lettere, per esempio IT.")
            if v not in out:
                out.append(v)
        return out

    @field_validator("folders")
    @classmethod
    def _folders(cls, values: list[str]) -> list[str]:
        out = []
        for v in values:
            v = str(v).strip()
            if v != "none" and not v.isdigit():
                raise ValueError("Cartella non valida.")
            if v not in out:
                out.append(v)
        return out


class ConfigBody(BaseModel):
    name: str | None = None
    active: bool | None = None
    rules: Rules | None = None
    schedule: dict | None = None
    max_items: int | None = Field(default=None, ge=5, le=100)
    period: Literal["auto", "day", "week", "month"] | None = None
    notify: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = " ".join(v.split())
        if not v:
            raise ValueError("Dai un nome all'Edizione.")
        if len(v) > 40:
            raise ValueError("Il nome può avere al massimo 40 caratteri.")
        return v

    @field_validator("schedule")
    @classmethod
    def _schedule(cls, v: dict | None) -> dict | None:
        return schedule.check(v) if v is not None else None


def _check_rules(conn: sqlite3.Connection, user_id: int, rules: Rules) -> dict:
    """Tag, cartelle e gruppi devono essere dell'utente."""
    def own(table: str, ids: list[int]) -> None:
        if not ids:
            return
        marks = ",".join("?" * len(ids))
        found = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ? AND id IN ({marks})", [user_id, *ids]).fetchone()[0]
        if found != len(set(ids)):
            raise HTTPException(status_code=422, detail="Una delle regole non è più valida: ricarica e riprova.")

    own("tags", rules.tags)
    own("word_groups", rules.groups)
    own("folders", [int(f) for f in rules.folders if f != "none"])
    return rules.model_dump()


def _tz(ctx: AppContext, user: User, conn: sqlite3.Connection) -> str:
    return edition.user_timezone(ctx, prefs_with_defaults(user.prefs), conn)


def config_payload(conn: sqlite3.Connection, config: dict, tz: str) -> dict:
    upcoming = schedule.next_occurrences(config["schedule"], tz, now(), 3) if config["active"] else []
    last = conn.execute(
        "SELECT id, created_at FROM editions WHERE config_id = ? ORDER BY created_at DESC LIMIT 1", (config["id"],)
    ).fetchone()
    return {
        **{k: config[k] for k in ("id", "name", "active", "rules", "schedule", "max_items", "period", "notify", "position")},
        "description": schedule.describe(config["schedule"]),
        "next": [{"at": iso(t), "time": slot} for t, slot in upcoming],
        "last_edition_id": last["id"] if last else None,
        "last_at": iso(last["created_at"]) if last else None,
    }


def configs_payload(conn: sqlite3.Connection, user: User, ctx: AppContext) -> dict:
    tz = _tz(ctx, user, conn)
    return {"configs": [config_payload(conn, c, tz) for c in edition.user_configs(conn, user.id)], "timezone": tz}


def _get_config(conn: sqlite3.Connection, user_id: int, config_id: int) -> dict:
    edition.ensure_configs(conn, user_id)
    row = conn.execute("SELECT * FROM edition_configs WHERE id = ? AND user_id = ?", (config_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Edizione non trovata.")
    return edition.load_config(row)


@router.get("/edition-configs")
def list_configs(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)):
    return configs_payload(conn, user, ctx)


@router.post("/edition-configs", status_code=201)
def create_config(
    body: ConfigBody, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    configs = edition.user_configs(conn, user.id)
    if len(configs) >= MAX_CONFIGS:
        raise HTTPException(status_code=422, detail=f"Puoi avere al massimo {MAX_CONFIGS} Edizioni.")
    rules = _check_rules(conn, user.id, body.rules or Rules())
    sched = body.schedule or {"kind": "daily", "times": ["07:30"]}
    name = body.name or (edition.DEFAULT_NAME if not configs else f"Edizione {len(configs) + 1}")
    position = max((c["position"] for c in configs), default=-1) + 1
    with conn:
        conn.execute(
            "INSERT INTO edition_configs (user_id, name, active, rules, schedule, max_items, period, notify, position, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user.id, name, int(body.active if body.active is not None else True), json.dumps(rules), json.dumps(sched),
                body.max_items or edition.MAX_ITEMS, body.period or "auto", int(body.notify if body.notify is not None else True),
                position, now(),
            ),
        )
    edition.sync_edition_pref(conn, user.id)
    return configs_payload(conn, user, ctx)


@router.patch("/edition-configs/{config_id}")
def update_config(
    config_id: int, body: ConfigBody, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    config = _get_config(conn, user.id, config_id)
    rules = _check_rules(conn, user.id, body.rules) if body.rules is not None else config["rules"]
    with conn:
        conn.execute(
            "UPDATE edition_configs SET name = ?, active = ?, rules = ?, schedule = ?, max_items = ?, period = ?, notify = ?"
            " WHERE id = ?",
            (
                body.name or config["name"],
                int(config["active"] if body.active is None else body.active),
                json.dumps(rules),
                json.dumps(body.schedule or config["schedule"]),
                body.max_items or config["max_items"],
                body.period or config["period"],
                int(config["notify"] if body.notify is None else body.notify),
                config_id,
            ),
        )
    edition.sync_edition_pref(conn, user.id)
    return configs_payload(conn, user, ctx)


@router.post("/edition-configs/{config_id}/duplicate", status_code=201)
def duplicate_config(
    config_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    config = _get_config(conn, user.id, config_id)
    body = ConfigBody(
        name=f"{config['name']} (copia)"[:40], active=False, rules=Rules(**config["rules"]), schedule=config["schedule"],
        max_items=config["max_items"], period=config["period"], notify=config["notify"],
    )
    return create_config(body, user, conn, ctx)


@router.delete("/edition-configs/{config_id}")
def delete_config(
    config_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    """Elimina l'Edizione e le sue uscite."""
    _get_config(conn, user.id, config_id)
    with conn:
        conn.execute("DELETE FROM editions WHERE config_id = ?", (config_id,))
        conn.execute("DELETE FROM edition_configs WHERE id = ?", (config_id,))
    edition.sync_edition_pref(conn, user.id)
    return configs_payload(conn, user, ctx)


class Order(BaseModel):
    ids: list[int] = Field(max_length=MAX_CONFIGS)


@router.put("/edition-configs/order")
def reorder_configs(
    body: Order, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    with conn:
        for position, config_id in enumerate(body.ids):
            conn.execute("UPDATE edition_configs SET position = ? WHERE id = ? AND user_id = ?", (position, config_id, user.id))
    return configs_payload(conn, user, ctx)


class PreviewBody(BaseModel):
    rules: Rules = Field(default_factory=Rules)
    schedule: dict = Field(default_factory=lambda: {"kind": "daily", "times": ["07:30"]})
    max_items: int = Field(default=edition.MAX_ITEMS, ge=5, le=100)
    period: Literal["auto", "day", "week", "month"] = "auto"

    _s = field_validator("schedule")(lambda v: schedule.check(v))


@router.post("/edition-configs/preview")
def preview_config(
    body: PreviewBody, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    """«Con queste regole oggi avresti 12 notizie», e le prossime uscite."""
    rules = _check_rules(conn, user.id, body.rules)
    config = {"rules": rules, "schedule": body.schedule, "max_items": body.max_items, "period": body.period}
    result = edition.preview(conn, user.id, config, prefs_with_defaults(user.prefs)["dedupe"])
    tz = _tz(ctx, user, conn)
    result["description"] = schedule.describe(body.schedule)
    result["next"] = [{"at": iso(t), "time": slot} for t, slot in schedule.next_occurrences(body.schedule, tz, now(), 3)]
    return result


# ---------- Uscite ----------


def _schedule_summary(conn: sqlite3.Connection, user: User, ctx: AppContext, config_id: int | None) -> dict:
    """La prossima uscita (dell'Edizione indicata o della prima attiva), per la testata."""
    configs = edition.user_configs(conn, user.id)
    tz = _tz(ctx, user, conn)
    active = [c for c in configs if c["active"]]
    chosen = next((c for c in configs if c["id"] == config_id), None) or (active[0] if active else None)
    upcoming = schedule.next_occurrences(chosen["schedule"], tz, now(), 1) if chosen and chosen["active"] else []
    return {
        "enabled": bool(active),
        "config_id": chosen["id"] if chosen else None,
        "times": chosen["schedule"]["times"] if chosen else [],
        "description": schedule.describe(chosen["schedule"]) if chosen else "",
        "next_at": iso(upcoming[0][0]) if upcoming else None,
        "next_time": upcoming[0][1] if upcoming else None,
        "timezone": tz,
    }


def _configs_brief(conn: sqlite3.Connection, user: User) -> list[dict]:
    """Le Edizioni per il selettore in Oggi, dalla più recente uscita."""
    rows = conn.execute(
        "SELECT c.id, c.name, c.active, MAX(e.created_at) AS last, MAX(e.id) AS last_id FROM edition_configs c"
        " LEFT JOIN editions e ON e.config_id = c.id WHERE c.user_id = ? GROUP BY c.id"
        " ORDER BY last IS NULL, last DESC, last_id DESC, c.position",
        (user.id,),
    ).fetchall()
    return [{"id": r["id"], "name": r["name"], "active": bool(r["active"]), "last_at": iso(r["last"])} for r in rows]


def edition_payload(conn: sqlite3.Connection, user: User, ctx: AppContext, row: sqlite3.Row) -> dict:
    items = conn.execute(
        "SELECT article_id, section FROM edition_items WHERE edition_id = ? ORDER BY position", (row["id"],)
    ).fetchall()
    details = query.article_rows(conn, user.id, [i["article_id"] for i in items])
    folders = {
        str(f["id"]): f
        for f in conn.execute("SELECT id, name, color, position FROM folders WHERE user_id = ? ORDER BY position, name", (user.id,))
    }
    order = list(folders)
    hero = None
    groups: dict[str, list[dict]] = {}
    for it in items:
        r = details.get(it["article_id"])
        if r is None or (r["sub_id"] is None and r["saved_at"] is None):
            continue  # fonte non più seguita
        payload = item_payload(r, ctx.secret)
        if it["section"] == "hero":
            hero = payload
            continue
        key = it["section"]
        if key not in ("none", "fonti") and key not in folders:
            key = "none"  # cartella cancellata nel frattempo
        groups.setdefault(key, []).append(payload)
    sections = []
    for key in [*order, "none", "fonti"]:
        if key not in groups:
            continue
        if key in folders:
            title, color = folders[key]["name"], folders[key]["color"]
        else:
            title, color = (NONE_TITLE if key == "none" else FONTI_TITLE), "grigio"
        sections.append({"key": key, "title": title, "color": color, "items": groups[key]})
    config = conn.execute("SELECT name FROM edition_configs WHERE id = ?", (row["config_id"],)).fetchone() if row["config_id"] else None
    return {
        "id": row["id"],
        "number": row["config_number"] or row["number"],
        "config_id": row["config_id"],
        "name": config["name"] if config else edition.DEFAULT_NAME,
        "slot": row["slot"],
        "created_at": iso(row["created_at"]),
        "since": iso(row["since"]),
        "stats": json.loads(row["stats"] or "{}"),
        "hero": hero,
        "sections": sections,
    }


@router.get("/editions/latest")
def latest(
    config: int | None = Query(None, description="id dell'Edizione; senza, l'ultima uscita di tutte"),
    user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx),
):
    edition.ensure_configs(conn, user.id)
    if config is not None:
        row = conn.execute(
            "SELECT * FROM editions WHERE user_id = ? AND config_id = ? ORDER BY created_at DESC, id DESC LIMIT 1", (user.id, config)
        ).fetchone()
    else:
        row = conn.execute("SELECT * FROM editions WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 1", (user.id,)).fetchone()
    shown = config if config is not None else (row["config_id"] if row else None)
    return {
        "edition": edition_payload(conn, user, ctx, row) if row else None,
        "schedule": _schedule_summary(conn, user, ctx, shown),
        "configs": _configs_brief(conn, user),
    }


@router.get("/editions/{edition_id}")
def get_edition(
    edition_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    row = conn.execute("SELECT * FROM editions WHERE id = ? AND user_id = ?", (edition_id, user.id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Edizione non trovata.")
    return {
        "edition": edition_payload(conn, user, ctx, row),
        "schedule": _schedule_summary(conn, user, ctx, row["config_id"]),
        "configs": _configs_brief(conn, user),
    }


@router.delete("/editions/{edition_id}")
def delete_edition(
    edition_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx)
):
    """Elimina un'uscita (per esempio una composta per prova); l'Edizione e le altre uscite restano.

    Restituisce l'uscita più recente rimasta della stessa Edizione, come «editions/latest».
    """
    row = conn.execute("SELECT config_id FROM editions WHERE id = ? AND user_id = ?", (edition_id, user.id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Edizione non trovata.")
    with conn:
        conn.execute("DELETE FROM editions WHERE id = ?", (edition_id,))
    return latest(config=row["config_id"], user=user, conn=conn, ctx=ctx)


class ComposeBody(BaseModel):
    config_id: int | None = None


@router.post("/editions", status_code=201)
def compose_now(
    body: ComposeBody | None = None,
    user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db), ctx: AppContext = Depends(get_ctx),
):
    """«Componi adesso»: un'uscita dell'Edizione indicata (o della prima) con le notizie arrivate dall'ultima."""
    prefs = prefs_with_defaults(user.prefs)
    configs = edition.user_configs(conn, user.id)
    if not configs:
        # Prima volta: si crea «La mia Edizione», spenta, solo per comporre adesso.
        create_config(ConfigBody(active=False), user, conn, ctx)
        configs = edition.user_configs(conn, user.id)
    config_id = body.config_id if body else None
    config = next((c for c in configs if c["id"] == config_id), None) if config_id else (next((c for c in configs if c["active"]), configs[0]))
    if config is None:
        raise HTTPException(status_code=404, detail="Edizione non trovata.")
    last = conn.execute("SELECT MAX(created_at) FROM editions WHERE config_id = ?", (config["id"],)).fetchone()[0]
    if last and now() - last < 60:
        raise HTTPException(status_code=429, detail="Hai appena composto questa Edizione: riprova tra un minuto.")
    slot = datetime.fromtimestamp(now(), schedule.zone(_tz(ctx, user, conn))).strftime("%H:%M")
    edition_id = edition.compose(conn, user.id, config, slot, dedupe=prefs["dedupe"])
    row = conn.execute("SELECT * FROM editions WHERE id = ?", (edition_id,)).fetchone()
    return {
        "edition": edition_payload(conn, user, ctx, row),
        "schedule": _schedule_summary(conn, user, ctx, config["id"]),
        "configs": _configs_brief(conn, user),
    }
