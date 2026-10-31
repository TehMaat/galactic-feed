<script>
  // Lettura di un articolo. Sul telefono scorre sopra l'elenco; sul computer sta nella
  // terza colonna, sempre visibile (come nel mockup).
  import { api } from "../lib/api.js";
  import { initials, sourceColor, timeAgoLong } from "../lib/format.js";
  import { TEXT_SIZES, closeReader, foldersById, savePrefs, session, setRead, setSaved, stream, saved, ui, toast } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";
  import Thumb from "./Thumb.svelte";

  let article = $state(null);
  let error = $state("");
  let loading = $state(false);
  let scroller = $state();
  let backBtn = $state();

  const open = $derived(ui.reader !== null);
  const color = $derived(article ? foldersById()[article.source.folder_id]?.color || "indaco" : "indaco");

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
    api(`/articles/${id}`)
      .then((r) => {
        if (cancelled) return;
        article = r.article;
        if (scroller) scroller.scrollTop = 0;
        const inList = listed(id);
        if (!article.read) {
          setRead(inList || article, true);
          article.read = true;
        }
        if (window.innerWidth < 1100) setTimeout(() => backBtn?.focus({ preventScroll: true }), 360);
      })
      .catch((err) => {
        if (!cancelled) {
          article = null;
          error = err.message;
        }
      })
      .finally(() => {
        if (!cancelled) loading = false;
      });
    return () => (cancelled = true);
  });

  function toggleSave() {
    if (!article) return;
    const target = listed(article.id) || article;
    const value = !article.saved;
    setSaved(target, value);
    article.saved = value;
  }

  function markUnread() {
    if (!article) return;
    setRead(listed(article.id) || article, false);
    article.read = false;
    toast("Segnato come non letto");
    closeReader();
  }

  function textSize() {
    const current = session.user?.prefs?.text_size ?? 1;
    const i = TEXT_SIZES.indexOf(current);
    const next = TEXT_SIZES[(i + 1) % TEXT_SIZES.length];
    savePrefs({ text_size: next });
    toast(next > 1 ? "Testo più grande" : next < 1 ? "Testo più piccolo" : "Testo standard");
  }

  function openOriginal() {
    if (article?.url) window.open(article.url, "_blank", "noopener,noreferrer");
  }

  // I link dentro l'articolo si aprono fuori dall'app.
  function bodyClick(e) {
    const a = e.target.closest("a[href]");
    if (!a) return;
    e.preventDefault();
    window.open(a.href, "_blank", "noopener,noreferrer");
  }

  const byline = $derived(
    article
      ? [article.author || article.source.title, timeAgoLong(article.published_at), article.reading_minutes ? `${article.reading_minutes} min di lettura` : article.video ? "video" : ""].filter(Boolean)
      : [],
  );
</script>

<article class="reader" class:is-open={open} class:is-empty={!open} aria-label="Articolo" aria-hidden={!open && window.innerWidth < 1100}>
  <div class="reader-bar">
    <button type="button" class="back-btn" bind:this={backBtn} onclick={closeReader}><Icon name="back" /><span>Indietro</span></button>
    <div class="reader-actions">
      <button type="button" class="icon-btn" aria-label="Dimensione del testo" onclick={textSize}><span class="aa">Aa</span></button>
      <button type="button" class="icon-btn" class:is-on={article?.saved} aria-pressed={!!article?.saved} aria-label={article?.saved ? "Rimuovi dai salvati" : "Salva"} onclick={toggleSave}><Icon name="bookmark" /></button>
      <button type="button" class="icon-btn" aria-label="Apri l'originale" onclick={openOriginal}><Icon name="external" /></button>
    </div>
  </div>
  <div class="reader-scroll" bind:this={scroller}>
    {#if !open}
      <div class="empty reader-empty"><Icon name="edition" /><h3>Scegli un articolo</h3><p>Lo leggi qui, con il testo completo e senza pubblicità.</p></div>
    {:else if error}
      <div class="empty reader-empty"><Icon name="alert" /><h3>Articolo non disponibile</h3><p>{error}</p></div>
    {:else if article && article.id === ui.reader}
      {#if article.video && article.url}
        <a class="video-link" href={article.url} target="_blank" rel="noopener noreferrer" aria-label="Guarda su YouTube"><Thumb {article} {color} wide /></a>
      {:else}
        <Thumb {article} {color} wide />
      {/if}
      <div class="reader-kicker">
        <div class="meta">
          <span class="mono-av" style="--src-c:{sourceColor(article.source, foldersById())}">{initials(article.source.title)}</span>
          <span class="src">{article.source.title}</span>
        </div>
        {#if article.match}<span class="match"><Icon name="spark" />{article.match.keyword}</span>{/if}
      </div>
      <h1 class="reader-title">{article.title}</h1>
      <div class="byline">
        {#each byline as part, i}{#if i}<span class="sep"></span>{/if}<span>{part}</span>{/each}
      </div>
      {#if article.also_on.length}
        <p class="also-on">Anche su: {article.also_on.map((o) => o.title).join(", ")}</p>
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
      <div class="reader-end">
        {#if article.url}
          <button type="button" class="btn-primary" onclick={openOriginal}><Icon name="external" />{article.video ? "Guarda su YouTube" : "Apri l'articolo originale"}</button>
        {/if}
        <button type="button" class="btn-secondary" onclick={markUnread}>Segna come non letto</button>
      </div>
    {:else if loading}
      <p class="loading">Apro l'articolo…</p>
    {/if}
  </div>
</article>
