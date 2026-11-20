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

// Sul telefono, scorrendo, le barre escono dallo schermo (#36): il focus le fa ricomparire,
// come quando ci si arriva con la tastiera.
async function barClick(button) {
  await button.focus();
  await button.click();
}

// Su telefono e tablet la Dock ha Oggi, Notiziario (con le Edizioni), Cerca e Profilo; Fonti,
// Interessi, Salvati, Impostazioni e Amministrazione si aprono dal Profilo (#64). Sul computer
// sono tutte nella barra in alto (#65).
async function tab(page, name) {
  if ((page.viewportSize()?.width || 0) >= 1100) {
    const nav = page.locator(".tabbar");
    if (name === "Impostazioni") return nav.locator(".nav-settings").click();
    if (name === "Amministrazione") return nav.locator(".nav-admin").click();
    if (name === "Cerca") return nav.locator(".nav-search").click();
    if (name === "Profilo") return nav.locator(".nav-me").click();
    return nav.getByRole("button", { name: new RegExp(`^${name}`) }).click();
  }
  const dock = page.locator(".dock");
  if (["Oggi", "Notiziario", "Cerca", "Profilo"].includes(name)) return barClick(dock.getByRole("button", { name, exact: true }));
  await barClick(dock.getByRole("button", { name: "Profilo", exact: true }));
  // «Impostazioni» nel Profilo scorre alle sezioni qui sotto (#81). Si entra da «Cerca nelle
  // impostazioni», che apre la pagina in cima senza scorrere: una sezione la farebbe scorrere in giù
  // e le barre uscirebbero (#36). Poi il cursore lascia il campo.
  if (name === "Impostazioni") {
    await page.locator(".profilo-settings").getByRole("button", { name: "Cerca nelle impostazioni" }).click();
    const search = page.locator(".settings-search.main input");
    await expect(search).toBeFocused();
    return search.blur();
  }
  await page.locator(".shortcuts").getByRole("button", { name: new RegExp(`^${name}`) }).click();
}

// Un preset del Notiziario (#68), dalla riga sopra le notizie.
async function preset(page, name) {
  await page.locator(".preset-row").getByRole("button", { name: new RegExp(`^${name}`) }).click();
  await expect(page.locator(".preset-row").getByRole("button", { name: new RegExp(`^${name}`) })).toHaveAttribute("aria-pressed", "true");
}

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
  // Il Notiziario parte da «Per te» (#69): senza interessi è vuoto e lo dice; «Tutte» le mostra.
  await expect(page.locator("section[aria-label='Oggi']")).toContainText("Ancora niente per te");
  await preset(page, "Tutte");
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(3);
  await expect(page.locator("#h-notiziario + .sec-sub")).toHaveText("3 notizie · 3 da leggere");

  // Seconda fonte, dal feed diretto. Sul telefono la Dock ha Oggi, Cerca e Profilo (senza Edizioni
  // niente «Notiziario»); Fonti si apre dal Profilo.
  await expect.poll(() => page.locator(".dock button").evaluateAll((b) => b.map((x) => x.getAttribute("aria-label")))).toEqual(["Oggi", "Cerca", "Profilo"]);
  await tab(page, "Fonti");
  await expect(page).toHaveURL(/\/fonti$/);
  await expect(page.locator(".dock").getByRole("button", { name: "Profilo" })).toHaveAttribute("aria-current", "page");
  // «Indietro» riporta al Profilo.
  await page.locator("section[aria-label='Fonti']").getByRole("button", { name: "Indietro" }).click();
  await expect(page).toHaveURL(/\/profilo$/);
  await page.locator(".shortcuts").getByRole("button", { name: /^Fonti/ }).click();
  await page.getByRole("button", { name: "Aggiungi", exact: true }).click();
  await page.getByLabel("Indirizzo").fill("http://127.0.0.1:8098/bitebyte.xml");
  await sheetClick(page, "Cerca feed");
  await sheetClick(page, "Aggiungi fonte");
  await expect(page.locator(".src-row")).toHaveCount(2);
  await expect(page.locator(".group-label").first()).toContainText("Spazio");

  // La cartella si modifica dal suo titolo, con la matita (#33).
  await page.getByRole("button", { name: "Modifica la cartella Spazio" }).click();
  await expect(page.locator(".sheet.is-open")).toContainText("Elimina la cartella");
  await page.locator(".sheet.is-open").getByLabel("Nome").fill("Cosmo");
  await sheetClick(page, "Salva");
  await expect(page.locator(".toast")).toContainText("Cartella aggiornata");
  await expect(page.locator(".group-label").first()).toContainText("Cosmo");
  // Di nuovo «Spazio», che serve più avanti.
  await page.getByRole("button", { name: "Modifica la cartella Cosmo" }).click();
  await page.locator(".sheet.is-open").getByLabel("Nome").fill("Spazio");
  await sheetClick(page, "Salva");
  await expect(page.getByRole("button", { name: "Modifica la cartella Spazio" })).toBeVisible();

  // Interessi e parole silenziate.
  await tab(page, "Interessi");
  await page.getByLabel("Nuovo interesse").fill("Luna");
  await page.getByLabel("Nuovo interesse").press("Enter");
  await expect(page.locator(".tag-pair")).toContainText("Luna");
  await page.getByLabel("Nuova parola da silenziare").fill("oroscopo");
  await page.getByLabel("Nuova parola da silenziare").press("Enter");
  await expect(page.locator(".panel .tag", { hasText: "oroscopo" })).toBeVisible();

  // Il cerchio con la «i» spiega come funzionano i doppioni.
  await page.getByRole("button", { name: "Come funzionano i doppioni" }).click();
  const help = page.getByRole("alertdialog", { name: "Come funzionano i doppioni" });
  await expect(help).toContainText("pubblicato per primo");
  await expect(help.getByRole("button", { name: "Annulla" })).toHaveCount(0);
  await help.getByRole("button", { name: "Ho capito" }).click();
  await expect(help).toBeHidden();

  // Notiziario: per te, nascosti; la ricerca è in Cerca.
  await tab(page, "Oggi");
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(4);
  await expect(page.locator(".hidden-note")).toContainText("1 articolo nascosto");
  await preset(page, "Per te");
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(1);
  await expect(page.locator("section[aria-label='Oggi'] .card .card-title")).toContainText(/lun/i);
  await preset(page, "Tutte");
  await tab(page, "Cerca");
  const cerca = page.locator("section[aria-label='Cerca']");
  await cerca.getByLabel("Cerca negli articoli e nelle fonti").fill("galassia");
  await expect(cerca.locator(".card")).toHaveCount(1);
  await expect(cerca.locator(".sec-sub")).toHaveText("1 notizia · 1 da leggere");
  await tab(page, "Oggi");
  await expect(page.locator("section[aria-label='Oggi'] .card")).toHaveCount(4);

  // Lettura con il testo completo e segnalibro.
  await page.locator("section[aria-label='Oggi'] .card", { hasText: "Le PWA su iPhone" }).click();
  const reader = page.locator(".reader.is-open");
  await expect(reader.locator(".reader-title")).toHaveText("Le PWA su iPhone: cosa possono fare davvero e cosa no");
  // Pulsanti essenziali (#9): in fondo un solo «Leggi su …», il resto nel menu «Altre azioni».
  await expect(reader.getByRole("button", { name: "Leggi su Bit & Byte" })).toBeVisible();
  await reader.getByRole("button", { name: "Altre azioni" }).click();
  const menu = reader.getByRole("menu", { name: "Altre azioni" });
  await expect(menu.getByRole("menuitem")).toContainText(["Apri l'originale", "Segna come non letto"]);
  await menu.getByRole("menuitemradio", { name: "Testo grande" }).click();
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.querySelector(".app")).getPropertyValue("--ts").trim())).toBe("1.12");
  await menu.getByRole("menuitemradio", { name: "Testo standard" }).click();
  await reader.getByRole("button", { name: "Altre azioni" }).click();
  await expect(menu).toHaveCount(0);
  await reader.getByRole("button", { name: "Salva" }).click();
  await expect(page.locator(".toast")).toContainText("Salvato");
  await reader.getByRole("button", { name: "Indietro" }).click();
  await expect(page.locator("section[aria-label='Oggi'] .card", { hasText: "Le PWA su iPhone" })).toHaveClass(/is-read/);
  await expect(page.locator("#h-notiziario + .sec-sub")).toHaveText("4 notizie · 3 da leggere");

  await tab(page, "Profilo");
  await expect(page.locator(".shortcuts").getByRole("button", { name: /^Salvati/ })).toContainText("1");
  await page.locator(".shortcuts").getByRole("button", { name: /^Salvati/ }).click();
  await expect(page.locator("[aria-label='Salvati'] .card")).toHaveCount(1);

  // Il tasto Indietro del browser chiude l'articolo.
  await page.locator("[aria-label='Salvati'] .card").click();
  await expect(page).toHaveURL(/\/salvati\?a=\d+/);
  await page.goBack();
  await expect(page.locator(".reader.is-open")).toHaveCount(0);

  // Tema scuro e invito.
  await tab(page, "Oggi");
  await tab(page, "Impostazioni");
  await expect(page).toHaveURL(/\/impostazioni$/);
  await page.locator(SETTINGS).getByRole("button", { name: "Scuro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  // Variante del tema scuro: Solarized (#73), poi grigio.
  await page.locator(SETTINGS).getByRole("group", { name: "Variante del tema scuro" }).getByRole("button", { name: "Solarized" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-dark", "solarized");
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--app-bg").trim().toUpperCase())).toBe("#002B36");
  await page.locator(SETTINGS).getByRole("group", { name: "Variante del tema scuro" }).getByRole("button", { name: "Grigio" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-dark", "grigio");
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--app-bg").trim().toUpperCase())).toBe("#18181B");
  // Preset all'apertura (#69): da qui in poi si parte da «Tutte».
  await page.locator(SETTINGS).getByRole("group", { name: "Preset all'apertura del Notiziario" }).getByRole("button", { name: "Tutte" }).click();
  await expect(page.locator(SETTINGS).getByRole("group", { name: "Preset all'apertura del Notiziario" }).getByRole("button", { name: "Tutte" })).toHaveAttribute("aria-pressed", "true");
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
  // La barra di navigazione è in alto, a tutta larghezza; sotto, la lista e il lettore.
  const nav = await page.locator(".tabbar").boundingBox();
  const list = await page.locator(".views").boundingBox();
  const reader = await page.locator(".reader").boundingBox();
  expect(nav).toMatchObject({ x: 0, y: 0, width: 1440, height: 64 });
  expect(list).toMatchObject({ x: 0, y: 64, width: 460 });
  expect(reader.x).toBeGreaterThanOrEqual(460);
  expect(reader.y).toBe(64);
  // Il nome dell'app a sinistra nella barra; Cerca, Impostazioni e l'avatar in alto a destra.
  await expect(page.locator(".appbar")).toBeHidden();
  await expect(page.locator(".dock")).toBeHidden();
  await expect(page.locator(".tabbar .nav-brand")).toHaveText("galactic feed");
  await expect(page.locator(".tabbar .nav-me")).toBeVisible();
  const settings = await page.locator(".tabbar .nav-settings").boundingBox();
  expect(settings.x).toBeGreaterThan(1440 / 2);
  expect(settings.y + settings.height).toBeLessThanOrEqual(64);
  await page.locator("section[aria-label='Oggi'] .card").first().click();
  await expect(page.locator(".reader .reader-title")).toBeVisible();
  await expect(page.locator("section[aria-label='Oggi'] .card").first()).toHaveClass(/is-current/);

  // Le Fonti occupano tutta la larghezza, senza il lettore. Sul computer sono nella barra in alto.
  await tab(page, "Fonti");
  await expect(page.locator(".reader")).toBeHidden();
  await expect(page.locator(".tabbar button:visible")).toContainText(["Oggi", "Fonti", "Interessi", "Salvati"]);

  // Impostazioni → Lettura → «Pagina intera» (#9): l'elenco usa tutta la larghezza e l'articolo
  // si apre sopra di esso; Indietro riporta all'elenco.
  await tab(page, "Impostazioni");
  await page.locator(SETTINGS).getByRole("group", { name: "Articolo sul computer" }).getByRole("button", { name: "Pagina intera" }).click();
  await expect(page.locator(".app")).toHaveAttribute("data-reader", "pagina");
  await tab(page, "Oggi");
  await expect(page.locator(".reader.is-open")).toHaveCount(0);
  expect((await page.locator(".views").boundingBox()).width).toBe(1440);
  await page.locator("section[aria-label='Oggi'] .card").first().click();
  await expect(page.locator(".reader.is-open .reader-title")).toBeVisible();
  await expect.poll(async () => (await page.locator(".reader").boundingBox()).x).toBe(0);
  await page.locator(".reader.is-open").getByRole("button", { name: "Indietro" }).click();
  await expect(page.locator(".reader.is-open")).toHaveCount(0);
  await page.locator("section[aria-label='Oggi'] .card").first().click();
  await page.keyboard.press("Escape");
  await expect(page.locator(".reader.is-open")).toHaveCount(0);
  // Di nuovo accanto all'elenco, per gli altri test.
  await tab(page, "Impostazioni");
  await page.locator(SETTINGS).getByRole("group", { name: "Articolo sul computer" }).getByRole("button", { name: "Accanto" }).click();
  await expect(page.locator(".app")).toHaveAttribute("data-reader", "colonne");
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
});

test("l'icona della schermata Home è una sola, scritta nell'HTML", async ({ page }) => {
  // iOS la salva all'aggiunta alla Home: niente varianti per tema scelte da JavaScript (#40).
  const icon = page.locator('link[rel="apple-touch-icon"]');
  for (const colorScheme of ["light", "dark"]) {
    await page.emulateMedia({ colorScheme });
    await page.goto("/");
    await expect(icon).toHaveCount(1);
    await expect(icon).toHaveAttribute("href", "/icons/apple-touch-icon.png");
  }
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
  await tab(page, "Salvati");
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
  await tab(page, "Impostazioni");
  await page.locator(SETTINGS).getByRole("button", { name: "Crea la tua Edizione" }).click();
  const edSheet = page.locator(".sheet.is-open");
  await expect(edSheet.locator("h3")).toHaveText("La mia Edizione");
  await expect(edSheet.locator(".tag.mono")).toHaveText(["07:30"]);
  await edSheet.getByLabel("Nuovo orario").fill("21:15");
  await edSheet.getByRole("button", { name: "Orario", exact: true }).click();
  await expect(edSheet.locator(".tag.mono")).toHaveText(["07:30", "21:15"]);
  await expect(edSheet.locator(".preview")).toContainText("con queste regole");

  // La prima la compone il server al giro successivo; qui la chiediamo subito. Si apre come un
  // articolo, sopra Oggi (#64).
  await edSheet.getByRole("button", { name: "Componi adesso" }).click();
  const reader = page.locator(".reader.is-open");
  await expect(reader.locator(".masthead .mast-kicker")).toContainText("La mia Edizione");
  await expect(reader.locator(".hero .hero-title")).toHaveText("Perché le prossime missioni lunari puntano tutte al polo sud");
  await reader.locator(".hero").click();
  await expect(reader.locator(".reader-title")).toHaveText("Perché le prossime missioni lunari puntano tutte al polo sud");
  // Indietro: dall'articolo all'Edizione, poi a Oggi.
  await reader.getByRole("button", { name: "Indietro" }).click();
  await expect(reader.locator(".hero")).toHaveClass(/is-read/);
  await reader.getByRole("button", { name: "Indietro" }).click();
  await expect(page.locator(".reader.is-open")).toHaveCount(0);

  // In Oggi la card dell'Edizione dice quante notizie ha; sotto c'è il Notiziario, e la Dock ha «Notiziario».
  const oggi = page.locator("section[aria-label='Oggi']");
  await expect(oggi.locator(".ed-card .ed-name")).toHaveText(["La mia Edizione"]);
  await expect(oggi.locator(".ed-card .ed-meta")).toContainText(/\d+ notizi[ae]/);
  await expect(page.locator(".dock").getByRole("button", { name: "Notiziario" })).toBeVisible();

  // Una seconda Edizione, settimanale, con una regola.
  await tab(page, "Impostazioni");
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
  await expect(reader.locator(".masthead .mast-kicker")).toContainText("Spazio del lunedì");
  await reader.getByRole("button", { name: "Indietro" }).click();
  await expect(oggi.locator(".ed-card .ed-name")).toHaveText(["Spazio del lunedì", "La mia Edizione"]);
  await expect(oggi.locator(".ed-card .ed-tag").first()).toHaveText("Spazio");

  // Un'uscita si elimina dall'Edizione aperta, un'Edizione dalle Impostazioni: con la conferma
  // dell'app, non quella del browser (che alcune app installate non mostrano).
  await oggi.locator(".ed-card", { hasText: "Spazio del lunedì" }).click();
  await reader.getByRole("button", { name: "Elimina questa uscita" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Eliminare «Spazio del lunedì» n. 1?");
  await page.getByRole("alertdialog").getByRole("button", { name: "Elimina" }).click();
  await expect(page.locator(".toast")).toContainText("Uscita eliminata");
  await expect(page.locator(".reader.is-open")).toHaveCount(0);
  await expect(oggi.locator(".ed-card .ed-name")).toHaveText(["La mia Edizione"]);
  await tab(page, "Impostazioni");
  await page.locator(SETTINGS).getByRole("button", { name: "Elimina l'Edizione Spazio del lunedì" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Annulla" }).click();
  await expect(page.locator(SETTINGS).locator(".preset-name b")).toHaveText(["La mia Edizione", "Spazio del lunedì"]);
  await page.locator(SETTINGS).getByRole("button", { name: "Elimina l'Edizione Spazio del lunedì" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Elimina" }).click();
  await expect(page.locator(".toast")).toContainText("«Spazio del lunedì» eliminata");
  await expect(page.locator(SETTINGS).locator(".preset-name b")).toHaveText(["La mia Edizione"]);

  // «Notiziario» nella Dock scorre fino alle notizie e si accende.
  await tab(page, "Notiziario");
  await expect(page.locator(".dock").getByRole("button", { name: "Notiziario" })).toHaveAttribute("aria-current", "page");
  await expect(oggi.locator(".card").first()).toBeInViewport();
});

test("AI: l'amministratore la configura, sceglie le notizie e scrive i riassunti", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await expect(page.locator(".tabbar")).toBeVisible();

  // Impostazioni → AI → Fornitore apre l'AI del pannello Amministrazione: Ollama (qui un finto servizio sul sito di prova).
  await tab(page, "Impostazioni");
  await page.locator(SETTINGS).getByRole("button", { name: /Fornitore/ }).click();
  const sheet = page.locator(ADMIN);
  await expect(sheet.locator("h2")).toHaveText("AI");
  await sheet.getByRole("button", { name: "Locale" }).click();
  await sheet.getByLabel("Indirizzo").fill("http://127.0.0.1:8098/v1");
  await sheet.getByLabel("Modello").fill("finto");
  await sheet.getByRole("button", { name: "Prova il collegamento" }).click();
  await expect(sheet.locator(".form-ok")).toContainText("Il modello finto risponde");

  // Interessi: scelta con l'AI e descrizione.
  await tab(page, "Interessi");
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

  await tab(page, "Oggi");
  const oggi = page.locator("section[aria-label='Oggi']");
  await preset(page, "Per te");
  await expect(oggi.locator(".card")).toHaveCount(1);
  await expect(oggi.locator(".card .card-title")).toHaveText("Come si misura la distanza di una galassia lontana");

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
  await tab(page, "Impostazioni");
  await expect(page.getByRole("switch", { name: "Notifiche su questo dispositivo" })).toBeVisible();
  await tab(page, "Oggi");

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
  await tab(page, "Fonti");
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
  await tab(page, "Impostazioni");
  // In fondo alle Impostazioni c'è la versione in uso (dal file VERSION), uguale per app e server.
  const version = fs.readFileSync(path.join(path.dirname(new URL(import.meta.url).pathname), "..", "..", "VERSION"), "utf8").trim();
  await expect(page.locator(SETTINGS).locator(".set-row", { hasText: "Versione dell'app" })).toContainText(version);
  await expect(page.locator(SETTINGS).locator(".set-row", { hasText: "Versione del server" })).toHaveCount(0);
  // Si aspetta che ogni scelta arrivi al server prima di ricaricare la pagina.
  const saved = () => page.waitForResponse((r) => r.url().endsWith("/api/me") && r.request().method() === "PATCH");
  let save = saved();
  await page.locator(SETTINGS).getByRole("button", { name: "Viola", exact: true }).click();
  await save;
  save = saved();
  await page.getByRole("group", { name: "Font dell'interfaccia e degli articoli", exact: true }).getByRole("button", { name: "Sistema" }).click();
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

  // Font «Sistema»: system-ui per l'interfaccia e anche per i titoli.
  const fonts = () => page.evaluate(() => {
    const s = getComputedStyle(document.documentElement);
    return [s.getPropertyValue("--font-ui").trim().split(",")[0], s.getPropertyValue("--font-display").trim().split(",")[0]];
  });
  expect(await fonts()).toEqual(["system-ui", "system-ui"]);

  // Colore del sistema (#46): Chromium dà sempre il suo blu (#0075FF) e la nota lo dice. Il colore
  // usato ne tiene la tinta, scurita in chiaro e schiarita in scuro perché si legga.
  save = saved();
  await page.locator(SETTINGS).getByRole("button", { name: "Colore del sistema" }).click();
  await save;
  await expect(page.locator(SETTINGS)).toContainText("dà sempre lo stesso blu");
  const systemColor = () => page.evaluate(() => {
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark" || (root.dataset.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
    const probe = document.createElement("i");
    probe.style.color = "var(--accent)";
    document.body.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return { accent: root.dataset.accent, lightness: Number(color.match(/^oklch\(([\d.]+) /)?.[1]), dark };
  });
  const sys = await systemColor();
  expect(sys.accent).toBe("system");
  expect(sys.lightness).toBe(sys.dark ? 0.78 : 0.45);
  await page.reload();
  expect(await systemColor()).toEqual(sys);
  await ctx.close();
});

test("pannello di amministrazione: impostazioni dell'istanza e predefiniti", async ({ page, browser }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();

  // Sul computer la voce è nella barra in alto, a destra di Impostazioni.
  const nav = page.locator(".tabbar");
  const settingsBox = await nav.getByRole("button", { name: "Impostazioni" }).boundingBox();
  const adminBox = await nav.getByRole("button", { name: "Amministrazione" }).boundingBox();
  expect(adminBox.x).toBeGreaterThan(settingsBox.x);
  expect(adminBox.y).toBe(settingsBox.y);
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
  await tab(page, "Interessi");
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
  // Nel Notiziario «Per te» c'è l'articolo trovato dal gruppo.
  await tab(page, "Oggi");
  const oggi = page.locator("section[aria-label='Oggi']");
  await preset(page, "Per te");
  await expect(oggi.locator(".card").filter({ hasText: "galassia lontana" })).toBeVisible();
  // Il gruppo acceso è anche un interesse nel pannello Filtri (#68).
  await page.locator(".filter-btn").click();
  await expect(page.locator(".sheet.is-open").getByRole("radiogroup", { name: "Scienza" }).first()).toBeVisible();
  await page.keyboard.press("Escape");
  await preset(page, "Tutte");
  // Spento di nuovo, per non cambiare gli altri test.
  await tab(page, "Interessi");
  await interessi.getByRole("group", { name: "Gruppo Scienza" }).getByRole("button", { name: "Spento" }).click();
  await expect(page.locator(".toast")).toContainText("Scienza: spento");
});

test("tag delle fonti: assegnati dalla scheda e usati come filtro nel Notiziario", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await tab(page, "Fonti");
  await page.getByRole("button", { name: "Fonte Orbita" }).click();
  const sheet = page.locator(".sheet.is-open");
  await sheet.getByLabel("Nuovo tag per questa fonte").fill("Astronomia");
  await sheet.getByLabel("Nuovo tag per questa fonte").press("Enter");
  await expect(page.locator(".toast")).toContainText("Tag #Astronomia aggiunto");
  await expect(sheet.getByRole("button", { name: "Togli il tag Astronomia" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".src-row").filter({ hasText: "Orbita" }).locator(".src-tag")).toHaveText(["Astronomia"]);

  // Nei Filtri del Notiziario il tag è un interesse: «solo questi» mostra solo le sue fonti,
  // «nascondi» le toglie (#68).
  await tab(page, "Oggi");
  const oggi = page.locator("section[aria-label='Oggi']");
  const sources = async () => [...new Set(await oggi.locator(".card .src-pill > span:last-child").allTextContents())];
  await page.locator(".filter-btn").click();
  const filters = page.locator(".sheet.is-open");
  await filters.getByRole("radio", { name: "Solo questi: Astronomia" }).click();
  await expect.poll(sources).toEqual(["Orbita"]);
  await filters.getByRole("radio", { name: "Nascondi: Astronomia" }).click();
  await expect.poll(sources).toEqual(["Bit & Byte"]);
  // Il filtro si salva come preset, con un nome; poi si torna a «Tutte».
  await filters.getByLabel("Nome del preset").fill("Senza cielo");
  await filters.getByRole("button", { name: "Salva", exact: true }).click();
  await expect(page.locator(".toast")).toContainText("Preset «Senza cielo» salvato");
  await page.keyboard.press("Escape");
  await expect(page.locator(".preset-row").getByRole("button", { name: /^Senza cielo/ })).toHaveAttribute("aria-pressed", "true");
  await preset(page, "Tutte");
  await expect.poll(async () => (await sources()).length).toBe(2);

  // Gestione dei tag: si può togliere dai Filtri del Notiziario.
  await tab(page, "Fonti");
  await page.getByRole("button", { name: /Tag delle fonti/ }).click();
  await page.locator(".sheet.is-open").getByRole("switch", { name: "Mostra #Astronomia nei Filtri del Notiziario" }).click();
  await expect(page.locator(".toast")).toContainText("#Astronomia non è più nei Filtri");
});

test("accesso con un provider OIDC configurato dal pannello", async ({ page, browser }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await tab(page, "Amministrazione");
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
  await tab(other, "Impostazioni");
  await expect(other.locator(`${SETTINGS} .who`)).toContainText("Olivia Bianchi");
  await ctx.close();
});

test("lettura: gli articoli senza testo completo si nascondono dalle Impostazioni", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();

  // Una fonte che dà solo l'estratto: il server prova a leggere le pagine, ma il sito non le dà.
  await tab(page, "Fonti");
  await page.getByRole("button", { name: "Aggiungi", exact: true }).click();
  await page.getByLabel("Indirizzo").fill("http://127.0.0.1:8098/chiuso.xml");
  await sheetClick(page, "Cerca feed");
  await expect(page.locator(".found-item")).toContainText("solo estratto");
  await sheetClick(page, "Aggiungi fonte");
  await expect(page.locator(".toast")).toContainText("Chiuso aggiunta");
  // Appena l'estrazione è fallita, la scheda della fonte lo dice (dopo aver ricaricato le fonti).
  await expect(async () => {
    await page.reload();
    await tab(page, "Fonti");
    await page.getByRole("button", { name: "Fonte Chiuso" }).click();
    await expect(page.locator(".sheet.is-open")).toContainText("Spesso solo estratto", { timeout: 1000 });
  }).toPass({ timeout: 20_000 });
  await expect(page.locator(".sheet.is-open")).toContainText("Impostazioni → Lettura");
  await page.keyboard.press("Escape");

  // Impostazioni → Lettura.
  await tab(page, "Impostazioni");
  const settings = page.locator(SETTINGS);
  const toggle = settings.getByRole("switch", { name: "Nascondi gli articoli senza testo completo" });
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");

  // Nel Notiziario non ci sono più, ma si possono mostrare per una volta.
  await tab(page, "Oggi");
  const oggi = page.locator("section[aria-label='Oggi']");
  await expect(oggi.locator(".card").first()).toBeVisible();
  await expect(oggi.locator(".card", { hasText: "Riservato agli abbonati" })).toHaveCount(0);
  const note = oggi.locator(".hidden-note", { hasText: "testo completo" });
  await expect(note).toContainText("3 articoli nascosti perché il sito non lascia leggere il testo completo");
  await note.getByRole("button", { name: "Mostra" }).click();
  await expect(oggi.locator(".card", { hasText: "Riservato agli abbonati" })).toHaveCount(3);

  // Spenta di nuovo, per non cambiare gli altri test.
  await tab(page, "Impostazioni");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
});

test("telefono: le barre escono scorrendo giù e rientrano tornando su (#36)", async ({ page }) => {
  // Schermo basso, così l'elenco scorre anche con pochi articoli.
  await page.setViewportSize({ width: 390, height: 520 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  const oggi = page.locator("section[aria-label='Oggi']");
  await expect(oggi.locator(".card").first()).toBeVisible();
  // Per cliccare un elemento che sta ancora entrando, Playwright può far scorrere la sezione:
  // si riparte dalla cima, dove le barre sono sempre visibili.
  await page.evaluate(() => window.scrollTo(0, 0));
  const app = page.locator(".app");
  await expect(app).not.toHaveAttribute("data-bars", "hidden");

  // La Dock è staccata dal fondo e dai lati.
  // (si aspetta la fine dell'animazione con cui rientra)
  const dock = page.locator(".dock");
  await expect.poll(async () => {
    const box = await dock.boundingBox();
    return 520 - (box.y + box.height);
  }).toBeGreaterThanOrEqual(16);
  expect((await dock.boundingBox()).x).toBeGreaterThanOrEqual(12);

  await page.mouse.move(195, 260);
  await page.mouse.wheel(0, 200);
  await expect(app).toHaveAttribute("data-bars", "hidden");
  await expect.poll(async () => (await page.locator(".dock").boundingBox()).y).toBeGreaterThan(520);

  await page.mouse.wheel(0, -40);
  await expect(app).not.toHaveAttribute("data-bars", "hidden");

  // Cambiando sezione tornano visibili.
  await page.mouse.wheel(0, 200);
  await expect(app).toHaveAttribute("data-bars", "hidden");
  await tab(page, "Fonti");
  await expect(app).not.toHaveAttribute("data-bars", "hidden");

  // Sul tablet le barre sono le stesse del telefono: barra in alto e Dock, che escono scorrendo.
  await page.setViewportSize({ width: 1024, height: 520 });
  await tab(page, "Oggi");
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(page.locator(".appbar")).toBeVisible();
  await expect(page.locator(".tabbar .nav-brand")).toBeHidden();
  await expect.poll(async () => 520 - (await dock.boundingBox()).y).toBeLessThan(100);
  await page.mouse.move(500, 260);
  await page.mouse.wheel(0, 200);
  await expect(app).toHaveAttribute("data-bars", "hidden");
  await page.mouse.wheel(0, -40);
  await expect(app).not.toHaveAttribute("data-bars", "hidden");

  // Sul computer la barra in alto non si muove.
  await page.setViewportSize({ width: 1440, height: 520 });
  await tab(page, "Oggi");
  await page.mouse.move(200, 300);
  await page.mouse.wheel(0, 300);
  await expect(app).not.toHaveAttribute("data-bars", "hidden");
});

test("telefono: scorre la pagina, e ogni sezione ricorda dove eri arrivato (#38)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 520 });
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  const oggi = page.locator("section[aria-label='Oggi']");
  await expect(oggi.locator(".card").first()).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  const scrollY = () => page.evaluate(() => Math.round(window.scrollY));

  // A scorrere è il documento (così nel browser la barra degli indirizzi si riduce), non la sezione.
  await page.mouse.move(195, 260);
  await page.mouse.wheel(0, 250);
  await expect.poll(scrollY).toBeGreaterThan(100);
  expect(await oggi.evaluate((v) => v.scrollTop)).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  const y = await scrollY();

  // Un'altra sezione parte dalla sua posizione; tornando a Oggi si ritrova la propria.
  await tab(page, "Interessi");
  await expect.poll(scrollY).toBe(0);
  await tab(page, "Oggi");
  await expect.poll(scrollY).toBe(y);

  // Con il lettore aperto la lista sotto non scorre; chiudendolo (anche con Indietro) resta dov'era.
  // Si tocca una scheda già in vista, così la pagina non si sposta prima di aprirla.
  // Sopra le notizie c'è la card dell'Edizione, alta (#80): si cerca la prima notizia che si vede.
  const point = await oggi.locator(".card").evaluateAll((cards) => {
    const c = cards.find((x) => x.getBoundingClientRect().top > 80 && x.getBoundingClientRect().top < window.innerHeight - 60);
    return c ? { x: c.getBoundingClientRect().left + 40, y: c.getBoundingClientRect().top + 30 } : null;
  });
  await page.mouse.click(point.x, point.y);
  await expect(page.locator(".reader.is-open")).toBeVisible();
  await expect(page.locator("html")).toHaveClass(/gf-lock/);
  await page.mouse.wheel(0, 300);
  await page.goBack();
  await expect(page.locator(".reader.is-open")).toHaveCount(0);
  await expect(page.locator("html")).not.toHaveClass(/gf-lock/);
  await expect.poll(scrollY).toBe(y);

  // Il logo riporta Oggi in cima.
  await barClick(page.locator(".appbar").getByRole("link", { name: /vai a Oggi/ }));
  await expect.poll(scrollY).toBe(0);

  // Sul tablet scorre ancora il documento.
  await page.setViewportSize({ width: 1024, height: 520 });
  await page.mouse.move(500, 260);
  await page.mouse.wheel(0, 250);
  await expect.poll(scrollY).toBeGreaterThan(100);
  expect(await oggi.evaluate((v) => v.scrollTop)).toBe(0);

  // Sul computer scorre la sezione, perché lista e lettore stanno affiancati.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.setViewportSize({ width: 1440, height: 520 });
  await page.mouse.move(200, 300);
  await page.mouse.wheel(0, 250);
  await expect.poll(() => oggi.evaluate((v) => v.scrollTop)).toBeGreaterThan(100);
  expect(await scrollY()).toBe(0);
});

// Una foto da 1 pixel, per l'avatar.
const PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";

test("profilo: statistiche, nome e avatar, ricerca nelle impostazioni e colore personalizzato", async ({ page }) => {
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await expect(page.locator("section[aria-label='Oggi']")).toBeVisible();

  // Statistiche (#78): gli articoli aperti nei test precedenti.
  await tab(page, "Profilo");
  const prof = page.locator("section[aria-label='Profilo']");
  await expect(prof.locator(".tile").first()).toContainText("Letti");
  await expect.poll(async () => Number(await prof.locator(".tile b").first().textContent())).toBeGreaterThan(0);
  const periodo = prof.getByRole("group", { name: "Periodo" });
  await periodo.getByRole("button", { name: "Mese" }).click();
  await expect(prof.locator(".bar-col")).toHaveCount(30);
  // Anno e di sempre (#83): l'anno va per mese, dodici barre.
  await periodo.getByRole("button", { name: "Anno" }).click();
  await expect(prof.locator(".bar-col")).toHaveCount(12);
  await expect(prof.locator(".stat-card h3").first()).toContainText("Letti al mese");
  await periodo.getByRole("button", { name: "Sempre" }).click();
  await expect(periodo.getByRole("button", { name: "Sempre" })).toHaveAttribute("aria-pressed", "true");
  await expect(prof.locator(".tile small").nth(1)).toHaveText("da sempre");

  // Nome e avatar (#76).
  await prof.getByRole("button", { name: "Cambia nome e avatar" }).click();
  const sheet = page.locator(".sheet.is-open");
  await sheet.getByLabel("Nome").fill("Anna Rossi");
  await sheet.getByRole("radio", { name: "Colore 3" }).click();
  await sheet.getByRole("button", { name: "Salva" }).click();
  await expect(page.locator(".toast")).toContainText("Profilo aggiornato");
  await expect(prof.locator(".me-text h1")).toHaveText("Anna Rossi");
  await expect(prof.locator(".me-card span.avatar")).toHaveText("AR");
  await prof.getByRole("button", { name: "Cambia nome e avatar" }).click();
  await sheet.locator("input[type=file]").setInputFiles({ name: "foto.png", mimeType: "image/png", buffer: Buffer.from(PNG, "base64") });
  await expect(sheet.locator("img.avatar")).toBeVisible();
  await sheet.getByRole("button", { name: "Salva" }).click();
  await expect(prof.locator(".me-card img.avatar")).toHaveAttribute("src", /\/api\/avatars\/\d+\?v=/);
  await prof.getByRole("button", { name: "Cambia nome e avatar" }).click();
  await sheet.getByRole("button", { name: "Usa le iniziali" }).click();
  await sheet.getByLabel("Nome").fill("Anna");
  await sheet.getByRole("button", { name: "Salva" }).click();
  await expect(prof.locator(".me-card span.avatar")).toHaveText("A");

  // Ricerca nelle impostazioni (#67): dal Profilo si apre con il cursore nel campo.
  await prof.getByRole("button", { name: "Cerca nelle impostazioni" }).click();
  await expect(page).toHaveURL(/\/impostazioni$/);
  const search = page.locator(".settings-search.main input");
  await expect(search).toBeFocused();
  await search.fill("dark");
  const settings = page.locator(SETTINGS);
  await expect(settings.getByRole("group", { name: "Tema", exact: true })).toBeVisible();
  await expect(settings.locator("[data-via='dark']").first()).toBeVisible();
  await expect(settings.getByText("Fuso orario")).toBeHidden();
  await expect(page.locator(".search-count")).toContainText(/impostazion/);
  await search.fill("password");
  await expect(settings.getByRole("button", { name: /Cambia password/ })).toBeVisible();
  await expect(settings.getByRole("switch", { name: "Nascondi gli articoli senza testo completo" })).toBeHidden();
  await search.fill("zzz");
  await expect(page.locator(".search-count")).toContainText("Nessuna impostazione");
  await search.fill("");
  await expect(settings.getByRole("switch", { name: "Nascondi gli articoli senza testo completo" })).toBeVisible();

  // Su uno schermo stretto (o con il testo ingrandito) la barra resta nei margini della pagina (#84).
  await page.setViewportSize({ width: 300, height: 700 });
  const field = await page.locator(".settings-search.main .search-field").boundingBox();
  const group = await settings.locator(".set-group").first().boundingBox();
  expect(field.x + field.width).toBeLessThanOrEqual(group.x + group.width + 0.5);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(300);
  await page.setViewportSize(PHONE);

  // «Impostazioni» nel Profilo (#81): sul telefono scorre alle sezioni qui sotto invece di aprire la
  // pagina, e il cursore non torna nella ricerca riaprendo le Impostazioni.
  await tab(page, "Profilo");
  await prof.locator(".shortcuts").getByRole("button", { name: "Impostazioni" }).click();
  await expect(page).toHaveURL(/\/profilo$/);
  await expect(prof.locator("#h-imp")).toBeFocused();
  await expect(prof.locator("#h-imp")).toBeInViewport();
  await prof.locator(".profilo-settings").getByRole("button", { name: /^Aspetto/ }).click();
  await expect(page).toHaveURL(/\/impostazioni$/);
  await expect(settings.getByRole("group", { name: "Tema", exact: true })).toBeVisible();
  await expect(search).not.toBeFocused();

  // Colore personalizzato (#74): l'ultimo pallino apre il selettore; l'app adatta il colore.
  const saved = page.waitForResponse((r) => r.url().endsWith("/api/me") && r.request().method() === "PATCH" && r.request().postData().includes("accent_custom"));
  await settings.getByLabel("Colore personalizzato").fill("#ff7a59");
  await saved;
  await expect(page.locator("html")).toHaveAttribute("data-accent", "custom");
  await expect.poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue("--acc-l"))).toMatch(/^#[0-9A-F]{6}$/);
  await settings.getByRole("button", { name: "Galassia", exact: true }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-accent", "custom");
  await expect.poll(() => page.evaluate(() => document.documentElement.style.getPropertyValue("--acc-l"))).toBe("");
});

test("aggiornamenti: la versione nuova si annuncia e si attiva con «Aggiorna» (#41)", async ({ page }) => {
  const sw = path.join(path.dirname(new URL(import.meta.url).pathname), "..", "dist", "sw.js");
  const original = fs.readFileSync(sw, "utf8");
  await page.setViewportSize(PHONE);
  await page.goto("/");
  await page.getByLabel("Nome utente").fill("anna");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra" }).click();
  await expect(page.locator("section[aria-label='Oggi']")).toBeVisible();
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);

  // In Impostazioni → Informazioni c'è la versione dell'app.
  await tab(page, "Impostazioni");
  const pkg = JSON.parse(fs.readFileSync(path.join(path.dirname(sw), "..", "package.json"), "utf8"));
  await expect(page.locator(SETTINGS).locator(".set-row", { hasText: "Versione dell'app" })).toContainText(pkg.version);
  await page.locator(SETTINGS).getByRole("button", { name: "Cerca aggiornamenti" }).click();
  await expect(page.locator(SETTINGS)).toContainText("L'app è aggiornata");
  await expect(page.locator(".update-bar")).toHaveCount(0);

  try {
    // Esce una versione nuova: la si trova cercando gli aggiornamenti, ma aspetta il tuo «Aggiorna».
    fs.writeFileSync(sw, `${original}\n// e2e: versione nuova ${Date.now()}\n`);
    await page.evaluate(() => (window.__primaDellAggiornamento = true));
    await page.locator(SETTINGS).getByRole("button", { name: "Cerca aggiornamenti" }).click();
    await expect(page.locator(".update-bar")).toContainText("È disponibile una nuova versione");
    expect(await page.evaluate(() => navigator.serviceWorker.getRegistration().then((r) => Boolean(r.waiting)))).toBe(true);
    expect(await page.evaluate(() => window.__primaDellAggiornamento)).toBe(true);

    // «Aggiorna»: la versione nuova si attiva e la pagina si ricarica da sola.
    await page.locator(".update-bar").getByRole("button", { name: "Aggiorna" }).click();
    await page.waitForFunction(() => window.__primaDellAggiornamento === undefined);
    await expect(page.locator(SETTINGS)).toBeVisible();
    await expect(page.locator(".update-bar")).toHaveCount(0);
    expect(await page.evaluate(() => navigator.serviceWorker.getRegistration().then((r) => Boolean(r.waiting)))).toBe(false);
  } finally {
    fs.writeFileSync(sw, original);
  }
});
