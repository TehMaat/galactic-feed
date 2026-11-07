"""Accesso con un provider OpenID Connect (issue #22), con un provider finto."""

import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa

from app import oidc
from conftest import PASSWORD, invite_user, new_client

ISSUER = "https://auth.example.org/application/o/galactic/"
CLIENT_ID = "galactic-feed"
SECRET = "segreto-del-client"


class Provider:
    """Un provider OIDC finto: discovery, chiavi, token (con controllo del PKCE), userinfo."""

    def __init__(self, web, algs=("RS256",)):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        self.jwk.update(kid="k1", use="sig", alg="RS256")
        self.claims: dict = {}
        self.overrides: dict = {}
        self.challenge = None
        self.sign_key = self.key
        self.alg = "RS256"
        base = ISSUER.rstrip("/")
        web.get(base + "/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={
            "issuer": ISSUER,
            "authorization_endpoint": "https://auth.example.org/authorize",
            "token_endpoint": "https://auth.example.org/token",
            "userinfo_endpoint": "https://auth.example.org/userinfo",
            "jwks_uri": "https://auth.example.org/jwks",
            "end_session_endpoint": "https://auth.example.org/logout",
            "id_token_signing_alg_values_supported": list(algs),
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
        }))
        web.get("https://auth.example.org/jwks").mock(side_effect=lambda r: httpx.Response(200, json={"keys": [self.jwk]}))
        web.post("https://auth.example.org/token").mock(side_effect=self._token)
        web.get("https://auth.example.org/userinfo").mock(side_effect=lambda r: httpx.Response(200, json={"sub": self.claims.get("sub")}))

    def _token(self, request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        expected = base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"][0].encode()).digest()).decode().rstrip("=")
        assert expected == self.challenge, "PKCE non valido"
        assert request.headers["authorization"].startswith("Basic ")
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": CLIENT_ID, "iat": now, "exp": now + 300, "nonce": self.nonce, **self.claims, **self.overrides}
        headers = {"kid": "k1"} if self.alg.startswith("RS") else {}
        token = jwt.encode(claims, self.sign_key, algorithm=self.alg, headers=headers)
        return httpx.Response(200, json={"id_token": token, "access_token": "at", "token_type": "Bearer"})

    def login(self, client, remember=False, link=False):
        """Fa tutto il giro: start → provider → callback. Restituisce la risposta finale."""
        r = client.get("/api/auth/oidc/start", params={"remember": int(remember), "link": int(link)}, follow_redirects=False)
        assert r.status_code == 303, r.text
        params = parse_qs(urlsplit(r.headers["location"]).query)
        if "oidc_error" in params:
            return r
        assert params["code_challenge_method"] == ["S256"] and params["client_id"] == [CLIENT_ID]
        assert params["redirect_uri"] == ["https://feed.example.org/api/auth/oidc/callback"]
        self.challenge, self.nonce = params["code_challenge"][0], params["nonce"][0]
        return client.get("/api/auth/oidc/callback", params={"code": "abc", "state": params["state"][0]}, follow_redirects=False)


def _error(r) -> str | None:
    return parse_qs(urlsplit(r.headers["location"]).query).get("oidc_error", [None])[0]


@pytest.fixture
def web():
    oidc.forget_cache()
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def provider(web):
    return Provider(web)


def _configure(admin, **extra):
    body = {"enabled": True, "issuer": ISSUER, "client_id": CLIENT_ID, "client_secret": SECRET, "label": "Entra con Authentik", **extra}
    r = admin.put("/api/admin/oidc", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Configurazione ----------


def test_not_configured(client, admin):
    assert client.get("/api/auth/oidc/start", follow_redirects=False).status_code == 404
    assert admin.get("/api/auth/state").json()["oidc"] == {"enabled": False, "label": "Entra con il tuo account", "password_login": True}


def test_configuration_from_the_panel(admin, app, provider):
    cfg = _configure(admin)
    assert cfg["redirect_uri"] == "https://feed.example.org/api/auth/oidc/callback"
    assert cfg["has_secret"] is True and "client_secret" not in cfg and SECRET not in json.dumps(cfg)
    assert cfg["scopes"] == "openid profile email" and cfg["ready"] is True
    with app.state.ctx.db.session() as conn:
        stored = conn.execute("SELECT value FROM app_settings WHERE key = 'oidc.client_secret'").fetchone()["value"]
    assert stored.startswith("enc1:") and SECRET not in stored
    # Senza client_secret resta quello salvato.
    assert admin.put("/api/admin/oidc", json={"label": "Authentik"}).json()["has_secret"] is True
    r = admin.post("/api/admin/oidc/test")
    assert r.status_code == 200 and r.json()["keys"] == 1 and r.json()["end_session"] is True
    assert admin.get("/api/auth/state").json()["oidc"] == {"enabled": True, "label": "Authentik", "password_login": True}
    assert admin.put("/api/admin/oidc", json={"issuer": "auth.example.org"}).status_code == 422
    bruno = invite_user(admin, app, "bruno")
    assert bruno.get("/api/admin/oidc").status_code == 403


def test_wrong_issuer_is_reported(admin, web):
    web.get("https://altro.example/.well-known/openid-configuration").mock(return_value=httpx.Response(200, json={
        "issuer": "https://diverso.example", "authorization_endpoint": "a", "token_endpoint": "t", "jwks_uri": "j"}))
    _configure(admin, issuer="https://altro.example")
    r = admin.post("/api/admin/oidc/test")
    assert r.status_code == 502 and "non coincide" in r.json()["detail"]


# ---------- Accesso ----------


def test_new_user_is_created_when_allowed(admin, app, provider):
    _configure(admin, auto_create=True)
    provider.claims = {"sub": "u-1", "preferred_username": "carla", "name": "Carla Rossi", "email": "Carla@Example.org", "email_verified": True}
    c = new_client(app)
    r = provider.login(c, remember=True)
    assert r.headers["location"] == "/" and _error(r) is None
    assert f"Max-Age={90 * 86400}" in r.headers["set-cookie"]
    me = c.get("/api/me").json()["user"]
    assert (me["username"], me["display_name"], me["is_admin"]) == ("carla", "Carla Rossi", False)
    with app.state.ctx.db.session() as conn:
        row = conn.execute("SELECT u.email, s.via FROM users u JOIN sessions s ON s.user_id = u.id WHERE u.username = 'carla'").fetchone()
    assert (row["email"], row["via"]) == ("carla@example.org", "oidc")
    # Di nuovo: stesso utente, nessun doppione.
    assert provider.login(new_client(app)).headers["location"] == "/"
    assert [u["username"] for u in admin.get("/api/admin/users").json()["users"]] == ["anna", "carla"]


def test_without_auto_create_an_invite_is_needed(admin, app, provider):
    _configure(admin)
    provider.claims = {"sub": "u-2", "preferred_username": "dario"}
    assert "non è collegato" in _error(provider.login(new_client(app)))


def test_existing_user_linked_by_username_or_verified_email(admin, app, provider):
    bruno = invite_user(admin, app, "bruno")
    _configure(admin, link_username=True)
    provider.claims = {"sub": "u-3", "preferred_username": "bruno"}
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me").json()["user"]["username"] == "bruno"
    assert len(bruno.get("/api/me/identities").json()["identities"]) == 1

    invite_user(admin, app, "elena")
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE users SET email = 'elena@example.org' WHERE username = 'elena'")
    _configure(admin, link_username=False)
    provider.claims = {"sub": "u-4", "email": "elena@example.org", "email_verified": False}
    assert "non è collegato" in _error(provider.login(new_client(app)))  # email non verificata
    provider.claims = {"sub": "u-4", "email": "ELENA@example.org", "email_verified": True}
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me").json()["user"]["username"] == "elena"


def test_disabled_users_are_refused(admin, app, provider):
    invite_user(admin, app, "bruno")
    _configure(admin, link_username=True)
    bid = next(u["id"] for u in admin.get("/api/admin/users").json()["users"] if u["username"] == "bruno")
    admin.patch(f"/api/admin/users/{bid}", json={"disabled": True})
    provider.claims = {"sub": "u-5", "preferred_username": "bruno"}
    assert "disattivato" in _error(provider.login(new_client(app)))


def test_admins_from_a_provider_group(admin, app, provider):
    _configure(admin, auto_create=True, admin_claim="groups", admin_value="galactic-admin")
    provider.claims = {"sub": "u-6", "preferred_username": "fabio", "groups": ["utenti", "galactic-admin"]}
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me").json()["user"]["is_admin"] is True
    provider.claims = {"sub": "u-6", "preferred_username": "fabio", "groups": ["utenti"]}
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me").json()["user"]["is_admin"] is False
    # L'ultimo amministratore non perde mai i permessi.
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE users SET is_admin = 0 WHERE username = 'anna'")
        conn.execute("UPDATE users SET is_admin = 1 WHERE username = 'fabio'")
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me").json()["user"]["is_admin"] is True


def test_manual_admin_is_kept_by_the_provider_group(admin, app, provider):
    """L'utente del provider reso amministratore a mano resta tale anche se non è nel gruppo."""
    _configure(admin, auto_create=True, admin_claim="groups", admin_value="galactic-admin")
    provider.claims = {"sub": "u-60", "preferred_username": "marco", "groups": ["utenti"]}
    c = new_client(app)
    provider.login(c)
    users = admin.get("/api/admin/users").json()["users"]
    marco = next(u for u in users if u["username"] == "marco")
    assert (marco["is_admin"], marco["has_password"], marco["linked_identities"]) == (False, False, 1)
    anna = next(u for u in users if u["username"] == "anna")
    assert (anna["has_password"], anna["linked_identities"]) == (True, 0)
    admin.patch(f"/api/admin/users/{marco['id']}", json={"is_admin": True})
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me").json()["user"]["is_admin"] is True


def test_local_admin_is_never_linked_automatically(admin, app, provider):
    """Stesso nome utente o stessa email dell'amministratore locale: si crea un utente a parte."""
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE users SET email = 'anna@example.org' WHERE username = 'anna'")
    _configure(admin, auto_create=True, link_username=True, link_email=True)
    provider.claims = {"sub": "u-61", "preferred_username": "anna", "email": "anna@example.org", "email_verified": True}
    c = new_client(app)
    provider.login(c)
    me = c.get("/api/me").json()["user"]
    assert me["username"] == "anna2" and me["is_admin"] is False
    assert admin.get("/api/me/identities").json()["identities"] == []
    # La password dell'amministratore locale funziona sempre.
    assert new_client(app).post("/api/auth/login", json={"username": "anna", "password": PASSWORD}).status_code == 200


# ---------- Sicurezza ----------


def test_state_must_match_and_is_used_once(admin, app, provider):
    _configure(admin, auto_create=True)
    provider.claims = {"sub": "u-7", "preferred_username": "gina"}
    c = new_client(app)
    r = c.get("/api/auth/oidc/start", follow_redirects=False)
    params = parse_qs(urlsplit(r.headers["location"]).query)
    provider.challenge, provider.nonce = params["code_challenge"][0], params["nonce"][0]
    state = params["state"][0]
    # Un altro browser (senza il cookie) non può usare lo state.
    assert "non valido" in _error(new_client(app).get("/api/auth/oidc/callback", params={"code": "x", "state": state}, follow_redirects=False))
    ok = c.get("/api/auth/oidc/callback", params={"code": "x", "state": state}, follow_redirects=False)
    assert _error(ok) is None
    c.cookies.set("gf_oidc", state, domain="feed.example.org", path="/api/auth/oidc")
    assert "non valido" in _error(c.get("/api/auth/oidc/callback", params={"code": "x", "state": state}, follow_redirects=False))
    r = c.get("/api/auth/oidc/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert "non ha concesso" in _error(r)


@pytest.mark.parametrize("override, message", [
    ({"nonce": "un-altro"}, "nonce"),
    ({"aud": "altra-app"}, "non è valido"),
    ({"iss": "https://falso.example/"}, "non è valido"),
    ({"exp": int(time.time()) - 3600}, "scaduto"),
])
def test_id_token_is_checked(admin, app, provider, override, message):
    _configure(admin, auto_create=True)
    provider.claims = {"sub": "u-8", "preferred_username": "ivo"}
    provider.overrides = override
    assert message in _error(provider.login(new_client(app)))


def test_signature_must_come_from_the_provider(admin, app, provider):
    _configure(admin, auto_create=True)
    provider.claims = {"sub": "u-9", "preferred_username": "lia"}
    provider.sign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert "non è valido" in _error(provider.login(new_client(app)))


def test_unsigned_tokens_are_refused(admin, app, web):
    p = Provider(web, algs=("RS256", "none"))
    _configure(admin, auto_create=True)
    p.claims = {"sub": "u-10", "preferred_username": "mia"}
    p.alg, p.sign_key = "none", None
    assert "Algoritmo" in _error(p.login(new_client(app)))


def test_hs256_with_the_client_secret(admin, app, web):
    p = Provider(web, algs=("HS256",))
    _configure(admin, auto_create=True)
    p.claims = {"sub": "u-11", "preferred_username": "nino"}
    p.alg, p.sign_key = "HS256", SECRET
    c = new_client(app)
    assert _error(p.login(c)) is None and c.get("/api/me").json()["user"]["username"] == "nino"


# ---------- Account collegati, login con password, emergenza, uscita ----------


def test_link_from_settings_and_unlink(admin, app, provider):
    _configure(admin)
    provider.claims = {"sub": "admin-sub", "preferred_username": "anna-sso", "email": "anna@example.org", "email_verified": True}
    r = provider.login(admin, link=True)
    assert r.headers["location"] == "/?oidc_linked=1"
    ids = admin.get("/api/me/identities").json()
    assert ids["has_password"] is True and ids["identities"][0]["email"] == "anna@example.org"
    # Ora anna entra anche con il provider.
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me").json()["user"]["username"] == "anna"
    # Lo stesso account del provider non si collega a un secondo utente.
    bruno = invite_user(admin, app, "bruno")
    assert "già collegato" in _error(provider.login(bruno, link=True))
    assert admin.delete(f"/api/me/identities/{ids['identities'][0]['id']}").json()["identities"] == []


def test_password_login_can_be_turned_off_with_emergency_access(admin, app, provider, monkeypatch):
    _configure(admin)
    # Nessun amministratore collegato al provider: non si può spegnere (resteremmo fuori).
    r = admin.put("/api/admin/oidc", json={"password_login": False})
    assert r.status_code == 422 and "amministratore" in r.json()["detail"]
    provider.claims = {"sub": "admin-sub", "preferred_username": "anna"}
    provider.login(admin, link=True)
    assert admin.put("/api/admin/oidc", json={"password_login": False}).json()["password_login"] is False
    assert admin.get("/api/auth/state").json()["oidc"]["password_login"] is False
    r = new_client(app).post("/api/auth/login", json={"username": "anna", "password": PASSWORD})
    assert r.status_code == 403 and "Entra con Authentik" in r.json()["detail"]
    # L'unico modo per entrare non si scollega.
    ident = admin.get("/api/me/identities").json()["identities"][0]["id"]
    assert admin.delete(f"/api/me/identities/{ident}").status_code == 409
    # Emergenza con la variabile d'ambiente…
    monkeypatch.setenv("EMERGENCY_PASSWORD_LOGIN", "true")
    assert new_client(app).post("/api/auth/login", json={"username": "anna", "password": PASSWORD}).status_code == 200
    monkeypatch.delenv("EMERGENCY_PASSWORD_LOGIN")
    # …oppure con il comando nel container, che riaccende l'accesso con password.
    from app import emergency

    monkeypatch.setenv("DATA_DIR", str(app.state.ctx.settings.data_dir))
    assert emergency.main(["emergency", "--reset", "anna"]) == 0
    assert new_client(app).post("/api/auth/login", json={"username": "anna", "password": PASSWORD}).status_code == 200


def test_logout_from_the_provider_too(admin, app, provider):
    _configure(admin, auto_create=True, rp_logout=True)
    provider.claims = {"sub": "u-12", "preferred_username": "olga"}
    c = new_client(app)
    provider.login(c)
    r = c.post("/api/auth/logout").json()
    assert r["redirect"].startswith("https://auth.example.org/logout?client_id=galactic-feed&post_logout_redirect_uri=")
    assert c.get("/api/me").status_code == 401
    # Chi è entrato con la password esce solo da Galactic Feed.
    assert admin.post("/api/auth/logout").json()["redirect"] is None


def test_provider_users_can_set_a_password(admin, app, provider):
    _configure(admin, auto_create=True)
    provider.claims = {"sub": "u-13", "preferred_username": "pia"}
    c = new_client(app)
    provider.login(c)
    assert c.get("/api/me/identities").json()["has_password"] is False
    assert c.post("/api/me/password", json={"new": "una-nuova-password"}).status_code == 200
    assert new_client(app).post("/api/auth/login", json={"username": "pia", "password": "una-nuova-password"}).status_code == 200
