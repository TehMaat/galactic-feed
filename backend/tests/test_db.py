from app.db import Database, migrate, _migrations


def test_migrations_apply_once(tmp_path):
    db = Database(tmp_path / "x.db")
    db.init()
    latest = _migrations()[-1][0]
    with db.session() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == latest
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        # Una seconda volta non deve fare nulla.
        assert migrate(conn) == latest


def test_fts5_available(tmp_path):
    db = Database(tmp_path / "x.db")
    with db.session() as conn:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(a, tokenize = 'unicode61 remove_diacritics 2')")
        conn.execute("INSERT INTO t VALUES ('Perché la Luna')")
        assert conn.execute("SELECT count(*) FROM t WHERE t MATCH 'perche'").fetchone()[0] == 1


def test_data_dir_not_writable(tmp_path, monkeypatch):
    import os

    import pytest

    from app.main import DataDirError, check_data_dir

    check_data_dir(tmp_path / "nuova")  # la crea se manca
    assert (tmp_path / "nuova").is_dir()
    monkeypatch.setattr(os, "access", lambda *a: False)
    with pytest.raises(DataDirError, match="sudo chown -R"):
        check_data_dir(tmp_path)


def test_healthcheck(monkeypatch):
    import io
    import json

    from app import healthcheck

    class Opener:
        def __init__(self, body=None, error=None):
            self.body, self.error = body, error

        def open(self, url, timeout):
            assert url == "http://127.0.0.1:9999/api/health"
            if self.error:
                raise self.error
            res = io.BytesIO(json.dumps(self.body).encode())
            res.status = 200
            return _Ctx(res)

    class _Ctx:
        def __init__(self, res):
            self.res = res

        def __enter__(self):
            return self.res

        def __exit__(self, *a):
            return False

    monkeypatch.setenv("PORT", "9999")
    monkeypatch.setattr(healthcheck.urllib.request, "build_opener", lambda *a: Opener({"status": "ok"}))
    assert healthcheck.main() == 0
    monkeypatch.setattr(healthcheck.urllib.request, "build_opener", lambda *a: Opener(error=OSError("rifiutata")))
    assert healthcheck.main() == 1
