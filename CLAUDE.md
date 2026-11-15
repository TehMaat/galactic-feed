# Galactic Feed · istruzioni per Claude

## Ogni PR che cambia l'app è una versione nuova

Non aspettare che te lo chieda: in ogni PR che cambia l'app (`backend/app`, `frontend/src`, `frontend/public`, `frontend/index.html`, `Dockerfile`, dipendenze) fai tu il bump della versione, nello stesso ramo, prima di aprire o aggiornare la PR. Il job «versione» del workflow Test fallisce se te ne dimentichi.

1. Scrivi le modifiche in `CHANGELOG.md`, nella sezione `## [Da pubblicare]` (creala sotto l'introduzione se non c'è), divise in `### Novità`, `### Correzioni` e, se serve, `### Da sapere per aggiornare` (migrazioni, cambi al `docker-compose.yml`). Stesso stile delle voci già presenti: in italiano, per chi usa l'app, con il numero della issue o della PR.
2. Aggiorna il ramo con `main` (prendi il `VERSION` più recente), poi:
   - `python3 scripts/release.py bump minor` se c'è almeno una novità (0.8.0 → 0.9.0);
   - `python3 scripts/release.py bump patch` se ci sono solo correzioni (0.8.0 → 0.8.1);
   - `major` (1.0.0) solo se te lo chiede l'utente.
   Lo script aggiorna `VERSION`, i pacchetti, il `docker-compose.yml` d'esempio e trasforma «Da pubblicare» nella sezione della versione.
3. Con una versione minore o maggiore aggiorna nel `README.md` i numeri d'esempio della serie consigliata (`0.9`, `0.9.0`, «da 0.8 a 0.9»…) e scrivi in «Da sapere per aggiornare» che il `docker-compose.yml` usa la serie nuova. Controlla con `python3 scripts/release.py check`.
4. Scrivi la versione nel titolo o nella descrizione della PR. Se la PR resta aperta mentre su `main` esce un'altra versione, aggiorna il ramo e rifai il bump con il numero successivo.

Al merge su `main` il workflow «Immagine Docker» pubblica le immagini, il tag `vX.Y.Z` e la release su GitHub: nessun tag a mano.

PR di soli test, documenti o workflow non cambiano versione.
