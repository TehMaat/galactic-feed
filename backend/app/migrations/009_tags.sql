-- Tag delle fonti (per utente): più tag per fonte, proposti in automatico e modificabili.

CREATE TABLE tags (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       TEXT    NOT NULL COLLATE NOCASE,
  color      TEXT    NOT NULL DEFAULT 'indaco',
  position   INTEGER NOT NULL DEFAULT 0,
  in_feed    INTEGER NOT NULL DEFAULT 1,     -- chip nel Flusso sì/no
  created_at INTEGER NOT NULL,
  UNIQUE (user_id, name)
);

-- origin: auto (proposto dall'app), user (scelto dall'utente), rejected (proposto e tolto
-- dall'utente: la proposta automatica non lo rimette più).
CREATE TABLE source_tags (
  subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  tag_id          INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  origin          TEXT    NOT NULL DEFAULT 'user' CHECK (origin IN ('auto', 'user', 'rejected')),
  created_at      INTEGER NOT NULL,
  PRIMARY KEY (subscription_id, tag_id)
) WITHOUT ROWID;
CREATE INDEX source_tags_tag ON source_tags(tag_id);

-- Quando l'app ha proposto i tag per questa fonte (NULL: ancora da fare).
ALTER TABLE subscriptions ADD COLUMN tags_suggested_at INTEGER;
