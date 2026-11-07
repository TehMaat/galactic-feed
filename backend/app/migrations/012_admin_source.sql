-- Da dove viene il permesso di amministratore: 1 se l'ha dato il gruppo del provider OIDC
-- (e quindi il gruppo lo può anche togliere), 0 se l'ha dato un amministratore nell'app
-- o il primo avvio: quello lo toglie solo un amministratore.
ALTER TABLE users ADD COLUMN admin_via_group INTEGER NOT NULL DEFAULT 0;
