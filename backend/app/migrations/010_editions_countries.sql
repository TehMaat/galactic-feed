-- Più Edizioni per utente, ognuna con nome, regole e pianificazione (#18, #19);
-- nazione e lingua delle fonti (#20).

CREATE TABLE edition_configs (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       TEXT    NOT NULL,
  active     INTEGER NOT NULL DEFAULT 1,
  -- Regole, tutte facoltative: {"tags": [id], "folders": ["id" | "none"], "countries": ["IT"], "groups": [id]}.
  -- Tra tipi diversi valgono tutte (E), dentro lo stesso tipo ne basta una (O). Nessuna regola = tutto.
  rules      TEXT    NOT NULL DEFAULT '{}',
  -- Pianificazione: {"kind": "daily" | "weekly" | "monthly", "times": ["07:30"], "days": [0-6],
  -- "day": 1-31 | -1, "nth": 1-4 | -1, "weekday": 0-6} (vedi reading/schedule.py).
  schedule   TEXT    NOT NULL DEFAULT '{}',
  max_items  INTEGER NOT NULL DEFAULT 30,
  -- Periodo coperto: auto (dall'Edizione precedente), day, week, month.
  period     TEXT    NOT NULL DEFAULT 'auto' CHECK (period IN ('auto', 'day', 'week', 'month')),
  notify     INTEGER NOT NULL DEFAULT 1,
  position   INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE INDEX edition_configs_user ON edition_configs(user_id);

ALTER TABLE editions ADD COLUMN config_id INTEGER REFERENCES edition_configs(id) ON DELETE CASCADE;
-- Numero progressivo dentro la sua Edizione (n. 1, 2, 3… per ognuna).
ALTER TABLE editions ADD COLUMN config_number INTEGER;
CREATE INDEX editions_config ON editions(config_id, created_at DESC);

-- Vero quando le Edizioni dell'utente sono già state create dalle preferenze di prima
-- (accesa sì/no e orari): si fa una volta sola, al primo uso.
ALTER TABLE users ADD COLUMN editions_ready INTEGER NOT NULL DEFAULT 0;

-- Nazione e lingua delle fonti. language e country sono proposti in automatico (lingua del
-- feed, dominio, testo); country_admin è la correzione dell'amministratore, valida per tutti.
ALTER TABLE feeds ADD COLUMN language TEXT NOT NULL DEFAULT '';
ALTER TABLE feeds ADD COLUMN country TEXT NOT NULL DEFAULT '';
ALTER TABLE feeds ADD COLUMN country_admin TEXT;
ALTER TABLE feeds ADD COLUMN geo_checked_at INTEGER;
-- Scelta dell'utente per sé (NULL: vale quella dell'amministratore o quella automatica;
-- '' = nessuna nazione).
ALTER TABLE subscriptions ADD COLUMN country TEXT;
