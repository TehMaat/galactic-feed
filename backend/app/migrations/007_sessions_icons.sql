-- «Ricordami» al login e icone delle fonti.

-- remember = 1: la sessione resta dopo la chiusura del browser e dura i giorni scelti
-- dall'amministratore; 0: cookie di sessione e scadenza breve. Le sessioni già aperte
-- erano tutte «ricordate».
ALTER TABLE sessions ADD COLUMN remember INTEGER NOT NULL DEFAULT 1;

-- Icona del sito (favicon, apple-touch-icon…) o avatar del canale YouTube, cercata in
-- automatico e condivisa da chi segue il feed. icon_checked_at: ultimo tentativo.
ALTER TABLE feeds ADD COLUMN icon_url TEXT NOT NULL DEFAULT '';
ALTER TABLE feeds ADD COLUMN icon_checked_at INTEGER;

-- Scelta dell'utente per la sua fonte: auto (l'icona trovata), custom (un'immagine scelta
-- da lui, in icon_custom) oppure none (le iniziali). L'aggiornamento automatico non la tocca.
ALTER TABLE subscriptions ADD COLUMN icon_mode TEXT NOT NULL DEFAULT 'auto'
  CHECK (icon_mode IN ('auto', 'custom', 'none'));
ALTER TABLE subscriptions ADD COLUMN icon_custom TEXT NOT NULL DEFAULT '';
