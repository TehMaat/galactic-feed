from conftest import PASSWORD, invite_user, new_client


def _id(admin, username):
    return next(u["id"] for u in admin.get("/api/admin/users").json()["users"] if u["username"] == username)


def test_list_users(admin, app):
    invite_user(admin, app, "bruno")
    users = admin.get("/api/admin/users").json()["users"]
    assert [u["username"] for u in users] == ["anna", "bruno"]
    assert users[0]["is_admin"] and not users[1]["is_admin"]


def test_promote_and_disable(admin, app):
    bruno = invite_user(admin, app, "bruno")
    bid = _id(admin, "bruno")
    r = admin.patch(f"/api/admin/users/{bid}", json={"is_admin": True})
    assert r.json()["user"]["is_admin"] is True
    assert bruno.get("/api/admin/users").status_code == 200

    admin.patch(f"/api/admin/users/{bid}", json={"disabled": True})
    assert bruno.get("/api/me").status_code == 401
    r = new_client(app).post("/api/auth/login", json={"username": "bruno", "password": PASSWORD})
    assert r.status_code == 403
    assert "disattivato" in r.json()["detail"]


def test_admin_cannot_lock_themselves_out(admin):
    me = admin.get("/api/me").json()["user"]["id"]
    assert admin.patch(f"/api/admin/users/{me}", json={"is_admin": False}).status_code == 400
    assert admin.patch(f"/api/admin/users/{me}", json={"disabled": True}).status_code == 400
    assert admin.delete(f"/api/admin/users/{me}").status_code == 400


def test_delete_user(admin, app):
    bruno = invite_user(admin, app, "bruno")
    assert admin.delete(f"/api/admin/users/{_id(admin, 'bruno')}").status_code == 200
    assert bruno.get("/api/me").status_code == 401
    assert [u["username"] for u in admin.get("/api/admin/users").json()["users"]] == ["anna"]


def test_admin_status(admin):
    s = admin.get("/api/admin/status").json()
    assert s["users"] == 1 and s["database_bytes"] > 0


def test_update_profile_and_prefs(admin):
    r = admin.patch("/api/me", json={"display_name": "  Anna   Rossi ", "prefs": {"theme": "dark"}})
    user = r.json()["user"]
    assert user["display_name"] == "Anna Rossi"
    assert user["prefs"] == {"theme": "dark", "text_size": 1.0, "dedupe": True}
    r = admin.patch("/api/me", json={"prefs": {"text_size": 1.12}})
    assert r.json()["user"]["prefs"]["theme"] == "dark"
    assert r.json()["user"]["prefs"]["text_size"] == 1.12


def test_invalid_prefs(admin):
    r = admin.patch("/api/me", json={"prefs": {"theme": "viola"}})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_change_password_logs_out_other_devices(admin, app):
    phone = new_client(app)
    phone.post("/api/auth/login", json={"username": "anna", "password": PASSWORD})
    r = admin.post("/api/me/password", json={"current": "sbagliata!", "new": "nuova-password-1"})
    assert r.status_code == 403
    r = admin.post("/api/me/password", json={"current": PASSWORD, "new": "nuova-password-1"})
    assert r.status_code == 200
    assert admin.get("/api/me").status_code == 200
    assert phone.get("/api/me").status_code == 401


def test_sessions_list_and_end(admin, app):
    phone = new_client(app)
    phone.post("/api/auth/login", json={"username": "anna", "password": PASSWORD}, headers={"User-Agent": "iPhone"})
    sessions = admin.get("/api/me/sessions").json()["sessions"]
    assert len(sessions) == 2
    other = next(s for s in sessions if not s["current"])
    assert other["user_agent"] == "iPhone"
    assert admin.delete(f"/api/me/sessions/{other['id']}").status_code == 200
    assert phone.get("/api/me").status_code == 401


def test_users_cannot_end_others_sessions(admin, app):
    bruno = invite_user(admin, app, "bruno")
    anna_session = admin.get("/api/me/sessions").json()["sessions"][0]["id"]
    assert bruno.delete(f"/api/me/sessions/{anna_session}").status_code == 404
