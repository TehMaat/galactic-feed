// Dati di esempio per il mockup: fonti e articoli sono inventati.
window.GF_DATA = {
  topics: {
    spazio: { label: "Spazio", color: "var(--c-spazio)", hue: 232, art: "planet" },
    tech: { label: "Tech", color: "var(--c-tech)", hue: 205, art: "grid" },
    selfhost: { label: "Self-hosting", color: "var(--c-selfhost)", hue: 145, art: "bars" },
    scienza: { label: "Scienza", color: "var(--c-scienza)", hue: 280, art: "nebula" },
    italia: { label: "Italia", color: "var(--c-italia)", hue: 345, art: "hills" }
  },

  sources: [
    { id: "orbita", name: "Orbita", type: "rss", topic: "spazio", initials: "Or", url: "orbita.example/feed.xml", status: "ok", every: "30 min" },
    { id: "cronache", name: "Cronache Spaziali", type: "youtube", topic: "spazio", initials: "CS", url: "youtube.com/@cronachespaziali", status: "ok", every: "1 h" },
    { id: "cielo", name: "Cielo Profondo", type: "rss", topic: "spazio", initials: "CP", url: "cieloprofondo.example/feed", status: "ok", every: "3 h" },
    { id: "bitbyte", name: "Bit & Byte", type: "rss", topic: "tech", initials: "BB", url: "bitebyte.example/rss", status: "ok", every: "30 min" },
    { id: "fronte", name: "Il Fronte Digitale", type: "rss", topic: "tech", initials: "FD", url: "frontedigitale.example/feed", status: "ok", every: "1 h" },
    { id: "settimanale", name: "Settimanale Self-hosted", type: "rss", topic: "selfhost", initials: "SS", url: "settimanaleselfhosted.example/rss", status: "ok", every: "1 h" },
    { id: "laboratorio", name: "Laboratorio Domestico", type: "youtube", topic: "selfhost", initials: "LD", url: "youtube.com/@laboratoriodomestico", status: "ok", every: "1 h" },
    { id: "diario", name: "Diario di un homelab", type: "rss", topic: "selfhost", initials: "Dh", url: "diariohomelab.example/index.xml", status: "err", every: "6 h", note: "Errore 404 da 2 giorni" },
    { id: "gazzetta", name: "Gazzetta della Scienza", type: "rss", topic: "scienza", initials: "GS", url: "gazzettascienza.example/feed", status: "ok", every: "1 h" },
    { id: "bussola", name: "La Bussola", type: "rss", topic: "italia", initials: "Lb", url: "labussola.example/rss/ultime", status: "ok", every: "15 min" },
    { id: "borgo", name: "Notizie dal Borgo", type: "rss", topic: "italia", initials: "NB", url: "notiziedalborgo.example/feed", status: "slow", every: "1 h", note: "Risponde lentamente · ultimo controllo 12 s" }
  ],

  interests: [
    { k: "Luna", level: "alta" },
    { k: "Docker", level: "alta" },
    { k: "Self-hosting", level: "media" },
    { k: "iPhone", level: "media" },
    { k: "RSS", level: "media" },
    { k: "Galassie", level: "media" },
    { k: "Razzi", level: "media" },
    { k: "Fibra", level: "off" }
  ],

  muted: ["criptovalute", "oroscopo", "gossip"],

  articles: [
    {
      id: "a1", src: "orbita", topic: "spazio", time: "25 min", mins: 6, seed: 11,
      title: "Perché le prossime missioni lunari puntano tutte al polo sud",
      excerpt: "Ghiaccio nei crateri in ombra perenne, luce quasi continua sulle creste: ecco cosa rende quella regione la più contesa della Luna.",
      tags: ["luna", "esplorazione", "acqua"],
      author: "Redazione Orbita",
      summary: [
        "Nei crateri che non vedono mai il Sole il ghiaccio d'acqua può restare stabile per tempi lunghissimi.",
        "Le creste vicine ricevono luce quasi continua, ideale per l'energia solare.",
        "Acqua sul posto significa ossigeno e propellente senza portarli dalla Terra."
      ],
      body: [
        "Tutte le principali agenzie spaziali che progettano di tornare sulla Luna guardano nella stessa direzione: la regione attorno al polo sud. Il motivo principale è l'acqua.",
        "Alcuni crateri vicino al polo non ricevono mai la luce del Sole. Lì dentro le temperature scendono sotto i −230 °C e il ghiaccio d'acqua può restare stabile per tempi lunghissimi. Diverse missioni in orbita hanno raccolto indizi della sua presenza.",
        { h: "Luce quasi continua sulle creste" },
        "A pochi chilometri di distanza, sulle creste più alte, il Sole resta sopra l'orizzonte per gran parte del mese lunare. È la combinazione ideale: energia solare quasi costante accanto a una riserva di ghiaccio.",
        { q: "Acqua sul posto significa acqua da bere, ossigeno da respirare e idrogeno per il propellente." },
        "Restano sfide enormi: il terreno è accidentato, le ombre lunghe rendono difficile l'atterraggio e le comunicazioni con la Terra non sono sempre dirette."
      ]
    },
    {
      id: "a2", src: "settimanale", topic: "selfhost", time: "1 h", mins: 6, seed: 23,
      title: "Ho sostituito 6 abbonamenti con un mini PC da 150 €: ecco il mio stack Docker",
      excerpt: "Foto, password, documenti, musica e backup: elenco dei container, consumi reali e cosa rifarei diversamente.",
      tags: ["docker", "self-hosting", "mini pc"],
      author: "Andrea Conti",
      body: [
        "Due anni fa pagavo sei abbonamenti diversi: foto, password, note, musica, VPN e un backup nel cloud. Ho preso un mini PC usato con 16 GB di RAM e un SSD da 1 TB e ho spostato quasi tutto in casa.",
        "Lo stack gira con Docker Compose: un reverse proxy davanti, un gestore di password, una libreria foto con riconoscimento dei volti, un server musicale, un archivio per i documenti scansionati e un job notturno che cifra i backup e li copia su un disco esterno e su un secondo sito.",
        "Cosa rifarei diversamente: impostare i backup automatici subito, non dopo il primo spavento, e documentare ogni container in un README. Tra sei mesi non ricorderai perché hai aperto quella porta."
      ]
    },
    {
      id: "a3", src: "bitbyte", topic: "tech", time: "2 h", mins: 7, seed: 37,
      title: "Le PWA su iPhone: cosa possono fare davvero e cosa no",
      excerpt: "Notifiche, badge sull'icona, funzionamento offline e i limiti che restano rispetto a un'app nativa.",
      tags: ["iphone", "pwa", "ios", "web app"],
      author: "Marta Ferri",
      summary: [
        "Dalla versione 16.4 di iOS le web app sulla Home ricevono notifiche push e badge.",
        "Manca la sincronizzazione in background: i dati si aggiornano quando apri l'app.",
        "Per un lettore di feed basta: il lavoro pesante lo fa il server."
      ],
      body: [
        "Una PWA è un sito che si comporta come un'app: si aggiunge alla schermata Home, si apre a tutto schermo e può funzionare anche senza connessione.",
        "Su iPhone le web app installate ricevono notifiche push e mostrano un badge sull'icona da iOS 16.4. Con iOS 26, un sito aggiunto alla Home dal menu Condividi di Safari si apre come web app, a meno di disattivare l'opzione.",
        { h: "I limiti che restano" },
        "Niente sincronizzazione in background: l'app si aggiorna quando la apri o quando arriva una notifica. Lo spazio offline lo gestisce il sistema, e alcune funzioni native, come i widget, restano fuori portata.",
        "Per un lettore di notizie è un compromesso accettabile: scaricare e filtrare i feed lo fa un server, e il telefono deve solo mostrare il risultato."
      ]
    },
    {
      id: "a4", src: "cronache", topic: "spazio", time: "3 h", seed: 41,
      title: "Come atterra in verticale un razzo riutilizzabile",
      excerpt: "Motori riaccesi in discesa, alette a griglia e gambe d'appoggio: l'atterraggio spiegato passo per passo.",
      tags: ["razzi", "lanci", "riutilizzabili"],
      video: { dur: "12:48" }
    },
    {
      id: "a5", src: "laboratorio", topic: "selfhost", time: "4 h", seed: 53,
      title: "Un homelab in uno sgabuzzino: rumore, consumi e lezioni imparate",
      excerpt: "Dopo un anno: 38 W di media, una ventola sostituita e un UPS che ha salvato i dati due volte.",
      tags: ["homelab", "self-hosting", "consumi"],
      video: { dur: "18:05" }
    },
    {
      id: "a6", src: "gazzetta", topic: "scienza", time: "5 h", mins: 8, seed: 67,
      title: "Come si misura la distanza di una galassia lontana",
      excerpt: "Parallasse, stelle variabili, supernove e redshift: la scala delle distanze cosmiche spiegata gradino per gradino.",
      tags: ["galassie", "astronomia", "cosmologia"],
      author: "Luca Bassi",
      body: [
        "Per le stelle vicine basta la geometria: osservando la stessa stella a sei mesi di distanza, la sua posizione apparente si sposta di pochissimo. È la parallasse.",
        "Più lontano servono le candele standard, oggetti di cui conosciamo la luminosità reale. Le variabili Cefeidi pulsano con un periodo legato alla loro luminosità; le supernove di tipo Ia raggiungono un picco di luminosità molto simile tra loro.",
        { h: "Oltre le candele" },
        "Per le galassie più lontane si usa lo spostamento verso il rosso della luce, il redshift, che cresce con la distanza a causa dell'espansione dell'universo."
      ]
    },
    {
      id: "a7", src: "fronte", topic: "tech", time: "6 h", mins: 9, seed: 71,
      title: "Backup 3-2-1 per chi ha un NAS in casa: la guida pratica",
      excerpt: "Tre copie, due supporti diversi, una fuori casa. Come applicarlo con strumenti gratuiti e senza impazzire.",
      tags: ["backup", "nas", "self-hosting"]
    },
    {
      id: "a8", src: "cielo", topic: "spazio", time: "7 h", mins: 5, seed: 83,
      title: "La Via Lattea fotografata con uno smartphone da un rifugio sulle Dolomiti",
      excerpt: "Treppiede, modalità notte e 4 minuti di esposizione totale. Nessun ritocco oltre a un po' di contrasto.",
      tags: ["astrofotografia", "via lattea", "smartphone"],
      author: "Giulia Sartori"
    },
    {
      id: "a9", src: "bitbyte", topic: "tech", time: "8 h", mins: 5, seed: 97,
      title: "RSS non è morto: perché sempre più persone tornano ai lettori di feed",
      excerpt: "Niente algoritmi, niente pubblicità mirata, e l'ordine lo decidi tu. Una tecnologia del 1999 che torna utile.",
      tags: ["rss", "lettori", "web"]
    },
    {
      id: "a10", src: "borgo", topic: "italia", time: "9 h", mins: 6, seed: 101,
      title: "Internet in campagna: antenne esterne e satellite a confronto",
      excerpt: "Dove la fibra non arriva e il 4G va a singhiozzo: costi, velocità reali e installazione delle alternative.",
      tags: ["fibra", "connessione", "casa"]
    },
    {
      id: "a11", src: "bussola", topic: "italia", time: "10 h", mins: 4, seed: 113,
      title: "Treni regionali: come leggere gli orari invernali",
      excerpt: "Cosa cambia nelle fasce del mattino, dove trovare gli orari ufficiali e come impostare gli avvisi sui ritardi.",
      tags: ["treni", "trasporti"]
    },
    {
      id: "a12", src: "bussola", topic: "italia", time: "11 h", mins: 3, seed: 127,
      title: "Criptovalute: le 5 monete da comprare subito secondo gli esperti",
      excerpt: "Una classifica che promette rendimenti sicuri.",
      tags: ["criptovalute", "finanza"]
    },
    {
      id: "a13", src: "fronte", topic: "tech", time: "12 h", mins: 2, seed: 131,
      title: "Oroscopo tech: cosa dicono le stelle sul tuo smartphone",
      excerpt: "Il segno zodiacale e il telefono giusto.",
      tags: ["oroscopo"]
    },
    {
      id: "a14", src: "gazzetta", topic: "scienza", time: "ieri", mins: 7, seed: 139,
      title: "Cosa ci dicono le galassie più lontane mai osservate",
      excerpt: "Luce partita poche centinaia di milioni di anni dopo il Big Bang: perché quelle galassie appaiono così luminose.",
      tags: ["galassie", "telescopi", "cosmologia"]
    }
  ]
};
