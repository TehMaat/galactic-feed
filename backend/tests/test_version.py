"""Versione: un numero solo (file VERSION), uguale ovunque e con le sue note in CHANGELOG.md."""

import importlib.util
from pathlib import Path

from app.config import VERSION

ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("release", ROOT / "scripts" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)


def test_server_reads_the_version_file(client):
    assert VERSION == (ROOT / "VERSION").read_text().strip()
    assert client.get("/api/health").json()["version"] == VERSION
    assert client.get("/api/auth/state").json()["version"] == VERSION


def test_versions_and_changelog_agree():
    assert release.check() == []
    assert release.check(f"v{VERSION}") == []
    assert release.check("v99.0.0") != []
    assert "###" in release.notes(VERSION)
