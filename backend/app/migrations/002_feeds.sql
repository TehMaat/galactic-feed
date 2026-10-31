-- Feed (condivisi tra gli utenti), cartelle e iscrizioni (per utente), articoli.

CREATE TABLE feeds (
  id               INTEGER PRIMARY KEY,
  url              TEXT    NOT NULL UNIQUE,
  kind             TEXT    NOT NULL DEFAULT 'rss' CHECK (kind IN ('rss', 'youtube')),
  title            TEXT    NOT NULL DEFAULT '',
  site_url         TEXT    NOT NULL DEFAULT '',
  etag             TEXT,
  last_modified    TEXT,
  -- Minuti tra un controllo e l'altro: il più breve tra quelli scelti dagli iscritti.
  interval_min     INTEGER NOT NULL DEFAULT 30,
  next_fetch_at    INTEGER NOT NULL DEFAULT 0,
  last_fetch_at    INTEGER,
  last_success_at  INTEGER,
  last_status      INTEGER,
  error_message    TEXT,
  error_since      INTEGER,
  error_count      INTEGER NOT NULL DEFAULT 0,
  created_at       INTEGER NOT NULL
);
CREATE INDEX feeds_due ON feeds(next_fetch_at);

CREATE TABLE folders (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name       TEXT    NOT NULL COLLATE NOCASE,
  color      TEXT    NOT NULL DEFAULT 'indaco',
  position   INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  UNIQUE (user_id, name)
);

CREATE TABLE subscriptions (
  id           INTEGER PRIMARY KEY,
  user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  feed_id      INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
  folder_id    INTEGER REFERENCES folders(id) ON DELETE SET NULL,
  title        TEXT    NOT NULL DEFAULT '',
  interval_min INTEGER NOT NULL DEFAULT 30,
  created_at   INTEGER NOT NULL,
  UNIQUE (user_id, feed_id)
);
CREATE INDEX subscriptions_feed ON subscriptions(feed_id);

CREATE TABLE articles (
  id            INTEGER PRIMARY KEY,
  feed_id       INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
  guid          TEXT    NOT NULL,
  url           TEXT    NOT NULL DEFAULT '',
  -- Link ripulito (senza utm_, www, #…): serve a riconoscere i doppioni.
  canonical_url TEXT    NOT NULL DEFAULT '',
  title         TEXT    NOT NULL DEFAULT '',
  author        TEXT    NOT NULL DEFAULT '',
  excerpt       TEXT    NOT NULL DEFAULT '',
  categories    TEXT    NOT NULL DEFAULT '[]',
  content_html  TEXT    NOT NULL DEFAULT '',
  full_html     TEXT,
  -- none: il feed basta · pending: da estrarre · ok · failed · skipped
  full_status   TEXT    NOT NULL DEFAULT 'none'
                CHECK (full_status IN ('none', 'pending', 'ok', 'failed', 'skipped')),
  image_url     TEXT    NOT NULL DEFAULT '',
  video_id      TEXT,
  word_count    INTEGER NOT NULL DEFAULT 0,
  published_at  INTEGER NOT NULL,
  fetched_at    INTEGER NOT NULL,
  cluster_id    INTEGER,
  UNIQUE (feed_id, guid)
);
CREATE INDEX articles_feed_published ON articles(feed_id, published_at DESC);
CREATE INDEX articles_published ON articles(published_at DESC);
CREATE INDEX articles_canonical ON articles(canonical_url);
CREATE INDEX articles_full_pending ON articles(full_status) WHERE full_status = 'pending';

-- Ricerca full-text: rowid = articles.id. Insensibile a maiuscole e accenti.
CREATE VIRTUAL TABLE articles_fts USING fts5(
  title, author, body,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER articles_fts_delete AFTER DELETE ON articles BEGIN
  DELETE FROM articles_fts WHERE rowid = old.id;
END;
