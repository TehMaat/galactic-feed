# Galactic Feed · architettura della prima versione

Proposta approvata il 31/10/2026. Descrive come è fatto il codice; i requisiti sono in [ANALISI.md](ANALISI.md).

## Struttura del repository

```
backend/                  Server Python (FastAPI)
  app/
    main.py               avvio: API, PWA, scheduler
    healthcheck.py        controllo di salute usato dal container (python -m app.healthcheck)
    config.py             variabili d'ambiente (PUBLIC_URL, TZ, …)
    db.py + migrations/   SQLite, schema versionato con file .sql numerati
    security.py           password argon2, sessioni, protezione CSRF
    api/                  un file per area: auth, admin, folders, sources, opml, articles, interests, images
    feeds/                discovery, fetcher, parser, youtube, extract (testo completo), sanitize, scheduler
    reading/              matching (interessi e silenziati), dedupe (doppioni), query, edition (Edizione)
    ai/                   configurazione, fornitori (Ollama/OpenAI, Anthropic), filtro AI, riassunti
    push/                 Web Push (VAPID, cifratura) e regole delle notifiche
    hooks.py              agganci tra le parti: nuovi articoli, Edizione pronta
  tests/                  pytest, con feed e siti finti: nessuna chiamata a Internet
frontend/                 PWA Svelte + Vite
  src/
    styles/               base.css e app.css presi dal mockup
    lib/                  client API, stato, copertine generative, coda offline
    views/                Oggi, Fonti, Interessi, Salvati, Accesso, Primo avvio, Invito
    components/           Card, Row, Reader, Sheet, AggiungiFonte, Impostazioni, TabBar, Chips, Toast
    sw.js                 service worker
  public/icons/
  tests/                  vitest (logica) + Playwright (prova nel browser)
Dockerfile                build in più fasi: PWA → dipendenze Python → immagine finale (utente non root, uid 1000)
docker-compose.yml
.github/workflows/        test e build multi-architettura
docs/  mockup/  README.md
```

Scelte:

- **Niente ORM**: SQL scritto a mano con il modulo `sqlite3` di Python. Con un solo database SQLite e la ricerca FTS5 è il modo più diretto, con meno pezzi da aggiornare.
- **Scheduler dentro il server**: un ciclo asincrono che ogni minuto guarda quali feed vanno controllati. Nessun altro container o processo.
- **La PWA compilata è servita dallo stesso server** sulla porta 8080.
- **Svelte 5 senza librerie di routing**: poche righe bastano per gestire gli indirizzi.
- **Orari nel database in secondi UTC**; l'API li restituisce in formato ISO 8601 e la PWA li mostra nel fuso del dispositivo.

## Schema del database

I contenuti dei feed sono **condivisi**: un feed seguito da tre utenti si scarica una volta. Tutto ciò che è personale sta in tabelle **per utente**. Lo schema cresce con migrazioni numerate in `backend/app/migrations/`; la versione applicata è in `PRAGMA user_version`.

**Account**
- `users`: username (unico, senza distinzione tra maiuscole e minuscole), nome visualizzato, hash della password, amministratore, disattivato, preferenze (JSON: tema, dimensione del testo, unione dei doppioni, Edizione e orari, metodo e descrizione per l'AI, riassunti, cartelle importanti per le notifiche), creato il, ultimo accesso
- `sessions`: hash del token, utente, creata il, ultimo uso, scadenza, dispositivo
- `invites`: hash del token, tipo (`invite` o `reset`), nota, creato da, utente destinatario (solo reset), scadenza, usato da, usato il

**Fonti**
- `feeds` (condivisa): url (unico), sito, titolo, tipo (rss / youtube), etag, last_modified, intervallo, prossimo controllo, ultimo controllo, ultimo successo, ultimo codice HTTP, messaggio d'errore, errori consecutivi
- `folders` (per utente): nome, colore, posizione
- `subscriptions` (per utente): utente, feed, cartella, nome personalizzato, intervallo scelto, aggiunta il

**Articoli**
- `articles` (condivisa): feed, guid, url, url normalizzato, titolo, autore, estratto, contenuto del feed, testo completo estratto, stato dell'estrazione, immagine, durata del video, pubblicato il, scaricato il, cluster dei doppioni
- `articles_fts`: indice full-text su titolo, autore, estratto e testo, insensibile agli accenti
- `user_articles` (per utente): letto il, salvato il. Nessuna riga vuol dire non letto

**Interessi**
- `interests` (per utente): parola chiave, priorità (alta / media / spento)
- `muted_words` (per utente): parola
- `user_matches` (per utente): esito delle regole su ogni articolo (interesse o tema dell'AI e priorità, oppure silenziato; `source` dice se viene dalle parole o dall'AI). Calcolato all'arrivo degli articoli, quando l'utente cambia le regole e quando l'AI valuta nuovi articoli, così filtri e contatori sono semplici query

**Seconda versione**
- `editions` ed `edition_items` (per utente): numero, orario, notizie e sezioni di ogni Edizione (si tengono le ultime 60)
- `app_settings`: configurazione dell'AI (fornitore, indirizzo, modello, chiave, tetto giornaliero, ultimo errore)
- `ai_usage`: richieste e token al giorno
- `ai_matches` (per utente): esito dell'AI per articolo, anche «non pertinente», così ogni articolo si valuta una volta sola
- `article_summaries` (condivisa): riassunto in tre punti
- `push_subscriptions` (per dispositivo) e `push_sent` (notizie già notificate)

Regole:

- **Interessi e silenziati**: confronto per parole intere su titolo, estratto e categorie, senza badare a maiuscole e accenti. Per l'italiano si riconoscono singolare e plurale cambiando l'ultima vocale («razzo» ↔ «razzi», «amica» ↔ «amiche»). "Per te" = articoli che toccano un interesse alto o medio; se ne toccano più d'uno vale quello con priorità più alta.
- **Doppioni**: all'arrivo, un articolo con lo stesso link normalizzato, oppure con un titolo quasi uguale (almeno 4 parole significative e il 75% in comune) in un altro feed nei 3 giorni intorno, entra nello stesso cluster. Prima si applicano i filtri, poi per ogni notizia si mostra l'articolo pubblicato per primo, con "anche su: …". Segnare come letto vale per tutta la notizia. Si può spegnere.
- **Visibilità**: un utente vede gli articoli dei feed che segue e quelli che ha salvato, anche se ha smesso di seguire la fonte.
- **Ricerca**: FTS5 su titolo, autore e testo (anche quello estratto), più il nome della fonte. Ogni parola deve comparire, anche come inizio di parola.
- **Pulizia**: gli articoli più vecchi di `RETENTION_DAYS` (90) vengono cancellati, tranne quelli salvati da qualcuno.

## Endpoint API

Tutti sotto `/api`; salvo `auth`, `invites` e `health` richiedono l'accesso. Gli errori hanno sempre la forma `{"detail": "messaggio in italiano"}`.

| Area | Endpoint |
|---|---|
| Accesso | `GET auth/state` · `POST auth/setup` · `POST auth/login` · `POST auth/logout` |
| Inviti | `GET invites/{token}` · `POST invites/{token}/accept` (anche per il reset della password) |
| Profilo | `GET`/`PATCH me` · `POST me/password` · `GET me/sessions` · `DELETE me/sessions/{id}` |
| Admin | `GET admin/users` · `PATCH`/`DELETE admin/users/{id}` · `POST admin/users/{id}/reset` · `GET`/`POST admin/invites` · `DELETE admin/invites/{id}` · `GET admin/status` |
| Cartelle | `GET`/`POST folders` · `PATCH`/`DELETE folders/{id}` |
| Fonti | `POST sources/discover` · `GET`/`POST sources` · `PATCH`/`DELETE sources/{id}` · `POST sources/{id}/refresh` · `POST sources/refresh` |
| OPML | `POST opml/import` · `GET opml/export` |
| Articoli | `GET articles` (filtri `tutti`, `perte`, `nonletti`, `video`, `salvati`, cartella, fonte, ricerca, cursore) · `GET articles/counts` · `GET articles/{id}` · `PUT`/`DELETE articles/{id}/read` · `PUT`/`DELETE articles/{id}/saved` · `POST articles/mark-read` · `POST articles/sync` |
| Interessi | `GET interests` · `POST`/`PATCH`/`DELETE interests/keywords[/{id}]` · `POST`/`DELETE interests/muted[/{id}]` · `GET interests/preview` |
| Edizione | `GET editions/latest` · `GET editions/{id}` · `POST editions` (componi adesso) |
| AI | `GET ai/status` · `GET`/`PUT admin/ai` · `POST admin/ai/test` · `POST articles/{id}/summary` |
| Notifiche | `GET push/key` · `GET`/`POST`/`DELETE push/subscriptions` · `POST push/test` |
| Immagini | `GET img?u=…&s=…` (proxy firmato) |
| Sistema | `GET health` |

Fuori da `/api`: la PWA, `/manifest.webmanifest`, `/sw.js`, `/icons/*`. Devono restare raggiungibili anche dietro un login del reverse proxy.

## Altre scelte

- **Primo avvio protetto**: per creare l'amministratore serve un codice di 6 cifre scritto nel log del server (`docker compose logs galactic-feed`). Il codice cambia a ogni riavvio e dopo troppi tentativi sbagliati.
- **Inviti**: link valido 48 ore, utilizzabile una volta. Lo stesso meccanismo reimposta la password di un utente.
- **Sessioni**: cookie `gf_session` HttpOnly, SameSite=Lax, Secure dietro HTTPS; durata 90 giorni, rinnovata con l'uso. Le richieste che modificano dati sono accettate solo dalla stessa origine (header `Sec-Fetch-Site` / `Origin`). Limite ai tentativi di login.
- **Fetcher**: ETag e Last-Modified, timeout 20 s, al massimo 4 download in parallelo, user agent `GalacticFeed/<versione> (+PUBLIC_URL)`, rispetto di `Retry-After`, controlli diradati in caso di errore fino a uno al giorno, messaggi d'errore chiari in italiano. L'intervallo di un feed seguito da più persone è il più breve tra quelli scelti.
- **Testo completo**: se il feed dà solo un estratto, il server estrae il testo con trafilatura all'arrivo dell'articolo. L'HTML viene ripulito: niente script, pubblicità o link per commentare.
- **YouTube**: dal link del canale o da `@nome` il server ricava il feed pubblico.
- **Immagini**: passano da un proxy firmato del server, così il service worker le può tenere offline.
- **Offline**: l'interfaccia è sempre in cache; restano disponibili tutti i salvati e gli ultimi 300 articoli letti. Le azioni fatte senza rete partono al ritorno della connessione.
  - Il service worker (`src/sw.js`) tiene la copia di ogni articolo aperto (`gf-articles`) e le sue immagini (`gf-img-offline`), più l'ultima risposta di account, fonti, contatori ed elenchi (`gf-api`, `gf-lists`): prima la rete, senza rete la copia.
  - Un indice in IndexedDB dice quali articoli sono salvati e quando sono stati letti: oltre i 300 letti si tolgono i più vecchi, con le loro immagini. I salvati fatti su un altro dispositivo vengono scaricati da soli all'apertura dell'app.
  - Letto e salvato fatti senza rete vanno in una coda in IndexedDB, inviata a `POST articles/sync` quando torna la rete, quando si riapre l'app e ogni minuto. Non si usa la sincronizzazione in background dei service worker, che su iPhone non c'è.
  - All'uscita, o se entra un altro account, le copie e la coda si cancellano dal dispositivo.
- **Edizione**: a ogni orario scelto (nel fuso `TZ`) lo scheduler compone una selezione delle notizie pubblicate dall'edizione precedente: prima quelle «per te» (priorità alta in primo piano), raggruppate per cartella; se sono meno di 3 si aggiungono le ultime di ogni fonte. Se il server era spento all'orario, la compone appena riparte.
- **AI** (facoltativa): la configura l'amministratore, locale (Ollama o un server compatibile con OpenAI) o cloud (Anthropic con l'SDK ufficiale, oppure OpenAI), con un tetto di richieste al giorno. Ogni utente sceglie parole chiave, AI o entrambi e descrive i suoi interessi. Lo scheduler manda al modello gli articoli delle ultime 48 ore a lotti di 20, con risposta in JSON strutturato; dopo un errore si ferma 15 minuti. Con Claude si usa effort basso e, sui modelli che lo permettono, il ripiego lato server se il modello rifiuta una richiesta. I riassunti (tre punti) si scrivono alla prima apertura di un articolo lungo e valgono per tutti.
- **Notifiche**: Web Push standard. Chiavi VAPID create al primo avvio in `data/vapid.pem`; contenuto cifrato (RFC 8291), così i servizi push dei browser non lo leggono. Si accettano solo gli indirizzi dei servizi push di Google, Mozilla, Apple e Microsoft. Per ogni utente: le notizie «per te» nelle cartelle importanti, non lette e mai notificate, in una notifica sola, al massimo una ogni 10 minuti; più, a scelta, l'Edizione pronta. Il numero di non letti va sull'icona dell'app (Badging API).
- **Reti locali**: le fonti possono stare sulla rete di casa; `BLOCK_PRIVATE_NETWORKS=true` lo impedisce.

## Variabili d'ambiente

| Variabile | Predefinito | A cosa serve |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | Indirizzo pubblico dell'app (link d'invito, manifest, user agent) |
| `TZ` | `Europe/Rome` | Fuso orario del server |
| `DATA_DIR` | `/data` | Cartella del database |
| `RETENTION_DAYS` | `90` | Giorni dopo cui si cancellano gli articoli non salvati |
| `BLOCK_PRIVATE_NETWORKS` | `false` | Vieta fonti su indirizzi della rete locale |
| `FORWARDED_ALLOW_IPS` | `*` | Da quali indirizzi accettare gli header `X-Forwarded-*` |
| `LOG_LEVEL` | `info` | Dettaglio del log |
