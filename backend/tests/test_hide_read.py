"""Preferenza «Nascondi le notizie lette» (#95)."""

from __future__ import annotations

from helpers import entry, feed


def _titles(client, **params):
    r = client.get("/api/articles", params=params)
    assert r.status_code == 200, r.text
    return [a["title"] for a in r.json()["items"]]


def _setup(app, client):
    ids = feed(app, client, "https://letture.example/feed", [
        entry("Galassia nuova", hours_ago=1),
        entry("Cometa lontana", hours_ago=2),
        entry("Pianeta rosso", hours_ago=3),
    ], title="Letture")
    client.put(f"/api/articles/{ids[1]}/read")
    return ids


def test_preference_defaults_and_validation(admin):
    assert admin.get("/api/me").json()["user"]["prefs"]["hide_read"] is False
    assert admin.patch("/api/me", json={"prefs": {"hide_read": True}}).json()["user"]["prefs"]["hide_read"] is True
    assert admin.patch("/api/me", json={"prefs": {"hide_read": "forse"}}).status_code == 422
    assert "hide_read" in admin.get("/api/admin/defaults").json()["prefs"]


def test_notiziario_hides_read_articles(admin, app):
    ids = _setup(app, admin)
    assert _titles(admin) == ["Galassia nuova", "Cometa lontana", "Pianeta rosso"]
    admin.patch("/api/me", json={"prefs": {"hide_read": True}})
    assert _titles(admin) == ["Galassia nuova", "Pianeta rosso"]
    # Anche i contatori del Notiziario e dei preset.
    [tally] = admin.post("/api/articles/tally", json={"filters": [{"view": "tutti"}]}).json()["results"]
    assert tally == {"total": 2, "unread": 2}
    # Salvati e Cerca mostrano anche le lette.
    admin.put(f"/api/articles/{ids[1]}/saved")
    assert _titles(admin, view="salvati") == ["Cometa lontana"]
    assert _titles(admin, q="cometa") == ["Cometa lontana"]
    # Si torna a vedere tutto.
    admin.patch("/api/me", json={"prefs": {"hide_read": False}})
    assert "Cometa lontana" in _titles(admin)
