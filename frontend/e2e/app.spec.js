import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const LOG = path.join(os.tmpdir(), "galactic-feed-e2e", "server.log");
const PHONE = { width: 390, height: 844 };
const PASSWORD = "una-password-lunga";

test.describe.configure({ mode: "serial" });

let inviteUrl = "";

// Impostazioni e Amministrazione sono pagine: il contenuto sta in .page-main (a sinistra, sul
// computer, c'è anche l'indice delle sezioni).
const SETTINGS = "section[aria-label='Impostazioni'] .page-main";
const ADMIN = "section[aria-label='Amministrazione'] .page-main";

async function sheetClick(page, text) {
  await page.locator(".sheet.is-open").getByRole("button", { name: text, exact: true }).click();
}

test("primo avvio, fonti, interessi, lettura e salvati sul telefono", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Primo avvio/ })).toBeVisible();

  const code = fs.readFileSync(LOG, "utf8").match(/Codice di primo avvio: (\d{6})/)[1];
  await page.getByLabel("Codice di primo avvio").fill("000000" === code ? "111111" : "000000");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Ripeti la password").fill(PASSWORD);
  await page.getByRole("button", { name: "Crea l'account" }).click();
  await expect(page.locator(".form-error")).toContainText("Codice di primo avvio non corretto");

  await page.getByLabel("Codice di primo avvio").fill(code);
  await page.getByLabel("Il tuo nome").fill("Anna");
  await page.getByRole("button", { name: "Crea l'account" }).click();
  await expect(page.getByText("Nessuna fonte, per ora")).toBeVisible();
  await expect(page.locator(".appbar")).toContainText("galactic feed");

  // Aggiungi una fonte dal sito: il feed dei commenti non viene proposto.
  await page.getByRole("button", { name: "Aggiungi una fonte" }).click();
  await page.getByLabel("Indirizzo").fill("http://127.0.0.1:8098/");
  await sheetClick(page, "Cerca feed");
  await expect(page.locator(".found-item")).toHaveCount(1);
  await expect(page.locator(".found-item")).toContainText("Orbita");
  await sheetClick(page, "Nuova");
  await page.getByLabel("Nome della nuova cartella").fill("Spazio");
  await sheetClick(page, "Crea");
  await sheetClick(page, "Aggiungi fonte");
  await expect(page.locator(".toast")).toContainText("Orbita aggiunta a Spazio");
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(3);

  // Seconda fonte, dal feed diretto.
  await page.locator(".tabbar").getByRole("button", { name: "Fonti" }).click();
  await page.getByRole("button", { name: "Aggiungi", exact: true }).click();
  await page.getByLabel("Indirizzo").fill("http://127.0.0.1:8098/bitebyte.xml");
  await sheetClick(page, "Cerca feed");
  await sheetClick(page, "Aggiungi fonte");
  await expect(page.locator(".src-row")).toHaveCount(2);
  await expect(page.locator(".group-label").first()).toContainText("Spazio");

  // Interessi e parole silenziate.
  await page.locator(".tabbar").getByRole("button", { name: "Interessi" }).click();
  await page.getByLabel("Nuovo interesse").fill("Luna");
  await page.getByLabel("Nuovo interesse").press("Enter");
  await expect(page.locator(".tag-pair")).toContainText("Luna");
  await page.getByLabel("Nuova parola da silenziare").fill("oroscopo");
  await page.getByLabel("Nuova parola da silenziare").press("Enter");
  await expect(page.locator(".panel .tag", { hasText: "oroscopo" })).toBeVisible();

  // Flusso: per te, nascosti, ricerca.
  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(4);
  await expect(page.locator(".hidden-note")).toContainText("1 articolo nascosto");
  await page.locator(".chip", { hasText: "Per te" }).click();
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(1);
  await expect(page.locator("section[aria-label='Oggi'] .card .match")).toHaveText("Luna");
  await page.locator(".chip", { hasText: "Tutti" }).click();
  await page.getByLabel("Cerca").fill("galassia");
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(1);
  await page.getByLabel("Cerca").fill("");
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(4);

  // Lettura con il testo completo e segnalibro.
  await page.locator("section[aria-label='Oggi'] .card", { hasText: "Le PWA su iPhone" }).click();
  const reader = page.locator(".reader.is-open");
  await expect(reader.locator(".reader-title")).toHaveText("Le PWA su iPhone: cosa possono fare davvero e cosa no");
  await expect(reader.getByRole("button", { name: "Apri l'articolo originale" })).toBeVisible();
  await reader.getByRole("button", { name: "Salva" }).click();
  await expect(page.locator(".toast")).toContainText("Salvato");
  await reader.getByRole("button", { name: "Indietro" }).click();
  await expect(page.locator("section[aria-label='Oggi'] .card", { hasText: "Le PWA su iPhone" })).toHaveClass(/is-read/);
  await expect(page.locator(".tab-badge")).toHaveText("1");

  await page.locator(".tabbar").getByRole("button", { name: "Salvati" }).click();
  await expect(page.locator("[aria-label='Salvati'] .card")).toHaveCount(1);

  // Il tasto Indietro del browser chiude l'articolo.
  await page.locator("[aria-label='Salvati'] .card").click();
  await expect(page).toHaveURL(/\/salvati\?a=\d+/);
  await page.goBack();
  await expect(page.locator(".reader.is-open")).toHaveCount(0);

  // Tema scuro e invito.
  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();
  await page.getByRole("button", { name: "Impostazioni" }).click();
  await expect(page).toHaveURL(/\/impostazioni$/);
  await page.locator(SETTINGS).getByRole("button", { name: "Scuro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  // Variante del tema scuro: grigio.
  await page.locator(SETTINGS).getByRole("group", { name: "Variante del tema scuro" }).getByRole("button", { name: "Grigio" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-dark", "grigio");
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--app-bg").trim().toUpperCase())).toBe("#18181B");
  // Utenti e inviti sono nell'Amministrazione, che sul telefono si apre dalle Impostazioni.
  await page.locator(SETTINGS).getByRole("button", { name: "Amministrazione", exact: true }).click();
  await expect(page).toHaveURL(/\/amministrazione$/);
  await expect(page.locator(`${ADMIN} h2`)).toHaveText("Amministrazione");
  await page.locator(ADMIN).getByRole("button", { name: /^Utenti e inviti/ }).click();
  await page.locator(ADMIN).getByRole("button", { name: "Crea un link d'invito", exact: true }).click();
  inviteUrl = await page.locator(".link-box input").inputValue();
  expect(inviteUrl).toMatch(/\/invito\/[\w-]+$/);
});

test("un invitato crea l'account e vede solo le sue fonti", async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: PHONE });
  const page = await ctx.newPage();
  await page.goto(inviteUrl.replace("http://127.0.0.1:8097", ""));
  await expect(page.getByText("Da Anna, su Galactic Feed.")).toBeVisible();
  await page.getByLabel("Il tuo nome").fill("Bruno");
  await page.getByLabel("Nome utente").fill("bruno");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Ripeti la password").fill(PASSWORD);
  await page.getByRole("button", { name: "Crea il mio account" }).click();
  await expect(page.getByText("Nessuna fonte, per ora")).toBeVisible();
  await expect(page).toHaveURL(/\/$/);

  // Il link vale una volta sola.
  const other = await browser.newContext();
  const p2 = await other.newPage();
  await p2.goto(inviteUrl.replace("http://127.0.0.1:8097", ""));
  await expect(p2.locator(".form-error")).toContainText("non è valido");
  await ctx.close();
  await other.close();
});

test("accesso e tre colonne sul computer", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill("sbagliata!");
  await page.getByRole("button", { name: "Entra" }).click();
  await expect(page.locator(".form-error")).toHaveText("Nome utente o password non corretti.");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();

  await expect(page.locator(".reader-empty")).toContainText("Scegli un articolo");
  const nav = await page.locator(".tabbar").boundingBox();
  const list = await page.locator(".views").boundingBox();
  const reader = await page.locator(".reader").boundingBox();
  expect(nav.width).toBe(220);
  expect(list.x).toBe(220);
  expect(reader.x).toBeGreaterThanOrEqual(640);
  // Il nome dell'app in cima alla barra laterale, le Impostazioni in basso a sinistra.
  await expect(page.locator(".tabbar .nav-brand")).toHaveText("galactic feed");
  const settings = await page.getByRole("button", { name: "Impostazioni" }).boundingBox();
  expect(settings.x + settings.width).toBeLessThanOrEqual(220);
  expect(settings.y + settings.height).toBeGreaterThan(900 - 80);
  await page.locator("section[aria-label='Oggi'] .card").first().click();
  await expect(page.locator(".reader .reader-title")).toBeVisible();
  await expect(page.locator("section[aria-label='Oggi'] .card").first()).toHaveClass(/is-current/);

  // Le Fonti occupano tutta la larghezza, senza il lettore.
  await page.locator(".tabbar").getByRole("button", { name: "Fonti" }).click();
  await expect(page.locator(".reader")).toBeHidden();
});

test("la PWA si può installare", async ({ request }) => {
  const manifest = await (await request.get("/manifest.webmanifest")).json();
  expect(manifest.name).toBe("Galactic Feed");
  expect(manifest.lang).toBe("it");
  expect(manifest.display).toBe("standalone");
  for (const icon of manifest.icons) expect((await request.get(icon.src)).status()).toBe(200);
  const sw = await request.get("/sw.js");
  expect(sw.status()).toBe(200);
  expect(sw.headers()["cache-control"]).toBe("no-cache");
  expect((await request.get("/icons/apple-touch-icon.png")).status()).toBe(200);
  expect((await request.get("/icons/apple-touch-icon-dark.png")).status()).toBe(200);
});

test("l'icona della schermata Home segue il tema del sistema", async ({ page }) => {
  const icon = page.locator('link[rel="apple-touch-icon"]');
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await expect(icon).toHaveAttribute("href", "/icons/apple-touch-icon.png");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(icon).toHaveAttribute("href", "/icons/apple-touch-icon-dark.png");
  await page.goto("/");
  await expect(icon).toHaveAttribute("href", "/icons/apple-touch-icon-dark.png");
});

test("offline: salvati e letti restano leggibili, le azioni partono al ritorno della rete", async ({ page, context }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  const cards = page.locator("section[aria-label='Oggi'] .card");
  await expect(cards.first()).toBeVisible();

  // Alla prima visita il service worker si installa; dalla successiva gestisce le richieste.
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
  await page.reload();
  await expect(cards.first()).toBeVisible();

  // Un articolo letto con la rete resta sul dispositivo.
  await cards.filter({ hasText: "Come si misura la distanza" }).click();
  const reader = page.locator(".reader.is-open");
  await expect(reader.locator(".reader-title")).toHaveText("Come si misura la distanza di una galassia lontana");
  await expect(reader.locator(".offline")).toHaveText("Disponibile offline");
  await reader.getByRole("button", { name: "Indietro" }).click();

  // Il salvato (dal primo test, su un altro dispositivo) viene scaricato da solo, con l'immagine.
  const cached = (name) => page.evaluate(async (n) => (await (await caches.open(n)).keys()).length, name);
  await expect.poll(() => cached("gf-articles")).toBe(2);
  await expect.poll(() => cached("gf-img-offline")).toBe(1);

  // Senza rete l'app si apre lo stesso, con l'ultimo elenco.
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator(".offline-pill")).toBeVisible();
  await expect(cards.filter({ hasText: "Le PWA su iPhone" })).toBeVisible();

  await cards.filter({ hasText: "Come si misura la distanza" }).click();
  await expect(reader.locator(".reader-title")).toHaveText("Come si misura la distanza di una galassia lontana");
  await expect(reader.locator(".offline")).toBeVisible();
  await reader.getByRole("button", { name: "Indietro" }).click();

  // Un articolo mai aperto non c'è: lo dice in modo chiaro.
  await cards.filter({ hasText: "Docker in un mini PC" }).click();
  await expect(reader.locator(".reader-empty")).toContainText("non è sul dispositivo");
  await reader.getByRole("button", { name: "Indietro" }).click();

  // Salvati: l'articolo si legge, con la sua immagine presa dalla cache.
  await page.locator(".tabbar").getByRole("button", { name: "Salvati" }).click();
  await page.locator("[aria-label='Salvati'] .card", { hasText: "Le PWA su iPhone" }).click();
  await expect(reader.locator(".reader-title")).toHaveText("Le PWA su iPhone: cosa possono fare davvero e cosa no");
  await expect(reader.locator(".offline")).toBeVisible();
  const image = reader.locator("img.thumb");
  await expect(image).toHaveAttribute("src", /^\/api\/img\?/);
  await expect.poll(() => image.evaluate((img) => img.complete && img.naturalWidth)).toBeGreaterThan(0);

  // Tolto dai salvati senza rete: l'azione resta in coda...
  await reader.getByRole("button", { name: "Rimuovi dai salvati" }).click();
  await expect(page.locator(".toast")).toContainText("appena torna la rete");
  const savedOnServer = async () => (await (await page.request.get("/api/articles?view=salvati")).json()).items.length;
  expect(await savedOnServer()).toBe(1);

  // ...e parte da sola quando torna la rete.
  await context.setOffline(false);
  await expect.poll(savedOnServer).toBe(0);
  await expect(page.locator(".offline-pill")).toHaveCount(0);
});

test("Edizione: si accende dalle Impostazioni e si compone", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await expect(page.locator("section[aria-label='Oggi'] .card").first()).toBeVisible();

  // Impostazioni → Edizioni: «Crea la tua Edizione» apre la sua scheda (ogni giorno alle 07:30).
  await page.getByRole("button", { name: "Impostazioni" }).click();
  await page.locator(SETTINGS).getByRole("button", { name: "Crea la tua Edizione" }).click();
  const edSheet = page.locator(".sheet.is-open");
  await expect(edSheet.locator("h3")).toHaveText("La mia Edizione");
  await expect(edSheet.locator(".tag.mono")).toHaveText(["07:30"]);
  await edSheet.getByLabel("Nuovo orario").fill("21:15");
  await edSheet.getByRole("button", { name: "Orario", exact: true }).click();
  await expect(edSheet.locator(".tag.mono")).toHaveText(["07:30", "21:15"]);
  await expect(edSheet.locator(".preview")).toContainText("con queste regole");
  await edSheet.getByRole("button", { name: "Chiudi" }).click();
  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();

  // La prima la compone il server al giro successivo; qui la chiediamo subito.
  const oggi = page.locator("section[aria-label='Oggi']");
  await expect(oggi.getByRole("tab", { name: "Edizione" })).toHaveAttribute("aria-selected", "true");
  const compose = oggi.getByRole("button", { name: "Componi adesso" });
  if (await compose.isVisible()) await compose.click();
  await expect(oggi.locator(".masthead")).toContainText("n. 1");
  await expect(oggi.locator(".hero .hero-title")).toHaveText("Perché le prossime missioni lunari puntano tutte al polo sud");
  await oggi.locator(".hero").click();
  await expect(page.locator(".reader.is-open .reader-title")).toHaveText("Perché le prossime missioni lunari puntano tutte al polo sud");
  await page.locator(".reader.is-open").getByRole("button", { name: "Indietro" }).click();
  await expect(oggi.locator(".hero")).toHaveClass(/is-read/);

  // Una seconda Edizione, settimanale, con una regola: compare il selettore in Oggi.
  await page.getByRole("button", { name: "Impostazioni" }).click();
  await page.locator(SETTINGS).getByRole("button", { name: "Nuova Edizione" }).click();
  await edSheet.getByLabel("Nome").fill("Spazio del lunedì");
  await edSheet.getByLabel("Nome").press("Enter");
  await edSheet.getByLabel("Nome").blur();
  await expect(page.locator(".toast")).toContainText("Nome aggiornato");
  await edSheet.getByRole("group", { name: "Ricorrenza" }).getByRole("button", { name: "Ogni settimana" }).click();
  await expect(edSheet.locator(".hint").first()).toContainText("lunedì alle 07:30");
  await edSheet.getByRole("group", { name: "Giorni della settimana" }).getByRole("button", { name: "venerdì" }).click();
  await expect(edSheet.locator(".hint").first()).toContainText("lunedì e venerdì alle 07:30");
  await edSheet.getByRole("button", { name: "Spazio", exact: true }).click();
  await expect(edSheet.locator(".preview")).toContainText("con queste regole");
  await edSheet.getByRole("button", { name: "Componi adesso" }).click();
  await expect(oggi.getByRole("tablist", { name: "Edizioni" }).getByRole("tab")).toHaveText(["Spazio del lunedì", "La mia Edizione"]);
  await expect(oggi.locator(".masthead .mast-kicker")).toHaveText("Spazio del lunedì · n. 1");
  await oggi.getByRole("tablist", { name: "Edizioni" }).getByRole("tab", { name: "La mia Edizione" }).click();
  await expect(oggi.locator(".masthead .mast-kicker")).toHaveText("La mia Edizione · n. 1");

  // Un'uscita si elimina da Oggi, un'Edizione dalle Impostazioni: con la conferma dell'app,
  // non quella del browser (che alcune app installate non mostrano).
  await oggi.getByRole("tablist", { name: "Edizioni" }).getByRole("tab", { name: "Spazio del lunedì" }).click();
  await expect(oggi.locator(".masthead .mast-kicker")).toHaveText("Spazio del lunedì · n. 1");
  await oggi.getByRole("button", { name: "Elimina questa uscita" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Eliminare «Spazio del lunedì» n. 1?");
  await page.getByRole("alertdialog").getByRole("button", { name: "Elimina" }).click();
  await expect(page.locator(".toast")).toContainText("Uscita eliminata");
  await expect(oggi.locator(".masthead")).toHaveCount(0);
  await page.getByRole("button", { name: "Impostazioni" }).click();
  await page.locator(SETTINGS).getByRole("button", { name: "Elimina l'Edizione Spazio del lunedì" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Annulla" }).click();
  await expect(page.locator(SETTINGS).locator(".preset-name b")).toHaveText(["La mia Edizione", "Spazio del lunedì"]);
  await page.locator(SETTINGS).getByRole("button", { name: "Elimina l'Edizione Spazio del lunedì" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Elimina" }).click();
  await expect(page.locator(".toast")).toContainText("«Spazio del lunedì» eliminata");
  await expect(page.locator(SETTINGS).locator(".preset-name b")).toHaveText(["La mia Edizione"]);
  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();
  await expect(oggi.locator(".masthead .mast-kicker")).toContainText("n. 1");

  // Il Flusso resta a un tocco.
  await oggi.getByRole("tab", { name: "Flusso" }).click();
  await expect(oggi.locator(".card").first()).toBeVisible();
});

test("AI: l'amministratore la configura, sceglie le notizie e scrive i riassunti", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await expect(page.locator(".tabbar")).toBeVisible();

  // Impostazioni → AI → Fornitore apre l'AI del pannello Amministrazione: Ollama (qui un finto servizio sul sito di prova).
  await page.getByRole("button", { name: "Impostazioni" }).click();
  await page.locator(SETTINGS).getByRole("button", { name: /Fornitore/ }).click();
  const sheet = page.locator(ADMIN);
  await expect(sheet.locator("h2")).toHaveText("AI");
  await sheet.getByRole("button", { name: "Locale" }).click();
  await sheet.getByLabel("Indirizzo").fill("http://127.0.0.1:8098/v1");
  await sheet.getByLabel("Modello").fill("finto");
  await sheet.getByRole("button", { name: "Prova il collegamento" }).click();
  await expect(sheet.locator(".form-ok")).toContainText("Il modello finto risponde");

  // Interessi: scelta con l'AI e descrizione.
  await page.locator(".tabbar").getByRole("button", { name: "Interessi" }).click();
  const interessi = page.locator("section[aria-label='Interessi']");
  await interessi.getByRole("button", { name: "AI", exact: true }).click();
  await interessi.getByLabel("Descrizione degli interessi per l'AI").fill("Astronomia e cosmologia");
  await interessi.getByRole("button", { name: "Salva la descrizione" }).click();
  await expect(page.locator(".toast")).toContainText("Descrizione salvata");

  // Lo scheduler valuta gli articoli subito: in «Per te» arriva quello sulla galassia.
  await expect.poll(async () => {
    const r = await (await page.request.get("/api/articles?view=perte")).json();
    return r.items.map((a) => `${a.title} · ${a.match.keyword}`);
  }, { timeout: 20_000 }).toEqual(["Come si misura la distanza di una galassia lontana · astronomia"]);

  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();
  const oggi = page.locator("section[aria-label='Oggi']");
  await oggi.getByRole("tab", { name: "Flusso" }).click();
  await oggi.locator(".chip", { hasText: "Per te" }).click();
  await expect(oggi.locator(".card")).toHaveCount(1);
  await expect(oggi.locator(".card .match")).toHaveText("astronomia");

  // Riassunto automatico in cima all'articolo.
  await oggi.locator(".card").click();
  await expect(page.locator(".reader .ai-summary li")).toHaveText(["Si misura con la parallasse.", "Poi con le Cefeidi.", "Infine con il redshift."]);
});

test("notifiche: il service worker riceve il messaggio push", async ({ page, context }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));

  // Le impostazioni delle notifiche ci sono; l'iscrizione vera richiede il servizio push di Google.
  await page.getByRole("button", { name: "Impostazioni" }).click();
  await expect(page.getByRole("switch", { name: "Notifiche su questo dispositivo" })).toBeVisible();
  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();

  // Un messaggio push consegnato al service worker come farebbe il browser.
  const cdp = await context.newCDPSession(page);
  const registration = new Promise((resolve) =>
    cdp.on("ServiceWorker.workerRegistrationUpdated", ({ registrations }) => {
      const r = registrations.find((x) => x.scopeURL === "http://127.0.0.1:8097/" && !x.isDeleted);
      if (r) resolve(r.registrationId);
    }),
  );
  await cdp.send("ServiceWorker.enable");
  const registrationId = await registration;
  await page.evaluate(() => navigator.serviceWorker.addEventListener("message", (e) => (window.__gfPush = e.data.data)));
  const payload = { title: "Orbita", body: "Una notizia per te", url: "/?a=1", tag: "art-1", badge: 3 };
  await cdp.send("ServiceWorker.deliverPushMessage", { origin: "http://127.0.0.1:8097", registrationId, data: JSON.stringify(payload) });
  // L'app aperta riceve il messaggio dal service worker (la notifica di sistema, in questo
  // browser senza schermo, non si può mostrare).
  await expect.poll(() => page.evaluate(() => window.__gfPush || null)).toEqual(payload);
});

test("icone delle fonti, logo, «Ricordami» e aspetto", async ({ browser }) => {
  // Senza «Ricordami» il cookie sparisce chiudendo il browser.
  const once = await browser.newContext({ viewport: PHONE, locale: "it-IT" });
  const p1 = await once.newPage();
  await p1.goto("/");
  await p1.getByLabel("Nome utente").fill("anna");
  await p1.getByLabel("Password").fill(PASSWORD);
  await expect(p1.getByLabel(/Ricordami/)).not.toBeChecked();
  await p1.getByRole("button", { name: "Entra" }).click();
  await expect(p1.locator(".appbar")).toBeVisible();
  expect((await once.cookies()).find((c) => c.name === "gf_session").expires).toBe(-1);
  await once.close();

  const ctx = await browser.newContext({ viewport: PHONE, locale: "it-IT" });
  const page = await ctx.newPage();
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByLabel(/Ricordami/).check();
  await page.getByRole("button", { name: "Entra" }).click();
  await expect(page.locator(".appbar")).toBeVisible();
  const cookie = (await ctx.cookies()).find((c) => c.name === "gf_session");
  expect(cookie.expires - Date.now() / 1000).toBeGreaterThan(89 * 86400);

  // Le icone dei siti al posto delle iniziali, in Oggi (qui l'Edizione, accesa da un test precedente) e nelle Fonti.
  await expect(page.locator("section[aria-label='Oggi'] img.mono-av.is-icon").first()).toBeVisible();
  await page.locator(".tabbar").getByRole("button", { name: "Fonti" }).click();
  await expect(page.locator(".src-row img.src-av.is-icon")).toHaveCount(2);
  await page.getByRole("button", { name: "Fonte Orbita" }).click();
  await sheetClick(page, "Iniziali");
  await expect(page.locator(".toast")).toContainText("Ora mostra le iniziali");
  await expect(page.locator(".src-row").filter({ hasText: "Orbita" }).locator("span.src-av")).toBeVisible();
  await sheetClick(page, "Automatica");
  await expect(page.locator(".src-row").filter({ hasText: "Orbita" }).locator("img.src-av")).toBeVisible();
  await page.keyboard.press("Escape");

  // Il logo riporta a Oggi.
  await page.locator(".appbar").getByRole("link", { name: /vai a Oggi/ }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator("section[aria-label='Oggi']")).toBeVisible();

  // Colore e font: si vedono subito e restano dopo aver ricaricato la pagina.
  await page.getByRole("button", { name: "Impostazioni" }).click();
  // In fondo alle Impostazioni c'è la versione in uso (dal file VERSION).
  const version = fs.readFileSync(path.join(path.dirname(new URL(import.meta.url).pathname), "..", "..", "VERSION"), "utf8").trim();
  await expect(page.locator(`${SETTINGS} .app-version`)).toHaveText(`Galactic Feed versione ${version}`);
  // Si aspetta che ogni scelta arrivi al server prima di ricaricare la pagina.
  const saved = () => page.waitForResponse((r) => r.url().endsWith("/api/me") && r.request().method() === "PATCH");
  let save = saved();
  await page.locator(SETTINGS).getByRole("button", { name: "Viola", exact: true }).click();
  await save;
  save = saved();
  await page.getByRole("group", { name: "Font", exact: true }).getByRole("button", { name: "Sistema" }).click();
  await save;
  // Il colore vero dipende dal tema in uso: variante chiara o scura del viola.
  const look = () => page.evaluate(() => {
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark" || (root.dataset.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
    const color = getComputedStyle(root).getPropertyValue("--accent").trim().toUpperCase();
    return { accent: root.dataset.accent, font: root.dataset.font, ok: color === (dark ? "#C9A3FF" : "#8141C3") };
  });
  await expect.poll(look).toEqual({ accent: "viola", font: "sistema", ok: true });
  await page.reload();
  expect(await look()).toEqual({ accent: "viola", font: "sistema", ok: true });
  await ctx.close();
});

test("pannello di amministrazione: impostazioni dell'istanza e predefiniti", async ({ page, browser }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();

  // Sul computer la voce è nella barra laterale, sotto Impostazioni.
  const nav = page.locator(".tabbar");
  const settingsBox = await nav.getByRole("button", { name: "Impostazioni" }).boundingBox();
  const adminBox = await nav.getByRole("button", { name: "Amministrazione" }).boundingBox();
  expect(adminBox.y).toBeGreaterThan(settingsBox.y);
  await nav.getByRole("button", { name: "Amministrazione" }).click();
  // Sul computer è una pagina larga, con l'indice delle sezioni a sinistra e senza il lettore.
  await expect(page.locator(".reader")).toBeHidden();
  const admin = page.locator("section[aria-label='Amministrazione']");
  expect((await admin.boundingBox()).width).toBeGreaterThan(1000);
  await expect(admin.locator(".page-nav")).toBeVisible();
  const sheet = page.locator(ADMIN);

  // Fonti e archivio: il valore cambia subito e si può riportare al predefinito.
  await sheet.getByRole("button", { name: /^Fonti e archivio/ }).click();
  await sheet.getByLabel("Conserva gli articoli").selectOption("30");
  await expect(page.locator(".toast")).toContainText("Conserva gli articoli: 30 giorni");
  await expect(sheet.getByText("Scelto qui.")).toBeVisible();
  await sheet.getByRole("button", { name: "Torna al valore predefinito" }).click();
  await expect(sheet.getByLabel("Conserva gli articoli")).toHaveValue("90");

  // Predefiniti per i nuovi utenti: tema scuro.
  await sheet.getByRole("button", { name: "Indietro" }).click();
  await sheet.getByRole("button", { name: /^Predefiniti per i nuovi utenti/ }).click();
  await sheet.getByRole("group", { name: "Tema predefinito" }).getByRole("button", { name: "Scuro" }).click();
  await expect(page.locator(".toast")).toContainText("vale per i nuovi utenti");

  // Stato del sistema: versione e variabili che restano solo all'avvio.
  await sheet.getByRole("button", { name: "Indietro" }).click();
  await sheet.getByRole("button", { name: /^Stato del sistema/ }).click();
  await expect(sheet.getByText("PUBLIC_URL")).toBeVisible();
  await expect(sheet.getByText("FORWARDED_ALLOW_IPS")).toBeVisible();

  // Chi non è amministratore non vede la voce.
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "it-IT" });
  const other = await ctx.newPage();
  await other.goto("/");
  await other.getByLabel("Nome utente").fill("bruno");
  await other.getByLabel("Password").fill(PASSWORD);
  await other.getByRole("button", { name: "Entra" }).click();
  await expect(other.locator(".tabbar").getByRole("button", { name: "Impostazioni" })).toBeVisible();
  await expect(other.locator(".tabbar").getByRole("button", { name: "Amministrazione" })).toHaveCount(0);
  await ctx.close();
});

test("gruppi di parole: un gruppo pronto acceso come interesse con un tocco", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await page.locator(".tabbar").getByRole("button", { name: "Interessi" }).click();
  const interessi = page.locator("section[aria-label='Interessi']");
  // Un test precedente ha scelto l'AI: qui servono le parole chiave.
  await interessi.getByRole("group", { name: "Metodo di selezione" }).getByRole("button", { name: "Parole chiave" }).click();
  // Il gruppo pronto «Scienza» acceso come interesse, con una parola in più.
  await interessi.getByRole("group", { name: "Gruppo Scienza" }).getByRole("button", { name: "Interesse" }).click();
  await expect(page.locator(".toast")).toContainText("Scienza: acceso come interesse");
  await interessi.getByRole("button", { name: /^Scienza/ }).click();
  await expect(interessi.getByRole("button", { name: "Togli astronomia da Scienza" })).toBeVisible();
  await interessi.getByLabel("Nuova parola per Scienza").fill("galassia");
  await interessi.getByLabel("Nuova parola per Scienza").press("Enter");
  await expect(page.locator(".toast")).toContainText("«galassia» aggiunta a Scienza");
  // Nel Flusso «Per te» l'articolo mostra il gruppo e la parola trovata.
  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();
  const oggi = page.locator("section[aria-label='Oggi']");
  if (await oggi.getByRole("tab", { name: "Flusso" }).count()) await oggi.getByRole("tab", { name: "Flusso" }).click();
  await oggi.getByRole("button", { name: /^Per te/ }).click();
  await expect(oggi.locator(".card").filter({ hasText: "galassia lontana" }).locator(".match")).toContainText("Scienza · galassia");
  // Spento di nuovo, per non cambiare gli altri test.
  await page.locator(".tabbar").getByRole("button", { name: "Interessi" }).click();
  await interessi.getByRole("group", { name: "Gruppo Scienza" }).getByRole("button", { name: "Spento" }).click();
  await expect(page.locator(".toast")).toContainText("Scienza: spento");
});

test("tag delle fonti: assegnati dalla scheda e usati come filtro nel Flusso", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await page.locator(".tabbar").getByRole("button", { name: "Fonti" }).click();
  await page.getByRole("button", { name: "Fonte Orbita" }).click();
  const sheet = page.locator(".sheet.is-open");
  await sheet.getByLabel("Nuovo tag per questa fonte").fill("Astronomia");
  await sheet.getByLabel("Nuovo tag per questa fonte").press("Enter");
  await expect(page.locator(".toast")).toContainText("Tag #Astronomia aggiunto");
  await expect(sheet.getByRole("button", { name: "Togli il tag Astronomia" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".src-row").filter({ hasText: "Orbita" }).locator(".src-tag")).toHaveText(["Astronomia"]);

  // Nel Flusso c'è la chip del tag: mostra solo gli articoli delle sue fonti.
  await page.locator(".tabbar").getByRole("button", { name: "Oggi" }).click();
  const oggi = page.locator("section[aria-label='Oggi']");
  if (await oggi.getByRole("tab", { name: "Flusso" }).count()) await oggi.getByRole("tab", { name: "Flusso" }).click();
  await oggi.getByRole("button", { name: /Astronomia/ }).click();
  await expect(oggi.locator(".card").first()).toBeVisible();
  for (const src of await oggi.locator(".card .meta .src").allTextContents()) expect(src).toBe("Orbita");

  // Gestione dei tag: la chip si può togliere dal Flusso.
  await page.locator(".tabbar").getByRole("button", { name: "Fonti" }).click();
  await page.getByRole("button", { name: /Tag delle fonti/ }).click();
  await page.locator(".sheet.is-open").getByRole("switch", { name: "Mostra #Astronomia nel Flusso" }).click();
  await expect(page.locator(".toast")).toContainText("#Astronomia non è più nel Flusso");
});

test("accesso con un provider OIDC configurato dal pannello", async ({ page, browser }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await page.locator(".tabbar").getByRole("button", { name: "Amministrazione" }).click();
  // L'accesso con OIDC ha la sua voce, raggiungibile anche dall'indice a sinistra.
  await page.locator("section[aria-label='Amministrazione'] .page-nav").getByRole("button", { name: "Accesso con OIDC" }).click();
  const sheet = page.locator(ADMIN);
  await expect(sheet.locator(".oidc-intro")).toContainText("Non sostituisce gli account locali");
  await sheet.getByRole("switch", { name: "Accesso con il provider" }).click();
  await sheet.getByLabel("Issuer").fill("http://127.0.0.1:8098/oidc");
  await sheet.getByLabel("Client ID").fill("galactic-e2e");
  await sheet.getByLabel("Client secret").fill("segreto-e2e");
  await sheet.getByLabel("Testo del pulsante").fill("Entra con Prova");
  await sheet.getByRole("switch", { name: "Crea gli utenti al primo accesso" }).click();
  await expect(sheet.getByLabel("Indirizzo di ritorno (da copiare nel provider)")).toHaveValue("http://127.0.0.1:8097/api/auth/oidc/callback");
  await sheet.getByRole("button", { name: "Prova la configurazione" }).click();
  await expect(sheet.locator(".form-ok")).toContainText("Il provider risponde");
  // Il client secret salvato non torna indietro.
  await expect(sheet.getByLabel("Client secret")).toHaveValue("");

  // Un nuovo utente entra con il pulsante: il provider lo rimanda all'app, già dentro.
  const ctx = await browser.newContext({ viewport: PHONE, locale: "it-IT" });
  const other = await ctx.newPage();
  await other.goto("/");
  await other.getByRole("link", { name: "Entra con Prova" }).click();
  await expect(other.locator(".appbar")).toBeVisible();
  await expect(other).toHaveURL(/127\.0\.0\.1:8097\/$/);
  await other.getByRole("button", { name: "Impostazioni" }).click();
  await expect(other.locator(`${SETTINGS} .who`)).toContainText("Olivia Bianchi");
  await ctx.close();
});
