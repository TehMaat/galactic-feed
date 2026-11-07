-- Gruppi di parole per interessi e parole silenziate (per esempio «Motori»: auto, motore, macchina…).

-- Gruppi pronti, offerti a tutti: quelli forniti con l'app (builtin, con una chiave fissa)
-- e quelli aggiunti dall'amministratore. Un gruppo fornito con l'app non si cancella: si nasconde.
CREATE TABLE preset_groups (
  id         INTEGER PRIMARY KEY,
  key        TEXT    UNIQUE,
  name       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
  words      TEXT    NOT NULL DEFAULT '[]',
  hidden     INTEGER NOT NULL DEFAULT 0,
  builtin    INTEGER NOT NULL DEFAULT 0,
  position   INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL
);

-- Gruppi dell'utente: copiati da un gruppo pronto (preset_id) oppure creati da lui.
-- mode: off (spento), interest (le parole valgono come interessi), mute (le parole silenziano).
CREATE TABLE word_groups (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  preset_id  INTEGER REFERENCES preset_groups(id) ON DELETE SET NULL,
  name       TEXT    NOT NULL COLLATE NOCASE,
  mode       TEXT    NOT NULL DEFAULT 'off' CHECK (mode IN ('off', 'interest', 'mute')),
  level      TEXT    NOT NULL DEFAULT 'media' CHECK (level IN ('alta', 'media')),
  created_at INTEGER NOT NULL,
  UNIQUE (user_id, name)
);
CREATE INDEX word_groups_user ON word_groups(user_id);

-- id tiene l'ordine in cui le parole sono state scritte.
CREATE TABLE word_group_words (
  id       INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES word_groups(id) ON DELETE CASCADE,
  word     TEXT    NOT NULL COLLATE NOCASE,
  UNIQUE (group_id, word)
);

-- Il gruppo che ha fatto corrispondere l'articolo, da mostrare accanto alla parola trovata.
ALTER TABLE user_matches ADD COLUMN group_id INTEGER REFERENCES word_groups(id) ON DELETE SET NULL;
