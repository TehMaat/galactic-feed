<script>
  // Lettura di un articolo. Su telefono e tablet scorre sopra l'elenco; sul computer sta nella
  // colonna di destra oppure, se lo scegli in Impostazioni → Lettura, a tutta pagina (#9).
  // Pulsanti ridotti all'essenziale: Indietro, Salva e «Altre azioni» (dimensione del testo,
  // condividi, originale, segna come non letto). Scorrendo verso il basso la barra esce dallo
  // schermo e rientra tornando su, come le barre delle sezioni (#36).
  import { api } from "../lib/api.js";
  import { barsAfterScroll } from "../lib/bars.js";
  import { shortcutFor } from "../lib/keys.js";
  import { explainDedupe } from "../lib/help.js";
  import { isAvailableOffline, overlay } from "../lib/offline.js";
  import { sourceColor, timeAgoLong } from "../lib/format.js";
  import { TEXT_SIZES, readerBeside, closeReader, confirmation, foldersById, savePrefs, session, setRead, setSaved, stream, saved, ui, toast } from "../lib/store.svelte.js";
  import Edition from "./Edition.svelte";
  import Icon from "./Icon.svelte";
  import SourceIcon from "./SourceIcon.svelte";
  import Thumb from "./Thumb.svelte";

  let article = $state(null);
  let error = $state("");
  let loading = $state(false);
  let available = $state(false); // c'è una copia sul dispositivo, leggibile senza rete
  let summary = $state({ points: null, loading: false, error: "" });
  let scroller = $state();
  let backBtn = $state();
  let menuOpen = $state(false);
  let menuBtn = $state();
  let barHidden = $state(false);
  let barRef = 0;
  let progress = $state(0); // quanto dell'articolo è stato letto, da 0 a 1
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  // Aperto con un articolo o con un'uscita dell'Edizione (#64); l'articolo, se c'è, sta sopra.
  const open = $derived(ui.reader !== null || ui.edition !== null);
  const showEdition = $derived(ui.reader === null && ui.edition !== null);
  const color = $derived(article ? foldersById()[article.source.folder_id]?.color || "indaco" : "indaco");

  // Aprendo un'Edizione si parte dalla cima.
  $effect(() => {
    if (ui.edition !== null && ui.reader === null && scroller) scroller.scrollTop = 0;
  });

  // Stato letto/salvato condiviso con gli elenchi.
  function listed(id) {
    return stream.items.find((a) => a.id === id) || saved.items.find((a) => a.id === id);
  }

  $effect(() => {
    const id = ui.reader;
    if (id === null) return;
    let cancelled = false;
    loading = true;
    error = "";
    available = false;
    api(`/articles/${id}`)
      .then((r) => {
        if (cancelled) return;
        article = overlay([r.article])[0];
        checkOffline(id);
        loadSummary(article);
        if (scroller) scroller.scrollTop = 0;
        barHidden = false;
        barRef = 0;
        progress = 0;
        const inList = listed(id);
        if (!article.read) {
          setRead(inList || article, true);
          article.read = true;
        }
        // Il lettore copre l'elenco: il focus va su «Indietro». Accanto all'elenco resta dov'è.
        if (!readerBeside()) setTimeout(() => backBtn?.focus({ preventScroll: true }), 360);
      })
      .catch((err) => {
        if (!cancelled) {
          article = null;
          error = err.status === 0 && !ui.online
            ? "Questo articolo non è sul dispositivo: lo puoi leggere quando torna la rete. Gli articoli salvati e quelli già letti restano disponibili anche offline."
            : err.message;
        }
      })
      .finally(() => {
        if (!cancelled) loading = false;
      });
    return () => (cancelled = true);
  });

  async function loadSummary(a) {
    summary = { points: a.summary, loading: false, error: "" };
    if (a.summary || !a.summary_available || !ui.online) return;
    summary.loading = true;
    try {
      const r = await api(`/articles/${a.id}/summary`, { method: "POST" });
      if (article?.id === a.id) summary = { points: r.points, loading: false, error: "" };
    } catch (err) {
      if (article?.id === a.id) summary = { points: null, loading: false, error: err.message };
    }
  }

  async function checkOffline(id) {
    const yes = await isAvailableOffline(id);
    if (article?.id === id) available = yes;
  }

  async function toggleSave() {
    if (!article) return;
    const id = article.id;
    const target = listed(id) || article;
    const value = !article.saved;
    article.saved = value;
    const ok = await setSaved(target, value);
    if (article?.id !== id) return;
    if (!ok) article.saved = !value;
    checkOffline(id);
  }

  function markUnread() {
    menuOpen = false;
    if (!article) return;
    setRead(listed(article.id) || article, false);
    article.read = false;
    toast("Segnato come non letto");
    closeReader();
  }

  // Dimensioni del testo, dalla più piccola alla più grande.
  const SIZES = [...TEXT_SIZES].sort((a, b) => a - b).map((v) => [v, v > 1 ? "Grande" : v < 1 ? "Piccolo" : "Standard"]);
  const textSize = $derived(session.user?.prefs?.text_size ?? 1);

  function openOriginal() {
    menuOpen = false;
    if (article?.url) window.open(article.url, "_blank", "noopener,noreferrer");
  }

  // Scorciatoie sull'articolo aperto (#94): «s» salva, «m» letto o da leggere, «o» l'originale.
  // Con l'articolo aperto si resta sull'articolo: «m» non lo chiude, come fa invece il menu.
  function onKey(e) {
    if (!article || ui.reader !== article.id || ui.sheet || confirmation.open) return;
    const key = shortcutFor(e);
    if (key === "s") {
      e.preventDefault();
      toggleSave();
    } else if (key === "m") {
      e.preventDefault();
      const read = !article.read;
      setRead(listed(article.id) || article, read);
      article.read = read;
      toast(read ? "Segnato come letto" : "Segnato come da leggere");
    } else if (key === "o") {
      e.preventDefault();
      openOriginal();
    }
  }

  async function share() {
    menuOpen = false;
    if (!article?.url) return;
    try {
      await navigator.share({ title: article.title, url: article.url });
    } catch {
      // annullato da chi legge: niente da dire
    }
  }

  function onScroll() {
    const max = scroller.scrollHeight - scroller.clientHeight;
    progress = max > 0 ? Math.min(1, Math.max(0, scroller.scrollTop / max)) : 0;
    if (menuOpen) return;
    const next = barsAfterScroll(barRef, scroller.scrollTop, max);
    barRef = next.ref;
    if (next.hidden !== null) barHidden = next.hidden;
  }

  // Il menu si chiude toccando fuori, con Esc o chiudendo l'articolo.
  $effect(() => {
    if (!open) menuOpen = false;
  });
  function onDocPointer(e) {
    if (menuOpen && !e.target.closest?.(".reader-menu, .more-btn")) menuOpen = false;
  }
  function onMenuKey(e) {
    if (e.key === "Escape" && menuOpen) {
      e.stopPropagation();
      menuOpen = false;
      menuBtn?.focus();
    }
  }

  // I link dentro l'articolo si aprono fuori dall'app.
  function bodyClick(e) {
    const a = e.target.closest("a[href]");
    if (!a) return;
    e.preventDefault();
    window.open(a.href, "_blank", "noopener,noreferrer");
  }

  // Niente tempo di lettura (#70); l'ora di pubblicazione è in alto a destra, accanto alla fonte.
  const byline = $derived(article ? [article.author, article.video ? "video" : ""].filter(Boolean) : []);
</script>

<svelte:document onpointerdown={onDocPointer} />
<svelte:window onkeydown={onKey} />

<article class="reader" class:has-back={ui.edition !== null && ui.reader !== null} class:is-open={open} class:is-empty={!open} class:bar-hidden={barHidden} aria-label="Articolo" aria-hidden={!open && !readerBeside()}>
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="reader-bar" onfocusin={() => (barHidden = false)} onkeydown={onMenuKey}>
    <button type="button" class="back-btn" bind:this={backBtn} onclick={closeReader}><Icon name="back" /><span>Indietro</span></button>
    {#if showEdition}<span class="reader-where">Edizione</span>{/if}
    <div class="reader-actions" hidden={showEdition}>
      <button type="button" class="icon-btn" class:is-on={article?.saved} aria-pressed={!!article?.saved} aria-label={article?.saved ? "Rimuovi dai salvati" : "Salva"} title={article?.saved ? "Rimuovi dai salvati" : "Salva"} onclick={toggleSave}><Icon name="bookmark" /></button>
      <button type="button" class="icon-btn more-btn" bind:this={menuBtn} aria-label="Altre azioni" title="Altre azioni" aria-haspopup="menu" aria-expanded={menuOpen} onclick={() => (menuOpen = !menuOpen)}><Icon name="more" /></button>
    </div>
    {#if menuOpen}
      <div class="reader-menu" role="menu" aria-label="Altre azioni">
        <div class="menu-sizes" role="group" aria-label="Dimensione del testo">
          {#each SIZES as [value, label], i}
            <button type="button" role="menuitemradio" aria-checked={textSize === value} aria-label="Testo {label.toLowerCase()}" title={label} onclick={() => savePrefs({ text_size: value })}><span class="aa s{i}">A</span></button>
          {/each}
        </div>
        {#if canShare && article?.url}<button type="button" role="menuitem" onclick={share}><Icon name="share" />Condividi</button>{/if}
        {#if article?.url}<button type="button" role="menuitem" onclick={openOriginal}><Icon name="external" />{article.video ? "Guarda su YouTube" : "Apri l'originale"}</button>{/if}
        <button type="button" role="menuitem" onclick={markUnread}><Icon name="check" />Segna come non letto</button>
      </div>
    {/if}
    <div class="read-progress" style="--p:{progress}" aria-hidden="true"></div>
  </div>
  <div class="reader-scroll" bind:this={scroller} onscroll={onScroll}>
    {#if !open}
      <!-- Si vede solo sul computer, con l'articolo accanto all'elenco. -->
      <div class="empty reader-empty"><Icon name="edition" /><h3>Scegli un articolo</h3><p>Lo leggi qui, con il testo completo e senza pubblicità.</p></div>
    {:else if showEdition}
      <div class="reader-edition"><Edition /></div>
    {:else if error}
      <div class="empty reader-empty"><Icon name="alert" /><h3>Articolo non disponibile</h3><p>{error}</p></div>
    {:else if article && article.id === ui.reader}
      <div class="reader-cover">
        {#if article.video && article.url}
          <a class="video-link" href={article.url} target="_blank" rel="noopener noreferrer" aria-label="Guarda su YouTube"><Thumb {article} {color} wide /></a>
        {:else}
          <Thumb {article} {color} wide />
        {/if}
        <span class="src-pill">
          <SourceIcon source={article.source} color={sourceColor(article.source, foldersById())} />
          <span>{article.source.title}</span>
          <span class="src-time"><time datetime={article.published_at}>{timeAgoLong(article.published_at)}</time></span>
        </span>
      </div>
      <h1 class="reader-title">{article.title}</h1>
      {#if byline.length || available}
        <div class="byline">
          {#each byline as part, i}{#if i}<span class="sep"></span>{/if}<span>{part}</span>{/each}
          {#if available}<span class="offline"><Icon name="check" />Disponibile offline</span>{/if}
        </div>
      {/if}
      {#if article.also_on.length}
        <p class="also-on">Anche su: {article.also_on.map((o) => o.title).join(", ")}
          <button type="button" class="info-btn" aria-label="Come funzionano i doppioni" onclick={explainDedupe}><Icon name="info" /></button></p>
      {/if}
      {#if summary.points}
        <div class="ai-summary"><div class="lbl"><Icon name="spark" />Riassunto automatico</div>
          <ul>{#each summary.points as p}<li>{p}</li>{/each}</ul>
        </div>
      {:else if summary.loading}
        <div class="ai-summary is-loading" role="status"><div class="lbl"><Icon name="spark" />Riassunto automatico</div>Sto scrivendo il riassunto…</div>
      {/if}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div class="reader-body" onclick={bodyClick}>
        {#if article.content_html}
          {@html article.content_html}
        {:else if article.excerpt}
          <p>{article.excerpt}</p>
        {/if}
        {#if !article.full_text && !article.video}
          <p class="hint">
            {article.full_text_status === "pending"
              ? "Il testo completo è in arrivo: il server lo sta scaricando dal sito."
              : "Il sito non permette di leggere qui il testo completo: lo trovi nell'articolo originale."}
          </p>
        {/if}
      </div>
      {#if article.url}
        <div class="reader-end">
          <button type="button" class="btn-primary" onclick={openOriginal}><Icon name="external" />{article.video ? "Guarda su YouTube" : `Leggi su ${article.source.title}`}</button>
        </div>
      {/if}
    {:else if loading}
      <p class="loading">Apro l'articolo…</p>
    {/if}
  </div>
</article>
