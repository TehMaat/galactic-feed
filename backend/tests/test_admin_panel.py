"""Pannello di amministrazione: impostazioni dell'istanza da GUI (issue #21)."""

import calendar
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.feeds.scheduler import cleanup
from app.main import create_app
from conftest import PASSWORD, invite_user
from helpers import entry, feed
from samples import RSS_EXCERPT


@pytest.fixture
def web():
    with respx.mock(assert_all_called=False) as mock:
        yield mock


def _patch(client, **values):
    return client.patch("/api/admin/settings", json=values)


def _titles(client):
    return [a["title"] for a in client.get("/api/articles").json()["items"]]


def test_only_admins_see_the_panel(admin, app):
    bruno = invite_user(admin, app, "bruno")
    for path in ("/api/admin/settings", "/api/admin/defaults", "/api/admin/status", "/api/admin/ai", "/api/admin/users"):
        assert bruno.get(path).status_code == 403, path
    assert _patch(bruno, retention_days=30).status_code == 403
    assert bruno.put("/api/admin/defaults", json={"theme": "dark"}).status_code == 403


def test_settings_list_every_instance_option(admin):
    s = admin.get("/api/admin/settings").json()["settings"]
    assert set(s) == {
        "remember_days", "session_hours", "invite_hours", "retention_days",
        "default_interval", "block_private_networks", "timezone",
    }
    assert s["retention_days"] == {
        "value": 90, "origin": "default", "group": "sources", "kind": "int", "default": 90,
        "env": "RETENTION_DAYS", "env_value": None, "choices": [14, 30, 60, 90, 180, 365, 730], "unit": "giorni",
    }
    assert s["block_private_networks"]["value"] is False and s["timezone"]["value"] == "Europe/Rome"


def test_changes_are_validated_all_or_nothing(admin):
    r = _patch(admin, retention_days=30, timezone="Marte/Base")
    assert r.status_code == 422 and "Fuso orario" in r.json()["detail"]
    assert admin.get("/api/admin/settings").json()["settings"]["retention_days"]["value"] == 90
    assert _patch(admin, retention_days=45).status_code == 422
    assert _patch(admin, block_private_networks="sì").status_code == 422
    assert _patch(admin, altro=1).status_code == 422
    s = _patch(admin, retention_days=30, timezone="America/New_York", block_private_networks=True).json()["settings"]
    assert (s["retention_days"]["value"], s["timezone"]["value"], s["block_private_networks"]["value"]) == (30, "America/New_York", True)
    assert {s[k]["origin"] for k in ("retention_days", "timezone", "block_private_networks")} == {"gui"}
    # null torna al predefinito.
    assert _patch(admin, timezone=None).json()["settings"]["timezone"] == {**s["timezone"], "value": "Europe/Rome", "origin": "default"}


def test_retention_applies_without_restart(admin, app):
    feed(app, admin, "https://orbita.example/feed", [entry("Recente"), entry("Di 40 giorni fa", hours_ago=24 * 40)])
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE articles SET fetched_at = 1")
    cleanup(app.state.ctx)
    assert len(_titles(admin)) == 2  # 90 giorni: restano
    _patch(admin, retention_days=30)
    cleanup(app.state.ctx)
    assert _titles(admin) == ["Recente"]


def test_invite_duration(admin):
    _patch(admin, invite_hours=24)
    invite = admin.post("/api/admin/invites", json={}).json()["invite"]
    expires = calendar.timegm(time.strptime(invite["expires_at"], "%Y-%m-%dT%H:%M:%SZ"))
    assert abs(expires - (time.time() + 24 * 3600)) < 120


def test_default_interval_for_new_sources(admin, app, web):
    web.get("https://orbita.example/feed.xml").mock(
        return_value=httpx.Response(200, text=RSS_EXCERPT, headers={"content-type": "application/rss+xml"})
    )
    _patch(admin, default_interval=180)
    assert admin.get("/api/sources").json()["default_interval"] == 180
    source = admin.post("/api/sources", json={"url": "https://orbita.example/feed.xml"}).json()["source"]
    assert source["interval_min"] == 180


def test_private_networks_switch(admin, web):
    assert _patch(admin, block_private_networks=True).status_code == 200
    r = admin.post("/api/sources", json={"url": "http://192.168.1.20/feed.xml"})
    assert r.status_code == 422 and "rete locale" in r.json()["detail"]


def test_environment_value_is_shown_until_changed_in_the_panel(settings):
    settings.retention_days = 45
    settings.timezone = "Europe/London"
    app = create_app(settings)
    with TestClient(app, base_url="https://feed.example.org") as c:
        c.post("/api/auth/setup", json={"code": app.state.ctx.setup_code, "username": "anna", "password": PASSWORD})
        s = c.get("/api/admin/settings").json()["settings"]
        assert (s["retention_days"]["value"], s["retention_days"]["origin"]) == (45, "env")
        assert (s["timezone"]["value"], s["timezone"]["origin"]) == ("Europe/London", "env")
        _patch(c, retention_days=60)
        assert c.get("/api/admin/settings").json()["settings"]["retention_days"]["origin"] == "gui"


# ---------- Preferenze per i nuovi utenti ----------


def test_new_users_start_with_the_chosen_prefs(admin, app):
    before = admin.get("/api/me").json()["user"]["prefs"]
    r = admin.put("/api/admin/defaults", json={"theme": "dark", "accent": "viola", "font": "leggibile",
                                               "edition": True, "edition_times": ["08:00", "19:30"]})
    assert r.status_code == 200, r.text
    assert r.json()["chosen"] == ["accent", "edition", "edition_times", "font", "theme"]
    assert r.json()["prefs"]["accent"] == "viola" and r.json()["prefs"]["font_read"] == "serif"

    bruno = invite_user(admin, app, "bruno")
    prefs = bruno.get("/api/me").json()["user"]["prefs"]
    assert (prefs["theme"], prefs["accent"], prefs["font"], prefs["edition"]) == ("dark", "viola", "leggibile", True)
    assert prefs["edition_times"] == ["08:00", "19:30"]
    # Chi c'era già non cambia, e ognuno può poi scegliere per sé.
    assert admin.get("/api/me").json()["user"]["prefs"] == before
    assert bruno.patch("/api/me", json={"prefs": {"accent": "blu"}}).json()["user"]["prefs"]["accent"] == "blu"


def test_defaults_are_validated(admin):
    assert admin.put("/api/admin/defaults", json={"accent": "fucsia"}).status_code == 422
    assert admin.put("/api/admin/defaults", json={"ai_text": "segreto"}).status_code == 422
    assert admin.put("/api/admin/defaults", json={"edition_times": []}).status_code == 422
    # Un oggetto vuoto torna ai valori predefiniti dell'app.
    assert admin.put("/api/admin/defaults", json={}).json() == {"prefs": admin.get("/api/admin/defaults").json()["prefs"], "chosen": []}


# ---------- Stato del sistema ----------


def test_system_status(admin, app):
    feed(app, admin, "https://orbita.example/feed", [entry("Uno")], title="Orbita")
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE feeds SET error_message = 'Il sito non risponde.', error_since = 1, last_fetch_at = 2")
    s = admin.get("/api/admin/status").json()
    assert s["version"] and s["users"] == 1 and s["feeds"] == 1 and s["articles"] == 1 and s["database_bytes"] > 0
    assert s["feeds_with_errors"] == 1 and s["recent_errors"][0]["error"] == "Il sito non risponde."
    assert s["recent_errors"][0]["followers"] == 1
    assert set(s["environment"]) == {"PUBLIC_URL", "DATA_DIR", "LOG_LEVEL", "FORWARDED_ALLOW_IPS"}
    assert s["environment"]["PUBLIC_URL"] == "https://feed.example.org"
    assert s["timezone"] == "Europe/Rome" and s["retention_days"] == 90


# ---------- Chiave dell'AI cifrata ----------


def _stored_key(app):
    with app.state.ctx.db.session() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'ai.api_key'").fetchone()
    return row["value"] if row else None


def test_ai_key_is_encrypted_in_the_database(admin, app):
    r = admin.put("/api/admin/ai", json={"provider": "anthropic", "model": "claude-haiku-5-5", "api_key": "sk-segretissima"})
    assert r.json()["has_key"] is True and "sk-segretissima" not in r.text
    stored = _stored_key(app)
    assert stored.startswith("enc1:") and "sk-segretissima" not in stored
    assert "sk-segretissima" not in admin.get("/api/admin/ai").text
    from app.ai import config

    with app.state.ctx.db.session() as conn:
        assert config.load(conn, app.state.ctx.secret).api_key == "sk-segretissima"


def test_plaintext_key_from_older_versions_is_encrypted_at_startup(settings):
    app = create_app(settings)
    with TestClient(app, base_url="https://feed.example.org"):
        with app.state.ctx.db.session() as conn, conn:
            conn.execute("INSERT INTO app_settings (key, value) VALUES ('ai.api_key', 'sk-vecchia-in-chiaro')")
    app = create_app(settings)
    with TestClient(app, base_url="https://feed.example.org"):
        stored = _stored_key(app)
        assert stored.startswith("enc1:") and "sk-vecchia" not in stored
        from app.ai import config

        with app.state.ctx.db.session() as conn:
            assert config.load(conn, app.state.ctx.secret).api_key == "sk-vecchia-in-chiaro"
