"""Edizione: orari, scelta delle notizie, sezioni e API."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.reading import edition

from helpers import entry, feed, user_id

ROME = "Europe/Rome"


def ts(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=ZoneInfo(ROME)).timestamp())


def test_slots():
    times = ["07:30", "19:00"]
    assert edition.last_slot(times, ROME, ts("2026-11-02 10:00")) == (ts("2026-11-02 07:30"), "07:30")
    assert edition.last_slot(times, ROME, ts("2026-11-02 06:00")) == (ts("2026-11-01 19:00"), "19:00")
    assert edition.next_slot(times, ROME, ts("2026-11-02 20:00")) == (ts("2026-11-03 07:30"), "07:30")
    # La prima edizione si compone subito; poi una per orario.
    assert edition.is_due(times, ROME, ts("2026-11-02 10:00"), None) == "07:30"
    assert edition.is_due(times, ROME, ts("2026-11-02 10:00"), ts("2026-11-02 07:31")) is None
    assert edition.is_due(times, ROME, ts("2026-11-02 19:00"), ts("2026-11-02 07:31")) == "19:00"
    # Server spento all'orario: si recupera appena riparte.
    assert edition.is_due(times, ROME, ts("2026-11-02 08:40"), ts("2026-11-01 19:00")) == "07:30"


def test_edition_flow(admin, app):
    folder = admin.post("/api/folders", json={"name": "Spazio", "color": "blu"}).json()["folder"]["id"]
    feed(app, admin, "https://orbita.example/feed", [
        entry("Missione lunare al polo sud", hours_ago=1),
        entry("Nuovo telescopio spaziale", hours_ago=2),
        entry("Oroscopo della settimana", hours_ago=3),
    ], title="Orbita", folder_id=folder)
    feed(app, admin, "https://bit.example/feed", [
        entry("Il razzo riutilizzabile vola ancora", hours_ago=1),
        entry("Docker su Raspberry", hours_ago=5),
        entry("Notizia di tre giorni fa sulla Luna", hours_ago=72),
    ], title="Bit")
    admin.post("/api/interests/keywords", json={"keyword": "razzo", "level": "alta"})
    admin.post("/api/interests/keywords", json={"keyword": "luna"})  # solo nella notizia vecchia
    admin.post("/api/interests/keywords", json={"keyword": "missione"})
    admin.post("/api/interests/keywords", json={"keyword": "telescopio"})
    admin.post("/api/interests/muted", json={"word": "oroscopo"})

    r = admin.get("/api/editions/latest").json()
    assert r["edition"] is None and r["schedule"]["enabled"] is False

    # Accesa dalle preferenze: lo scheduler compone subito la prima.
    me = admin.patch("/api/me", json={"prefs": {"edition": True, "edition_times": ["19:00", "07:30"]}}).json()
    assert me["user"]["prefs"]["edition_times"] == ["07:30", "19:00"]
    made = edition.run_due(app.state.ctx)
    assert len(made) == 1 and made[0][0] == user_id(admin)
    assert edition.run_due(app.state.ctx) == []  # già fatta per questo orario

    ed = admin.get("/api/editions/latest").json()["edition"]
    assert ed["number"] == 1
    # In primo piano la priorità alta; poi per cartella, «Senza cartella» in fondo.
    assert ed["hero"]["title"] == "Il razzo riutilizzabile vola ancora"
    assert [s["title"] for s in ed["sections"]] == ["Spazio"]
    assert [a["title"] for a in ed["sections"][0]["items"]] == ["Missione lunare al polo sud", "Nuovo telescopio spaziale"]
    assert ed["stats"] == {"sources": 2, "new": 4, "selected": 3, "hidden": 1}

    # «Componi adesso» subito dopo: troppo presto.
    r = admin.post("/api/editions")
    assert r.status_code == 429


def test_edition_filler_and_validation(admin, app):
    feed(app, admin, "https://a.example/feed", [entry("Prima", hours_ago=1), entry("Seconda", hours_ago=2)], title="A")
    feed(app, admin, "https://b.example/feed", [entry("Terza", hours_ago=1)], title="B")
    r = admin.post("/api/editions")
    assert r.status_code == 201
    ed = r.json()["edition"]
    # Nessun interesse: le ultime notizie, una per fonte.
    assert ed["hero"] is None
    assert ed["sections"][0]["title"] == "Dalle tue fonti"
    assert sorted(a["title"] for a in ed["sections"][0]["items"]) == ["Prima", "Terza"]
    assert admin.get(f"/api/editions/{ed['id']}").status_code == 200
    assert admin.get("/api/editions/999").status_code == 404

    bad = admin.patch("/api/me", json={"prefs": {"edition_times": ["25:00"]}})
    assert bad.status_code == 422 and "07:30" in bad.json()["detail"]
    assert admin.patch("/api/me", json={"prefs": {"edition_times": []}}).status_code == 422
