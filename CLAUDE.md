# Galactic Feed · istruzioni per Claude

## Ogni PR che cambia l'app è una versione nuova

Non aspettare che te lo chieda: in ogni PR che cambia l'app (`backend/app`, `frontend/src`, `frontend/public`, `frontend/index.html`, `Dockerfile`, dipendenze) fai tu il bump della versione, nello stesso ramo, prima di aprire o aggiornare la PR. Il job «versione» del workflow Test fallisce se te ne dimentichi.

1. Scrivi le modifiche in `CHANGELOG.md`, nella sezione `## [Da pubblicare]` (creala sotto l'introduzione se non c'è), divise in `### Novità`, `### Correzioni` e, se serve, `### Da sapere per aggiornare` (migrazioni, cambi al `docker-compose.yml`). Stesso stile delle voci già presenti: in italiano, per chi usa l'app, con il numero della issue o della PR.
2. Aggiorna il ramo con `main` (prendi il `VERSION` più recente), poi:
   - `python3 scripts/release.py bump minor` se c'è almeno una novità (0.8.0 → 0.9.0);
   - `python3 scripts/release.py bump patch` se ci sono solo correzioni (0.8.0 → 0.8.1);
   - `major` (1.0.0) solo se te lo chiede l'utente.
   Lo script aggiorna `VERSION`, i pacchetti, il `docker-compose.yml` d'esempio e trasforma «Da pubblicare» nella sezione della versione.
3. Con una versione minore o maggiore aggiorna i numeri d'esempio della serie consigliata (`0.9`, `0.9.0`, «da 0.8 a 0.9»…) nel `README.md`, in `docs/installazione.md`, `docs/aggiornare-e-backup.md` e `docs/sviluppo.md`, e scrivi in «Da sapere per aggiornare» che il `docker-compose.yml` usa la serie nuova. Controlla con `python3 scripts/release.py check` e `python3 scripts/docs.py check`.
4. Scrivi la versione nel titolo o nella descrizione della PR. Se la PR resta aperta mentre su `main` esce un'altra versione, aggiorna il ramo e rifai il bump con il numero successivo.

Al merge su `main` il workflow «Immagine Docker» pubblica le immagini, il tag `vX.Y.Z` e la release su GitHub: nessun tag a mano.

PR di soli test, documenti o workflow non cambiano versione.

## La documentazione cambia con l'app

Non aspettare che te lo chieda: ogni PR che cambia comportamento, schermate, variabili d'ambiente, installazione o workflow aggiorna, nello stesso ramo, `README.md` e le pagine di `docs/` (l'indice è `docs/README.md`). Il job «documenti» del workflow Test esegue `python3 scripts/docs.py check` e fallisce se le docs restano indietro.

- **Variabili d'ambiente**: ogni variabile letta in `backend/app` sta nella tabella di `docs/configurazione.md`, con predefinito, uso ed esempio.
- **Diagrammi**: solo immagini, mai schemi in ASCII. Si scrivono in Mermaid in `docs/diagrammi/<nome>.mmd` e si rigenerano con `python3 scripts/docs.py diagrammi` (serve Node; con un Chromium già installato `PUPPETEER_EXECUTABLE_PATH`). Nelle pagine si mostrano con `<picture>`, versione `-scuro.svg` e `-chiaro.svg`. Se non riesci a disegnarli, il workflow «Diagrammi» lo fa sulla PR.
- **Screenshot**: se cambia l'interfaccia, rigenerali con `cd frontend && npm run build && npx playwright test -c playwright.screenshots.config.js` (finiscono in `docs/img/screenshot/`); per una schermata nuova aggiungi uno `shot()` in `frontend/screenshots/screenshots.spec.js`. Dopo il merge il workflow «Screenshot» li rifà comunque e apre una PR se sono cambiati.
- **Dati inventati**: negli esempi, nelle immagini e nei dati demo niente nomi, indirizzi, email, host o chiavi veri. Domini `example.org`, IP `192.0.2.x` / `198.51.100.x` / `203.0.113.x`, persone e testate di fantasia.
- **Full Vibe Coded**: il badge resta in cima al `README.md` e a `docs/README.md`, e la pagina `docs/come-e-fatto.md` si aggiorna quando cambia il modo di lavorare (nuovi workflow, nuove regole).

## Branch

Il workflow «Pulizia dei branch» cancella i branch delle PR mergiate e, ogni settimana, quelli abbandonati (regole in `docs/sviluppo.md`, «Pulizia dei branch»). Un branch con una PR aperta o con commit negli ultimi 7 giorni non si tocca mai; per tenerne uno per sempre chiamalo `keep/…`. Se le regole cambiano nel workflow, cambiale anche nelle docs e qui.
