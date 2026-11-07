# Novità

Tutte le versioni di Galactic Feed, dalla più recente. I numeri seguono [semver](https://semver.org/lang/it/): `MAGGIORE.MINORE.CORRETTIVA`. Finché la versione comincia con `0.` l'app è giovane: le novità arrivano con le versioni minori (0.4, 0.5…), le correzioni con le correttive (0.3.1).

Per aggiornare basta scaricare la nuova immagine: le modifiche al database si applicano da sole all'avvio. Prima di saltare a una nuova versione minore conviene fare una copia del volume `/data` (vedi il README, «Versioni e aggiornamenti»).

## [0.5.0] – 2026-11-07

### Novità
- **Gruppi di parole** pronti e personali per interessi e parole silenziate (Motori, Politica, Tecnologia, Calcio…): si accendono con un tocco come interesse o per silenziare, se ne cambiano le parole, se ne creano di nuovi. La corrispondenza mostra il gruppo («Tecnologia · iPhone»). L'amministratore gestisce i gruppi pronti (#16).
- **Tag delle fonti**: proposti in automatico quando aggiungi una fonte, modificabili dalla scheda della fonte, usati come chip nel Flusso; gestione dei tag (rinomina, colore, ordine, unisci, elimina). Le tue scelte non vengono mai annullate (#17).
- **Più Edizioni**, ognuna con nome, regole (tag, cartelle, nazioni, gruppi di parole), numero massimo di notizie, periodo coperto e notifica; anteprima delle notizie e selettore in Oggi (#18).
- **Edizioni settimanali e mensili**: giorni della settimana, un giorno del mese o «il primo lunedì del mese», a uno o più orari, nel tuo fuso orario (#19).
- **Nazione delle fonti**, proposta dal dominio e dalla lingua: si sceglie per sé, l'amministratore la corregge per tutti; filtro nelle Fonti e nel Flusso, regola delle Edizioni (#20).

### Correzioni
- La scheda della fonte tornava ai dati iniziali dopo ogni modifica (icona, tag).

### Da sapere per aggiornare
- Migrazioni automatiche `008`–`010`.
- L'Edizione di prima diventa «La mia Edizione», con gli stessi orari e numeri. Si gestisce in Impostazioni → Edizioni.
- Il `docker-compose.yml` d'esempio ora usa `:0.5`.

## [0.4.0] – 2026-11-07

Prima versione pubblicata come release: immagini `ghcr.io/tehmaat/galactic-feed:0.4.0` e `:0.4`.

### Novità
- **Pannello di amministrazione**: nella barra laterale sotto Impostazioni (sul telefono dentro le Impostazioni), solo per gli amministratori. Ci sono utenti e inviti, accesso, fonti e archivio, AI, predefiniti per i nuovi utenti e stato del sistema. Ogni impostazione dell'istanza si cambia dall'app senza riavviare; mostra se il valore è scelto lì, viene da una variabile d'ambiente o è il predefinito (#21).
- Nuove impostazioni da GUI: per quanto tenere gli articoli, intervallo proposto per le fonti nuove, fonti della rete locale sì/no, validità dei link d'invito, fuso orario dell'istanza.
- **Predefiniti per i nuovi utenti**: tema, colore, font, dimensione del testo, doppioni, riassunti, Edizione e orari.
- **Stato del sistema**: versione, spazio del database, ultimo controllo dei feed, feed con errori, ultimo errore dell'AI, variabili che valgono solo all'avvio.
- **Release automatiche**: quando su `main` arriva un numero nuovo in `VERSION`, il workflow pubblica le immagini `:X.Y.Z` e `:X.Y` e crea da solo il tag e la release su GitHub con le note di questo registro.

### Sicurezza
- La chiave dell'AI è salvata cifrata con `data/secret.key`; quella già salvata in chiaro si cifra da sola all'avvio.

### Correzioni
- Sul computer, nelle schede delle Impostazioni, il pulsante «Indietro» era invisibile.

### Da sapere per aggiornare
- Utenti, inviti e AI non sono più nelle Impostazioni personali ma in Amministrazione.
- Nuova variabile d'ambiente facoltativa `INVITE_HOURS`.
- Il `docker-compose.yml` d'esempio ora usa `:0.4` invece di `:latest`.
- **Copia di `data/secret.key`**: d'ora in poi serve anche per leggere la chiave dell'AI; se va persa, la chiave va reinserita.

## [0.3.0] – 2026-11-06

Non pubblicata come release: le sue novità escono con la 0.4.0, la prima con le immagini numerate.

### Novità
- **Icone dei giornali** al posto delle iniziali: favicon del sito o avatar del canale YouTube, trovate in automatico, anche offline. Dalla scheda della fonte si aggiornano, si sostituiscono con un'altra immagine o si tolgono (#11).
- **«Ricordami»** al login. Senza, chiudendo il browser si esce e la sessione finisce dopo 12 ore senza usare l'app; con, dura 90 giorni. L'amministratore sceglie le durate in Impostazioni → Accesso (#12).
- **Colore principale** a scelta tra otto, con contrasto verificato in chiaro e in scuro, oppure quello del sistema dove il browser lo permette (#14).
- **Font** dell'interfaccia (Galactic, Sistema, Inter, Alta leggibilità) e del testo degli articoli; dimensione del testo anche in Impostazioni → Aspetto (#15).
- Il **logo** «galactic feed» riporta a Oggi (#13).
- **Versioni**: numero unico nel file `VERSION` e questo registro delle novità.

### Correzioni
- La foto principale non compare più due volte aprendo un articolo (#10).

### Da sapere per aggiornare
- Migrazione automatica `007`: sessioni, icone delle fonti.
- Nuove variabili d'ambiente facoltative: `REMEMBER_DAYS`, `SESSION_HOURS`.

## [0.2.0] – 2026-11-03

Non pubblicata come release (immagine solo come `latest`). PR #8.

### Novità
- **Edizione**: una selezione delle notizie per te, composta agli orari che scegli.
- **AI** facoltativa, locale (Ollama) o cloud (Anthropic, OpenAI): sceglie le notizie e scrive riassunti in tre punti.
- **Notifiche push** per le categorie importanti e numero di non letti sull'icona dell'app.

## [0.1.0] – 2026-11-02

Prima versione. Non pubblicata come release (immagine solo come `latest`). PR #3–#7.

### Novità
- Account multiutente: primo avvio con codice nel log, inviti, link per una nuova password.
- Fonti RSS, Atom e canali YouTube, con ricerca automatica del feed, cartelle e OPML.
- Flusso con filtri, ricerca, interessi, parole silenziate e doppioni uniti; testo completo estratto dalla pagina.
- PWA per telefono, tablet e computer, con lettura offline di salvati e letti.
- Un solo container Docker per amd64, arm64 e armv7.
