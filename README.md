# Galactic Feed

Lettore di notizie self-hosted e multiutente. Il server raccoglie feed RSS/Atom e canali YouTube, sceglie le notizie che ti interessano con parole chiave o con l'AI e toglie i doppioni. Se vuoi, agli orari che scegli compone un'Edizione in stile giornale e ti avvisa con una notifica. Le leggi da una PWA per telefono, tablet e computer, anche offline.

- Un solo container Docker, con il server e l'app.
- Gira su PC e server (amd64), Raspberry Pi 4/5 e Mac con Apple Silicon (arm64), Raspberry Pi a 32 bit (armv7).
- I dati restano in un file SQLite nel volume `/data`.
- Interfaccia e documentazione in italiano.

Documenti: [novità delle versioni](CHANGELOG.md) · [analisi e decisioni](docs/ANALISI.md) · [architettura](docs/ARCHITETTURA.md) · [mockup](mockup/) (`python3 -m http.server 8000 --directory mockup`).

## Installazione

Serve Docker con il plugin Compose.

1. Crea una cartella, per esempio `galactic-feed`, e mettici il file [`docker-compose.yml`](docker-compose.yml) di questo repository.
2. Nel file cambia `PUBLIC_URL` con l'indirizzo da cui aprirai l'app, per esempio `https://notizie.example.org`. Serve per i link d'invito e per riconoscere le richieste che arrivano dall'app.
3. Avvia:

   ```bash
   docker compose up -d
   ```

4. Cerca il **codice di primo avvio** nel log:

   ```bash
   docker compose logs galactic-feed
   ```

   Trovi un riquadro così:

   ```
   ── Galactic Feed · primo avvio ──
   Apri https://notizie.example.org e crea l'amministratore.
   Codice di primo avvio: 291619
   ```

5. Apri l'indirizzo, inserisci il codice e crea il tuo account: sei l'amministratore. Gli altri utenti li inviti da **Impostazioni → Utenti e inviti**.

Il codice cambia a ogni riavvio finché non esiste un account. Serve solo a evitare che qualcun altro crei l'amministratore prima di te.

### Aggiornare

Le correzioni della versione che usi (per esempio da 0.6.0 a 0.6.1) arrivano con:

```bash
docker compose pull
```

```bash
docker compose up -d
```

Per passare a una versione nuova (per esempio da 0.6 a 0.7) leggi cosa cambia in [CHANGELOG.md](CHANGELOG.md), fai una copia dei dati (vedi sotto), poi cambia il numero nel `docker-compose.yml` (`galactic-feed:0.7`) e ripeti i due comandi. Il database si aggiorna da solo all'avvio. La versione in uso è scritta in fondo alle Impostazioni.

## Versioni e aggiornamenti

Le versioni sono numerate `MAGGIORE.MINORE.CORRETTIVA` ([semver](https://semver.org/lang/it/)) e sono elencate, con le novità, in [CHANGELOG.md](CHANGELOG.md) e nelle [release di GitHub](https://github.com/TehMaat/galactic-feed/releases).

| Etichetta dell'immagine | Cosa ricevi |
|---|---|
| `0.6` (consigliata) | La versione 0.6 con tutte le sue correzioni |
| `0.6.0` | Esattamente quella versione, senza aggiornamenti |
| `latest` | L'ultima modifica del ramo principale, anche prima di una release |

**Copia dei dati.** Gli aggiornamenti del database vanno solo in avanti: per tornare a una versione precedente serve la copia fatta prima. Con il volume del `docker-compose.yml`:

```bash
docker compose stop
```

```bash
docker run --rm -v galactic-feed_galactic-data:/data -v "$PWD":/backup alpine tar czf /backup/galactic-data.tar.gz -C /data .
```

```bash
docker compose start
```

Il nome del volume è quello che vedi con `docker volume ls` (di solito `<cartella>_galactic-data`).

### Backup

Tutto sta nel volume `galactic-data`: il database `galactic-feed.db` e le chiavi `secret.key` e `vapid.pem` (quest'ultima serve alle notifiche: se la perdi, ogni dispositivo deve riaccenderle). Per una copia, ferma il container e salva il volume in un archivio:

```bash
docker compose stop
```

```bash
docker run --rm -v galactic-feed_galactic-data:/data -v "$PWD":/backup debian:stable-slim tar czf /backup/galactic-feed-backup.tgz -C /data .
```

```bash
docker compose start
```

Il nome del volume dipende dalla cartella del progetto: lo vedi con `docker volume ls`.

### Usare una cartella invece del volume

Se preferisci `./data:/data`, la cartella deve appartenere all'utente del container (uid 1000), che non è root:

```bash
mkdir -p data && sudo chown -R 1000:1000 data
```

Se i permessi non vanno bene, il log lo dice con un messaggio chiaro e il comando da usare.

## Impostazioni

Quasi tutto si configura dall'app: **Amministrazione** (solo per gli amministratori) è nella barra laterale sotto Impostazioni, oppure, sul telefono, in Impostazioni → Amministrazione. Le modifiche valgono subito, senza riavviare.

- **Utenti e inviti**: inviti, nuove password, permessi, validità dei link.
- **Accesso**: durata delle sessioni con e senza «Ricordami», accesso con un provider OIDC.
- **Fonti e archivio**: per quanti giorni tenere gli articoli, ogni quanto controllare le fonti nuove, fonti della rete di casa sì o no.
- **AI**: fornitore, modello, chiave (salvata cifrata) e limite giornaliero.
- **Predefiniti per i nuovi utenti**: tema, colore, font, Edizione e orari con cui parte chi si iscrive.
- **Stato del sistema**: versione, spazio occupato, ultimo controllo dei feed, errori recenti, fuso orario.

Ogni impostazione mostra da dove arriva il valore: scelto nell'app, dalla variabile d'ambiente o predefinito. Il valore scelto nell'app vale più della variabile d'ambiente, e si può riportare al predefinito.

### Variabili d'ambiente

Si scrivono nel `docker-compose.yml`. Le prime quattro servono prima dell'avvio e si cambiano **solo** qui (poi `docker compose up -d`); le altre sono un valore iniziale, che il pannello può cambiare.

| Variabile | Predefinito | A cosa serve |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | Indirizzo pubblico dell'app (solo all'avvio) |
| `DATA_DIR` | `/data` | Cartella del database (solo all'avvio) |
| `FORWARDED_ALLOW_IPS` | `*` | Da quali indirizzi accettare gli header `X-Forwarded-*`, vedi sotto (solo all'avvio) |
| `LOG_LEVEL` | `info` | Dettaglio del log: `debug`, `info`, `warning` (solo all'avvio) |
| `PORT` | `8080` | Porta interna del container (solo all'avvio) |
| `TZ` | `Europe/Rome` | Fuso orario del log; per l'Edizione vale quello scelto nel pannello |
| `RETENTION_DAYS` | `90` | Dopo quanti giorni si cancellano gli articoli non salvati |
| `BLOCK_PRIVATE_NETWORKS` | `false` | Con `true` non si possono aggiungere fonti della rete di casa |
| `REMEMBER_DAYS` | `90` | Durata di un accesso con «Ricordami», in giorni dall'ultimo utilizzo |
| `SESSION_HOURS` | `12` | Senza «Ricordami»: dopo quante ore senza usare l'app bisogna rientrare |
| `INVITE_HOURS` | `48` | Per quante ore valgono i link d'invito e quelli per una nuova password |
| `EMERGENCY_PASSWORD_LOGIN` | `false` | Con `true` l'accesso con password resta acceso anche se l'amministratore l'ha spento (emergenza OIDC) |

## Aspetto

In Impostazioni → Aspetto ognuno sceglie tema (automatico, chiaro, scuro), colore principale, font dell'interfaccia e degli articoli e dimensione del testo. Le scelte valgono su tutti i suoi dispositivi.

- Il **colore del sistema** funziona solo dove il browser lo fa conoscere, soprattutto sui computer: su iPhone, iPad e Android una web app non può leggere i colori del sistema (per esempio Material You), quindi resta il colore predefinito.
- Il font **Sistema** usa quello del dispositivo (San Francisco su iPhone e Mac, Roboto su Android). Inter e Alta leggibilità (Atkinson Hyperlegible) sono inclusi nell'app e funzionano anche offline.

Accanto a ogni fonte compare l'icona del sito o l'avatar del canale YouTube, trovata in automatico. Dalla scheda della fonte la puoi aggiornare, sostituire con un'altra immagine o togliere per tornare alle iniziali.

## Accesso con un provider (OIDC)

Se hai già un sistema di login self-hosted, gli utenti possono entrare con quello, senza un'altra password. Funziona con Authentik, Authelia, Keycloak, Pocket ID e gli altri provider OpenID Connect. Si configura tutto dall'app, in **Amministrazione → Accesso**, senza riavviare.

1. Nel provider crea un'applicazione (client) **confidenziale** con il flusso *authorization code*. Come indirizzo di ritorno (redirect URI) registra quello mostrato nel pannello: `https://<il tuo indirizzo>/api/auth/oidc/callback`.
2. Nel pannello scrivi l'**issuer** (l'app legge da sola `/.well-known/openid-configuration`), il **client ID**, il **client secret** e il testo del pulsante, per esempio «Entra con Authentik». Poi premi **Prova la configurazione**.
3. Scegli come trattare gli utenti: crearli al primo accesso, oppure collegare quelli esistenti per email verificata o nome utente. Senza creazione automatica serve ancora un invito; poi ognuno collega il suo account da **Impostazioni → Account collegati**.
4. Facoltativo: un gruppo del provider per gli amministratori (claim `groups`, valore per esempio `galactic-admin`).

Dove trovare l'issuer:

| Provider | Issuer |
|---|---|
| Authentik | `https://auth.example.org/application/o/<slug dell'applicazione>/` |
| Authelia | `https://auth.example.org` |
| Keycloak | `https://auth.example.org/realms/<realm>` |
| Pocket ID | `https://id.example.org` |

L'accesso usa il flusso *authorization code* con PKCE, `state` e `nonce`; l'ID token si verifica con le chiavi del provider. Il client secret è salvato cifrato e l'app non lo mostra mai.

**Accesso d'emergenza.** Il login con password si può spegnere, ma solo dopo aver collegato al provider almeno un amministratore. Se poi il provider non risponde:

```bash
docker compose exec galactic-feed python -m app.emergency
```

Questo comando riaccende l'accesso con password; con `--reset <nome utente>` stampa anche un link per sceglierne una nuova. In alternativa, la variabile `EMERGENCY_PASSWORD_LOGIN=true` tiene acceso l'accesso con password finché resta impostata.

## Interessi, tag e nazioni

- **Gruppi di parole**: negli Interessi trovi gruppi pronti (Motori, Politica, Economia, Tecnologia, Videogiochi, Sport, Calcio, Scienza, Salute, Spettacolo, Cronaca). Con un tocco li accendi come interesse o per silenziare i loro articoli; puoi cambiarne le parole o creare i tuoi. L'amministratore gestisce i gruppi pronti in Amministrazione.
- **Tag delle fonti**: quando aggiungi una fonte l'app propone fino a tre tag (per esempio #Tecnologia) guardando titoli e categorie degli articoli. Li tieni, li togli o ne aggiungi altri dalla scheda della fonte; quelli che togli non tornano. Nel Flusso ogni tag ha la sua chip; in Fonti → Tag delle fonti li rinomini, colori, ordini e unisci.
- **Nazione delle fonti**: proposta dal dominio (.it, .co.uk…) e dalla lingua del feed. La cambi per te dalla scheda della fonte; l'amministratore la corregge per tutti in Amministrazione → Fonti e archivio. Con fonti di più nazioni compaiono le chip delle nazioni nel Flusso e il filtro nelle Fonti.

## Edizioni, AI e notifiche

Sono tutte facoltative e si accendono dalle Impostazioni.

- **Edizioni**: in Impostazioni → Edizioni crei una o più Edizioni, ognuna con nome, regole e uscite proprie. Le trovi in Oggi → Edizione, con un selettore se sono più di una; il Flusso resta a un tocco.
  - **Quando**: ogni giorno, in alcuni giorni della settimana (per esempio il lunedì) o una volta al mese (il giorno 1, l'ultimo giorno, il primo lunedì…), a uno o più orari, nel tuo fuso orario.
  - **Cosa**: senza regole, le notizie per te. Con le regole (tag delle fonti, cartelle, nazioni, gruppi di parole) solo quelle che le rispettano: per esempio «Politica · Italia» con #Politica e Italia, o «Videogiochi» del venerdì con il gruppo Videogiochi.
  - L'anteprima dice quante notizie avrebbe adesso; il numero massimo e il periodo coperto si scelgono per ogni Edizione.
- **AI**: la configura l'amministratore in Impostazioni → AI.
  - **Locale**: [Ollama](https://ollama.com) su un computer della tua rete. Scrivi l'indirizzo con `/v1` in fondo (per esempio `http://192.168.1.20:11434/v1`) e il nome del modello (quello che vedi con `ollama list`). I testi non escono da casa; su un Raspberry Pi è molto lento, meglio un PC.
  - **Cloud**: Anthropic (Claude) oppure OpenAI, con la chiave API del servizio. Il modello predefinito per Claude è `claude-opus-5-5`; per scegliere e riassumere notizie basta `claude-haiku-5-5`, che costa molto meno. Si paga a consumo e titoli e testi degli articoli vengono inviati al servizio.
  - Il tetto di richieste al giorno limita la spesa; «Prova il collegamento» dice subito se qualcosa non va.
  - Poi ogni utente, negli Interessi, sceglie tra parole chiave, AI o entrambi, descrive cosa gli interessa e può accendere i riassunti automatici.
- **Notifiche**: in Impostazioni → Notifiche si accendono per ogni dispositivo. Poi scegli le categorie importanti (le cartelle): ti avviso quando arriva una notizia per te, al massimo una volta ogni 10 minuti. Sull'icona dell'app compare il numero di non letti.
  - Su iPhone e iPad le notifiche arrivano solo nell'app aggiunta alla schermata Home (iOS 16.4 o successivo), e serve HTTPS.
  - Il server deve poter raggiungere i servizi push dei browser (Google, Mozilla, Apple, Microsoft) su Internet.

## Dietro un reverse proxy

Galactic Feed non gestisce HTTPS: lo fa il reverse proxy che hai già (Pangolin, Caddy, Traefik, Nginx Proxy Manager…). L'HTTPS serve, perché su iPhone e Android la PWA si installa e il service worker funziona solo con HTTPS.

1. **Inoltro**: il proxy manda le richieste a `http://<host>:8080`, o `http://galactic-feed:8080` se è nella stessa rete Docker.
2. **Header**: il proxy deve passare `Host`, `X-Forwarded-Proto` e `X-Forwarded-For`. Lo fanno quasi tutti in automatico. Con `X-Forwarded-Proto: https` il cookie di accesso diventa `Secure`. `X-Forwarded-For` dà l'indirizzo vero di chi si collega, che serve al limite dei tentativi di accesso.
3. **`FORWARDED_ALLOW_IPS`**: dice da quali indirizzi fidarsi di quegli header. Il predefinito `*` va bene se il container si raggiunge **solo** dal proxy. In quel caso, nel `docker-compose.yml`, pubblica la porta come `"127.0.0.1:8080:8080"` oppure non pubblicarla e metti proxy e app nella stessa rete Docker. Se la porta 8080 è aperta anche ad altri, scrivi l'indirizzo del proxy, per esempio `FORWARDED_ALLOW_IPS=172.18.0.5`.
4. **`PUBLIC_URL`**: deve essere l'indirizzo HTTPS completo che usi nel browser.

### Se il proxy chiede un login (per esempio l'autenticazione di Pangolin)

Galactic Feed ha già i suoi account, quindi il login del proxy non serve. Se vuoi tenerlo, lascia aperti questi indirizzi, altrimenti la PWA non si installa o non si aggiorna:

- `/manifest.webmanifest`: il browser lo scarica senza cookie;
- `/sw.js`: il service worker;
- `/icons/*`: le icone dell'app e della schermata Home.

In Pangolin si fa con le regole della risorsa: una regola "Bypass Auth" per ciascun percorso. Ricorda anche che su iPhone l'app installata ha cookie separati da Safari: la prima volta dovrai rifare il login del proxy dentro l'app.

## Installare l'app sul telefono

**iPhone e iPad** (Safari):

1. Apri l'indirizzo in Safari ed entra con il tuo account.
2. Tocca il pulsante Condividi, poi **Aggiungi alla schermata Home**, poi **Aggiungi**.
3. Apri Galactic Feed dall'icona: si apre a schermo intero, come un'app.

Su iPhone l'app non si aggiorna in background: le notizie le scarica sempre il server, e l'app le prende quando la apri. I salvati e gli ultimi 300 articoli letti restano leggibili anche offline. Quello che segni o salvi senza rete parte quando la rete torna.

**Android** (Chrome): menu ⋮, poi **Installa app** o **Aggiungi a schermata Home**.

**Computer** (Chrome, Edge): l'icona di installazione nella barra degli indirizzi.

## Immagini Docker

Le immagini sono su GitHub Container Registry: `ghcr.io/tehmaat/galactic-feed`.

- `0.6` e `0.6.0`: le versioni pubblicate (vedi «Versioni e aggiornamenti»);
- `latest`: l'ultima versione del ramo principale;
- `sha-xxxxxxx`: un commit preciso.

Le costruisce il workflow [`.github/workflows/docker.yml`](.github/workflows/docker.yml) per amd64, arm64 e armv7. Dopo la prima pubblicazione il pacchetto su GHCR è privato: per scaricarlo senza login, rendilo pubblico da GitHub, alla voce **Packages → galactic-feed → Package settings → Change visibility**.

Per costruirla da te:

```bash
docker build -t galactic-feed .
```

## Sviluppo

Python 3.12 e Node 22.

```bash
python3.12 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements-dev.txt
```

```bash
cd backend && python -m pytest
```

```bash
cd frontend && npm ci && npm test
```

```bash
cd frontend && npm run build && npx playwright test
```

### Pubblicare una versione

Il numero di versione sta solo nel file [`VERSION`](VERSION); lo script lo copia nei pacchetti e i test controllano che coincidano. Le novità si scrivono via via nella sezione «Da pubblicare» di `CHANGELOG.md`.

1. Nella PR che chiude il lavoro, prepara la versione: la sezione «Da pubblicare» prende il numero nuovo.

   ```bash
   python3 scripts/release.py bump 0.7.0
   ```

2. Fai il merge della PR su `main`. Il workflow vede che `v0.7.0` non esiste ancora: pubblica le immagini `:0.7.0` e `:0.7`, poi crea il tag e la release con le note del `CHANGELOG.md`. Nessun tag a mano.

Una versione come `0.7.0-rc.1` diventa una versione di prova: solo `:0.7.0-rc.1`, segnata come pre-release.

Per lavorare sull'interfaccia, avvia il server con `cd backend && DATA_DIR=../data python -m app`, poi `cd frontend && npm run dev`. Vite manda le chiamate `/api` al server sulla porta 8080.
