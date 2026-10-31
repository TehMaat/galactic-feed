"""Cartelle personali in cui raggruppare le fonti."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..db import now
from ..deps import User, current_user, get_db

router = APIRouter(prefix="/api/folders", tags=["cartelle"])

# Colori disponibili, nello stesso ordine della palette del mockup (la PWA li traduce in CSS).
COLORS = ["indaco", "blu", "verde", "viola", "rosa", "ambra", "azzurro", "grigio"]


def clean_name(value: str) -> str:
    value = " ".join((value or "").split())
    if not value:
        raise ValueError("Dai un nome alla cartella.")
    if len(value) > 40:
        raise ValueError("Il nome della cartella può avere al massimo 40 caratteri.")
    return value


def folder_payload(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"], "color": row["color"], "position": row["position"]}


def list_folders(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM folders WHERE user_id = ? ORDER BY position, name COLLATE NOCASE", (user_id,)
    ).fetchall()
    return [folder_payload(r) for r in rows]


def get_or_create_folder(conn: sqlite3.Connection, user_id: int, name: str, color: str | None = None) -> tuple[int, bool]:
    """Id della cartella con quel nome, creandola se manca. Il secondo valore dice se è nuova."""
    row = conn.execute("SELECT id FROM folders WHERE user_id = ? AND name = ?", (user_id, name)).fetchone()
    if row:
        return row["id"], False
    used = [r["color"] for r in conn.execute("SELECT color FROM folders WHERE user_id = ?", (user_id,))]
    if color not in COLORS:
        free = [c for c in COLORS if c not in used]
        color = free[0] if free else COLORS[len(used) % len(COLORS)]
    position = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM folders WHERE user_id = ?", (user_id,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO folders (user_id, name, color, position, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, color, position, now()),
    )
    return cur.lastrowid, True


def check_folder(conn: sqlite3.Connection, user_id: int, folder_id: int | None) -> None:
    if folder_id is None:
        return
    if not conn.execute("SELECT 1 FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id)).fetchone():
        raise HTTPException(status_code=404, detail="Cartella non trovata.")


@router.get("")
def folders(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return {"folders": list_folders(conn, user.id), "colors": COLORS}


class NewFolder(BaseModel):
    name: str
    color: str | None = None

    _n = field_validator("name")(clean_name)


@router.post("", status_code=201)
def create_folder(body: NewFolder, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    if conn.execute("SELECT 1 FROM folders WHERE user_id = ? AND name = ?", (user.id, body.name)).fetchone():
        raise HTTPException(status_code=409, detail="Hai già una cartella con questo nome.")
    with conn:
        folder_id, _ = get_or_create_folder(conn, user.id, body.name, body.color)
    row = conn.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
    return {"folder": folder_payload(row)}


class FolderPatch(BaseModel):
    name: str | None = None
    color: str | None = None
    position: int | None = None

    _n = field_validator("name")(lambda v: clean_name(v) if v is not None else None)


@router.patch("/{folder_id}")
def update_folder(
    folder_id: int, body: FolderPatch, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)
):
    row = conn.execute("SELECT * FROM folders WHERE id = ? AND user_id = ?", (folder_id, user.id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Cartella non trovata.")
    if body.color is not None and body.color not in COLORS:
        raise HTTPException(status_code=422, detail="Colore non disponibile.")
    name = body.name if body.name is not None else row["name"]
    clash = conn.execute(
        "SELECT 1 FROM folders WHERE user_id = ? AND name = ? AND id != ?", (user.id, name, folder_id)
    ).fetchone()
    if clash:
        raise HTTPException(status_code=409, detail="Hai già una cartella con questo nome.")
    with conn:
        conn.execute(
            "UPDATE folders SET name = ?, color = ?, position = ? WHERE id = ?",
            (name, body.color or row["color"], row["position"] if body.position is None else body.position, folder_id),
        )
    return {"folder": folder_payload(conn.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone())}


@router.delete("/{folder_id}")
def delete_folder(folder_id: int, user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    """Le fonti della cartella non si perdono: restano «senza cartella»."""
    with conn:
        cur = conn.execute("DELETE FROM folders WHERE id = ? AND user_id = ?", (folder_id, user.id))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Cartella non trovata.")
    return {"ok": True}
