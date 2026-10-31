-- Lettura per utente: letti e salvati, interessi, parole silenziate, doppioni.

-- Una riga solo per gli articoli letti o salvati: nessuna riga = non letto.
CREATE TABLE user_articles (
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  read_at    INTEGER,
  saved_at   INTEGER,
  PRIMARY KEY (user_id, article_id)
) WITHOUT ROWID;
CREATE INDEX user_articles_article ON user_articles(article_id);
CREATE INDEX user_articles_saved ON user_articles(user_id, saved_at) WHERE saved_at IS NOT NULL;

CREATE TABLE interests (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  keyword    TEXT    NOT NULL COLLATE NOCASE,
  level      TEXT    NOT NULL DEFAULT 'media' CHECK (level IN ('alta', 'media', 'spento')),
  created_at INTEGER NOT NULL,
  UNIQUE (user_id, keyword)
);

CREATE TABLE muted_words (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  word       TEXT    NOT NULL COLLATE NOCASE,
  created_at INTEGER NOT NULL,
  UNIQUE (user_id, word)
);

-- Esito delle regole di ogni utente sugli articoli, calcolato all'arrivo degli articoli
-- e quando l'utente cambia interessi o parole silenziate. Righe solo dove c'è qualcosa:
-- un interesse trovato (keyword, level) oppure una parola silenziata (muted = 1).
-- Nella v2 anche il filtro AI scriverà qui il suo esito.
CREATE TABLE user_matches (
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  keyword    TEXT,
  level      TEXT CHECK (level IN ('alta', 'media')),
  muted      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, article_id)
) WITHOUT ROWID;
CREATE INDEX user_matches_article ON user_matches(article_id);

-- Titolo ridotto alle parole significative, per riconoscere la stessa notizia da fonti diverse.
ALTER TABLE articles ADD COLUMN title_key TEXT NOT NULL DEFAULT '';
CREATE INDEX articles_cluster ON articles(cluster_id);
UPDATE articles SET cluster_id = id WHERE cluster_id IS NULL;
