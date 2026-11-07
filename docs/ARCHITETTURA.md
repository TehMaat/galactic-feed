# Galactic Feed · architettura della prima versione

Proposta approvata il 31/10/2026. Descrive come è fatto il codice; i requisiti sono in [ANALISI.md](ANALISI.md).

## Struttura del repository

```
backend/                  Server Python (FastAPI)
  app/
    main.py               avvio: API, PWA, scheduler
    healthcheck.py        controllo di salute usato dal container (python -m app.healthcheck)
    config.py             variabili d'ambiente (PUBLIC_URL, TZ, …) e versione (dal file VERSION)
    instance.py           impostazioni dell'istanza scelte dall'amministratore (GUI → variabile d'ambiente → predefinito)
    secretbox.py          segreti cifrati nel database (chiave dell'AI, client secret OIDC) con data/secret.key
    oidc.py               accesso con un provider OpenID Connect: configurazione, discovery, verifica dei token
    emergency.py          accesso d'emergenza: riaccende il login con password (python -m app.emergency)
    db.py + migrations/   SQLite, schema versionato con file .sql numerati
    security.py           password argon2, sessioni, protezione CSRF
    api/                  un file per area: auth, admin, folders, sources, opml, articles, interests, images
    feeds/                discovery, fetcher, parser, youtube, extract (testo completo), icons, geo (nazione e lingua), sanitize, scheduler
    reading/              matching (interessi e silenziati), presets (gruppi pronti), tagging (tag proposti), dedupe (doppioni), query, edition e schedule (Edizioni)
    ai/                   configurazione, fornitori (Ollama/OpenAI, Anthropic), filtro AI, riassunti
    push/                 Web Push (VAPID, cifratura) e regole delle notifiche
    hooks.py              agganci tra le parti: nuovi articoli, Edizione pronta
  tests/                  pytest, con feed e siti finti: nessuna chiamata a Internet
frontend/                 PWA Svelte + Vite
  src/
    styles/               base.css e app.css presi dal mockup
    lib/                  client API, stato, copertine generative, coda offline
    views/                Oggi, Fonti, Interessi, Salvati, Impostazioni, Amministrazione, Accesso, Primo avvio, Invito
    components/           Card, Row, Reader, Sheet, Page (pagine con indice), Confirm (conferme dell'app), TabBar, Chips, Toast
    sw.js                 service worker
  public/icons/
  tests/                  vitest (logica) + Playwright (prova nel browser)
Dockerfile                build in più fasi: PWA → dipendenze Python → immagine finale (utente non root, uid 1000)
docker-compose.yml
VERSION                   numero di versione (l'unico: lo legge il server, lo controllano test e workflow)
CHANGELOG.md              novità di ogni versione, usate anche per le note delle release
scripts/release.py        nuova versione (bump), controllo (check), note della release (notes)
.github/workflows/        test, build multi-architettura, release sui tag v*
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
- `users`: username (unico, senza distinzione tra maiuscole e minuscole), nome visualizzato, hash della password, amministratore (e se l'ha dato il gruppo del provider, `admin_via_group`), disattivato, preferenze (JSON: tema e varianti dello scuro e del chiaro, colore principale, font dell'interfaccia e degli articoli, dimensione del testo, unione dei doppioni, Edizione e orari, metodo e descrizione per l'AI, riassunti, cartelle importanti per le notifiche), creato il, ultimo accesso
- `sessions`: hash del token, utente, creata il, ultimo uso, scadenza, dispositivo
- `user_identities`: account del provider OIDC collegati a un utente (issuer, subject, email, nome utente)
- `oidc_states`: accessi in corso verso il provider (hash dello state, verificatore PKCE, nonce; 10 minuti, una volta sola)
- `invites`: hash del token, tipo (`invite` o `reset`), nota, creato da, utente destinatario (solo reset), scadenza, usato da, usato il

**Fonti**
- `feeds` (condivisa): url (unico), sito, titolo, tipo (rss / youtube), etag, last_modified, intervallo, prossimo controllo, ultimo controllo, ultimo successo, ultimo codice HTTP, messaggio d'errore, errori consecutivi, icona trovata in automatico e quando è stata cercata
- `folders` (per utente): nome, colore, posizione
- `subscriptions` (per utente): utente, feed, cartella, nome personalizzato, intervallo scelto, aggiunta il, icona scelta (`auto`, `custom` con l'indirizzo dell'immagine, `none` per le iniziali)

**Articoli**
- `articles` (condivisa): feed, guid, url, url normalizzato, titolo, autore, estratto, contenuto del feed, testo completo estratto, stato dell'estrazione, immagine, durata del video, pubblicato il, scaricato il, cluster dei doppioni
- `articles_fts`: indice full-text su titolo, autore, estratto e testo, insensibile agli accenti
- `user_articles` (per utente): letto il, salvato il. Nessuna riga vuol dire non letto

**Interessi**
- `interests` (per utente): parola chiave, priorità (alta / media / spento)
- `muted_words` (per utente): parola
- `preset_groups` (condivisa): gruppi di parole pronti, forniti con l'app (`builtin`, si nascondono soltanto) o aggiunti dall'amministratore
- `word_groups` e `word_group_words` (per utente): gruppi di parole propri o copiati da un gruppo pronto, spenti, accesi come interesse (con priorità) o come silenziatore
- `tags` (per utente): nome, colore, posizione, chip nel Flusso sì/no
- `source_tags` (per utente, tramite la fonte): tag della fonte con `origin` = `auto` (proposto), `user` (scelto) o `rejected` (proposto e tolto: non torna)
- `user_matches` (per utente): esito delle regole su ogni articolo (interesse o tema dell'AI e priorità, oppure silenziato; `source` dice se viene dalle parole o dall'AI; `group_id` il gruppo di parole che ha trovato l'articolo). Calcolato all'arrivo degli articoli, quando l'utente cambia le regole e quando l'AI valuta nuovi articoli, così filtri e contatori sono semplici query

**Seconda versione**
- `edition_configs` (per utente): le Edizioni, con nome, attiva sì/no, regole (tag, cartelle, nazioni, gruppi di parole), pianificazione (giornaliera, settimanale, mensile), numero massimo di notizie, periodo coperto, notifica
- `editions` ed `edition_items` (per utente): le uscite, con l'Edizione (`config_id`) e il numero dentro di lei, orario, notizie e sezioni (si tengono le ultime 60 di ogni Edizione)
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
- **Pulizia**: gli articoli più vecchi del periodo scelto nel pannello (90 giorni, oppure `RETENTION_DAYS`) vengono cancellati, tranne quelli salvati da qualcuno.

## Endpoint API

Tutti sotto `/api`; salvo `auth`, `invites` e `health` richiedono l'accesso. Gli errori hanno sempre la forma `{"detail": "messaggio in italiano"}`.

| Area | Endpoint |
|---|---|
| Accesso | `GET auth/state` · `POST auth/setup` · `POST auth/login` · `POST auth/logout` · `GET auth/oidc/start` · `GET auth/oidc/callback` · `GET`/`DELETE me/identities[/{id}]` · `GET`/`PUT admin/oidc` · `POST admin/oidc/test` |
| Inviti | `GET invites/{token}` · `POST invites/{token}/accept` (anche per il reset della password) |
| Profilo | `GET`/`PATCH me` · `POST me/password` · `GET me/sessions` · `DELETE me/sessions/{id}` |
| Admin | `GET admin/users` · `PATCH`/`DELETE admin/users/{id}` · `POST admin/users/{id}/reset` · `GET`/`POST admin/invites` · `DELETE admin/invites/{id}` · `GET admin/status` · `GET`/`PATCH admin/settings` (impostazioni dell'istanza) · `GET`/`PUT admin/defaults` (preferenze dei nuovi utenti) |
| Cartelle | `GET`/`POST folders` · `PATCH`/`DELETE folders/{id}` |
| Fonti | `POST sources/discover` · `GET`/`POST sources` · `PATCH`/`DELETE sources/{id}` · `POST sources/{id}/refresh` · `POST sources/refresh` · `PUT sources/{id}/icon` · `POST sources/{id}/icon/refresh` |
| OPML | `POST opml/import` · `GET opml/export` |
| Articoli | `GET articles` (filtri `tutti`, `perte`, `nonletti`, `video`, `salvati`, cartella, fonte, ricerca, cursore) · `GET articles/counts` · `GET articles/{id}` · `PUT`/`DELETE articles/{id}/read` · `PUT`/`DELETE articles/{id}/saved` · `POST articles/mark-read` · `POST articles/sync` |
| Interessi | `GET interests` (con gruppi e gruppi pronti) · `POST`/`PATCH`/`DELETE interests/keywords[/{id}]` · `POST`/`DELETE interests/muted[/{id}]` · `GET interests/preview` · `POST groups` · `PATCH`/`DELETE groups/{id}` |
| Tag | `GET`/`POST tags` · `PATCH`/`DELETE tags/{id}` · `PUT tags/order` · `POST tags/{id}/merge` · `PUT sources/{id}/tags` · `POST sources/{id}/tags/suggest` |
| Edizioni | `GET`/`POST edition-configs` · `PATCH`/`DELETE edition-configs/{id}` · `POST edition-configs/{id}/duplicate` · `PUT edition-configs/order` · `POST edition-configs/preview` · `GET editions/latest[?config=]` · `GET`/`DELETE editions/{id}` · `POST editions` (componi adesso) |
| Admin (2) | `GET`/`POST admin/presets` · `PATCH`/`DELETE admin/presets/{id}` (gruppi pronti) · `GET admin/feeds` · `PATCH admin/feeds/{id}` (nazione dei feed) |
| AI | `GET ai/status` · `GET`/`PUT admin/ai` · `POST admin/ai/test` · `POST articles/{id}/summary` |
| Notifiche | `GET push/key` · `GET`/`POST`/`DELETE push/subscriptions` · `POST push/test` |
| Immagini | `GET img?u=…&s=…` (proxy firmato) |
| Sistema | `GET health` |

Fuori da `/api`: la PWA, `/manifest.webmanifest`, `/sw.js`, `/icons/*`. Devono restare raggiungibili anche dietro un login del reverse proxy.

## Altre scelte

- **Primo avvio protetto**: per creare l'amministratore serve un codice di 6 cifre scritto nel log del server (`docker compose logs galactic-feed`). Il codice cambia a ogni riavvio e dopo troppi tentativi sbagliati.
- **Inviti**: link valido 48 ore, utilizzabile una volta. Lo stesso meccanismo reimposta la password di un utente.
- **Sessioni**: cookie `gf_session` HttpOnly, SameSite=Lax, Secure dietro HTTPS. Con «Ricordami» il cookie dura 90 giorni (`REMEMBER_DAYS`); senza, è un cookie di sessione che sparisce chiudendo il browser e il server chiude la sessione dopo 12 ore senza utilizzo (`SESSION_HOURS`). Entrambe le durate si rinnovano con l'uso e l'amministratore le cambia dall'app (tabella `app_settings`, chiavi `instance.*`: valore da GUI → variabile d'ambiente → predefinito, vedi `backend/app/instance.py`). Le richieste che modificano dati sono accettate solo dalla stessa origine (header `Sec-Fetch-Site` / `Origin`). Limite ai tentativi di login.
- **Fetcher**: ETag e Last-Modified, timeout 20 s, al massimo 4 download in parallelo, user agent `GalacticFeed/<versione> (+PUBLIC_URL)`, rispetto di `Retry-After`, controlli diradati in caso di errore fino a uno al giorno, messaggi d'errore chiari in italiano. L'intervallo di un feed seguito da più persone è il più breve tra quelli scelti.
- **Testo completo**: se il feed dà solo un estratto, il server estrae il testo con trafilatura all'arrivo dell'articolo. L'HTML viene ripulito: niente script, pubblicità o link per commentare.
- **YouTube**: dal link del canale o da `@nome` il server ricava il feed pubblico.
- **Immagini**: passano da un proxy firmato del server, così il service worker le può tenere offline. Il tipo si riconosce dai primi byte del file (non dall'header del sito); si servono solo immagini raster, anche `.ico`, mai SVG.
- **Icone delle fonti**: lo scheduler cerca l'icona dei feed nuovi e la ricontrolla ogni 7 giorni (`feeds/icons.py`): `<link rel="icon">` e `apple-touch-icon` della pagina del sito (prima quelle da almeno 96 px), poi `/favicon.ico`, poi `og:image`; per YouTube l'avatar del canale. Ogni candidata viene scaricata per verificare che sia un'immagine. Nell'app passano dal proxy con `k=icon`, che il service worker tiene in una cache a parte (`gf-icons`, 60 giorni). Se manca o non si carica restano le iniziali colorate. L'utente può sostituirla o spegnerla per sé dalla scheda della fonte.
- **Aspetto**: tema con le sue varianti (`data-dark`: notte, grigio, nero; `data-light`: neutro, carta; contrasti verificati da `frontend/tests/look.test.js`), colore principale (otto colori con contrasto AA verificato da `frontend/tests/look.test.js`, oppure `AccentColor` del sistema dove il browser lo dà) e font sono attributi `data-*` su `<html>` letti da `styles/base.css`. Si applicano prima di disegnare la pagina con la copia in `localStorage`. Inter e Atkinson Hyperlegible sono inclusi nell'app e precaricati dal service worker.
- **Lettore**: se l'articolo ha un'immagine principale, la prima immagine del testo si toglie quando viene prima di qualunque parola (è quasi sempre la stessa foto in un altro formato).
- **Offline**: l'interfaccia è sempre in cache; restano disponibili tutti i salvati e gli ultimi 300 articoli letti. Le azioni fatte senza rete partono al ritorno della connessione.
  - Il service worker (`src/sw.js`) tiene la copia di ogni articolo aperto (`gf-articles`) e le sue immagini (`gf-img-offline`), più l'ultima risposta di account, fonti, contatori ed elenchi (`gf-api`, `gf-lists`): prima la rete, senza rete la copia.
  - Un indice in IndexedDB dice quali articoli sono salvati e quando sono stati letti: oltre i 300 letti si tolgono i più vecchi, con le loro immagini. I salvati fatti su un altro dispositivo vengono scaricati da soli all'apertura dell'app.
  - Letto e salvato fatti senza rete vanno in una coda in IndexedDB, inviata a `POST articles/sync` quando torna la rete, quando si riapre l'app e ogni minuto. Non si usa la sincronizzazione in background dei service worker, che su iPhone non c'è.
  - All'uscita, o se entra un altro account, le copie e la coda si cancellano dal dispositivo.
- **Edizioni** (`reading/edition.py`, `reading/schedule.py`): ogni utente ne può avere più d'una. A ogni uscita (nel fuso dell'utente, o in quello dell'istanza) lo scheduler compone una selezione delle notizie pubblicate dall'uscita precedente della stessa Edizione, con un limite che dipende dalla pianificazione (2, 8 o 32 giorni). Senza regole entrano prima quelle «per te» (priorità alta in primo piano), raggruppate per cartella, e se sono meno di 3 le ultime di ogni fonte; con le regole entrano quelle che le rispettano (E tra tipi diversi, O dentro lo stesso tipo), prima quelle per te. Le date tengono conto dell'ora legale e dei mesi brevi (il 31 diventa l'ultimo giorno). Se il server era spento all'orario, l'uscita si compone appena riparte. L'Edizione delle versioni precedenti diventa «La mia Edizione» al primo uso.
- **Gruppi di parole** (`api/groups.py`, `reading/presets.py`): le parole dei gruppi accesi valgono come interessi o parole silenziate in `matching.py`; i gruppi pronti si aggiungono all'avvio solo se mancano, così le modifiche dell'amministratore restano.
- **Tag delle fonti** (`reading/tagging.py`): proposti all'aggiunta della fonte, o dallo scheduler per quelle importate con l'OPML, dai gruppi pronti che ricorrono nei titoli recenti e dalle categorie frequenti del feed.
- **Nazione e lingua** (`feeds/geo.py`): lingua dichiarata dal feed o dedotta dalle parole dei titoli; nazione dal dominio nazionale, dalla regione della lingua o dalla lingua. Vale, in quest'ordine: la scelta dell'utente (`subscriptions.country`), la correzione dell'amministratore (`feeds.country_admin`), la proposta (`feeds.country`).
- **AI** (facoltativa): la configura l'amministratore, locale (Ollama o un server compatibile con OpenAI) o cloud (Anthropic con l'SDK ufficiale, oppure OpenAI), con un tetto di richieste al giorno. Ogni utente sceglie parole chiave, AI o entrambi e descrive i suoi interessi. Lo scheduler manda al modello gli articoli delle ultime 48 ore a lotti di 20, con risposta in JSON strutturato; dopo un errore si ferma 15 minuti. Con Claude si usa effort basso e, sui modelli che lo permettono, il ripiego lato server se il modello rifiuta una richiesta. I riassunti (tre punti) si scrivono alla prima apertura di un articolo lungo e valgono per tutti.
- **Notifiche**: Web Push standard. Chiavi VAPID create al primo avvio in `data/vapid.pem`; contenuto cifrato (RFC 8291), così i servizi push dei browser non lo leggono. Si accettano solo gli indirizzi dei servizi push di Google, Mozilla, Apple e Microsoft. Per ogni utente: le notizie «per te» nelle cartelle importanti, non lette e mai notificate, in una notifica sola, al massimo una ogni 10 minuti; più, a scelta, l'Edizione pronta. Il numero di non letti va sull'icona dell'app (Badging API).
- **Reti locali**: le fonti possono stare sulla rete di casa; l'amministratore lo può vietare dal pannello (o con `BLOCK_PRIVATE_NETWORKS=true`). Il controllo vale per ogni richiesta, compresi i redirect.
- **Accesso con OIDC** (`oidc.py`, `api/oidc.py`): configurazione in `app_settings` (`oidc.*`, client secret cifrato con `secretbox.py`). Flusso authorization code con PKCE S256, `state` legato al browser con un cookie e `nonce`. L'ID token si verifica con PyJWT sulle chiavi JWKS del provider (o con il client secret per HS256): firma, `iss`, `aud`, `azp`, `exp`, `iat`, `nonce`; mai `none`. L'utente si trova per identità collegata, poi per email verificata o nome utente (se permesso, e mai verso un amministratore: l'amministratore locale resta un account a parte), oppure si crea; i gruppi del provider possono dare i permessi di amministratore e togliere solo quelli dati da loro (`users.admin_via_group`; mai l'ultimo amministratore). L'OIDC affianca gli account locali, non li sostituisce. Il login con password si spegne solo con un amministratore collegato; `EMERGENCY_PASSWORD_LOGIN` e `python -m app.emergency` lo riaccendono.
- **Impostazioni e Amministrazione come pagine**: sono sezioni dell'app con indirizzo proprio (`/impostazioni`, `/amministrazione`, componente `Page.svelte`), larghe sul computer con l'indice a sinistra. Le conferme usano una finestra dell'app (`Confirm.svelte`, `ask()` in `store.svelte.js`), non `window.confirm`, che alcune app installate non mostrano.
- **Pannello di amministrazione** (`frontend/src/views/Admin.svelte`, API `admin/*`): tutte le impostazioni dell'istanza da GUI. `instance.py` le risolve in quest'ordine: valore salvato in `app_settings` (`instance.*`) → variabile d'ambiente → predefinito; ne tiene una copia in memoria che si rinnova a ogni salvataggio, così valgono subito. Le preferenze per i nuovi utenti (`instance.user_defaults`) si copiano nell'account quando viene creato. I segreti (chiave dell'AI; poi il client secret OIDC) sono cifrati con una chiave ricavata da `data/secret.key` (`secretbox.py`) e le API non li restituiscono mai.

## Variabili d'ambiente

«Solo all'avvio»: si leggono quando il server parte e non si cambiano dal pannello. Le altre sono il valore iniziale di un'impostazione che l'amministratore può cambiare da GUI.

| Variabile | Predefinito | A cosa serve |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | Indirizzo pubblico dell'app (link d'invito, manifest, user agent). Solo all'avvio |
| `DATA_DIR` | `/data` | Cartella del database e di `secret.key`. Solo all'avvio |
| `LOG_LEVEL` | `info` | Dettaglio del log. Solo all'avvio |
| `FORWARDED_ALLOW_IPS` | `*` | Da quali indirizzi accettare gli header `X-Forwarded-*`. Solo all'avvio |
| `TZ` | `Europe/Rome` | Fuso orario del log e valore iniziale del fuso dell'istanza |
| `RETENTION_DAYS` | `90` | Giorni dopo cui si cancellano gli articoli non salvati |
| `BLOCK_PRIVATE_NETWORKS` | `false` | Vieta fonti su indirizzi della rete locale |
| `REMEMBER_DAYS` | `90` | Giorni di una sessione con «Ricordami» |
| `SESSION_HOURS` | `12` | Ore senza utilizzo dopo cui chiude una sessione senza «Ricordami» |
| `INVITE_HOURS` | `48` | Ore di validità dei link d'invito e di reimpostazione della password |
| `EMERGENCY_PASSWORD_LOGIN` | `false` | Tiene acceso l'accesso con password anche se spento dal pannello (emergenza OIDC) |
