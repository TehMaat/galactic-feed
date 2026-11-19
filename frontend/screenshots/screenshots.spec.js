// Screenshot della documentazione (#55). Prepara un'istanza con dati inventati (utenti, cartelle,
// fonti, interessi, un'Edizione) e fotografa le schermate principali su telefono e computer, in
// chiaro e in scuro. Le immagini vanno in docs/img/screenshot/ in WebP, senza metadati.
//
//   npm run build && npx playwright test -c playwright.screenshots.config.js

import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(here, "..", "..", "docs", "img", "screenshot");
const LOG = path.join(os.tmpdir(), "galactic-feed-screenshots", "server.log");
const SITE = "http://127.0.0.1:8198";
const PHONE = { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
const COMPUTER = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 };
const ADMIN = { username: "livia", display_name: "Livia Ferraris", password: "una-password-di-prova" };
const SECOND = { username: "teo", display_name: "Teo Marchetti", password: "un'altra-password-di-prova" };

test.describe.configure({ mode: "serial" });
fs.mkdirSync(OUT, { recursive: true });

/** Salva lo screenshot in WebP: lo converte il browser stesso, così non servono altri programmi. */
async function shot(page, name) {
  // Niente cursore lampeggiante, animazioni ferme, toast spariti.
  await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}.toast{display:none!important}" });
  await page.waitForTimeout(300);
  const png = await page.screenshot();
  const webp = await page.evaluate(async (b64) => {
    const img = new Image();
    img.src = `data:image/png;base64,${b64}`;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    canvas.getContext("2d").drawImage(img, 0, 0);
    return canvas.toDataURL("image/webp", 0.86).split(",")[1];
  }, png.toString("base64"));
  fs.writeFileSync(path.join(OUT, `${name}.webp`), Buffer.from(webp, "base64"));
}

async function api(request, method, url, data) {
  const res = await request.fetch(`/api${url}`, { method, data });
  expect(res.ok(), `${method} ${url}: ${res.status()} ${await res.text()}`).toBeTruthy();
  return res.json();
}

async function newPage(browser, device, scheme) {
  const context = await browser.newContext({ ...device, colorScheme: scheme, baseURL: "http://127.0.0.1:8197", locale: "it-IT", timezoneId: "Europe/Rome" });
  return context.newPage();
}

async function login(page, who = ADMIN) {
  await page.goto("/");
  await page.getByLabel("Nome utente").fill(who.username);
  await page.getByLabel("Password", { exact: true }).fill(who.password);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.locator("section[aria-label='Oggi']")).toBeVisible();
}

test("primo avvio e dati demo", async ({ browser }) => {
  const page = await newPage(browser, PHONE, "light");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Primo avvio/ })).toBeVisible();
  await shot(page, "primo-avvio-telefono-chiaro");

  const code = fs.readFileSync(LOG, "utf8").match(/Codice di primo avvio: (\d{6})/)[1];
  const r = page.request;
  await api(r, "POST", "/auth/setup", { ...ADMIN, code });

  const folders = {};
  for (const name of ["Spazio", "Tecnologia", "Tempo libero"]) {
    folders[name] = (await api(r, "POST", "/folders", { name })).folder.id;
  }
  const sources = [
    ["orione.xml", "Spazio"], ["gazzettino.xml", "Spazio"],
    ["officina.xml", "Tecnologia"], ["circuiti.xml", "Tecnologia"],
    ["pedale.xml", "Tempo libero"],
  ];
  for (const [file, folder] of sources) {
    await api(r, "POST", "/sources", { url: `${SITE}/${file}`, folder_id: folders[folder] });
  }

  // Interessi: due gruppi pronti accesi e una parola chiave importante.
  const interests = await api(r, "GET", "/interests");
  const presets = interests.presets || [];
  for (const name of ["Scienza", "Tecnologia"]) {
    const preset = presets.find((p) => p.name === name);
    if (preset) await api(r, "POST", "/groups", { preset_id: preset.id, mode: "interest", level: "media" });
  }
  await api(r, "POST", "/interests/keywords", { keyword: "Luna", level: "alta" });

  // Un'Edizione del mattino, con un'uscita già pronta.
  const created = await api(r, "POST", "/edition-configs", { name: "Il Mattino", active: true });
  const config = created.configs.find((c) => c.name === "Il Mattino").id;
  await api(r, "POST", "/editions", { config_id: config });

  // Profilo (#76) e preset del Notiziario (#68): un colore per le iniziali e due preset.
  await api(r, "PATCH", "/me", {
    avatar_color: 0,
    prefs: { presets: [
      { id: "mattina", name: "Mattina", filter: { scope: "perte", unread: true, inc: [], exc: [] } },
      { id: "solo-spazio", name: "Solo spazio", filter: { scope: "tutte", unread: false, inc: [`f:${folders.Spazio}`], exc: [] } },
    ] },
  });
  // Qualche articolo aperto, per le statistiche (#78).
  const list = await api(r, "GET", "/articles?view=tutti");
  for (const a of list.items.slice(2, 7)) await api(r, "PUT", `/articles/${a.id}/read`);

  // Un secondo utente, invitato dall'amministratrice.
  const invite = await api(r, "POST", "/admin/invites", { note: "Per Teo" });
  const token = invite.invite.url.split("/").pop();
  const other = await browser.newContext({ baseURL: "http://127.0.0.1:8197" });
  await api(other.request, "POST", `/invites/${token}/accept`, SECOND);
  await other.close();
  // E un invito ancora da usare, per la lista in Amministrazione.
  await api(r, "POST", "/admin/invites", { note: "Per Nora" });
  await page.context().close();
});

for (const scheme of ["light", "dark"]) {
  const tone = scheme === "light" ? "chiaro" : "scuro";

  test(`telefono, ${tone}`, async ({ browser }) => {
    const page = await newPage(browser, PHONE, scheme);
    await login(page);
    const oggi = page.locator("section[aria-label='Oggi']");
    await expect(oggi.locator(".card").first()).toBeVisible();
    await expect(oggi.locator(".ed-card").first()).toBeVisible();
    await shot(page, `oggi-telefono-${tone}`);

    if (scheme === "light") {
      await oggi.locator(".ed-card").first().click();
      await page.waitForTimeout(800);
      await shot(page, "edizione-telefono-chiaro");
      await page.keyboard.press("Escape");
      await page.waitForTimeout(400);
    }

    await oggi.locator(".card").first().click();
    await page.waitForTimeout(800);
    await shot(page, `articolo-telefono-${tone}`);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

    if (scheme === "light") {
      await page.getByRole("button", { name: "Notiziario" }).click();
      await page.waitForTimeout(800);
      await page.getByRole("button", { name: "Filtri", exact: true }).click();
      await page.waitForTimeout(700);
      await shot(page, "filtri-telefono-chiaro");
      await page.keyboard.press("Escape");

      await page.goto("/fonti");
      await expect(page.locator(".src-row").first()).toBeVisible();
      await shot(page, "fonti-telefono-chiaro");
      await page.goto("/interessi");
      await page.waitForTimeout(800);
      await shot(page, "interessi-telefono-chiaro");
      await page.goto("/impostazioni");
      await page.locator(".settings-search.main input").fill("dark");
      await page.waitForTimeout(600);
      await shot(page, "impostazioni-ricerca-telefono-chiaro");
    }
    await page.goto("/profilo");
    await expect(page.locator(".stat-grid")).toBeVisible();
    await page.waitForTimeout(500);
    await shot(page, `profilo-telefono-${tone}`);
    await page.context().close();
  });

  test(`computer, ${tone}`, async ({ browser }) => {
    const page = await newPage(browser, COMPUTER, scheme);
    await login(page);
    await expect(page.locator("section[aria-label='Oggi'] .card").first()).toBeVisible();
    await page.locator("section[aria-label='Oggi'] .card").first().click();
    await page.waitForTimeout(800);
    await shot(page, `oggi-computer-${tone}`);
    if (scheme === "dark") {
      await page.locator("section[aria-label='Oggi'] .ed-card").first().click();
      await page.waitForTimeout(800);
      await shot(page, "edizione-computer-scuro");
    }
    await page.goto("/profilo");
    await expect(page.locator(".stat-grid")).toBeVisible();
    await page.waitForTimeout(500);
    await shot(page, `profilo-computer-${tone}`);

    if (scheme === "light") {
      await page.goto("/impostazioni");
      await page.locator(".page-nav").getByRole("button", { name: "Aspetto" }).click();
      await page.waitForTimeout(600);
      await shot(page, "impostazioni-aspetto-computer-chiaro");
    } else {
      await page.goto("/amministrazione");
      await page.locator(".page-nav").getByRole("button", { name: "Utenti e inviti" }).click();
      await expect(page.getByText("Teo Marchetti").first()).toBeVisible();
      await page.waitForTimeout(600);
      await shot(page, "amministrazione-computer-scuro");
    }
    await page.context().close();
  });
}

test("accesso", async ({ browser }) => {
  const page = await newPage(browser, PHONE, "dark");
  await page.goto("/");
  await expect(page.getByLabel("Nome utente")).toBeVisible();
  await shot(page, "accesso-telefono-scuro");
  await page.context().close();
});
