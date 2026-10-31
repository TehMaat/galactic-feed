import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const LOG = path.join(os.tmpdir(), "galactic-feed-e2e", "server.log");
const PHONE = { width: 390, height: 844 };
const PASSWORD = "una-password-lunga";

test.describe.configure({ mode: "serial" });

let inviteUrl = "";

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
  await page.locator(".sheet.is-open").getByRole("button", { name: "Scuro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await sheetClick(page, "Utenti e inviti");
  await sheetClick(page, "Crea un link d'invito");
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
});
