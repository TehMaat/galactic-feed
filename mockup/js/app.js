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
  const app = $("#app");

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
  const BACKLOG = { orbita: 6, cronache: 1, cielo: 3, bitbyte: 9, fronte: 3, settimanale: 5, laboratorio: 2, diario: 0, gazzetta: 4, bussola: 10, borgo: 7 };
  const LEVEL = { alta: "alta", media: "media", off: "spento" };
  const NEXT_LEVEL = { alta: "media", media: "off", off: "alta" };
  const FILTERS = [["tutti", "Tutti"], ["perte", "Per te"], ["nonletti", "Non letti"], ["video", "Video"]]
    .concat(Object.entries(D.topics).map(([k, t]) => [k, t.label]));
  const AI_MODES = { parole: "Parole chiave", ai: "AI", entrambi: "Entrambi" };
  const AI_HINTS = {
    parole: "Un articolo entra nell'Edizione se il titolo o i tag contengono un tuo interesse.",
    ai: "Un modello AI legge titolo e inizio di ogni articolo e lo confronta con la tua descrizione.",
    entrambi: "Prima le parole chiave, poi l'AI recupera gli articoli pertinenti che non le contengono."
  };

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
    rules: { dedupe: true, summaries: true, edition: true, push: true },
    aiMode: "entrambi",
    aiProvider: "locale",
    aiText: "Esplorazione spaziale e astronomia spiegata bene, self-hosting con Docker, novità su iPhone. Niente finanza.",
    times: ["07:00", "18:00"],
    notifyTopics: new Set(["spazio", "selfhost"]),
    sources: D.sources.map((s) => ({ ...s })),
    current: null,
    ts: 1,
    theme: store.get("theme", "auto"),
    device: "phone",
    lastFetch: "07:00",
    addType: "rss",
    addUrl: "",
    addFound: false,
    addChoice: 0,
    addTopic: "spazio"
  };

  // ---------- Helpers ----------
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const icon = (id) => `<svg class="ico" aria-hidden="true"><use href="#i-${id}"/></svg>`;
  const srcOf = (a) => state.sources.find((s) => s.id === a.src);
  const haystack = (a) => (a.title + " " + a.tags.join(" ")).toLowerCase();
  const ago = (t) => (t === "ieri" ? "ieri" : t + " fa");
  const typeLabel = (t) => ({ rss: "RSS", youtube: "YouTube" }[t]);
  const isWide = () => app.offsetWidth >= 1100;

  const srcColor = (s) => (s.type === "youtube" ? "var(--c-video)" : D.topics[s.topic].color);

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

  const avatar = (s) => `<span class="mono-av" style="--src-c:${srcColor(s)}">${esc(s.initials)}</span>`;

  function meta(a) {
    const s = srcOf(a);
    return `<div class="meta">${avatar(s)}<span class="src">${esc(s.name)}</span><span class="sep"></span><span>${esc(a.time)}</span></div>`;
  }

  const matchTag = (m) => `<span class="match">${icon("spark")}${esc(m.k)}</span>`;
  const itemState = (a) => `${state.read.has(a.id) ? "is-read" : ""} ${state.current === a.id ? "is-current" : ""}`;

  function saveBtn(a) {
    const on = state.saved.has(a.id);
    return `<button type="button" class="save-btn ${on ? "is-on" : ""}" data-action="toggle-save" data-id="${a.id}" aria-pressed="${on}" aria-label="${on ? "Rimuovi dai salvati" : "Salva"}">${icon("bookmark")}</button>`;
  }

  function switchBtn(key, label) {
    return `<button type="button" class="switch" role="switch" aria-checked="${state.rules[key]}" data-action="rule" data-key="${key}" aria-label="${esc(label)}"></button>`;
  }

  function segmented(action, options, current, label) {
    return `<div class="segmented" style="--cols:${options.length}" role="group" aria-label="${esc(label)}">${options.map(([k, l]) =>
      `<button type="button" aria-pressed="${current === k}" data-action="${action}" data-value="${k}">${esc(l)}</button>`).join("")}</div>`;
  }

  // ---------- Edizione ----------
  function greeting() {
    const h = new Date().getHours();
    if (h < 13) return "Buongiorno.";
    if (h < 18) return "Buon pomeriggio.";
    return "Buonasera.";
  }

  function editionSlots() {
    const now = new Date();
    const mins = now.getHours() * 60 + now.getMinutes();
    const toMin = (t) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3));
    const sorted = state.times.slice().sort();
    const past = sorted.filter((t) => toMin(t) <= mins);
    const last = past.length ? past[past.length - 1] : sorted[sorted.length - 1];
    const next = sorted.find((t) => toMin(t) > mins) || sorted[0];
    return { last, next };
  }

  function renderEdition() {
    const items = editionItems();
    const visible = D.articles.filter((a) => !isMuted(a));
    const hidden = D.articles.length - visible.length;
    const hero = items.find((x) => x.m.level === "alta") || items[0];
    const rest = items.filter((x) => x !== hero);
    const { last, next } = editionSlots();
    const date = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long" }).format(new Date());

    let html = `
      <section class="masthead" aria-label="Edizione di oggi">
        <canvas class="stars" aria-hidden="true"></canvas>
        <p class="mast-kicker">Edizione delle ${last} · n. 214</p>
        <h2 class="mast-title">${greeting()}<br>Ecco cosa conta oggi.</h2>
        <p class="mast-date">${esc(date)}</p>
        <div class="mast-stats">
          <div><b>${state.sources.length}</b><span>fonti</span></div>
          <div><b>${visible.length}</b><span>nuovi</span></div>
          <div class="is-star"><b>${items.length}</b><span>per te</span></div>
          <div><b>${hidden}</b><span>nascosti</span></div>
        </div>
        <p class="mast-foot">Composta alle ${last} · prossima alle ${next} · filtri: ${AI_MODES[state.aiMode].toLowerCase()}</p>
      </section>`;

    if (hero) {
      const a = hero.a;
      html += `
      <article class="hero tap ${itemState(a)}" role="button" tabindex="0" data-action="open" data-id="${a.id}">
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
        <article class="row tap ${itemState(a)}" role="button" tabindex="0" data-action="open" data-id="${a.id}">
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
      case "video": return !!a.video;
      default: return a.topic === filter;
    }
  }

  function card(a) {
    const m = matchOf(a);
    const tag = a.video ? `<span class="type-tag video">Video</span>` : "";
    const info = a.video ? "Video · " + esc(a.video.dur) : a.mins ? a.mins + " min di lettura" : "";
    const badge = m ? matchTag(m) : isMuted(a) ? `<span class="match">Silenziato</span>` : "";
    return `
      <article class="card tap ${itemState(a)}" role="button" tabindex="0" data-action="open" data-id="${a.id}">
        <div class="card-top">${meta(a)}${tag}</div>
        <div class="card-main">
          <div class="card-text">
            <h3 class="card-title clamp-3">${esc(a.title)}</h3>
            <p class="excerpt clamp-2">${esc(a.excerpt)}</p>
          </div>
          ${thumb(a)}
        </div>
        <div class="card-foot"><div class="stats"><span>${info}</span></div><div class="foot-r">${badge}${saveBtn(a)}</div></div>
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
    const dot = s.status === "err" ? "err" : s.status === "slow" ? "warn" : "";
    const sub = s.note || `${typeLabel(s.type)} · ogni ${s.every}`;
    return `
      <div class="src-row" role="button" tabindex="0" data-action="filter-source" data-id="${s.id}" aria-label="Mostra gli articoli di ${esc(s.name)}">
        <span class="src-av" style="--src-c:${srcColor(s)}">${esc(s.initials)}</span>
        <span class="src-text"><span class="src-name">${esc(s.name)}</span><span class="src-sub"><span class="status-dot ${dot}"></span>${esc(sub)}</span></span>
        <span class="unread">${unreadOf(s)}</span>
      </div>`;
  }

  function renderSources() {
    $("#sources-count").textContent = `${state.sources.length} fonti in ${Object.keys(D.topics).length} cartelle · solo tue`;
    let html = "";
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
    const usesAi = state.aiMode !== "parole";
    $("#interests").innerHTML = `
      <div class="preview"><b>${n}</b><span>notizie di oggi entrano nell'Edizione con queste regole, su ${total} arrivate.</span></div>
      <section class="panel">
        <h3>Come scegliere le notizie</h3>
        ${segmented("ai-mode", Object.entries(AI_MODES), state.aiMode, "Metodo di selezione")}
        <p class="hint">${esc(AI_HINTS[state.aiMode])}</p>
      </section>
      ${usesAi ? `<section class="panel">
        <h3>Descrivi cosa ti interessa <span class="count">per l'AI</span></h3>
        <textarea class="textarea" id="ai-text" rows="4" aria-label="Descrizione degli interessi per l'AI">${esc(state.aiText)}</textarea>
        <p class="hint">Scrivi come lo diresti a un amico. Il fornitore AI si sceglie nelle Impostazioni.</p>
      </section>` : ""}
      <section class="panel">
        <h3>Parole chiave <span class="count">tocca per la priorità</span></h3>
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
        ${rule("dedupe", "Unisci i doppioni", "La stessa notizia da più fonti compare una volta sola.")}
        ${rule("summaries", "Riassunto automatico", "Tre punti in cima agli articoli lunghi, scritti dall'AI.")}
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

  function renderReaderEmpty() {
    $("#reader").classList.add("is-empty");
    $("#reader-scroll").innerHTML = `<div class="empty reader-empty">${icon("edition")}<h3>Scegli un articolo</h3><p>Lo leggi qui, con il testo completo e senza pubblicità.</p></div>`;
  }

  function openReader(id) {
    const a = byId[id];
    if (!a) return;
    const s = srcOf(a);
    const m = matchOf(a);
    state.current = id;
    state.read.add(id);

    const byline = [a.author || s.name, ago(a.time), a.mins ? `${a.mins} min di lettura` : a.video ? `durata ${a.video.dur}` : ""];
    const summary = a.summary && state.rules.summaries
      ? `<div class="ai-summary"><div class="lbl">${icon("spark")}Riassunto automatico</div><ul>${a.summary.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`
      : "";
    const body = a.body
      ? a.body.map(paragraph).join("")
      : `<p>${esc(a.excerpt)}</p><p class="hint">In questo mockup il testo completo c'è solo per alcuni articoli. Nell'app vera il server lo estrae dalla pagina originale, senza pubblicità.</p>`;

    $("#reader-scroll").innerHTML = `
      ${thumb(a, "wide")}
      <div class="reader-kicker"><div class="meta">${avatar(s)}<span class="src">${esc(s.name)}</span></div>${m ? matchTag(m) : ""}<span class="offline">${icon("check")}Disponibile offline</span></div>
      <h1 class="reader-title">${esc(a.title)}</h1>
      <div class="byline">${byline.filter(Boolean).map(esc).join(`<span class="sep"></span>`)}</div>
      ${summary}
      <div class="reader-body">${body}</div>
      <div class="reader-end">
        <button type="button" class="btn-primary" data-action="open-original">${icon("external")}${a.video ? "Guarda su YouTube" : "Apri l'articolo originale"}</button>
        <button type="button" class="btn-secondary" data-action="mark-unread">Segna come non letto</button>
      </div>`;

    const reader = $("#reader");
    reader.classList.remove("is-empty");
    $("#reader-scroll").scrollTop = 0;
    reader.classList.add("is-open");
    reader.setAttribute("aria-hidden", "false");
    updateReaderSave();
    renderAll();
    if (!isWide()) setTimeout(() => $(".back-btn", reader).focus({ preventScroll: true }), 360);
  }

  function closeReader() {
    const reader = $("#reader");
    const had = state.current;
    reader.classList.remove("is-open");
    reader.setAttribute("aria-hidden", "true");
    state.current = null;
    if (isWide()) {
      renderReaderEmpty();
      if (had) renderAll();
    } else {
      setTimeout(() => { if (!state.current) renderReaderEmpty(); }, 380);
    }
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
    youtube: { label: "Canale YouTube", ph: "Link del canale o @nome", hint: "Ogni canale YouTube ha un feed pubblico con gli ultimi video: non serve nessun account." }
  };

  function guessName() {
    const raw = state.addUrl.trim();
    if (state.addType === "youtube") return raw.replace(/^.*@/, "@").replace(/[^\w@.-]/g, "") || "@divulgazione";
    let host = "astrofili.example";
    try { host = new URL(/^https?:\/\//.test(raw) ? raw : "https://" + raw).hostname || host; } catch (err) { /* indirizzo non valido: si usa l'esempio */ }
    const word = host.replace(/^www\./, "").split(".")[0];
    return word.charAt(0).toUpperCase() + word.slice(1);
  }

  function candidates() {
    const name = guessName();
    if (state.addType === "youtube") return [{ name, sub: "ultimi 15 video · feed pubblico del canale" }];
    return [
      { name: `${name} · tutte le notizie`, sub: "/feed.xml · circa 25 articoli al giorno · testo completo" },
      { name: `${name} · solo approfondimenti`, sub: "/categoria/approfondimenti/feed · 3 a settimana · solo estratto" },
      { name: `${name} · commenti`, sub: "/comments/feed" }
    ];
  }

  function renderAdd() {
    const t = ADD_TYPES[state.addType];
    const found = state.addFound
      ? `<div class="field"><span class="label">Feed trovati</span><div class="found" role="radiogroup" aria-label="Feed trovati">${candidates().map((c, i) => `
          <button type="button" class="found-item" role="radio" aria-checked="${state.addChoice === i}" data-action="add-choice" data-i="${i}"><span class="radio">${icon("check")}</span><span><span class="found-name">${esc(c.name)}</span><br><span class="found-sub">${esc(c.sub)}</span></span></button>`).join("")}</div></div>
         <div class="field"><span class="label">Cartella</span><div class="tags">${Object.entries(D.topics).map(([k, tp]) => `<button type="button" class="tag" aria-pressed="${state.addTopic === k}" data-action="add-topic" data-k="${k}"><span class="dot" style="--topic-c:${tp.color}"></span>${esc(tp.label)}</button>`).join("")}</div></div>
         <button type="button" class="btn-primary" data-action="add-confirm">${icon("plus")}Aggiungi fonte</button>`
      : "";
    $("#add-body").innerHTML = `
      <div class="form-stack">
        ${segmented("add-type", Object.entries(ADD_TYPES).map(([k, v]) => [k, v.label]), state.addType, "Tipo di fonte")}
        <form class="form-stack" data-form="find">
          <div class="field"><label for="add-url">Indirizzo</label><input class="input" id="add-url" placeholder="${esc(t.ph)}" value="${esc(state.addUrl)}" autocomplete="off" autocapitalize="off" spellcheck="false"></div>
          <p class="hint">${esc(t.hint)}</p>
          <button type="submit" class="btn-secondary">${icon("search")}Cerca feed</button>
        </form>
        ${found}
      </div>`;
  }

  function renderSettings() {
    const ed = state.rules.edition;
    const push = state.rules.push;
    $("#settings-body").innerHTML = `
      <div class="set-label">Account</div>
      <div class="set-group">
        <div class="set-row"><span class="who"><span class="user-av">TU</span><span><b>Il tuo profilo</b><br><small>amministratore</small></span></span><span class="val">3 utenti</span></div>
        <button type="button" class="link-row" data-action="toast" data-msg="Nell'app vera generi un link d'invito valido 48 ore">${icon("plus")}Invita un utente</button>
      </div>
      <p class="set-note">Ogni utente ha fonti, interessi, letti e salvati propri. I feed in comune vengono scaricati una volta sola.</p>

      <div class="set-label">Edizione</div>
      <div class="set-group">
        <div class="set-row"><span>Componi l'Edizione</span>${switchBtn("edition", "Componi l'Edizione")}</div>
        ${ed ? `<div class="set-block"><span class="label">Orari</span><div class="tags">${state.times.map((t, i) => `<button type="button" class="tag mono" data-action="remove-time" data-i="${i}" aria-label="Togli l'edizione delle ${t}">${t}${icon("close")}</button>`).join("")}<button type="button" class="tag" data-action="add-time">${icon("plus")}Orario</button></div></div>` : ""}
      </div>
      <p class="set-note">${ed ? "L'Edizione si legge solo nell'app, niente email." : "Senza Edizione la schermata Oggi mostra solo il Flusso."}</p>

      <div class="set-label">Notifiche</div>
      <div class="set-group">
        <div class="set-row"><span>Notizie importanti</span>${switchBtn("push", "Notifiche per le notizie importanti")}</div>
        ${push ? `<div class="set-block"><span class="label">Categorie importanti</span><div class="tags">${Object.entries(D.topics).map(([k, tp]) => `<button type="button" class="tag" aria-pressed="${state.notifyTopics.has(k)}" data-action="notify-topic" data-k="${k}"><span class="dot" style="--topic-c:${tp.color}"></span>${esc(tp.label)}</button>`).join("")}</div></div>` : ""}
      </div>
      <p class="set-note">Su iPhone le notifiche arrivano solo se l'app è aggiunta alla schermata Home (iOS 16.4 o successivo).</p>

      <div class="set-label">AI</div>
      <div class="set-group">
        <div class="set-row"><span>Fornitore</span>${segmented("ai-provider", [["locale", "Locale"], ["cloud", "Cloud"]], state.aiProvider, "Fornitore AI")}</div>
        <div class="set-row"><span>${state.aiProvider === "locale" ? "Ollama" : "Servizio"}</span><span class="val">${state.aiProvider === "locale" ? "http://ollama:11434" : "chiave API impostata"}</span></div>
      </div>
      <p class="set-note">${state.aiProvider === "locale" ? "I testi non escono dalla tua rete. Su un Raspberry Pi è lento: meglio Ollama su un PC più potente." : "Veloce anche su hardware piccolo. Si paga a consumo e i testi vengono inviati al servizio."}</p>

      <div class="set-label">Aspetto</div>
      <div class="set-group">
        <div class="set-row"><span>Tema</span>${segmented("theme", [["auto", "Auto"], ["light", "Chiaro"], ["dark", "Scuro"]], state.theme, "Tema")}</div>
        <div class="set-row"><span>Dimensione del testo</span><span class="val">${Math.round(state.ts * 100)}%</span></div>
      </div>

      <div class="set-label">Server</div>
      <div class="set-group">
        <div class="set-row"><span>Indirizzo</span><span class="val">feed.casa.example</span></div>
        <div class="set-row"><span>Controllo delle fonti</span><span class="val">ogni 30 min</span></div>
        <div class="set-row"><span>Ultimo controllo</span><span class="val">${state.lastFetch}</span></div>
      </div>
      <div class="set-label">Dati</div>
      <div class="set-group"><button type="button" class="link-row" data-action="toast" data-msg="Nell'app vera scarichi un file .opml con tutte le tue fonti">${icon("upload")}Esporta le fonti (OPML)</button></div>
      <p class="set-note">Mockup v0.2 · tutti i contenuti sono di esempio.</p>`;
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
    if (!isWide()) closeReader();
    closeSheet();
    state.tab = tab;
    app.dataset.tab = tab;
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
    if (!state.rules.edition) mode = "flusso";
    state.mode = mode;
    $("#edition").hidden = mode !== "edizione";
    $("#stream").hidden = mode !== "flusso";
    $("#mode-edizione").setAttribute("aria-selected", String(mode === "edizione"));
    $("#mode-flusso").setAttribute("aria-selected", String(mode === "flusso"));
    if (mode === "edizione") ART.paintStars($("#edition .stars"), 214);
  }

  function applyEdition() {
    $("#mode-switch").hidden = !state.rules.edition;
    setMode(state.rules.edition ? "edizione" : "flusso");
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

  // Dimensioni esterne delle cornici (contenuto + bordi + barra del browser).
  const FRAMES = { phone: [412, 866], tablet: [1056, 800], desktop: [1282, 842] };

  function fitDevice() {
    const device = $("#device");
    if (window.matchMedia("(max-width: 859px)").matches) {
      device.style.zoom = "";
      if (state.device !== "phone") setDevice("phone");
      return;
    }
    const [w, h] = FRAMES[state.device];
    const stacked = state.device !== "phone";
    const availW = stacked ? window.innerWidth - 48 : 640;
    const availH = window.innerHeight - 80 - (stacked ? $(".brief").offsetHeight + 24 : 0);
    device.style.zoom = Math.min(1, availW / w, availH / h).toFixed(3);
  }

  function setDevice(d) {
    state.device = d;
    const device = $("#device");
    device.classList.remove("is-phone", "is-tablet", "is-desktop");
    device.classList.add("is-" + d);
    $(".stage").classList.toggle("is-stacked", d !== "phone");
    $$('[data-action="device"]').forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.value === d)));
    fitDevice();
    if (d === "desktop" && !state.current && state.tab === "oggi") openReader("a1");
    ART.paintStars($("#edition .stars"), 214);
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
      app.style.setProperty("--ts", state.ts);
      toast(state.ts > 1 ? "Testo più grande" : state.ts < 1 ? "Testo più piccolo" : "Testo standard");
    },
    "open-original": () => toast("Nell'app vera si apre la pagina originale nel browser"),
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
      if (key === "edition") { applyEdition(); renderSettings(); }
      if (key === "push") renderSettings();
    },
    "ai-mode": (el) => { state.aiMode = el.dataset.value; renderInterests(); renderEdition(); },
    "ai-provider": (el) => { state.aiProvider = el.dataset.value; renderSettings(); },
    "add-time": () => {
      const next = ["12:30", "21:00", "09:00", "15:00"].find((t) => !state.times.includes(t));
      if (!next) { toast("Massimo 6 edizioni al giorno"); return; }
      state.times.push(next);
      state.times.sort();
      renderSettings();
      renderEdition();
      toast(`Nuova edizione alle ${next}`);
    },
    "remove-time": (el) => {
      if (state.times.length === 1) { toast("Serve almeno un orario, oppure spegni l'Edizione"); return; }
      const [t] = state.times.splice(Number(el.dataset.i), 1);
      renderSettings();
      renderEdition();
      toast(`Edizione delle ${t} tolta`);
    },
    "notify-topic": (el) => {
      const k = el.dataset.k;
      if (state.notifyTopics.has(k)) state.notifyTopics.delete(k); else state.notifyTopics.add(k);
      renderSettings();
    },
    "open-sheet": (el) => openSheet(el.dataset.sheet),
    "close-sheet": () => closeSheet(),
    "add-type": (el) => { state.addType = el.dataset.value; state.addFound = false; state.addUrl = ""; renderAdd(); },
    "add-choice": (el) => { state.addChoice = Number(el.dataset.i); renderAdd(); },
    "add-topic": (el) => { state.addTopic = el.dataset.k; renderAdd(); },
    "add-confirm": () => {
      const c = candidates()[state.addChoice];
      const name = c.name.split(" · ")[0];
      state.sources.push({
        id: "nuova-" + state.sources.length,
        name,
        type: state.addType,
        topic: state.addTopic,
        initials: name.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2) || "N",
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
    device: (el) => setDevice(el.dataset.value),
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

  document.addEventListener("input", (e) => {
    if (e.target.id === "ai-text") state.aiText = e.target.value;
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
    resizeTimer = setTimeout(() => {
      fitDevice();
      ART.paintStars($("#edition .stars"), 214);
    }, 150);
  });

  // ---------- Avvio ----------
  if (state.theme !== "auto") applyTheme(state.theme);
  app.dataset.tab = state.tab;
  renderStreamShell();
  renderAll();
  renderReaderEmpty();
  setDevice("phone");
  if (window.matchMedia("(max-width: 859px)").matches) {
    setTimeout(() => toast("Mockup interattivo: tocca un articolo o prova il Flusso"), 900);
  }
})();
