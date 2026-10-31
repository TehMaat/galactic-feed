from conftest import PASSWORD, invite_user, new_client


def _token(url: str) -> str:
    return url.rsplit("/", 1)[1]


def test_admin_creates_invite_link(admin):
    r = admin.post("/api/admin/invites", json={"note": "Per Bruno"})
    assert r.status_code == 200
    inv = r.json()["invite"]
    assert inv["url"].startswith("https://feed.example.org/invito/")
    assert inv["note"] == "Per Bruno"
    listed = admin.get("/api/admin/invites").json()["invites"]
    assert listed[0]["status"] == "valido"
    # Il token si vede solo alla creazione, mai nell'elenco.
    assert "url" not in listed[0]


def test_invite_can_be_described_and_accepted_once(admin, app):
    url = admin.post("/api/admin/invites", json={}).json()["invite"]["url"]
    guest = new_client(app)
    info = guest.get(f"/api/invites/{_token(url)}").json()
    assert info["kind"] == "invite" and info["invited_by"] == "anna"

    r = guest.post(f"/api/invites/{_token(url)}/accept", json={"username": "bruno", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["user"]["is_admin"] is False
    assert guest.get("/api/me").json()["user"]["username"] == "bruno"

    other = new_client(app)
    r = other.post(f"/api/invites/{_token(url)}/accept", json={"username": "carla", "password": PASSWORD})
    assert r.status_code == 404
    assert admin.get("/api/admin/invites").json()["invites"][0]["status"] == "usato"


def test_invite_rejects_taken_username(admin, app):
    url = admin.post("/api/admin/invites", json={}).json()["invite"]["url"]
    r = new_client(app).post(f"/api/invites/{_token(url)}/accept", json={"username": "Anna", "password": PASSWORD})
    assert r.status_code == 409
    # L'invito resta valido per riprovare con un altro nome.
    r = new_client(app).post(f"/api/invites/{_token(url)}/accept", json={"username": "bruno", "password": PASSWORD})
    assert r.status_code == 200


def test_invite_validation_message(admin, app):
    url = admin.post("/api/admin/invites", json={}).json()["invite"]["url"]
    r = new_client(app).post(f"/api/invites/{_token(url)}/accept", json={"username": "bruno", "password": "x"})
    assert r.status_code == 422
    assert "almeno 8" in r.json()["detail"]


def test_expired_invite(admin, app):
    url = admin.post("/api/admin/invites", json={}).json()["invite"]["url"]
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE invites SET expires_at = 1")
    r = new_client(app).get(f"/api/invites/{_token(url)}")
    assert r.status_code == 404
    assert "scaduto" in r.json()["detail"]


def test_revoked_invite(admin, app):
    inv = admin.post("/api/admin/invites", json={}).json()["invite"]
    assert admin.delete(f"/api/admin/invites/{inv['id']}").status_code == 200
    assert new_client(app).get(f"/api/invites/{_token(inv['url'])}").status_code == 404


def test_unknown_token(client):
    assert client.get("/api/invites/inventato").status_code == 404


def test_only_admin_can_invite(admin, app):
    bruno = invite_user(admin, app, "bruno")
    assert bruno.post("/api/admin/invites", json={}).status_code == 403


def test_password_reset_link(admin, app):
    bruno = invite_user(admin, app, "bruno")
    bruno_id = bruno.get("/api/me").json()["user"]["id"]
    inv = admin.post(f"/api/admin/users/{bruno_id}/reset").json()["invite"]
    assert "/reimposta/" in inv["url"]

    guest = new_client(app)
    info = guest.get(f"/api/invites/{_token(inv['url'])}").json()
    assert info["kind"] == "reset" and info["username"] == "bruno"
    r = guest.post(f"/api/invites/{_token(inv['url'])}/accept", json={"password": "nuova-password-1"})
    assert r.status_code == 200
    # La vecchia sessione di Bruno non vale più.
    assert bruno.get("/api/me").status_code == 401
    assert guest.get("/api/me").json()["user"]["username"] == "bruno"
    login = new_client(app).post("/api/auth/login", json={"username": "bruno", "password": "nuova-password-1"})
    assert login.status_code == 200


def test_new_reset_link_replaces_old(admin, app):
    invite_user(admin, app, "bruno")
    users = admin.get("/api/admin/users").json()["users"]
    bruno_id = next(u["id"] for u in users if u["username"] == "bruno")
    first = admin.post(f"/api/admin/users/{bruno_id}/reset").json()["invite"]["url"]
    admin.post(f"/api/admin/users/{bruno_id}/reset")
    assert new_client(app).get(f"/api/invites/{_token(first)}").status_code == 404
