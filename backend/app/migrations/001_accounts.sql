-- Account, sessioni e inviti. Gli orari sono secondi UTC.

CREATE TABLE users (
  id            INTEGER PRIMARY KEY,
  username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
  display_name  TEXT    NOT NULL DEFAULT '',
  password_hash TEXT    NOT NULL,
  is_admin      INTEGER NOT NULL DEFAULT 0,
  disabled      INTEGER NOT NULL DEFAULT 0,
  prefs         TEXT    NOT NULL DEFAULT '{}',
  created_at    INTEGER NOT NULL,
  last_seen_at  INTEGER
);

CREATE TABLE sessions (
  id           INTEGER PRIMARY KEY,
  token_hash   TEXT    NOT NULL UNIQUE,
  user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at   INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  expires_at   INTEGER NOT NULL,
  user_agent   TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX sessions_user ON sessions(user_id);

-- kind = 'invite': link per creare un nuovo account.
-- kind = 'reset':  link per scegliere una nuova password (target_user_id).
CREATE TABLE invites (
  id             INTEGER PRIMARY KEY,
  token_hash     TEXT    NOT NULL UNIQUE,
  kind           TEXT    NOT NULL CHECK (kind IN ('invite', 'reset')),
  note           TEXT    NOT NULL DEFAULT '',
  created_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
  target_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  created_at     INTEGER NOT NULL,
  expires_at     INTEGER NOT NULL,
  used_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
  used_at        INTEGER
);
