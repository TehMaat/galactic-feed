-- Edizione: una selezione delle notizie, composta per ogni utente agli orari che sceglie.

CREATE TABLE editions (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  number     INTEGER NOT NULL,           -- n. progressivo dell'utente
  slot       TEXT    NOT NULL,           -- orario dell'edizione, per esempio «07:30»
  since      INTEGER NOT NULL,           -- notizie pubblicate da questo momento
  stats      TEXT    NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  UNIQUE (user_id, number)
);
CREATE INDEX editions_user ON editions(user_id, created_at DESC);

-- section: «hero» per la notizia in primo piano, l'id della cartella, «none» per le fonti
-- senza cartella, «fonti» per le notizie aggiunte quando quelle per te sono poche.
CREATE TABLE edition_items (
  edition_id INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
  article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  position   INTEGER NOT NULL,
  section    TEXT    NOT NULL,
  PRIMARY KEY (edition_id, article_id)
) WITHOUT ROWID;
CREATE INDEX edition_items_article ON edition_items(article_id);
