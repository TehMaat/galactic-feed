"""Accesso d'emergenza (issue #22), da usare nel container se il provider OIDC non risponde.

    docker compose exec galactic-feed python -m app.emergency
        riaccende l'accesso con password ed elenca gli amministratori;
    docker compose exec galactic-feed python -m app.emergency --reset NOME
        stampa anche un link per scegliere una nuova password (vale un'ora).

In alternativa, la variabile d'ambiente EMERGENCY_PASSWORD_LOGIN=true tiene acceso
l'accesso con password finché resta impostata.
"""

from __future__ import annotations

import sys

from .config import Settings
from .db import Database, now, set_setting
from .security import new_token, token_hash


def main(argv: list[str]) -> int:
    settings = Settings.from_env()
    db = Database(settings.db_path)
    db.init()
    with db.session() as conn:
        with conn:
            set_setting(conn, "oidc.password_login", "1")
        admins = conn.execute("SELECT id, username FROM users WHERE is_admin = 1 AND disabled = 0 ORDER BY id").fetchall()
        print("Accesso con password riacceso.")
        print("Amministratori: " + (", ".join(a["username"] for a in admins) or "nessuno"))
        if len(argv) >= 3 and argv[1] == "--reset":
            row = conn.execute("SELECT id, username FROM users WHERE username = ?", (argv[2],)).fetchone()
            if row is None:
                print(f"Utente «{argv[2]}» non trovato.", file=sys.stderr)
                return 1
            token, ts = new_token(), now()
            with conn:
                conn.execute("DELETE FROM invites WHERE kind = 'reset' AND target_user_id = ? AND used_at IS NULL", (row["id"],))
                conn.execute(
                    "INSERT INTO invites (token_hash, kind, note, target_user_id, created_at, expires_at)"
                    " VALUES (?, 'reset', 'Accesso d''emergenza', ?, ?, ?)",
                    (token_hash(token), row["id"], ts, ts + 3600),
                )
            print(f"Nuova password per {row['username']}: {settings.public_url}/reimposta/{token}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
