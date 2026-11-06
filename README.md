# Galactic Feed

Lettore di notizie self-hosted e multiutente. Il server raccoglie feed RSS/Atom e canali YouTube, sceglie le notizie che ti interessano con parole chiave o con l'AI e toglie i doppioni. Se vuoi, agli orari che scegli compone un'Edizione in stile giornale e ti avvisa con una notifica. Le leggi da una PWA per telefono, tablet e computer, anche offline.

- Un solo container Docker, con il server e l'app.
- Gira su PC e server (amd64), Raspberry Pi 4/5 e Mac con Apple Silicon (arm64), Raspberry Pi a 32 bit (armv7).
- I dati restano in un file SQLite nel volume `/data`.
- Interfaccia e documentazione in italiano.

Documenti: [analisi e decisioni](docs/ANALISI.md) · [architettura](docs/ARCHITETTURA.md) · [mockup](mockup/) (`python3 -m http.server 8000 --directory mockup`).

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

```bash
docker compose pull
```

```bash
docker compose up -d
```

Il database si aggiorna da solo all'avvio.

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

Si impostano con le variabili d'ambiente nel `docker-compose.yml`.

| Variabile | Predefinito | A cosa serve |
|---|---|---|
| `PUBLIC_URL` | `http://localhost:8080` | Indirizzo pubblico dell'app |
| `TZ` | `Europe/Rome` | Fuso orario del server e del log |
| `RETENTION_DAYS` | `90` | Dopo quanti giorni si cancellano gli articoli non salvati |
| `BLOCK_PRIVATE_NETWORKS` | `false` | Con `true` non si possono aggiungere fonti della rete di casa |
| `REMEMBER_DAYS` | `90` | Durata di un accesso con «Ricordami», in giorni dall'ultimo utilizzo |
| `SESSION_HOURS` | `12` | Senza «Ricordami»: dopo quante ore senza usare l'app bisogna rientrare |
| `FORWARDED_ALLOW_IPS` | `*` | Da quali indirizzi accettare gli header `X-Forwarded-*` (vedi sotto) |
| `LOG_LEVEL` | `info` | Dettaglio del log (`debug`, `info`, `warning`) |
| `PORT` | `8080` | Porta interna del container |

La durata delle sessioni si cambia anche dall'app, senza riavviare: **Impostazioni → Accesso e durata delle sessioni** (solo l'amministratore). Il valore scelto lì vale più della variabile d'ambiente.

## Edizione, AI e notifiche

Sono tutte facoltative e si accendono dalle Impostazioni.

- **Edizione**: in Impostazioni → Edizione scegli uno o più orari. A ogni orario il server prepara una selezione delle notizie per te, divisa per cartelle, che trovi in Oggi → Edizione. Il Flusso resta a un tocco.
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

- `latest`: l'ultima versione del ramo principale;
- `1.2.3` e `1.2`: le versioni pubblicate con un tag `v1.2.3`;
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

Per lavorare sull'interfaccia, avvia il server con `cd backend && DATA_DIR=../data python -m app`, poi `cd frontend && npm run dev`. Vite manda le chiamate `/api` al server sulla porta 8080.
