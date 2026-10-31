// Ambiente per i test nel browser:
// - un piccolo sito di notizie finto su http://127.0.0.1:8098 (feed RSS, pagine, immagini);
// - il server di Galactic Feed su http://127.0.0.1:8097, con un database nuovo e la PWA compilata.
// Il codice di primo avvio finisce nel log, che i test leggono come farebbe una persona.

import { spawn } from "node:child_process";
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
const LONG = (lead) => Array.from({ length: 10 }, (_, i) => `<p>${lead} Paragrafo ${i + 1}, con abbastanza testo da sembrare un vero articolo di giornale scritto con calma.</p>`).join("");

function rss(title, items) {
  const entries = items.map(([t, lead, hours, cat], i) => {
    const slug = `${title.toLowerCase().replace(/\W+/g, "-")}-${i}`;
    const date = new Date(now - hours * 3600e3).toUTCString();
    return `<item><title>${t}</title><link>${SITE}/${slug}</link><guid>${slug}</guid><pubDate>${date}</pubDate>${cat ? `<category>${cat}</category>` : ""}<description>${lead}</description>${i === 0 ? `<media:thumbnail url="${SITE}/img/a.png"/>` : ""}</item>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>${title}</title><link>${SITE}/</link>${entries.join("")}</channel></rss>`;
}

const pages = {
  "/": `<html><head><title>Orbita</title><link rel="alternate" type="application/rss+xml" title="Orbita" href="/orbita.xml"><link rel="alternate" type="application/rss+xml" title="Commenti" href="/comments/feed"></head><body>Orbita</body></html>`,
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

const site = http.createServer((req, res) => {
  const url = req.url.split("?")[0];
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
