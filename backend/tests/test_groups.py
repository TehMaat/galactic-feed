"""Gruppi di parole pronti e personali, come interessi o come silenziatori (issue #16)."""

from conftest import invite_user
from helpers import entry, feed


def _titles(client, **params):
    return [a["title"] for a in client.get("/api/articles", params=params).json()["items"]]


def _setup(app, client):
    feed(app, client, "https://news.example/feed", [
        entry("Ferrari vince il Gran Premio di Monza", hours_ago=1),
        entry("Il governo approva la legge di bilancio", hours_ago=2),
        entry("Nuovo smartphone con chip più veloce", hours_ago=3),
        entry("Ricetta della carbonara", hours_ago=4),
    ], title="Notizie")


def _preset(client, name):
    return next(p for p in client.get("/api/interests").json()["presets"] if p["name"] == name)


def test_ready_groups_are_offered(admin):
    data = admin.get("/api/interests").json()
    names = [p["name"] for p in data["presets"]]
    assert {"Motori", "Politica", "Economia", "Tecnologia", "Videogiochi", "Sport", "Calcio", "Scienza", "Salute", "Spettacolo"} <= set(names)
    assert "auto" in _preset(admin, "Motori")["words"]
    assert data["groups"] == []


def test_activate_a_ready_group_as_interest_with_one_tap(admin, app):
    _setup(app, admin)
    motori = _preset(admin, "Motori")
    r = admin.post("/api/groups", json={"preset_id": motori["id"], "mode": "interest"})
    assert r.status_code == 201, r.text
    group = r.json()["groups"][0]
    assert group["name"] == "Motori" and group["mode"] == "interest" and "Ferrari" in group["words"]
    # Il gruppo preso non è più tra quelli pronti da prendere.
    assert "Motori" not in [p["name"] for p in r.json()["presets"]]
    items = admin.get("/api/articles", params={"view": "perte"}).json()["items"]
    assert [a["title"] for a in items] == ["Ferrari vince il Gran Premio di Monza"]
    # La corrispondenza mostra il gruppo oltre alla parola trovata.
    assert items[0]["match"]["group"] == "Motori" and items[0]["match"]["keyword"] in ("Ferrari", "Gran Premio")
    assert admin.get("/api/articles/counts").json()["perte"] == 1
    assert admin.post("/api/groups", json={"preset_id": motori["id"]}).status_code == 409


def test_group_as_mute_hides_articles(admin, app):
    _setup(app, admin)
    politica = _preset(admin, "Politica")
    admin.post("/api/groups", json={"preset_id": politica["id"], "mode": "mute"})
    assert "Il governo approva la legge di bilancio" not in _titles(admin)
    assert admin.get("/api/articles", params={"show_muted": True}).json()["items"][1]["muted"] is True
    assert admin.get("/api/articles/counts").json()["hidden"] == 1


def test_edit_words_mode_and_level(admin, app):
    _setup(app, admin)
    r = admin.post("/api/groups", json={"preset_id": _preset(admin, "Tecnologia")["id"]})
    gid = r.json()["groups"][0]["id"]
    assert _titles(admin, view="perte") == []  # spento
    r = admin.patch(f"/api/groups/{gid}", json={"mode": "interest", "level": "alta", "words": ["carbonara"]})
    assert r.json()["groups"][0]["words"] == ["carbonara"]
    items = admin.get("/api/articles", params={"view": "perte"}).json()["items"]
    assert [(a["title"], a["match"]["level"]) for a in items] == [("Ricetta della carbonara", "alta")]
    admin.patch(f"/api/groups/{gid}", json={"mode": "off"})
    assert _titles(admin, view="perte") == []
    # Eliminato, il gruppo pronto torna disponibile.
    r = admin.delete(f"/api/groups/{gid}")
    assert r.json()["groups"] == [] and "Tecnologia" in [p["name"] for p in r.json()["presets"]]


def test_personal_groups(admin, app):
    _setup(app, admin)
    r = admin.post("/api/groups", json={"name": "Cucina", "words": ["carbonara", "ricetta", "Carbonara", " "], "mode": "interest"})
    assert r.json()["groups"][0]["words"] == ["carbonara", "ricetta"]
    assert _titles(admin, view="perte") == ["Ricetta della carbonara"]
    assert admin.post("/api/groups", json={"name": "cucina", "words": []}).status_code == 409
    assert admin.post("/api/groups", json={"words": ["x"]}).status_code == 422
    # Ogni utente ha i propri gruppi.
    bruno = invite_user(admin, app, "bruno")
    assert bruno.get("/api/interests").json()["groups"] == []
    gid = r.json()["groups"][0]["id"]
    assert bruno.patch(f"/api/groups/{gid}", json={"mode": "off"}).status_code == 404


def test_admin_manages_ready_groups(admin, app):
    bruno = invite_user(admin, app, "bruno")
    assert bruno.get("/api/admin/presets").status_code == 403
    presets = admin.get("/api/admin/presets").json()["presets"]
    motori = next(p for p in presets if p["name"] == "Motori")
    assert motori["builtin"] is True and motori["hidden"] is False
    # Nascosto: non è più proposto agli utenti.
    admin.patch(f"/api/admin/presets/{motori['id']}", json={"hidden": True})
    assert "Motori" not in [p["name"] for p in bruno.get("/api/interests").json()["presets"]]
    # Un gruppo pronto nuovo, poi modificato.
    r = admin.post("/api/admin/presets", json={"name": "Montagna", "words": ["Dolomiti", "rifugio"]})
    new = next(p for p in r.json()["presets"] if p["name"] == "Montagna")
    admin.patch(f"/api/admin/presets/{new['id']}", json={"words": ["Dolomiti", "rifugio", "ferrata"]})
    offered = next(p for p in bruno.get("/api/interests").json()["presets"] if p["name"] == "Montagna")
    assert offered["words"] == ["Dolomiti", "rifugio", "ferrata"]
    # Quelli forniti con l'app si nascondono soltanto; gli altri si cancellano.
    r = admin.delete(f"/api/admin/presets/{motori['id']}").json()["presets"]
    assert any(p["name"] == "Motori" and p["hidden"] for p in r)
    r = admin.delete(f"/api/admin/presets/{new['id']}").json()["presets"]
    assert "Montagna" not in [p["name"] for p in r]


def test_seed_keeps_admin_changes(admin, app):
    from app.reading.presets import seed

    motori = next(p for p in admin.get("/api/admin/presets").json()["presets"] if p["name"] == "Motori")
    admin.patch(f"/api/admin/presets/{motori['id']}", json={"words": ["auto"]})
    with app.state.ctx.db.session() as conn:
        assert seed(conn) == 0
    again = next(p for p in admin.get("/api/admin/presets").json()["presets"] if p["name"] == "Motori")
    assert again["words"] == ["auto"]
