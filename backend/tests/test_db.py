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
