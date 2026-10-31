import xml.etree.ElementTree as ET

import httpx
import respx

from conftest import invite_user
from samples import OPML, RSS_EXCERPT


def _upload(client, data: bytes, name="fonti.opml"):
    return client.post("/api/opml/import", files={"file": (name, data, "text/x-opml")})


def test_import_creates_folders_and_sources(admin, app):
    r = _upload(admin, OPML.encode())
    assert r.status_code == 200, r.text
    report = r.json()
    assert report == {
        "total": 4, "added": 3, "existing": 0, "invalid": 1,
        "invalid_urls": ["javascript:alert(1)"], "folders_created": 1,
    }
    sources = admin.get("/api/sources").json()["sources"]
    folders = {f["id"]: f["name"] for f in admin.get("/api/folders").json()["folders"]}
    by_title = {s["title"]: s for s in sources}
    assert set(by_title) == {"Orbita", "Cronache", "Bit & Byte"}
    assert folders[by_title["Orbita"]["folder_id"]] == "Spazio"
    # Cartelle annidate: si usa quella più esterna.
    assert folders[by_title["Cronache"]["folder_id"]] == "Spazio"
    assert by_title["Bit & Byte"]["folder_id"] is None
    assert by_title["Cronache"]["kind"] == "youtube"
    assert all(s["status"] == "pending" for s in sources)


def test_import_twice_counts_existing(admin):
    _upload(admin, OPML.encode())
    report = _upload(admin, OPML.encode()).json()
    assert report["added"] == 0 and report["existing"] == 3 and report["folders_created"] == 0


def test_imported_feeds_are_fetched_by_scheduler(admin, app):
    with respx.mock(assert_all_called=False) as web:
        orbita = web.get("https://orbita.example/feed.xml").mock(
            return_value=httpx.Response(200, text=RSS_EXCERPT, headers={"content-type": "application/rss+xml"})
        )
        web.get(url__regex=r".*").mock(return_value=httpx.Response(404))
        _upload(admin, OPML.encode())
        admin.portal.call(app.state.ctx.scheduler.run_once)
    assert orbita.called
    by_title = {s["title"]: s for s in admin.get("/api/sources").json()["sources"]}
    assert by_title["Orbita"]["status"] == "ok" and by_title["Orbita"]["articles"] == 2
    assert by_title["Bit & Byte"]["status"] == "err"


def test_import_rejects_bad_files(admin):
    r = _upload(admin, b"non sono xml")
    assert r.status_code == 422 and "OPML" in r.json()["detail"]
    r = _upload(admin, b"<html><body/></html>")
    assert r.status_code == 422
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><opml><body/></opml>'
    assert _upload(admin, bomb).status_code == 422
    assert _upload(admin, b"x" * (2 * 1024 * 1024 + 10)).status_code == 413


def test_export_roundtrip(admin, app):
    _upload(admin, OPML.encode())
    r = admin.get("/api/opml/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"] and ".opml" in r.headers["content-disposition"]
    root = ET.fromstring(r.content)
    folder = root.find("body/outline[@text='Spazio']")
    assert {o.get("xmlUrl") for o in folder.findall("outline")} == {
        "https://orbita.example/feed.xml",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnopqrstuv",
    }
    assert root.find("body/outline[@text='Bit & Byte']").get("xmlUrl") == "https://bitebyte.example/atom.xml"

    # Un altro utente importa l'export: stessi feed, nessun download in più.
    bruno = invite_user(admin, app, "bruno")
    report = _upload(bruno, r.content).json()
    assert report["added"] == 3
    with app.state.ctx.db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0] == 3


def test_export_is_per_user(admin, app):
    _upload(admin, OPML.encode())
    bruno = invite_user(admin, app, "bruno")
    root = ET.fromstring(bruno.get("/api/opml/export").content)
    assert root.find("body").findall("outline") == []
