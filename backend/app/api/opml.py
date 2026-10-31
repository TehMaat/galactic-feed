"""Import ed export OPML: il formato con cui i lettori RSS si scambiano l'elenco delle fonti."""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import formatdate

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from ..deps import AppContext, User, current_user, get_ctx, get_db
from ..feeds.net import FetchError, normalize_input_url
from ..feeds.sanitize import normalize_feed_url
from .folders import get_or_create_folder
from .sources import DEFAULT_INTERVAL, ensure_feed, subscribe

router = APIRouter(prefix="/api/opml", tags=["opml"])

MAX_OPML_BYTES = 2 * 1024 * 1024
INVALID = "Il file non è un OPML valido. Esportalo di nuovo dal tuo lettore RSS e riprova."


def parse_opml(data: bytes) -> list[tuple[str, str, str | None]]:
    """(indirizzo del feed, titolo, cartella) per ogni fonte del file."""
    if b"<!ENTITY" in data[:4096].upper():
        raise ValueError("entità non permesse")
    root = ET.fromstring(data)
    if root.tag.lower() != "opml":
        raise ValueError("non è OPML")
    body = root.find("body")
    if body is None:
        raise ValueError("manca il body")
    found: list[tuple[str, str, str | None]] = []

    def walk(node: ET.Element, folder: str | None) -> None:
        for outline in node.findall("outline"):
            url = outline.get("xmlUrl") or outline.get("xmlurl")
            title = (outline.get("title") or outline.get("text") or "").strip()
            if url:
                found.append((url.strip(), title, folder))
            # Le cartelle annidate diventano una cartella sola: quella più esterna.
            walk(outline, folder or (title if not url else None) or None)

    walk(body, None)
    return found


@router.post("/import")
async def import_opml(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    data = await file.read(MAX_OPML_BYTES + 1)
    if len(data) > MAX_OPML_BYTES:
        raise HTTPException(status_code=413, detail="Il file è troppo grande (massimo 2 MB).")
    try:
        entries = parse_opml(data)
    except (ET.ParseError, ValueError):
        raise HTTPException(status_code=422, detail=INVALID)

    added = existing = invalid = folders_created = 0
    failed: list[str] = []
    with conn:
        for raw_url, title, folder_name in entries:
            try:
                url = normalize_feed_url(normalize_input_url(raw_url))
            except FetchError:
                invalid += 1
                failed.append(raw_url)
                continue
            folder_id = None
            if folder_name:
                folder_id, created = get_or_create_folder(conn, user.id, " ".join(folder_name.split())[:40])
                folders_created += created
            feed_id, _ = ensure_feed(conn, url, title[:120])
            if subscribe(conn, user.id, feed_id, folder_id, "", DEFAULT_INTERVAL):
                added += 1
            else:
                existing += 1
    # I feed nuovi vengono scaricati subito dallo scheduler, in sottofondo.
    ctx.scheduler.wake()
    return {
        "total": len(entries),
        "added": added,
        "existing": existing,
        "invalid": invalid,
        "invalid_urls": failed[:20],
        "folders_created": folders_created,
    }


@router.get("/export")
def export_opml(user: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT COALESCE(NULLIF(s.title, ''), NULLIF(f.title, ''), f.url) AS title, f.url, f.site_url, f.kind,"
        " d.name AS folder, d.position FROM subscriptions s JOIN feeds f ON f.id = s.feed_id"
        " LEFT JOIN folders d ON d.id = s.folder_id WHERE s.user_id = ?"
        " ORDER BY d.position IS NULL, d.position, d.name COLLATE NOCASE, title COLLATE NOCASE",
        (user.id,),
    ).fetchall()

    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = f"Fonti di {user.display_name} · Galactic Feed"
    ET.SubElement(head, "dateCreated").text = formatdate(usegmt=True)
    body = ET.SubElement(opml, "body")
    groups: dict[str, ET.Element] = {}
    for r in rows:
        parent = body
        if r["folder"]:
            parent = groups.get(r["folder"])
            if parent is None:
                parent = groups[r["folder"]] = ET.SubElement(body, "outline", text=r["folder"], title=r["folder"])
        attrs = {"type": "rss", "text": r["title"], "title": r["title"], "xmlUrl": r["url"]}
        if r["site_url"]:
            attrs["htmlUrl"] = r["site_url"]
        ET.SubElement(parent, "outline", attrs)
    ET.indent(opml)
    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(opml, encoding="utf-8")
    filename = f"galactic-feed-{datetime.now().strftime('%Y-%m-%d')}.opml"
    return Response(
        content=xml,
        media_type="text/x-opml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
