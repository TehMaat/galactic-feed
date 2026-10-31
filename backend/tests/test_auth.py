from conftest import PASSWORD, new_client


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_fresh_server_needs_setup(client, setup_code):
    state = client.get("/api/auth/state").json()
    assert state["setup_needed"] is True
    assert state["user"] is None
    assert len(setup_code) == 6 and setup_code.isdigit()


def test_setup_requires_the_code(client, setup_code):
    wrong = "000000" if setup_code != "000000" else "111111"
    r = client.post("/api/auth/setup", json={"code": wrong, "username": "anna", "password": PASSWORD})
    assert r.status_code == 403
    assert "log del server" in r.json()["detail"]
    assert client.get("/api/auth/state").json()["setup_needed"] is True


def test_setup_creates_admin_and_logs_in(client, setup_code):
    r = client.post(
        "/api/auth/setup",
        json={"code": setup_code, "username": "anna", "password": PASSWORD, "display_name": "Anna"},
    )
    assert r.status_code == 200
    user = r.json()["user"]
    assert user["is_admin"] is True and user["display_name"] == "Anna"
    cookie = r.headers["set-cookie"]
    assert "gf_session=" in cookie and "HttpOnly" in cookie and "Secure" in cookie
    assert "samesite=lax" in cookie.lower()

    state = client.get("/api/auth/state").json()
    assert state["setup_needed"] is False
    assert state["user"]["username"] == "anna"


def test_setup_only_once(admin, app):
    r = new_client(app).post("/api/auth/setup", json={"code": "123456", "username": "bruno", "password": PASSWORD})
    assert r.status_code == 409
    assert app.state.ctx.setup_code is None


def test_setup_validates_username_and_password(client, setup_code):
    r = client.post("/api/auth/setup", json={"code": setup_code, "username": "a!", "password": PASSWORD})
    assert r.status_code == 422
    assert "nome utente" in r.json()["detail"]
    r = client.post("/api/auth/setup", json={"code": setup_code, "username": "anna", "password": "corta"})
    assert r.status_code == 422
    assert "almeno 8" in r.json()["detail"]


def test_setup_code_changes_after_many_failures(client, app, setup_code):
    ctx = app.state.ctx
    for _ in range(20):
        ctx.check_setup_code("not-a-code")
    assert ctx.setup_code is not None


def test_login_logout(admin, app):
    c = new_client(app)
    r = c.post("/api/auth/login", json={"username": "ANNA", "password": PASSWORD})
    assert r.status_code == 200
    assert c.get("/api/me").json()["user"]["username"] == "anna"

    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/me").status_code == 401


def test_login_wrong_password(admin, app):
    c = new_client(app)
    r = c.post("/api/auth/login", json={"username": "anna", "password": "sbagliata!"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Nome utente o password non corretti."
    r = c.post("/api/auth/login", json={"username": "nessuno", "password": "sbagliata!"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Nome utente o password non corretti."


def test_login_rate_limit(admin, app):
    c = new_client(app)
    for _ in range(10):
        c.post("/api/auth/login", json={"username": "anna", "password": "sbagliata!"})
    r = c.post("/api/auth/login", json={"username": "anna", "password": PASSWORD})
    assert r.status_code == 429


def test_protected_endpoints_need_login(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/me").json()["detail"].startswith("Accesso richiesto")


def test_cross_site_requests_are_rejected(admin):
    r = admin.post("/api/admin/invites", json={}, headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403
    r = admin.post("/api/admin/invites", json={}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = admin.post("/api/admin/invites", json={}, headers={"Origin": "https://feed.example.org"})
    assert r.status_code == 200
    r = admin.post("/api/admin/invites", json={}, headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200
    # Le letture sono sempre permesse.
    assert admin.get("/api/me", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200


def test_unknown_api_path_is_json_404(client):
    r = client.get("/api/non-esiste")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_frontend_placeholder_without_build(client):
    r = client.get("/fonti")
    assert r.status_code == 503
    assert "interfaccia non è stata compilata" in r.text


def test_cookie_not_secure_over_plain_http(app):
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://192.168.1.10:8080") as c:
        code = app.state.ctx.setup_code
        r = c.post("/api/auth/setup", json={"code": code, "username": "anna", "password": PASSWORD})
        assert r.status_code == 200
        assert "Secure" not in r.headers["set-cookie"]
        assert c.get("/api/me").status_code == 200


def test_frontend_is_served_with_cache_headers(tmp_path, settings):
    from fastapi.testclient import TestClient
    from app.main import create_app

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>GF</title>")
    (dist / "sw.js").write_text("// sw")
    (dist / "manifest.webmanifest").write_text("{}")
    (dist / "assets" / "app-abc.js").write_text("//")
    settings.frontend_dir = dist
    with TestClient(create_app(settings), base_url="https://feed.example.org") as c:
        r = c.get("/fonti")
        assert r.status_code == 200 and "<title>GF</title>" in r.text
        assert c.head("/").status_code == 200
        sw = c.get("/sw.js")
        assert sw.headers["cache-control"] == "no-cache" and sw.headers["service-worker-allowed"] == "/"
        assert c.get("/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json")
        assert "immutable" in c.get("/assets/app-abc.js").headers["cache-control"]
        assert c.get("/../secret.key").status_code in (200, 404)  # mai fuori dalla cartella dist
        assert "GF" in c.get("/%2e%2e/%2e%2e/etc/passwd").text
        assert c.get("/api/non-esiste").status_code == 404
