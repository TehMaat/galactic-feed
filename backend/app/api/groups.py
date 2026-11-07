"""Gruppi di parole (issue #16): pronti o personali, accesi come interessi o come silenziatori.

- Ogni utente vede i gruppi pronti (preset_groups) e i propri (word_groups). Accendere un
  gruppo pronto ne crea una copia personale, con le stesse parole, che poi si può modificare.
- L'amministratore gestisce i gruppi pronti offerti a tutti: aggiunge, modifica, nasconde.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..db import now
from ..deps import User, current_user, get_db, require_admin
from ..reading.matching import recompute_user
from ..reading.text import normalize

router = APIRouter(prefix="/api", tags=["gruppi di parole"])

MAX_GROUPS = 50
MAX_WORDS = 100
Mode = Literal["off", "interest", "mute"]


def clean_name(value: str) -> str:
    value = " ".join((value or "").split())
    if not normalize(value):
        raise ValueError("Dai un nome al gruppo.")
    if len(value) > 40:
        raise ValueError("Il nome del gruppo può avere al massimo 40 caratteri.")
    return value


def clean_words(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values:
        v = " ".join((v or "").split())
        key = normalize(v)
        if not key or key in seen:
            continue
        if len(v) > 60:
            raise ValueError("Ogni parola può avere al massimo 60 caratteri.")
        seen.add(key)
        out.append(v)
    if len(out) > MAX_WORDS:
        raise ValueError(f"Al massimo {MAX_WORDS} parole per gruppo.")
    return out


# ---------- Gruppi dell'utente ----------


def _words(conn: sqlite3.Connection, group_ids: list[int]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {g: [] for g in group_ids}
    if group_ids:
        marks = ",".join("?" * len(group_ids))
        for r in conn.execute(f"SELECT group_id, word FROM word_group_words WHERE group_id IN ({marks}) ORDER BY id", group_ids):
            out[r["group_id"]].append(r["word"])
    return out


def groups_payload(conn: sqlite3.Connection, user_id: int) -> dict:
    """I gruppi dell'utente e quelli pronti che non ha ancora preso."""
    rows = conn.execute(
        "SELECT g.*, p.position AS preset_position FROM word_groups g LEFT JOIN preset_groups p ON p.id = g.preset_id"
        " WHERE g.user_id = ? ORDER BY p.position IS NULL, p.position, g.created_at, g.id",
        (user_id,),
    ).fetchall()
    words = _words(conn, [r["id"] for r in rows])
    taken = {r["preset_id"] for r in rows if r["preset_id"]}
    presets = conn.execute("SELECT * FROM preset_groups WHERE hidden = 0 ORDER BY position, name").fetchall()
    return {
        "groups": [
            {"id": r["id"], "name": r["name"], "mode": r["mode"], "level": r["level"], "preset_id": r["preset_id"], "words": words[r["id"]]}
            for r in rows
        ],
        "presets": [
            {"id": p["id"], "name": p["name"], "words": json.loads(p["words"])} for p in presets if p["id"] not in taken
        ],
    }


def _own_group(conn: sqlite3.Connection, user_id: int, group_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM word_groups WHERE id = ? AND user_id = ?", (group_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Gruppo non trovato.")
    return row


def _set_words(conn: sqlite3.Connection, group_id: int, words: list[str]) -> None:
    conn.execute("DELETE FROM word_group_words WHERE group_id = ?", (group_id,))
    conn.executemany("INSERT INTO word_group_words (group_id, word) VALUES (?, ?)", [(group_id, w) for w in words])


class NewGroup(BaseModel):
    name: str | None = None
    words: list[str] | None = Field(default=None, max_length=MAX_WORDS * 2)
    preset_id: int | None = None
    mode: Mode = "off"
    level: Literal["alta", "media"] = "media"

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return clean_name(v) if v is not None else None

    @field_validator("words")
    @classmethod
    def _w(cls, v: list[str] | None) -> list[str] | None:
        return clean_words(v) if v is not None else None


@router.post("/groups", status_code=201)
def create_group(body: NewGroup, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """Un gruppo nuovo: da un gruppo pronto (preset_id, con le sue parole) oppure personale."""
    if conn.execute("SELECT COUNT(*) FROM word_groups WHERE user_id = ?", (user.id,)).fetchone()[0] >= MAX_GROUPS:
        raise HTTPException(status_code=422, detail=f"Puoi avere al massimo {MAX_GROUPS} gruppi.")
    name, words = body.name, body.words
    if body.preset_id is not None:
        preset = conn.execute("SELECT * FROM preset_groups WHERE id = ? AND hidden = 0", (body.preset_id,)).fetchone()
        if preset is None:
            raise HTTPException(status_code=404, detail="Gruppo pronto non trovato.")
        taken = conn.execute(
            "SELECT id FROM word_groups WHERE user_id = ? AND preset_id = ?", (user.id, body.preset_id)
        ).fetchone()
        if taken:
            raise HTTPException(status_code=409, detail="Hai già questo gruppo.")
        name = name or preset["name"]
        words = words if words is not None else json.loads(preset["words"])
    if not name:
        raise HTTPException(status_code=422, detail="Dai un nome al gruppo.")
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO word_groups (user_id, preset_id, name, mode, level, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user.id, body.preset_id, name, body.mode, body.level, now()),
            )
            _set_words(conn, cur.lastrowid, words or [])
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Hai già un gruppo con questo nome.")
    if body.mode != "off":
        recompute_user(conn, user.id)
    return groups_payload(conn, user.id)


class GroupPatch(BaseModel):
    name: str | None = None
    mode: Mode | None = None
    level: Literal["alta", "media"] | None = None
    words: list[str] | None = Field(default=None, max_length=MAX_WORDS * 2)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return clean_name(v) if v is not None else None

    @field_validator("words")
    @classmethod
    def _w(cls, v: list[str] | None) -> list[str] | None:
        return clean_words(v) if v is not None else None


@router.patch("/groups/{group_id}")
def update_group(group_id: int, body: GroupPatch, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    row = _own_group(conn, user.id, group_id)
    try:
        with conn:
            conn.execute(
                "UPDATE word_groups SET name = ?, mode = ?, level = ? WHERE id = ?",
                (body.name or row["name"], body.mode or row["mode"], body.level or row["level"], group_id),
            )
            if body.words is not None:
                _set_words(conn, group_id, body.words)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Hai già un gruppo con questo nome.")
    # Le regole cambiano solo se il gruppo è (o era) acceso.
    if row["mode"] != "off" or (body.mode or "off") != "off":
        recompute_user(conn, user.id)
    return groups_payload(conn, user.id)


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """Elimina il gruppo. Se veniva da un gruppo pronto, quello torna disponibile con le parole originali."""
    row = _own_group(conn, user.id, group_id)
    with conn:
        conn.execute("DELETE FROM word_groups WHERE id = ?", (group_id,))
    if row["mode"] != "off":
        recompute_user(conn, user.id)
    return groups_payload(conn, user.id)


# ---------- Gruppi pronti (amministratore) ----------


def _preset_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "words": json.loads(r["words"]),
        "hidden": bool(r["hidden"]),
        "builtin": bool(r["builtin"]),
    }


def presets_payload(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT * FROM preset_groups ORDER BY position, name").fetchall()
    return {"presets": [_preset_row(r) for r in rows]}


@router.get("/admin/presets")
def list_presets(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    return presets_payload(conn)


class NewPreset(BaseModel):
    name: str
    words: list[str] = Field(default_factory=list, max_length=MAX_WORDS * 2)

    _n = field_validator("name")(clean_name)
    _w = field_validator("words")(clean_words)


@router.post("/admin/presets", status_code=201)
def create_preset(body: NewPreset, _: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    position = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM preset_groups").fetchone()[0]
    try:
        with conn:
            conn.execute(
                "INSERT INTO preset_groups (name, words, position, updated_at) VALUES (?, ?, ?, ?)",
                (body.name, json.dumps(body.words, ensure_ascii=False), position, now()),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Esiste già un gruppo pronto con questo nome.")
    return presets_payload(conn)


class PresetPatch(BaseModel):
    name: str | None = None
    words: list[str] | None = Field(default=None, max_length=MAX_WORDS * 2)
    hidden: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return clean_name(v) if v is not None else None

    @field_validator("words")
    @classmethod
    def _w(cls, v: list[str] | None) -> list[str] | None:
        return clean_words(v) if v is not None else None


def _preset(conn: sqlite3.Connection, preset_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM preset_groups WHERE id = ?", (preset_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Gruppo pronto non trovato.")
    return row


@router.patch("/admin/presets/{preset_id}")
def update_preset(preset_id: int, body: PresetPatch, _: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    """Le modifiche valgono per chi prende il gruppo da adesso; chi lo usa già tiene la sua copia."""
    row = _preset(conn, preset_id)
    words = json.dumps(body.words, ensure_ascii=False) if body.words is not None else row["words"]
    hidden = row["hidden"] if body.hidden is None else int(body.hidden)
    try:
        with conn:
            conn.execute(
                "UPDATE preset_groups SET name = ?, words = ?, hidden = ?, updated_at = ? WHERE id = ?",
                (body.name or row["name"], words, hidden, now(), preset_id),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Esiste già un gruppo pronto con questo nome.")
    return presets_payload(conn)


@router.delete("/admin/presets/{preset_id}")
def delete_preset(preset_id: int, _: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    """I gruppi forniti con l'app si nascondono (tornerebbero al prossimo avvio); gli altri si cancellano."""
    row = _preset(conn, preset_id)
    with conn:
        if row["builtin"]:
            conn.execute("UPDATE preset_groups SET hidden = 1, updated_at = ? WHERE id = ?", (now(), preset_id))
        else:
            conn.execute("DELETE FROM preset_groups WHERE id = ?", (preset_id,))
    return presets_payload(conn)
