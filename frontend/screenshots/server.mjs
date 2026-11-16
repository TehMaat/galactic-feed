// Ambiente per gli screenshot della documentazione (#55): tutto inventato.
// - un sito di notizie finto su http://127.0.0.1:8198, con cinque testate che non esistono;
// - il server di Galactic Feed su http://127.0.0.1:8197, con un database nuovo e la PWA compilata.
// Nomi, testate, articoli e indirizzi sono di fantasia: negli screenshot non deve comparire
// niente di reale (siti, loghi, persone). Il codice di primo avvio finisce nel log, come sempre.

import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "..");
export const WORK = path.join(os.tmpdir(), "galactic-feed-screenshots");
fs.rmSync(WORK, { recursive: true, force: true });
fs.mkdirSync(WORK, { recursive: true });

const SITE = "http://127.0.0.1:8198";
const now = Date.now();

const paragraphs = (lead, topic) =>
  [
    lead,
    `Chi segue ${topic} da qualche anno lo sa: le notizie vere arrivano piano, una conferma alla volta. Anche questa volta i primi dati sono stati letti e riletti prima di essere annunciati.`,
    "Il gruppo di lavoro ha pubblicato i numeri completi, con le tabelle e le note sui metodi usati. Chiunque può rifare i conti e controllare dove le stime sono più incerte.",
    "Restano domande aperte, e i prossimi mesi diranno quanto reggono le prime conclusioni. Intanto il calendario è già fitto: nuove misure, un secondo gruppo indipendente e un incontro pubblico in primavera.",
    "«Non è un punto d'arrivo», ha detto la coordinatrice del progetto, «ma un buon punto da cui ripartire con più strumenti e più persone».",
  ]
    .map((p) => `<p>${p}</p>`)
    .join("");

// [titolo, estratto, ore fa, categoria]
const SOURCES = {
  "orione.xml": {
    title: "Cronache di Orione",
    topic: "lo spazio",
    items: [
      ["La sonda Aurora-7 manda la prima foto ravvicinata della luna ghiacciata di Teti", "Crepe lunghe centinaia di chilometri e una superficie più giovane del previsto.", 0.6, "Spazio"],
      ["Perché le prossime missioni lunari puntano tutte al polo sud", "Ghiaccio nei crateri in ombra perenne: acqua, ossigeno e carburante.", 2.5, "Luna"],
      ["Come si misura la distanza di una galassia lontana", "Parallasse, Cefeidi e redshift: la scala delle distanze spiegata bene.", 6, "Astronomia"],
      ["Un telescopio sul lato nascosto della Luna: il progetto è pronto", "Lontano dal rumore radio della Terra si ascolta l'universo giovane.", 20, "Luna"],
    ],
  },
  "gazzettino.xml": {
    title: "Il Gazzettino Stellare",
    topic: "l'astronomia",
    items: [
      ["Pioggia di meteore stanotte: gli orari migliori per guardarla", "Cielo sereno quasi ovunque, picco dopo mezzanotte.", 1.2, "Astronomia"],
      ["Nuova cometa scoperta da un gruppo di astrofili", "Sarà visibile a occhio nudo a febbraio, se resiste al Sole.", 9, "Astronomia"],
      ["Il planetario cittadino riapre con una cupola nuova", "Proiezioni in 8K e serate dedicate alle scuole.", 30, "Eventi"],
    ],
  },
  "officina.xml": {
    title: "Officina Byte",
    topic: "la tecnologia",
    items: [
      ["Un server di casa in un mini PC da 150 euro: guida passo passo", "Docker, backup automatici e consumi sotto i 10 watt.", 1.5, "Tecnologia"],
      ["Le web app su telefono: cosa possono fare davvero", "Notifiche, badge, lettura offline e installazione.", 4, "Tecnologia"],
      ["Raspberry Pi come lettore di notizie: abbastanza veloce?", "Le prove su un modello da 4 GB con una dozzina di feed.", 12, "Tecnologia"],
      ["Password e passkey: come organizzarsi in famiglia", "Un gestore condiviso e qualche regola semplice.", 26, "Sicurezza"],
    ],
  },
  "circuiti.xml": {
    title: "Rete & Circuiti",
    topic: "l'elettronica",
    items: [
      ["La stazione meteo fatta in casa che parla con il telefono", "Sensori economici, un microcontrollore e un grafico in tempo reale.", 3, "Tecnologia"],
      ["Saldare senza paura: i cinque errori più comuni", "Temperatura, stagno e un po' di pazienza.", 15, "Elettronica"],
    ],
  },
  "pedale.xml": {
    title: "Pedale Lento",
    topic: "il ciclismo",
    items: [
      ["Il giro delle colline in tre tappe: percorso e consigli", "Strade bianche, salite brevi e paesi da non perdere.", 5, "Sport"],
      ["Bici e treno: dove si viaggia meglio con la bicicletta al seguito", "Posti, prenotazioni e piccoli trucchi.", 18, "Viaggi"],
    ],
  },
};

const slug = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\W+/g, "-").replace(/^-|-$/g, "");

function rss(file) {
  const src = SOURCES[file];
  const entries = src.items.map(([t, lead, hours, cat]) => {
    const id = slug(t);
    const date = new Date(now - hours * 3600e3).toUTCString();
    return `<item><title>${t}</title><link>${SITE}/${slug(src.title)}/${id}</link><guid>${id}</guid><pubDate>${date}</pubDate><category>${cat}</category><description>${lead}</description><content:encoded><![CDATA[${paragraphs(lead, src.topic)}]]></content:encoded></item>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>${src.title}</title><link>${SITE}/${slug(src.title)}/</link><language>it</language>${entries.join("")}</channel></rss>`;
}

const site = http.createServer((req, res) => {
  const url = req.url.split("?")[0].slice(1);
  if (SOURCES[url]) {
    res.writeHead(200, { "Content-Type": "application/rss+xml; charset=utf-8" });
    return res.end(rss(url));
  }
  // Pagine degli articoli: il testo completo è già nel feed, qui basta una pagina semplice.
  if (/^[\w-]+\/[\w-]+$/.test(url)) {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    return res.end(`<html><body><article><p>Articolo di prova.</p></article></body></html>`);
  }
  res.writeHead(404);
  res.end();
});
site.listen(8198, "127.0.0.1");

const python = process.env.GF_PYTHON || (fs.existsSync(path.join(root, ".venv/bin/python")) ? path.join(root, ".venv/bin/python") : "python3");
const log = fs.openSync(path.join(WORK, "server.log"), "w");
const backend = spawn(python, ["-m", "app"], {
  cwd: path.join(root, "backend"),
  env: {
    ...process.env,
    DATA_DIR: path.join(WORK, "data"),
    PUBLIC_URL: "http://127.0.0.1:8197",
    PORT: "8197",
    HOST: "127.0.0.1",
    TZ: "Europe/Rome",
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
