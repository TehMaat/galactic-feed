<script>
  // Schermata «Oggi». Senza Edizione (arriva nella v2) mostra il Flusso, come nel mockup
  // quando l'Edizione è spenta.
  import Card from "../components/Card.svelte";
  import Icon from "../components/Icon.svelte";
  import { folderColor } from "../lib/format.js";
  import { data, loadStream, markAllRead, openSheet, refreshAll, setFilter, stream, ui } from "../lib/store.svelte.js";

  let { active } = $props();
  let query = $state(stream.q);
  let sentinel = $state();
  let timer;

  const VIEWS = [
    ["tutti", "Tutti"],
    ["perte", "Per te"],
    ["nonletti", "Non letti"],
    ["video", "Video"],
  ];

  const chips = $derived([
    ...VIEWS.map(([k, label]) => ({ key: "v:" + k, label, n: data.counts[k] ?? 0, on: !stream.folder && stream.view === k })),
    ...data.folders.map((f) => ({
      key: "f:" + f.id,
      label: f.name,
      n: data.counts.folders?.[String(f.id)] ?? 0,
      color: folderColor(f.color),
      on: stream.folder === String(f.id),
    })),
  ]);

  function pick(chip) {
    const [kind, value] = chip.key.split(":");
    if (kind === "v") setFilter({ view: value, folder: null, source: null, sourceTitle: "" });
    else setFilter({ view: "tutti", folder: value, source: null, sourceTitle: "" });
  }

  function onSearch(e) {
    query = e.target.value;
    clearTimeout(timer);
    timer = setTimeout(() => setFilter({ q: query.trim() }), 250);
  }

  $effect(() => {
    if (!sentinel) return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && stream.items.length && !stream.done) loadStream();
    }, { rootMargin: "600px" });
    io.observe(sentinel);
    return () => io.disconnect();
  });

  const noSources = $derived(data.loaded && data.sources.length === 0);
  const filtering = $derived(stream.q || stream.view !== "tutti" || stream.folder || stream.source);
</script>

<section class="view" class:is-entering={active} hidden={!active} aria-label="Oggi">
  <header class="topbar">
    <div class="wordmark"><Icon name="orbit" /><span>galactic feed</span></div>
    <div class="topbar-actions">
      {#if !ui.online}<span class="offline-pill" title="Sei offline: vedi gli articoli già scaricati"><Icon name="cloud-off" />offline</span>{/if}
      <button type="button" class="icon-btn" class:is-spinning={ui.refreshing} aria-label="Aggiorna le fonti" onclick={refreshAll}><Icon name="refresh" /></button>
      <button type="button" class="icon-btn" aria-label="Impostazioni" onclick={() => openSheet("settings")}><Icon name="sliders" /></button>
    </div>
  </header>

  {#if noSources}
    <div class="empty">
      <Icon name="rss" />
      <h3>Nessuna fonte, per ora</h3>
      <p>Aggiungi un sito, un feed o un canale YouTube: gli articoli compariranno qui.</p>
      <button type="button" class="pill-btn" onclick={() => openSheet("add")}><Icon name="plus" />Aggiungi una fonte</button>
    </div>
  {:else}
    <label class="search">
      <Icon name="search" />
      <input type="search" placeholder="Cerca negli articoli e nelle fonti" autocomplete="off" aria-label="Cerca" value={query} oninput={onSearch} />
    </label>
    <div class="chips" role="toolbar" aria-label="Filtri">
      {#each chips as chip (chip.key)}
        <button type="button" class="chip" aria-pressed={chip.on} onclick={() => pick(chip)}>
          {#if chip.color}<span class="dot" style="--topic-c:{chip.color}"></span>{/if}{chip.label}<span class="n">{chip.n}</span>
        </button>
      {/each}
    </div>

    {#if stream.source}
      <div class="filter-note">
        <span>Solo <b>{stream.sourceTitle}</b></span>
        <button type="button" onclick={() => setFilter({ source: null, sourceTitle: "" })}>Mostra tutte le fonti</button>
      </div>
    {/if}

    <div class="stack">
      {#each stream.items as article (article.id)}
        <Card {article} />
      {/each}
    </div>

    {#if stream.error}
      <div class="empty"><Icon name="alert" /><h3>Non riesco a caricare gli articoli</h3><p>{stream.error}</p>
        <button type="button" class="btn-secondary small" onclick={() => loadStream(true)}>Riprova</button></div>
    {:else if !stream.loading && stream.items.length === 0}
      <div class="empty">
        <Icon name={filtering ? "search" : "check"} />
        <h3>{filtering ? "Nessun risultato" : "Ancora nessun articolo"}</h3>
        <p>{filtering ? "Prova un altro filtro o un'altra parola." : "Le fonti appena aggiunte arrivano entro pochi minuti."}</p>
      </div>
    {/if}

    {#if stream.hidden && !stream.showMuted}
      <div class="hidden-note">
        <Icon name="eye-off" /><span>{stream.hidden === 1 ? "1 articolo nascosto" : `${stream.hidden} articoli nascosti`} dalle parole silenziate</span>
        <button type="button" onclick={() => setFilter({ showMuted: true })}>Mostra</button>
      </div>
    {/if}

    <div bind:this={sentinel} class="sentinel" aria-hidden="true"></div>
    {#if stream.loading}<p class="loading">Carico gli articoli…</p>{/if}

    {#if stream.done && stream.items.length && !stream.loading}
      <div class="edition-end">
        <Icon name="check" /><b>Sei in pari</b>
        {#if stream.items.some((a) => !a.read)}
          <button type="button" class="link-btn" onclick={markAllRead}>Segna tutti come letti</button>
        {:else}
          <span>Hai visto tutto quello che c'è.</span>
        {/if}
      </div>
    {/if}
  {/if}
</section>
