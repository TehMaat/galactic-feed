"""Strumenti comuni ai test: ogni test ha un database nuovo in una cartella temporanea."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "una-password-lunga"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        public_url="https://feed.example.org",
        data_dir=tmp_path / "data",
        frontend_dir=tmp_path / "dist",
        # Argon2 leggero: nei test conta la velocità, non la resistenza agli attacchi.
        argon2_time_cost=1,
        argon2_memory_cost=1024,
        argon2_parallelism=1,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    # base_url in https perché i cookie di sessione sono "Secure" dietro HTTPS.
    with TestClient(app, base_url="https://feed.example.org") as c:
        yield c


def new_client(app) -> TestClient:
    return TestClient(app, base_url="https://feed.example.org")


@pytest.fixture
def setup_code(client, app):
    return app.state.ctx.setup_code


@pytest.fixture
def admin(client, setup_code):
    """Client collegato come amministratore."""
    r = client.post("/api/auth/setup", json={"code": setup_code, "username": "anna", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


def invite_user(admin_client, app, username: str, password: str = PASSWORD) -> TestClient:
    """Crea un utente tramite invito e restituisce un client collegato come lui."""
    url = admin_client.post("/api/admin/invites", json={}).json()["invite"]["url"]
    token = url.rsplit("/", 1)[1]
    c = new_client(app)
    r = c.post(f"/api/invites/{token}/accept", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c
