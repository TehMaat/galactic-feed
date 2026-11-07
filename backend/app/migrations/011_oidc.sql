-- Accesso con un provider OpenID Connect (Authentik, Authelia, Keycloak, Pocket ID…), issue #22.

-- Gli account del provider collegati a un utente: (issuer, subject) identificano la persona.
CREATE TABLE user_identities (
  id            INTEGER PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  issuer        TEXT    NOT NULL,
  subject       TEXT    NOT NULL,
  email         TEXT    NOT NULL DEFAULT '',
  username      TEXT    NOT NULL DEFAULT '',
  created_at    INTEGER NOT NULL,
  last_login_at INTEGER,
  UNIQUE (issuer, subject)
);
CREATE INDEX user_identities_user ON user_identities(user_id);

-- Accessi in corso verso il provider: state (solo l'hash), verificatore PKCE e nonce.
-- Valgono 10 minuti e una volta sola.
CREATE TABLE oidc_states (
  state_hash   TEXT    PRIMARY KEY,
  verifier     TEXT    NOT NULL,
  nonce        TEXT    NOT NULL,
  remember     INTEGER NOT NULL DEFAULT 0,
  link_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  created_at   INTEGER NOT NULL
) WITHOUT ROWID;

-- Email verificata dal provider, per riconoscere un utente esistente al primo accesso.
ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT '';
-- Come è stata aperta la sessione: password oppure oidc (per l'uscita anche dal provider).
ALTER TABLE sessions ADD COLUMN via TEXT NOT NULL DEFAULT 'password';
