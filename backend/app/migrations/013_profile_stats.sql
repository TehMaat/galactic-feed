-- Profilo e statistiche (#76, #78).

-- Avatar del profilo: una foto piccola (JPEG, PNG o WebP già ridotta dall'app) oppure le
-- iniziali su uno dei colori proposti (avatar_color). avatar_v cambia a ogni foto nuova, così
-- il browser non tiene quella vecchia.
ALTER TABLE users ADD COLUMN avatar BLOB;
ALTER TABLE users ADD COLUMN avatar_type TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN avatar_color INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN avatar_v INTEGER NOT NULL DEFAULT 0;

-- Articoli aperti, per le statistiche: uno per articolo, quando lo si apre la prima volta.
-- Non conta «Segna tutti come letti» né i doppioni segnati insieme alla notizia. La fonte
-- (feed_id) resta anche se l'articolo viene cancellato con la pulizia periodica.
CREATE TABLE reading_log (
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  article_id INTEGER NOT NULL,
  feed_id    INTEGER,
  read_at    INTEGER NOT NULL,
  PRIMARY KEY (user_id, article_id)
) WITHOUT ROWID;
CREATE INDEX reading_log_time ON reading_log(user_id, read_at);

-- Quando un'uscita dell'Edizione è stata aperta la prima volta (per le statistiche).
ALTER TABLE editions ADD COLUMN opened_at INTEGER;
