-- AI facoltativa: configurazione (fatta dall'amministratore), consumi, esiti e riassunti.

CREATE TABLE app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
) WITHOUT ROWID;

-- Richieste e token del giorno (UTC), per il tetto giornaliero.
CREATE TABLE ai_usage (
  day           TEXT PRIMARY KEY,
  requests      INTEGER NOT NULL DEFAULT 0,
  input_tokens  INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0
) WITHOUT ROWID;

-- Esito del filtro AI per utente e articolo, anche «non pertinente» (level NULL),
-- così ogni articolo si valuta una volta sola. Si azzera quando l'utente cambia descrizione.
CREATE TABLE ai_matches (
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  level      TEXT CHECK (level IN ('alta', 'media')),
  label      TEXT NOT NULL DEFAULT '',
  checked_at INTEGER NOT NULL,
  PRIMARY KEY (user_id, article_id)
) WITHOUT ROWID;
CREATE INDEX ai_matches_article ON ai_matches(article_id);

-- Riassunto in tre punti, uguale per tutti gli utenti.
CREATE TABLE article_summaries (
  article_id INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
  points     TEXT    NOT NULL,
  model      TEXT    NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL
);

-- Da dove viene la pertinenza: «parole» (interessi) oppure «ai».
ALTER TABLE user_matches ADD COLUMN source TEXT NOT NULL DEFAULT 'parole';
