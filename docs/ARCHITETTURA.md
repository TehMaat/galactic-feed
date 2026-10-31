# Galactic Feed · architettura della prima versione

Proposta approvata il 31/10/2026. Descrive come è fatto il codice; i requisiti sono in [ANALISI.md](ANALISI.md).

## Struttura del repository

```
backend/                  Server Python (FastAPI)
  app/
    main.py               avvio: API, PWA, scheduler
    config.py             variabili d'ambiente (PUBLIC_URL, TZ, …)
    db.py + migrations/   SQLite, schema versionato con file .sql numerati
    security.py           password argon2, sessioni, protezione CSRF
    api/                  un file per area: auth, admin, folders, sources, opml, articles, interests, images
    feeds/                discovery, fetcher, parser, youtube, extract (testo completo), sanitize, scheduler
    reading/              matching (interessi e silenziati), dedupe (doppioni), search (FTS5)
    hooks.py              punti di aggancio per la v2 (edizione, AI, push)
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
Dockerfile                build in più fasi: PWA → backend → immagine finale
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
- `users`: username (unico, senza distinzione tra maiuscole e minuscole), nome visualizzato, hash della password, amministratore, disattivato, preferenze (JSON: tema, dimensione del testo, unione dei doppioni), creato il, ultimo accesso
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

Regole:

- **Interessi e silenziati**: confronto per parole intere su titolo, estratto e categorie, senza badare a maiuscole e accenti. "Per te" = articoli che toccano un interesse alto o medio.
- **Doppioni**: all'arrivo, un articolo con lo stesso link normalizzato o un titolo quasi uguale a uno degli ultimi 3 giorni entra nello stesso cluster. Ogni utente vede la notizia una volta sola, con "anche su: …". Si può spegnere.
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
- **Seconda versione**: `hooks.py` contiene i punti di aggancio ("nuovi articoli arrivati" e "calcolo della pertinenza"). Nelle Impostazioni le sezioni Edizione, Notifiche e AI compaiono disattivate con "Nella prossima versione".
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
