"""Nuovo aspetto: filtri del Notiziario (#66 #68 #69), avatar (#76), statistiche (#78), Edizioni in Oggi (#64)."""

import base64

from helpers import entry, feed, source_id

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * 64).decode()


def _setup(app, client):
    space = feed(app, client, "https://cielo.example/feed", [
        entry("La sonda arriva su Teti", hours_ago=1),
        entry("Pioggia di meteore stanotte", hours_ago=2),
        entry("Lancio notturno dal molo", hours_ago=3, video_id="abc123"),
    ], title="Cronache di Orione")
    motors = feed(app, client, "https://box.example/feed", [
        entry("Gran Premio sotto la pioggia", hours_ago=1),
        entry("Il circuito apre ai test", hours_ago=4),
    ], title="Bollettino di Vesta")
    sky, box = source_id(client, "Cronache di Orione"), source_id(client, "Bollettino di Vesta")
    tag = client.put(f"/api/sources/{sky}/tags", json={"tags": ["Spazio"]}).json()["source"]["tags"][0]["id"]
    client.put(f"/api/sources/{box}/tags", json={"tags": ["Motori"]})
    motors_tag = next(t["id"] for t in client.get("/api/tags").json()["tags"] if t["name"] == "Motori")
    return space, motors, tag, motors_tag, sky, box


def _titles(client, **params):
    return sorted(a["title"] for a in client.get("/api/articles", params=params).json()["items"])


def test_include_and_exclude_filters(admin, app):
    space, motors, spazio, motori, sky, box = _setup(app, admin)
    assert _titles(admin, inc=f"t:{spazio}") == ["La sonda arriva su Teti", "Lancio notturno dal molo", "Pioggia di meteore stanotte"]
    assert _titles(admin, exc=f"t:{spazio}") == ["Gran Premio sotto la pioggia", "Il circuito apre ai test"]
    # Due interessi inclusi: basta uno. Un'esclusione toglie sempre.
    assert len(_titles(admin, inc=f"t:{spazio},t:{motori}")) == 5
    assert _titles(admin, inc=f"t:{spazio}", exc="v") == ["La sonda arriva su Teti", "Pioggia di meteore stanotte"]
    # Tipi diversi devono valere tutti: interesse Spazio e fonte del Bollettino non hanno niente in comune.
    assert _titles(admin, inc=f"t:{spazio},s:{box}") == []
    admin.put(f"/api/articles/{space[0]}/read")
    assert _titles(admin, inc=f"s:{sky}", unread="true") == ["Lancio notturno dal molo", "Pioggia di meteore stanotte"]
    assert admin.get("/api/articles", params={"inc": "x:1"}).status_code == 422


def test_tally_counts_total_and_unread(admin, app):
    space, motors, spazio, motori, sky, box = _setup(app, admin)
    admin.put(f"/api/articles/{motors[0]}/read")
    r = admin.post("/api/articles/tally", json={"filters": [
        {"view": "tutti"}, {"view": "tutti", "unread": True}, {"view": "tutti", "exc": [f"t:{motori}"]}, {"view": "tutti", "inc": ["v"]},
    ]})
    assert r.status_code == 200, r.text
    assert r.json()["results"] == [
        {"total": 5, "unread": 4}, {"total": 4, "unread": 4}, {"total": 3, "unread": 3}, {"total": 1, "unread": 1},
    ]


def test_mark_read_follows_the_filter(admin, app):
    space, motors, spazio, motori, sky, box = _setup(app, admin)
    r = admin.post("/api/articles/mark-read", json={"exc": [f"t:{spazio}"]})
    assert r.json()["marked"] == 2
    assert admin.post("/api/articles/tally", json={"filters": [{"view": "tutti"}]}).json()["results"] == [{"total": 5, "unread": 3}]


def test_presets_and_start_preset_in_prefs(admin):
    preset = {"id": "mattina", "name": "Mattina", "filter": {"scope": "perte", "unread": True, "inc": ["t:3", "c:it"], "exc": ["v"]}}
    r = admin.patch("/api/me", json={"prefs": {"presets": [preset], "start_preset": "mattina", "last_filter": preset["filter"]}})
    assert r.status_code == 200, r.text
    prefs = r.json()["user"]["prefs"]
    assert prefs["presets"][0]["filter"]["inc"] == ["t:3", "c:IT"]
    assert prefs["start_preset"] == "mattina" and prefs["last_filter"]["exc"] == ["v"]
    # Tolto il preset, all'apertura si torna a «Per te».
    prefs = admin.patch("/api/me", json={"prefs": {"presets": []}}).json()["user"]["prefs"]
    assert prefs["start_preset"] == "perte"
    bad = admin.patch("/api/me", json={"prefs": {"presets": [{"id": "perte", "name": "Doppio"}]}})
    assert bad.status_code == 422
    assert admin.patch("/api/me", json={"prefs": {"presets": [{"id": "x", "name": "X", "filter": {"inc": ["boh"]}}]}}).status_code == 422


def test_look_prefs(admin):
    prefs = admin.patch("/api/me", json={"prefs": {
        "dark_style": "solarized", "light_style": "solarized", "accent": "custom", "accent_custom": "#ff7a59", "font": "classico",
    }}).json()["user"]["prefs"]
    assert (prefs["dark_style"], prefs["light_style"], prefs["accent"], prefs["accent_custom"], prefs["font"]) == (
        "solarized", "solarized", "custom", "#FF7A59", "classico",
    )
    assert admin.patch("/api/me", json={"prefs": {"accent_custom": "rosso"}}).status_code == 422


def test_name_and_avatar(admin, app):
    user = admin.patch("/api/me", json={"display_name": "Mara Vento", "avatar_color": 3}).json()["user"]
    assert user["display_name"] == "Mara Vento" and user["avatar_color"] == 3 and user["avatar"] is None
    assert admin.put("/api/me/avatar", json={"data": base64.b64encode(b"non sono una foto").decode()}).status_code == 422
    user = admin.put("/api/me/avatar", json={"data": "data:image/png;base64," + PNG}).json()["user"]
    assert user["avatar"].startswith(f"/api/avatars/{user['id']}?v=")
    r = admin.get(user["avatar"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert admin.delete("/api/me/avatar").json()["user"]["avatar"] is None
    assert admin.get(f"/api/avatars/{user['id']}").status_code == 404


def test_stats_count_opened_articles(admin, app):
    space, motors, spazio, motori, sky, box = _setup(app, admin)
    for article in (space[0], space[1], motors[0]):
        admin.put(f"/api/articles/{article}/read")
    admin.put(f"/api/articles/{space[0]}/read")  # di nuovo: conta una volta sola
    admin.post("/api/articles/mark-read", json={})  # «Segna tutti come letti» non conta
    admin.put(f"/api/articles/{space[1]}/saved")
    s = admin.get("/api/me/stats", params={"days": 7}).json()
    assert s["days"] == 7 and s["read"] == 3 and s["saved"] == 1
    assert s["streak"] == 1 and s["best_streak"] == 1
    assert len(s["per_day"]) == 7 and s["per_day"][-1]["n"] == 3 and sum(s["hours"]) == 3
    assert s["interests"][0] == {"name": "Spazio", "n": 2, "share": 67}
    assert [x["title"] for x in s["sources"]] == ["Cronache di Orione", "Bollettino di Vesta"]
    assert len(admin.get("/api/me/stats", params={"days": 30}).json()["per_day"]) == 30


def test_editions_for_today(admin, app):
    _setup(app, admin)
    assert admin.get("/api/editions/today").json()["editions"] == []
    configs = admin.post("/api/edition-configs", json={"name": "Buongiorno", "rules": {"tags": []}}).json()["configs"]
    config = next(c for c in configs if c["name"] == "Buongiorno")
    issue = admin.post("/api/editions", json={"config_id": config["id"]}).json()["edition"]
    eds = admin.get("/api/editions/today").json()["editions"]
    assert [e["name"] for e in eds] == ["Buongiorno"]
    n = (1 if issue["hero"] else 0) + sum(len(sec["items"]) for sec in issue["sections"])
    assert n and eds[0]["count"] == n and eds[0]["unread"] == n and eds[0]["lead"]["title"]
    # Aprire l'uscita conta nelle statistiche.
    admin.get(f"/api/editions/{issue['id']}")
    assert admin.get("/api/me/stats").json()["editions"] == {"issued": 1, "opened": 1}
