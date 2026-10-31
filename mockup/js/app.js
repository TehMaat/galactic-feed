// Galactic Feed · logica del mockup (nessun server: tutto gira nel browser con i dati di esempio).
(function () {
  "use strict";

  const D = window.GF_DATA;
  const ART = window.GF_ART;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const byId = Object.fromEntries(D.articles.map((a) => [a.id, a]));
  const root = document.documentElement;
  const hostTheme = root.dataset.theme;

  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem("gf-" + key);
        return v == null ? fallback : JSON.parse(v);
      } catch (err) {
        return fallback;
      }
    },
    set(key, value) {
      try { localStorage.setItem("gf-" + key, JSON.stringify(value)); } catch (err) { /* storage non disponibile */ }
    }
  };

  // Non letti già presenti sul server prima di oggi, per rendere realistici i contatori.
  const BACKLOG = { orbita: 6, cronache: 1, rspace: 12, bitbyte: 9, fronte: 3, rselfhosted: 21, rhomelab: 7, diario: 0, gazzetta: 4, bussola: 10, ritaly: 28 };
  const LEVEL = { alta: "alta", media: "media", off: "spento" };
  const NEXT_LEVEL = { alta: "media", media: "off", off: "alta" };
  const FILTERS = [["tutti", "Tutti"], ["perte", "Per te"], ["nonletti", "Non letti"], ["reddit", "Reddit"], ["video", "Video"]]
    .concat(Object.entries(D.topics).map(([k, t]) => [k, t.label]));

  const state = {
    tab: "oggi",
    mode: "edizione",
    filter: "tutti",
    query: "",
    showHidden: false,
    read: new Set(["a11"]),
    saved: new Set(store.get("saved", ["a6"])),
    interests: D.interests.map((i) => ({ ...i })),
    muted: D.muted.slice(),
    rules: { minVotes: true, dedupe: true, summaries: true, push: true, evening: false },
    sources: D.sources.map((s) => ({ ...s })),
    current: null,
    ts: 1,
    theme: store.get("theme", "auto"),
    lastFetch: "07:00",
    addType: "rss",
    addUrl: "",
    addFound: false,
    addChoice: 0,
    addSort: 1,
    addTopic: "spazio"
  };

  // ---------- Helpers ----------
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const icon = (id) => `<svg class="ico" aria-hidden="true"><use href="#i-${id}"/></svg>`;
  const srcOf = (a) => state.sources.find((s) => s.id === a.src);
  const haystack = (a) => (a.title + " " + a.tags.join(" ")).toLowerCase();
  const ago = (t) => (t === "ieri" ? "ieri" : t + " fa");
  const typeLabel = (t) => ({ rss: "RSS", reddit: "Reddit", youtube: "YouTube" }[t]);

  function srcColor(s) {
    if (s.type === "reddit") return "var(--c-reddit)";
    if (s.type === "youtube") return "var(--c-video)";
    return D.topics[s.topic].color;
  }

  function isMuted(a) {
    const t = haystack(a);
    return state.muted.some((m) => t.includes(m.toLowerCase()));
  }

  function matchOf(a) {
    const t = haystack(a);
    const hits = state.interests.filter((i) => i.level !== "off" && t.includes(i.k.toLowerCase()));
    hits.sort((x, y) => (x.level === "alta" ? 0 : 1) - (y.level === "alta" ? 0 : 1));
    return hits[0] || null;
  }

  function editionItems() {
    return D.articles
      .filter((a) => !isMuted(a))
      .map((a) => ({ a, m: matchOf(a) }))
      .filter((x) => x.m);
  }

  function unreadOf(s) {
    const fresh = D.articles.filter((a) => a.src === s.id && !state.read.has(a.id) && !isMuted(a)).length;
    return fresh + (BACKLOG[s.id] || 0);
  }

  function thumb(a, kind) {
    const wide = kind === "wide";
    const img = `<img class="thumb" src="${ART.cover(a.seed, a.topic, wide ? 480 : 96, wide ? 300 : 96)}" alt="" decoding="async">`;
    if (!a.video) return img;
    return `<span class="thumb-wrap">${img}<span class="play">${icon("play")}</span><span class="dur">${esc(a.video.dur)}</span></span>`;
  }

  function avatar(s) {
    return `<span class="mono-av" style="--src-c:${srcColor(s)}">${esc(s.initials)}</span>`;
  }

  function meta(a) {
    const s = srcOf(a);
    return `<div class="meta">${avatar(s)}<span class="src">${esc(s.name)}</span><span class="sep"></span><span>${esc(a.time)}</span></div>`;
  }

  const matchTag = (m) => `<span class="match">${icon("spark")}${esc(m.k)}</span>`;

  function saveBtn(a) {
    const on = state.saved.has(a.id);
    return `<button type="button" class="save-btn ${on ? "is-on" : ""}" data-action="toggle-save" data-id="${a.id}" aria-pressed="${on}" aria-label="${on ? "Rimuovi dai salvati" : "Salva"}">${icon("bookmark")}</button>`;
  }

  function switchBtn(key, label) {
    return `<button type="button" class="switch" role="switch" aria-checked="${state.rules[key]}" data-action="rule" data-key="${key}" aria-label="${esc(label)}"></button>`;
  }

  // ---------- Edizione ----------
  function greeting() {
    const h = new Date().getHours();
    if (h < 13) return "Buongiorno.";
    if (h < 18) return "Buon pomeriggio.";
    return "Buonasera.";
  }

  function renderEdition() {
    const items = editionItems();
    const visible = D.articles.filter((a) => !isMuted(a));
    const hidden = D.articles.length - visible.length;
    const hero = items.find((x) => x.m.level === "alta") || items[0];
    const rest = items.filter((x) => x !== hero);
    const evening = new Date().getHours() >= 18;
    const date = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long" }).format(new Date());

    let html = `
      <section class="masthead" aria-label="Edizione di oggi">
        <canvas class="stars" aria-hidden="true"></canvas>
        <p class="mast-kicker">${evening ? "Edizione della sera" : "Edizione del mattino"} · n. 214</p>
        <h2 class="mast-title">${greeting()}<br>Ecco cosa conta oggi.</h2>
        <p class="mast-date">${esc(date)}</p>
        <div class="mast-stats">
          <div><b>${state.sources.length}</b><span>fonti</span></div>
          <div><b>${visible.length}</b><span>nuovi</span></div>
          <div class="is-star"><b>${items.length}</b><span>per te</span></div>
          <div><b>${hidden}</b><span>nascosti</span></div>
        </div>
        <p class="mast-foot">Composta alle ${evening ? "18:00 · prossima alle 07:00" : "07:00 · prossima alle 18:00"}</p>
      </section>`;

    if (hero) {
      const a = hero.a;
      html += `
      <article class="hero tap ${state.read.has(a.id) ? "is-read" : ""}" role="button" tabindex="0" data-action="open" data-id="${a.id}">
        ${thumb(a, "wide")}
        <div class="hero-body">
          <div class="hero-label"><span class="count">In primo piano</span>${matchTag(hero.m)}</div>
          <h3 class="hero-title">${esc(a.title)}</h3>
          <p class="excerpt clamp-2">${esc(a.excerpt)}</p>
          ${meta(a)}
        </div>
      </article>`;
    }

    for (const [key, t] of Object.entries(D.topics)) {
      const group = rest.filter((x) => x.a.topic === key);
      if (!group.length) continue;
      html += `
      <div class="section-h"><h3><span class="dot" style="--topic-c:${t.color}"></span>${esc(t.label)}</h3><span class="count">${group.length}</span></div>
      <div class="list">${group.map(({ a, m }) => `
        <article class="row tap ${state.read.has(a.id) ? "is-read" : ""}" role="button" tabindex="0" data-action="open" data-id="${a.id}">
          <div class="row-text">
            <h4 class="row-title clamp-3">${esc(a.title)}</h4>
            <div class="row-foot">${meta(a)}${matchTag(m)}</div>
          </div>
          ${thumb(a)}
        </article>`).join("")}
      </div>`;
    }

    html += `
      <div class="edition-end">${icon("check")}<b>Sei in pari</b><span>${items.length} notizie scelte tra ${visible.length}. Il resto è nel Flusso.</span></div>`;

    const el = $("#edition");
    el.innerHTML = html;
    ART.paintStars($(".stars", el), 214);
  }

  // ---------- Flusso ----------
  function passes(a, filter, q) {
    if (isMuted(a) && !state.showHidden) return false;
    if (q && !(haystack(a).includes(q) || srcOf(a).name.toLowerCase().includes(q))) return false;
    switch (filter) {
      case "tutti": return true;
      case "perte": return !!matchOf(a);
      case "nonletti": return !state.read.has(a.id);
      case "reddit": return srcOf(a).type === "reddit";
      case "video": return !!a.video;
      default: return a.topic === filter;
    }
  }

  function card(a) {
    const s = srcOf(a);
    const m = matchOf(a);
    const tag = s.type === "reddit" ? `<span class="type-tag reddit">Reddit</span>` : a.video ? `<span class="type-tag video">Video</span>` : "";
    const stats = a.reddit
      ? `<span>${icon("up")}${esc(a.reddit.up)}</span><span>${icon("comment")}${a.reddit.comments}</span><span>${esc(a.reddit.flair)}</span>`
      : `<span>${a.video ? "Video · " + esc(a.video.dur) : a.mins ? a.mins + " min di lettura" : ""}</span>`;
    const badge = m ? matchTag(m) : isMuted(a) ? `<span class="match">Silenziato</span>` : "";
    return `
      <article class="card tap ${state.read.has(a.id) ? "is-read" : ""}" role="button" tabindex="0" data-action="open" data-id="${a.id}">
        <div class="card-top">${meta(a)}${tag}</div>
        <div class="card-main">
          <div class="card-text">
            <h3 class="card-title clamp-3">${esc(a.title)}</h3>
            <p class="excerpt clamp-2">${esc(a.excerpt)}</p>
          </div>
          ${thumb(a)}
        </div>
        <div class="card-foot"><div class="stats">${stats}</div><div class="foot-r">${badge}${saveBtn(a)}</div></div>
      </article>`;
  }

  function renderStreamShell() {
    $("#stream").innerHTML = `
      <label class="search">${icon("search")}<input id="stream-search" type="search" placeholder="Cerca negli articoli e nelle fonti" autocomplete="off" aria-label="Cerca"></label>
      <div class="chips" id="chips" role="toolbar" aria-label="Filtri"></div>
      <div class="stack" id="stream-list"></div>`;
    $("#stream-search").addEventListener("input", (e) => {
      state.query = e.target.value;
      renderStreamList();
    });
  }

  function renderStreamList() {
    const q = state.query.trim().toLowerCase();
    const chips = $("#chips");
    const scroll = chips.scrollLeft;
    chips.innerHTML = FILTERS.map(([k, label]) => {
      const n = D.articles.filter((a) => passes(a, k, q)).length;
      const dot = D.topics[k] ? `<span class="dot" style="--topic-c:${D.topics[k].color}"></span>` : "";
      return `<button type="button" class="chip" data-action="filter" data-f="${k}" aria-pressed="${state.filter === k}">${dot}${esc(label)}<span class="n">${n}</span></button>`;
    }).join("");
    chips.scrollLeft = scroll;

    const list = D.articles.filter((a) => passes(a, state.filter, q));
    const hiddenCount = D.articles.filter(isMuted).length;
    let html = list.length
      ? list.map(card).join("")
      : `<div class="empty">${icon("search")}<h3>Nessun risultato</h3><p>Prova un altro filtro o un'altra parola.</p></div>`;
    if (hiddenCount && !state.showHidden) {
      html += `<div class="hidden-note">${icon("eye-off")}<span>${hiddenCount} articoli nascosti dalle parole silenziate</span><button type="button" data-action="show-hidden">Mostra</button></div>`;
    }
    $("#stream-list").innerHTML = html;
  }

  // ---------- Fonti ----------
  function srcRow(s) {
    const dot = s.status === "err" ? "err" : s.status === "warn" ? "warn" : "";
    const sub = s.note || (s.type === "reddit" ? `Reddit · RSS fino al 13/11 · ogni ${s.every}` : `${typeLabel(s.type)} · ogni ${s.every}`);
    return `
      <div class="src-row" role="button" tabindex="0" data-action="filter-source" data-id="${s.id}" aria-label="Mostra gli articoli di ${esc(s.name)}">
        <span class="src-av" style="--src-c:${srcColor(s)}">${esc(s.initials)}</span>
        <span class="src-text"><span class="src-name">${esc(s.name)}</span><span class="src-sub"><span class="status-dot ${dot}"></span>${esc(sub)}</span></span>
        <span class="unread">${unreadOf(s)}</span>
      </div>`;
  }

  function renderSources() {
    const reddit = state.sources.filter((s) => s.type === "reddit").length;
    $("#sources-count").textContent = `${state.sources.length} fonti in ${Object.keys(D.topics).length} cartelle`;
    let html = `<div class="banner">${icon("alert")}<p><b>Reddit chiude i feed RSS il 13 novembre 2026.</b> Le ${reddit} fonti Reddit funzionano fino a quella data. Dopo servirà l'accesso alle API, da richiedere a Reddit, oppure un'alternativa.</p></div>`;
    for (const [key, t] of Object.entries(D.topics)) {
      const list = state.sources.filter((s) => s.topic === key);
      if (!list.length) continue;
      const unread = list.reduce((n, s) => n + unreadOf(s), 0);
      html += `<div class="group-label"><span>${esc(t.label)}</span><span>${unread} non letti</span></div><div class="list">${list.map(srcRow).join("")}</div>`;
    }
    html += `<div class="list mt"><button type="button" class="link-row" data-action="toast" data-msg="Nell'app vera scegli il file .opml esportato da Feedly, Inoreader o un altro lettore">${icon("upload")}Importa da un altro lettore (OPML)</button></div>`;
    $("#sources").innerHTML = html;
  }

  // ---------- Interessi ----------
  function rule(key, title, sub) {
    return `<div class="rule"><div><div class="rule-title">${esc(title)}</div><div class="rule-sub">${esc(sub)}</div></div>${switchBtn(key, title)}</div>`;
  }

  function renderInterests() {
    const n = editionItems().length;
    const total = D.articles.filter((a) => !isMuted(a)).length;
    $("#interests").innerHTML = `
      <div class="preview"><b>${n}</b><span>notizie di oggi entrano nell'Edizione con queste regole, su ${total} arrivate.</span></div>
      <section class="panel">
        <h3>Mi interessa <span class="count">tocca per la priorità</span></h3>
        <div class="tags">${state.interests.map((it, i) => `<button type="button" class="tag" data-level="${it.level}" data-action="cycle-interest" data-i="${i}">${esc(it.k)}<span class="lvl">${LEVEL[it.level]}</span></button>`).join("")}</div>
        <form class="add-inline" data-form="interest"><input id="new-interest" placeholder="Parola o argomento" autocomplete="off" aria-label="Nuovo interesse"><button type="submit">Aggiungi</button></form>
      </section>
      <section class="panel">
        <h3>Silenzia</h3>
        <p class="hint">Gli articoli che contengono queste parole spariscono dall'Edizione e dal Flusso.</p>
        <div class="tags">${state.muted.map((w, i) => `<button type="button" class="tag" data-action="unmute" data-i="${i}" aria-label="Smetti di silenziare ${esc(w)}">${esc(w)}${icon("close")}</button>`).join("")}</div>
        <form class="add-inline" data-form="mute"><input id="new-mute" placeholder="Parola da silenziare" autocomplete="off" aria-label="Nuova parola da silenziare"><button type="submit">Aggiungi</button></form>
      </section>
      <section class="panel">
        <h3>Regole</h3>
        ${rule("minVotes", "Reddit: solo post sopra i 100 voti", "Salta i post appena pubblicati e senza discussione.")}
        ${rule("dedupe", "Unisci i doppioni", "La stessa notizia da più fonti compare una volta sola.")}
        ${rule("summaries", "Riassunto automatico", "Tre punti in cima agli articoli lunghi, scritti da un modello AI. Facoltativo.")}
      </section>`;
  }

  // ---------- Salvati ----------
  function renderSaved() {
    const items = D.articles.filter((a) => state.saved.has(a.id));
    $("#saved").innerHTML = items.length
      ? `<div class="stack">${items.map(card).join("")}</div>`
      : `<div class="empty">${icon("bookmark")}<h3>Ancora niente</h3><p>Tocca il segnalibro su un articolo per ritrovarlo qui, anche senza connessione.</p></div>`;
    const badge = $("#saved-badge");
    badge.hidden = !items.length;
    badge.textContent = items.length;
  }

  function renderAll() {
    renderEdition();
    renderStreamList();
    renderSources();
    renderInterests();
    renderSaved();
  }

  // ---------- Lettore ----------
  function paragraph(p) {
    if (typeof p === "string") return `<p>${esc(p)}</p>`;
    if (p.h) return `<h4>${esc(p.h)}</h4>`;
    return `<blockquote>${esc(p.q)}</blockquote>`;
  }

  function openReader(id) {
    const a = byId[id];
    if (!a) return;
    const s = srcOf(a);
    const m = matchOf(a);
    state.current = id;
    state.read.add(id);

    const byline = a.reddit
      ? [a.reddit.author, ago(a.time), `${a.reddit.up} voti`, `${a.reddit.comments} commenti`]
      : [a.author || s.name, ago(a.time), a.mins ? `${a.mins} min di lettura` : a.video ? `durata ${a.video.dur}` : ""];
    const summary = a.summary && state.rules.summaries
      ? `<div class="ai-summary"><div class="lbl">${icon("spark")}Riassunto automatico</div><ul>${a.summary.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`
      : "";
    const body = a.body
      ? a.body.map(paragraph).join("")
      : `<p>${esc(a.excerpt)}</p><p class="hint">In questo mockup il testo completo c'è solo per alcuni articoli. Nell'app vera il server lo estrae dalla pagina originale, senza pubblicità.</p>`;
    const comments = a.comments
      ? `<h4 class="comments-h">Commenti più votati</h4><div class="comments">${a.comments.map((c) => `
          <div class="comment"><div class="who"><b>${esc(c.who)}</b>${c.op ? `<span class="type-tag">autore</span>` : ""}<span>↑ ${esc(c.up)}</span></div>${esc(c.text)}</div>`).join("")}</div>`
      : "";
    const cta = a.reddit ? "Apri la discussione su Reddit" : a.video ? "Guarda su YouTube" : "Apri l'articolo originale";

    $("#reader-scroll").innerHTML = `
      ${thumb(a, "wide")}
      <div class="reader-kicker"><div class="meta">${avatar(s)}<span class="src">${esc(s.name)}</span></div>${a.reddit ? `<span class="type-tag reddit">${esc(a.reddit.flair)}</span>` : ""}${m ? matchTag(m) : ""}</div>
      <h1 class="reader-title">${esc(a.title)}</h1>
      <div class="byline">${byline.filter(Boolean).map(esc).join(`<span class="sep"></span>`)}</div>
      ${summary}
      <div class="reader-body">${body}</div>
      ${comments}
      <div class="reader-end">
        <button type="button" class="btn-primary" data-action="open-original">${icon("external")}${cta}</button>
        <button type="button" class="btn-secondary" data-action="mark-unread">Segna come non letto</button>
      </div>`;

    const reader = $("#reader");
    $("#reader-scroll").scrollTop = 0;
    reader.classList.add("is-open");
    reader.setAttribute("aria-hidden", "false");
    updateReaderSave();
    renderAll();
    setTimeout(() => $(".back-btn", reader).focus({ preventScroll: true }), 360);
  }

  function closeReader() {
    const reader = $("#reader");
    reader.classList.remove("is-open");
    reader.setAttribute("aria-hidden", "true");
    state.current = null;
  }

  function updateReaderSave() {
    const btn = $("#reader-save");
    const on = state.current && state.saved.has(state.current);
    btn.classList.toggle("is-on", !!on);
    btn.setAttribute("aria-label", on ? "Rimuovi dai salvati" : "Salva");
    btn.setAttribute("aria-pressed", String(!!on));
  }

  // ---------- Schede (aggiungi fonte, impostazioni) ----------
  const ADD_TYPES = {
    rss: { label: "Sito o feed", ph: "https://sito.it o l'indirizzo del feed", hint: "Incolla l'indirizzo di un sito: il server cerca da solo i feed RSS o Atom disponibili." },
    reddit: { label: "Reddit", ph: "r/nome-del-subreddit", hint: "" },
    youtube: { label: "YouTube", ph: "Link del canale o @nome", hint: "Ogni canale YouTube ha un feed pubblico con gli ultimi video: non serve nessun account." }
  };
  const REDDIT_SORT = ["Hot", "Top del giorno", "Nuovi"];

  function guessName() {
    const raw = state.addUrl.trim();
    if (state.addType === "reddit") return "r/" + (raw.replace(/^.*r\//, "").replace(/[^\w]/g, "") || "fotografia");
    if (state.addType === "youtube") return raw.replace(/^.*@/, "@").replace(/[^\w@.-]/g, "") || "@divulgazione";
    let host = "astrofili.example";
    try { host = new URL(/^https?:\/\//.test(raw) ? raw : "https://" + raw).hostname || host; } catch (err) { /* indirizzo non valido: si usa l'esempio */ }
    const word = host.replace(/^www\./, "").split(".")[0];
    return word.charAt(0).toUpperCase() + word.slice(1);
  }

  function candidates() {
    const name = guessName();
    if (state.addType === "reddit") {
      return [
        { name, sub: `${REDDIT_SORT[state.addSort]} · circa 40 post al giorno` },
        { name: `${name} · solo con immagini`, sub: "filtro sui post con foto o video" }
      ];
    }
    if (state.addType === "youtube") return [{ name, sub: "ultimi 15 video · feed pubblico del canale" }];
    return [
      { name: `${name} · tutte le notizie`, sub: "/feed.xml · circa 25 articoli al giorno" },
      { name: `${name} · solo approfondimenti`, sub: "/categoria/approfondimenti/feed · 3 a settimana" },
      { name: `${name} · commenti`, sub: "/comments/feed" }
    ];
  }

  function renderAdd() {
    const t = ADD_TYPES[state.addType];
    const options = state.addType === "reddit"
      ? `<div class="field"><span class="label">Ordina per</span><div class="segmented" style="--cols:3">${REDDIT_SORT.map((x, i) => `<button type="button" aria-pressed="${state.addSort === i}" data-action="add-sort" data-i="${i}">${x}</button>`).join("")}</div></div>
         <div class="banner">${icon("alert")}<p><b>Dal 13 novembre 2026</b> Reddit non offre più i feed RSS. Fino ad allora funziona; dopo servirà l'accesso alle API approvato da Reddit, oppure un'alternativa.</p></div>`
      : `<p class="hint">${esc(t.hint)}</p>`;
    const found = state.addFound
      ? `<div class="field"><span class="label">Feed trovati</span><div class="found" role="radiogroup" aria-label="Feed trovati">${candidates().map((c, i) => `
          <button type="button" class="found-item" role="radio" aria-checked="${state.addChoice === i}" data-action="add-choice" data-i="${i}"><span class="radio">${icon("check")}</span><span><span class="found-name">${esc(c.name)}</span><br><span class="found-sub">${esc(c.sub)}</span></span></button>`).join("")}</div></div>
         <div class="field"><span class="label">Cartella</span><div class="tags">${Object.entries(D.topics).map(([k, tp]) => `<button type="button" class="tag" aria-pressed="${state.addTopic === k}" data-action="add-topic" data-k="${k}"><span class="dot" style="--topic-c:${tp.color}"></span>${esc(tp.label)}</button>`).join("")}</div></div>
         <button type="button" class="btn-primary" data-action="add-confirm">${icon("plus")}Aggiungi fonte</button>`
      : "";
    $("#add-body").innerHTML = `
      <div class="form-stack">
        <div class="segmented" style="--cols:3" role="tablist" aria-label="Tipo di fonte">${Object.entries(ADD_TYPES).map(([k, v]) => `<button type="button" role="tab" aria-selected="${state.addType === k}" data-action="add-type" data-type="${k}">${v.label}</button>`).join("")}</div>
        <form class="form-stack" data-form="find">
          <div class="field"><label for="add-url">Indirizzo</label><input class="input" id="add-url" placeholder="${esc(t.ph)}" value="${esc(state.addUrl)}" autocomplete="off" autocapitalize="off" spellcheck="false"></div>
          ${options}
          <button type="submit" class="btn-secondary">${icon("search")}Cerca feed</button>
        </form>
        ${found}
      </div>`;
  }

  function renderSettings() {
    $("#settings-body").innerHTML = `
      <div class="set-label">Aspetto</div>
      <div class="set-group">
        <div class="set-row"><span>Tema</span><div class="segmented" style="--cols:3">${[["auto", "Auto"], ["light", "Chiaro"], ["dark", "Scuro"]].map(([k, l]) => `<button type="button" aria-pressed="${state.theme === k}" data-action="theme" data-value="${k}">${l}</button>`).join("")}</div></div>
        <div class="set-row"><span>Dimensione del testo</span><span class="val">${Math.round(state.ts * 100)}%</span></div>
      </div>
      <div class="set-label">Edizione</div>
      <div class="set-group">
        <div class="set-row"><span>Edizione del mattino</span><span class="val">07:00</span></div>
        <div class="set-row"><span>Edizione della sera</span>${switchBtn("evening", "Edizione della sera")}</div>
        <div class="set-row"><span>Notifica per le priorità alte</span>${switchBtn("push", "Notifica per le priorità alte")}</div>
      </div>
      <p class="set-note">Su iPhone le notifiche arrivano solo se l'app è aggiunta alla schermata Home (iOS 16.4 o successivo).</p>
      <div class="set-label">Server</div>
      <div class="set-group">
        <div class="set-row"><span>Indirizzo</span><span class="val">feed.casa.example</span></div>
        <div class="set-row"><span>Controllo delle fonti</span><span class="val">ogni 30 min</span></div>
        <div class="set-row"><span>Ultimo controllo</span><span class="val">${state.lastFetch}</span></div>
      </div>
      <div class="set-label">Dati</div>
      <div class="set-group"><button type="button" class="link-row" data-action="toast" data-msg="Nell'app vera scarichi un file .opml con tutte le fonti">${icon("upload")}Esporta le fonti (OPML)</button></div>
      <p class="set-note">Mockup v0.1 · tutti i contenuti sono di esempio.</p>`;
  }

  function openSheet(name) {
    if (name === "add") renderAdd();
    if (name === "settings") renderSettings();
    const sheet = $("#sheet-" + name);
    const scrim = $("#scrim");
    scrim.hidden = false;
    requestAnimationFrame(() => {
      scrim.classList.add("is-on");
      sheet.classList.add("is-open");
      sheet.setAttribute("aria-hidden", "false");
    });
  }

  function closeSheet() {
    $$(".sheet.is-open").forEach((s) => {
      s.classList.remove("is-open");
      s.setAttribute("aria-hidden", "true");
    });
    const scrim = $("#scrim");
    scrim.classList.remove("is-on");
    setTimeout(() => { if (!$(".sheet.is-open")) scrim.hidden = true; }, 260);
  }

  // ---------- Navigazione ----------
  function switchTab(tab) {
    closeReader();
    closeSheet();
    state.tab = tab;
    $$(".view").forEach((v) => {
      const on = v.dataset.view === tab;
      v.hidden = !on;
      v.classList.toggle("is-entering", on);
    });
    $$(".tabbar button").forEach((b) => {
      if (b.dataset.tab === tab) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    if (tab === "oggi") ART.paintStars($("#edition .stars"), 214);
  }

  function setMode(mode) {
    state.mode = mode;
    $("#edition").hidden = mode !== "edizione";
    $("#stream").hidden = mode !== "flusso";
    $("#mode-edizione").setAttribute("aria-selected", String(mode === "edizione"));
    $("#mode-flusso").setAttribute("aria-selected", String(mode === "flusso"));
    if (mode === "edizione") ART.paintStars($("#edition .stars"), 214);
  }

  function applyTheme(theme) {
    state.theme = theme;
    store.set("theme", theme);
    if (theme === "auto") {
      if (hostTheme) root.dataset.theme = hostTheme;
      else delete root.dataset.theme;
    } else {
      root.dataset.theme = theme;
    }
  }

  let toastTimer;
  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.add("is-on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("is-on"), 2600);
  }

  const DEMOS = {
    edizione: () => { switchTab("oggi"); setMode("edizione"); },
    flusso: () => { switchTab("oggi"); setMode("flusso"); },
    articolo: () => { switchTab("oggi"); openReader("a1"); },
    reddit: () => { switchTab("oggi"); openReader("a2"); },
    fonti: () => switchTab("fonti"),
    aggiungi: () => { switchTab("fonti"); openSheet("add"); },
    interessi: () => switchTab("interessi"),
    impostazioni: () => { switchTab("oggi"); openSheet("settings"); }
  };

  // ---------- Azioni ----------
  const actions = {
    tab: (el) => switchTab(el.dataset.tab),
    mode: (el) => setMode(el.dataset.mode),
    open: (el) => openReader(el.dataset.id),
    "close-reader": () => closeReader(),
    "toggle-save": (el) => {
      const id = el.dataset.id || state.current;
      if (!id) return;
      const on = !state.saved.has(id);
      if (on) state.saved.add(id); else state.saved.delete(id);
      store.set("saved", [...state.saved]);
      updateReaderSave();
      renderStreamList();
      renderSaved();
      toast(on ? "Salvato: lo trovi anche offline" : "Rimosso dai salvati");
    },
    "text-size": () => {
      const sizes = [1, 1.12, 0.92];
      state.ts = sizes[(sizes.indexOf(state.ts) + 1) % sizes.length];
      $("#app").style.setProperty("--ts", state.ts);
      toast(state.ts > 1 ? "Testo più grande" : state.ts < 1 ? "Testo più piccolo" : "Testo standard");
    },
    "open-original": () => toast("Nell'app vera si apre la pagina originale in Safari"),
    "mark-unread": () => {
      if (state.current) state.read.delete(state.current);
      closeReader();
      renderAll();
      toast("Segnato come non letto");
    },
    refresh: (el) => {
      el.classList.add("is-spinning");
      setTimeout(() => {
        el.classList.remove("is-spinning");
        state.lastFetch = new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit" }).format(new Date());
        toast(`${state.sources.length} fonti controllate · nessun articolo nuovo`);
      }, 1100);
    },
    filter: (el) => { state.filter = el.dataset.f; renderStreamList(); },
    "show-hidden": () => { state.showHidden = true; renderStreamList(); },
    "filter-source": (el) => {
      const s = state.sources.find((x) => x.id === el.dataset.id);
      switchTab("oggi");
      setMode("flusso");
      state.filter = "tutti";
      state.query = s.name;
      $("#stream-search").value = s.name;
      renderStreamList();
    },
    "cycle-interest": (el) => {
      const it = state.interests[Number(el.dataset.i)];
      it.level = NEXT_LEVEL[it.level];
      renderAll();
      toast(`${it.k}: priorità ${LEVEL[it.level]}`);
    },
    unmute: (el) => {
      const [w] = state.muted.splice(Number(el.dataset.i), 1);
      renderAll();
      toast(`"${w}" non è più silenziata`);
    },
    rule: (el) => {
      const key = el.dataset.key;
      state.rules[key] = !state.rules[key];
      el.setAttribute("aria-checked", String(state.rules[key]));
    },
    "open-sheet": (el) => openSheet(el.dataset.sheet),
    "close-sheet": () => closeSheet(),
    "add-type": (el) => { state.addType = el.dataset.type; state.addFound = false; state.addUrl = ""; renderAdd(); },
    "add-sort": (el) => { state.addSort = Number(el.dataset.i); renderAdd(); },
    "add-choice": (el) => { state.addChoice = Number(el.dataset.i); renderAdd(); },
    "add-topic": (el) => { state.addTopic = el.dataset.k; renderAdd(); },
    "add-confirm": () => {
      const c = candidates()[state.addChoice];
      const name = c.name.split(" · ")[0];
      const type = state.addType;
      state.sources.push({
        id: "nuova-" + state.sources.length,
        name,
        type,
        topic: state.addTopic,
        initials: type === "reddit" ? "r/" : name.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2) || "N",
        status: "ok",
        every: "30 min",
        note: "Appena aggiunta · primo controllo in corso"
      });
      state.addFound = false;
      state.addUrl = "";
      closeSheet();
      renderAll();
      toast(`${name} aggiunta a ${D.topics[state.addTopic].label}`);
    },
    theme: (el) => { applyTheme(el.dataset.value); renderSettings(); },
    toast: (el) => toast(el.dataset.msg),
    demo: (el) => {
      $$(".brief-links button").forEach((b) => b.classList.toggle("is-active", b === el));
      DEMOS[el.dataset.demo]();
    }
  };

  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-action]");
    if (!el || !actions[el.dataset.action]) return;
    actions[el.dataset.action](el, e);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if ($(".sheet.is-open")) closeSheet();
      else if (state.current) closeReader();
      return;
    }
    const el = e.target;
    if ((e.key === "Enter" || e.key === " ") && el.getAttribute && el.getAttribute("role") === "button" && el.dataset.action) {
      e.preventDefault();
      actions[el.dataset.action](el, e);
    }
  });

  document.addEventListener("submit", (e) => {
    const form = e.target.closest("form[data-form]");
    if (!form) return;
    e.preventDefault();
    const kind = form.dataset.form;
    if (kind === "find") {
      state.addUrl = $("#add-url").value;
      state.addFound = true;
      state.addChoice = 0;
      renderAdd();
      return;
    }
    const input = $("input", form);
    const value = input.value.trim();
    if (!value) { input.focus(); return; }
    if (kind === "interest") {
      state.interests.push({ k: value, level: "media" });
      toast(`${value}: aggiunto agli interessi`);
    } else {
      state.muted.push(value.toLowerCase());
      toast(`"${value}" silenziata`);
    }
    renderAll();
  });

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => ART.paintStars($("#edition .stars"), 214), 150);
  });

  // ---------- Avvio ----------
  if (state.theme !== "auto") applyTheme(state.theme);
  renderStreamShell();
  renderAll();
  if (window.matchMedia("(max-width: 859px)").matches) {
    setTimeout(() => toast("Mockup interattivo: tocca un articolo o prova il Flusso"), 900);
  }
})();
