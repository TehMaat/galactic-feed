"""«Ricordami» al login e durata delle sessioni scelta dall'amministratore (issue #12)."""

import time

from conftest import PASSWORD, invite_user, new_client


def _login(app, remember):
    c = new_client(app)
    r = c.post("/api/auth/login", json={"username": "anna", "password": PASSWORD, "remember": remember})
    assert r.status_code == 200, r.text
    return c, r.headers["set-cookie"]


def _session(app, client):
    sid = next(s["id"] for s in client.get("/api/me/sessions").json()["sessions"] if s["current"])
    with app.state.ctx.db.session() as conn:
        return conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()


def test_login_without_remember_uses_a_browser_session_cookie(admin, app):
    c, cookie = _login(app, remember=False)
    # Nessuna scadenza nel cookie: il browser lo cancella quando si chiude.
    assert "Max-Age" not in cookie and "expires" not in cookie.lower()
    row = _session(app, c)
    assert row["remember"] == 0
    # Lato server la sessione dura 12 ore senza utilizzo.
    assert abs(row["expires_at"] - (time.time() + 12 * 3600)) < 60
    assert c.get("/api/auth/state").headers.get("set-cookie") is None
    current = next(s for s in c.get("/api/me/sessions").json()["sessions"] if s["current"])
    assert current["remember"] is False and current["expires_at"]


def test_login_with_remember_lasts_90_days(admin, app):
    c, cookie = _login(app, remember=True)
    assert f"Max-Age={90 * 86400}" in cookie
    row = _session(app, c)
    assert row["remember"] == 1
    assert abs(row["expires_at"] - (time.time() + 90 * 86400)) < 60
    # A ogni apertura dell'app il cookie si rinnova.
    assert f"Max-Age={90 * 86400}" in c.get("/api/auth/state").headers["set-cookie"]


def test_remember_is_off_by_default(admin, app):
    c = new_client(app)
    r = c.post("/api/auth/login", json={"username": "anna", "password": PASSWORD})
    assert "Max-Age" not in r.headers["set-cookie"]


def test_idle_session_expires(admin, app):
    c, _ = _login(app, remember=False)
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE sessions SET expires_at = ? WHERE remember = 0", (int(time.time()) - 1,))
    assert c.get("/api/me").status_code == 401


def test_using_the_app_moves_the_expiry_forward(admin, app):
    c, _ = _login(app, remember=False)
    with app.state.ctx.db.session() as conn, conn:
        # Ultimo utilizzo 4 ore fa: la scadenza si sposta di nuovo a 12 ore da adesso.
        conn.execute(
            "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE remember = 0",
            (int(time.time()) - 4 * 3600, int(time.time()) + 8 * 3600),
        )
    assert c.get("/api/me").status_code == 200
    assert abs(_session(app, c)["expires_at"] - (time.time() + 12 * 3600)) < 60


def test_admin_chooses_the_durations(admin, app):
    s = admin.get("/api/admin/settings").json()["settings"]
    assert s["remember_days"]["value"] == 90 and s["remember_days"]["origin"] == "default"
    assert s["session_hours"]["value"] == 12
    r = admin.patch("/api/admin/settings", json={"remember_days": 30, "session_hours": 4})
    assert r.status_code == 200
    assert r.json()["settings"]["remember_days"] == {**s["remember_days"], "value": 30, "origin": "gui"}

    # Vale subito, per i nuovi accessi, senza riavviare.
    c, cookie = _login(app, remember=True)
    assert f"Max-Age={30 * 86400}" in cookie
    c, _ = _login(app, remember=False)
    assert abs(_session(app, c)["expires_at"] - (time.time() + 4 * 3600)) < 60

    # Solo i valori proposti; null torna al predefinito.
    assert admin.patch("/api/admin/settings", json={"remember_days": 5}).status_code == 422
    assert admin.patch("/api/admin/settings", json={"altro": 1}).status_code == 422
    r = admin.patch("/api/admin/settings", json={"remember_days": None})
    assert r.json()["settings"]["remember_days"]["value"] == 90


def test_only_admins_change_the_durations(admin, app):
    bruno = invite_user(admin, app, "bruno")
    assert bruno.get("/api/admin/settings").status_code == 403
    assert bruno.patch("/api/admin/settings", json={"remember_days": 365}).status_code == 403


def test_environment_variable_is_used_when_not_set_in_the_gui(tmp_path, settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings.remember_days = 7
    app = create_app(settings)
    with TestClient(app, base_url="https://feed.example.org") as c:
        code = app.state.ctx.setup_code
        c.post("/api/auth/setup", json={"code": code, "username": "anna", "password": PASSWORD})
        s = c.get("/api/admin/settings").json()["settings"]["remember_days"]
        assert s["value"] == 7 and s["origin"] == "env" and s["env_value"] == 7
        c.patch("/api/admin/settings", json={"remember_days": 180})
        assert c.get("/api/admin/settings").json()["settings"]["remember_days"]["origin"] == "gui"


def test_expired_sessions_are_cleaned_up(admin, app):
    from app.feeds.scheduler import cleanup

    c, _ = _login(app, remember=False)
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE sessions SET expires_at = 1 WHERE remember = 0")
    cleanup(app.state.ctx)
    with app.state.ctx.db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM sessions WHERE remember = 0").fetchone()[0] == 0
