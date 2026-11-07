// Ambiente per i test nel browser:
// - un piccolo sito di notizie finto su http://127.0.0.1:8098 (feed RSS, pagine, immagini);
// - il server di Galactic Feed su http://127.0.0.1:8097, con un database nuovo e la PWA compilata.
// Il codice di primo avvio finisce nel log, che i test leggono come farebbe una persona.

import { spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..");
export const WORK = path.join(os.tmpdir(), "galactic-feed-e2e");
fs.rmSync(WORK, { recursive: true, force: true });
fs.mkdirSync(WORK, { recursive: true });

const SITE = "http://127.0.0.1:8098";
const now = Date.now();
const LONG = (lead) => Array.from({ length: 16 }, (_, i) => `<p>${lead} Paragrafo ${i + 1}, con abbastanza testo da sembrare un vero articolo di giornale scritto con calma.</p>`).join("");

function rss(title, items) {
  const entries = items.map(([t, lead, hours, cat], i) => {
    const slug = `${title.toLowerCase().replace(/\W+/g, "-")}-${i}`;
    const date = new Date(now - hours * 3600e3).toUTCString();
    return `<item><title>${t}</title><link>${SITE}/${slug}</link><guid>${slug}</guid><pubDate>${date}</pubDate>${cat ? `<category>${cat}</category>` : ""}<description>${lead}</description>${i === 0 ? `<media:thumbnail url="${SITE}/img/a.png"/>` : ""}</item>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>${title}</title><link>${SITE}/</link>${entries.join("")}</channel></rss>`;
}

const pages = {
  "/": `<html><head><title>Orbita</title><link rel="apple-touch-icon" href="/img/a.png"><link rel="alternate" type="application/rss+xml" title="Orbita" href="/orbita.xml"><link rel="alternate" type="application/rss+xml" title="Commenti" href="/comments/feed"></head><body>Orbita</body></html>`,
  "/orbita.xml": rss("Orbita", [
    ["Perché le prossime missioni lunari puntano tutte al polo sud", "Ghiaccio nei crateri in ombra perenne.", 0.5, "Luna"],
    ["Come si misura la distanza di una galassia lontana", "Parallasse, Cefeidi e redshift.", 5],
    ["Oroscopo spaziale della settimana", "Le stelle dicono.", 7],
  ]),
  "/bitebyte.xml": rss("Bit & Byte", [
    ["Le PWA su iPhone: cosa possono fare davvero e cosa no", "Notifiche, badge, offline.", 1.5],
    ["Docker in un mini PC da 150 euro: il mio stack", "Foto, password e backup.", 3, "Docker"],
  ]),
};

// Un finto servizio AI compatibile con OpenAI (come Ollama): sceglie gli articoli che parlano
// di galassie e scrive riassunti di tre punti.
function fakeAi(body) {
  const system = body.messages[0].content;
  const prompt = body.messages[1].content;
  if (system.startsWith("Selezioni notizie")) {
    const articoli = prompt.split("\n").filter((l) => /^\[\d+\]/.test(l)).map((l) => {
      const n = Number(l.slice(1, l.indexOf("]")));
      const yes = /galassi/i.test(l);
      return { n, pertinenza: yes ? "alta" : "no", tema: yes ? "astronomia" : "" };
    });
    return { articoli };
  }
  if (system.startsWith("Riassumi")) return { punti: ["Si misura con la parallasse.", "Poi con le Cefeidi.", "Infine con il redshift."] };
  return { risposta: "ok" };
}

// Un provider OpenID Connect finto (#22): approva subito chi arriva e firma l'ID token in RS256.
const OIDC = `${SITE}/oidc`;
const { publicKey, privateKey } = crypto.generateKeyPairSync("rsa", { modulusLength: 2048 });
const jwk = { ...publicKey.export({ format: "jwk" }), kid: "e2e", use: "sig", alg: "RS256" };
const codes = new Map();
const b64url = (buf) => Buffer.from(buf).toString("base64url");

function idToken(claims) {
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT", kid: "e2e" }));
  const body = b64url(JSON.stringify(claims));
  const sig = crypto.sign("sha256", Buffer.from(`${head}.${body}`), privateKey);
  return `${head}.${body}.${b64url(sig)}`;
}

function oidc(req, res, url, query) {
  const json = (data, status = 200) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(data));
  };
  if (url === "/oidc/.well-known/openid-configuration") {
    return json({
      issuer: OIDC, authorization_endpoint: `${OIDC}/authorize`, token_endpoint: `${OIDC}/token`,
      jwks_uri: `${OIDC}/jwks`, userinfo_endpoint: `${OIDC}/userinfo`,
      id_token_signing_alg_values_supported: ["RS256"], token_endpoint_auth_methods_supported: ["client_secret_basic"],
    });
  }
  if (url === "/oidc/jwks") return json({ keys: [jwk] });
  if (url === "/oidc/authorize") {
    const code = crypto.randomBytes(12).toString("hex");
    codes.set(code, { nonce: query.get("nonce"), challenge: query.get("code_challenge") });
    res.writeHead(302, { Location: `${query.get("redirect_uri")}?code=${code}&state=${encodeURIComponent(query.get("state"))}` });
    return res.end();
  }
  if (url === "/oidc/token" && req.method === "POST") {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      const form = new URLSearchParams(raw);
      const saved = codes.get(form.get("code"));
      codes.delete(form.get("code"));
      const pkce = saved && crypto.createHash("sha256").update(form.get("code_verifier") || "").digest("base64url");
      if (!saved || pkce !== saved.challenge || req.headers.authorization !== `Basic ${Buffer.from("galactic-e2e:segreto-e2e").toString("base64")}`) {
        return json({ error: "invalid_grant" }, 400);
      }
      const now = Math.floor(Date.now() / 1000);
      const claims = { iss: OIDC, aud: "galactic-e2e", sub: "olivia-1", iat: now, exp: now + 300, nonce: saved.nonce,
        preferred_username: "olivia", name: "Olivia Bianchi", email: "olivia@example.org", email_verified: true };
      json({ id_token: idToken(claims), access_token: "at", token_type: "Bearer" });
    });
    return;
  }
  if (url === "/oidc/userinfo") return json({ sub: "olivia-1" });
  res.writeHead(404);
  res.end();
}

const site = http.createServer((req, res) => {
  const url = req.url.split("?")[0];
  if (url.startsWith("/oidc/")) return oidc(req, res, url, new URL(req.url, SITE).searchParams);
  if (req.method === "POST" && url === "/v1/chat/completions") {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      const body = JSON.parse(raw);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ model: body.model, choices: [{ message: { content: JSON.stringify(fakeAi(body)) }, finish_reason: "stop" }], usage: { prompt_tokens: 100, completion_tokens: 20 } }));
    });
    return;
  }
  if (pages[url]) {
    res.writeHead(200, { "Content-Type": url.endsWith(".xml") ? "application/rss+xml" : "text/html; charset=utf-8" });
    return res.end(pages[url]);
  }
  if (url === "/img/a.png") {
    res.writeHead(200, { "Content-Type": "image/png" });
    return res.end(fs.readFileSync(path.join(root, "frontend", "public", "icons", "icon-192.png")));
  }
  if (/^\/(orbita|bit-byte)-\d$/.test(url)) {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(`<html><body><nav>Menu</nav><article><h1>Articolo</h1>${LONG("Testo completo estratto dalla pagina.")}</article><footer>Fine</footer></body></html>`);
  }
  res.writeHead(404);
  res.end();
});
site.listen(8098, "127.0.0.1");

const python = process.env.GF_PYTHON || (fs.existsSync(path.join(root, ".venv/bin/python")) ? path.join(root, ".venv/bin/python") : "python3");
const log = fs.openSync(path.join(WORK, "server.log"), "w");
const backend = spawn(python, ["-m", "app"], {
  cwd: path.join(root, "backend"),
  env: {
    ...process.env,
    DATA_DIR: path.join(WORK, "data"),
    PUBLIC_URL: "http://127.0.0.1:8097",
    PORT: "8097",
    HOST: "127.0.0.1",
    FRONTEND_DIR: path.join(root, "frontend", "dist"),
  },
  stdio: ["ignore", log, log],
});

const stop = () => {
  backend.kill();
  site.close();
  process.exit(0);
};
process.on("SIGTERM", stop);
process.on("SIGINT", stop);
backend.on("exit", (code) => {
  console.error(`Il server si è fermato (codice ${code}). Log: ${path.join(WORK, "server.log")}`);
  process.exit(1);
});
