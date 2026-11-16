# Risoluzione dei problemi

Prima di tutto guarda il log:

```bash
docker compose logs --tail 100 galactic-feed
```

e **Amministrazione → Stato del sistema**, che mostra versione, ultimo controllo dei feed ed errori recenti. Con `LOG_LEVEL: "debug"` il log dice di più (poi rimettilo a `info`).

## Installazione e avvio

**Non trovo il codice di primo avvio.** È nel log, in un riquadro «Galactic Feed · primo avvio». Cambia a ogni riavvio e dopo troppi tentativi sbagliati: usa sempre l'ultimo. Se un account esiste già, il codice non c'è più: entra con quell'account.

**Il container si ferma subito e il log parla di permessi.** Stai usando una cartella (`./data:/data`) che non appartiene all'utente del container. Il log scrive il comando giusto; di solito è `sudo chown -R 1000:1000 data`.

## Accesso

**Dopo il login torno alla pagina di accesso, o le azioni danno «Richiesta rifiutata: arriva da un sito diverso da Galactic Feed».** `PUBLIC_URL` non è l'indirizzo che usi nel browser (attenzione a `http`/`https` e alla porta), oppure il proxy non passa `Host` e `X-Forwarded-Proto`. Vedi [Dietro un reverse proxy](reverse-proxy.md).

**«Troppi tentativi».** Il limite ai tentativi di accesso conta per indirizzo. Se tutti risultano dallo stesso indirizzo (quello del proxy), il proxy non passa `X-Forwarded-For` o `FORWARDED_ALLOW_IPS` non lo accetta.

**Ho perso la password dell'amministratore.** Un altro amministratore può crearti un link per una nuova password da **Amministrazione → Utenti e inviti**. Se non c'è nessuno: `docker compose exec galactic-feed python -m app.emergency --reset <nome utente>` stampa il link.

**Il provider OIDC non risponde e il login con password è spento.** Vedi [Accesso d'emergenza](accesso-oidc.md#accesso-demergenza).

## Fonti

**«Non riesco ad aggiungere questa fonte».** Il messaggio dice perché: indirizzo senza feed, sito che blocca i programmi automatici, certificato non valido… Prova con l'indirizzo diretto del feed (spesso `/feed`, `/rss` o `/atom.xml`).

**Una fonte della rete di casa viene rifiutata.** L'amministratore ha vietato gli indirizzi privati (**Amministrazione → Fonti e archivio**, o `BLOCK_PRIVATE_NETWORKS=true`).

**Una fonte non si aggiorna più.** In Fonti compare l'errore; dopo errori ripetuti il server dirada i controlli fino a uno al giorno. Dalla scheda della fonte puoi forzare un controllo.

**Vedo solo l'estratto degli articoli.** Il sito non mette il testo nel feed e non lascia leggere le pagine (paywall o blocchi). Puoi nascondere questi articoli in **Impostazioni → Lettura**.

## App installata e notifiche

**Su iPhone non compare «Aggiungi alla schermata Home» o l'app non si installa.** Serve HTTPS e Safari. Se il proxy chiede un login, lascia aperti `/manifest.webmanifest`, `/sw.js` e `/icons/*` ([Dietro un reverse proxy](reverse-proxy.md#se-il-proxy-chiede-un-login)).

**L'app installata non mostra le novità.** Apri **Impostazioni → Informazioni → Cerca aggiornamenti**. Icona e nome sulla schermata Home di iOS cambiano solo togliendo e riaggiungendo l'app.

**Le notifiche non arrivano.** Su iPhone servono iOS 16.4 o successivo e l'app aggiunta alla schermata Home. Il server deve raggiungere i servizi push dei browser su Internet. Se hai ripristinato i dati senza `vapid.pem`, riaccendi le notifiche su ogni dispositivo. **Impostazioni → Notifiche** ha una prova.

## AI

**«Prova il collegamento» fallisce.** Con Ollama l'indirizzo deve finire con `/v1` ed essere raggiungibile dal container (non `localhost`, che dentro il container è il container stesso). Con un servizio cloud controlla chiave e nome del modello.

**L'AI ha smesso di scegliere.** Probabilmente è stato raggiunto il tetto di richieste del giorno, oppure il servizio ha dato errore: dopo un errore il server aspetta 15 minuti. L'ultimo errore è in **Amministrazione → AI**.

## Ancora niente?

Apri una [issue](https://github.com/TehMaat/galactic-feed/issues) con la versione (in **Impostazioni → Informazioni**), cosa hai fatto e le righe del log. Prima di incollarle togli indirizzi, nomi e chiavi.
