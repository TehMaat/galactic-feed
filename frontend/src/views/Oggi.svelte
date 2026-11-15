<script>
  // Schermata «Oggi». Senza Edizione mostra il Flusso, come nel mockup quando l'Edizione è
  // spenta. Con l'Edizione accesa si passa dall'una all'altro con il selettore o, sul touch,
  // con uno swipe orizzontale (#29): verso sinistra il Flusso, verso destra l'Edizione. Lo
  // swipe cambia solo ui.oggiMode, senza toccare l'indirizzo né la cronologia.
  import { tick, untrack } from "svelte";
  import Card from "../components/Card.svelte";
  import Edition from "../components/Edition.svelte";
  import Icon from "../components/Icon.svelte";
  import { countryName, flag, folderColor } from "../lib/format.js";
  import { scrollViewTo, viewScrollTop } from "../lib/scroll.js";
  import { NO_SWIPE, canStart, lockAxis, offset, release } from "../lib/swipe.js";
  import { confirmation, data, editionOn, loadStream, markAllRead, openSheet, refreshAll, setFilter, stream, ui } from "../lib/store.svelte.js";

  let { active } = $props();
  let query = $state(stream.q);
  let sentinel = $state();
  let viewEl = $state();
  let timer;

  // Tocco sul logo: si torna in cima (se si è già in cima non succede altro).
  $effect(() => {
    if (ui.homeTick && viewEl && viewScrollTop(viewEl) > 0) scrollViewTo(viewEl, { top: 0, behavior: "smooth" });
  });

  const VIEWS = [
    ["tutti", "Tutti"],
    ["perte", "Per te"],
    ["nonletti", "Non letti"],
    ["video", "Video"],
  ];

  const chips = $derived([
    ...VIEWS.map(([k, label]) => ({ key: "v:" + k, label, n: data.counts[k] ?? 0, on: !stream.folder && !stream.tag && !stream.country && stream.view === k })),
    // Tag delle fonti (#17): quelli scelti per il Flusso, nell'ordine dei tag.
    ...data.tags.filter((t) => t.in_feed).map((t) => ({
      key: "t:" + t.id,
      label: t.name,
      n: data.counts.tags?.[String(t.id)] ?? 0,
      color: folderColor(t.color),
      tag: true,
      on: stream.tag === t.id,
    })),
    // Nazioni delle fonti (#20), solo se le fonti sono di almeno due nazioni.
    ...(Object.keys(data.counts.countries || {}).length > 1
      ? Object.entries(data.counts.countries)
          .sort((a, b) => b[1] - a[1])
          .map(([code, n]) => ({ key: "c:" + code, label: `${flag(code)} ${countryName(code)}`, n, on: stream.country === code }))
      : []),
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
    const reset = { source: null, sourceTitle: "", folder: null, tag: null, country: null };
    if (kind === "v") setFilter({ ...reset, view: value });
    else if (kind === "t") setFilter({ ...reset, view: "tutti", tag: chip.on ? null : Number(value) });
    else if (kind === "c") setFilter({ ...reset, view: "tutti", country: chip.on ? null : value });
    else setFilter({ ...reset, view: "tutti", folder: value });
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

  // ---- Swipe tra Edizione e Flusso (#29) ----
  let dragX = $state(0); // spostamento del contenuto mentre il dito si muove
  let settling = $state(false); // il contenuto torna al suo posto, animato
  let enterFrom = $state(""); // "left" · "right": da dove entra la modalità appena scelta
  let gesture = null; // { id, x, y, t, axis, lastX, lastT, vx }
  let swipedAt = 0;
  const reduceMotion = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const swipeOn = $derived(active && editionOn() && !noSources && !ui.reader && !ui.sheet && !confirmation.open);

  function onPointerDown(e) {
    if (!swipeOn || gesture || e.pointerType === "mouse" || !e.isPrimary) return;
    if (!canStart(e.clientX, window.innerWidth) || e.target.closest?.(NO_SWIPE)) return;
    gesture = { id: e.pointerId, x: e.clientX, y: e.clientY, t: e.timeStamp, axis: null, lastX: e.clientX, lastT: e.timeStamp, vx: 0 };
  }

  function onPointerMove(e) {
    if (!gesture || e.pointerId !== gesture.id) return;
    const dx = e.clientX - gesture.x;
    const dy = e.clientY - gesture.y;
    if (!gesture.axis) {
      gesture.axis = lockAxis(dx, dy);
      if (gesture.axis === "y") return (gesture = null); // scorre la pagina: non è uno swipe
      if (!gesture.axis) return;
      viewEl.setPointerCapture?.(e.pointerId);
      settling = false;
    }
    const dt = e.timeStamp - gesture.lastT;
    if (dt > 0) gesture.vx = 0.8 * ((e.clientX - gesture.lastX) / dt) + 0.2 * gesture.vx;
    gesture.lastX = e.clientX;
    gesture.lastT = e.timeStamp;
    dragX = reduceMotion ? 0 : offset(ui.oggiMode, dx);
  }

  function onPointerUp(e) {
    if (!gesture || e.pointerId !== gesture.id) return;
    const g = gesture;
    gesture = null;
    if (g.axis !== "x") return;
    swipedAt = performance.now();
    const dx = e.clientX - g.x;
    const next = release(ui.oggiMode, dx, g.vx, window.innerWidth);
    if (next) {
      enterFrom = reduceMotion ? "" : dx < 0 ? "right" : "left";
      dragX = 0;
      settling = false;
      ui.oggiMode = next;
    } else {
      settling = !reduceMotion;
      dragX = 0;
    }
  }

  // Il sistema si è preso il gesto (per esempio il «indietro» dal bordo): si annulla tutto.
  function onPointerCancel(e) {
    if (!gesture || e.pointerId !== gesture.id) return;
    gesture = null;
    settling = !reduceMotion;
    dragX = 0;
  }

  // Dopo uno swipe il dito si alza su una scheda: quel clic non deve aprire l'articolo.
  function onClickCapture(e) {
    if (performance.now() - swipedAt < 350) {
      e.preventDefault();
      e.stopPropagation();
    }
  }

  // Ogni modalità ricorda dove eri arrivato: passando avanti e indietro non si perde il punto.
  const modeScroll = {};
  let shownMode = ui.oggiMode;
  $effect.pre(() => {
    const mode = ui.oggiMode;
    untrack(() => {
      const from = shownMode;
      shownMode = mode;
      if (mode === from || !viewEl || !active) return;
      modeScroll[from] = viewScrollTop(viewEl);
      const y = modeScroll[mode] ?? 0;
      tick().then(() => scrollViewTo(viewEl, { top: y }));
    });
  });

  const today = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long" }).format(new Date()).replace(/^./, (c) => c.toUpperCase());
  const showEdition = $derived(editionOn() && ui.oggiMode === "edizione");
  const noSources = $derived(data.loaded && data.sources.length === 0);
  const filtering = $derived(stream.q || stream.view !== "tutti" || stream.folder || stream.source || stream.tag || stream.country);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<section
  class="view oggi-view"
  class:can-swipe={swipeOn}
  bind:this={viewEl}
  class:is-entering={active}
  hidden={!active}
  aria-label="Oggi"
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerCancel}
  onclickcapture={onClickCapture}
>
  <header class="large-title">
    <div><h2>Oggi</h2><p class="subtitle">{today}</p></div>
    <div class="topbar-actions">
      {#if !ui.online}<span class="offline-pill" title="Sei offline: vedi gli articoli già scaricati"><Icon name="cloud-off" />offline</span>{/if}
      <button type="button" class="icon-btn" class:is-spinning={ui.refreshing} aria-label="Aggiorna le fonti" onclick={refreshAll}><Icon name="refresh" /></button>
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
    {#if editionOn()}
      <div class="segmented mode-switch" role="tablist" aria-label="Modalità di lettura">
        <button type="button" role="tab" aria-selected={ui.oggiMode === "edizione"} onclick={() => { enterFrom = ""; ui.oggiMode = "edizione"; }}>Edizione</button>
        <button type="button" role="tab" aria-selected={ui.oggiMode === "flusso"} onclick={() => { enterFrom = ""; ui.oggiMode = "flusso"; }}>Flusso</button>
      </div>
    {/if}
  {/if}
  {#if !noSources}
  <div
    class="mode-pane"
    class:is-dragging={dragX !== 0}
    class:is-settling={settling}
    data-enter={enterFrom || undefined}
    style:transform={dragX ? `translate3d(${dragX}px, 0, 0)` : undefined}
    ontransitionend={() => (settling = false)}
    onanimationend={() => (enterFrom = "")}
  >
  {#if showEdition}
    <Edition />
  {:else}
    <label class="search">
      <Icon name="search" />
      <input type="search" placeholder="Cerca negli articoli e nelle fonti" autocomplete="off" aria-label="Cerca" value={query} oninput={onSearch} />
    </label>
    <div class="chips" role="toolbar" aria-label="Filtri">
      {#each chips as chip (chip.key)}
        <button type="button" class="chip" aria-pressed={chip.on} onclick={() => pick(chip)}>
          {#if chip.tag}<span class="hash" style="--topic-c:{chip.color}">#</span>{:else if chip.color}<span class="dot" style="--topic-c:{chip.color}"></span>{/if}{chip.label}<span class="n">{chip.n}</span>
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

    {#if stream.hiddenPartial && !stream.showPartial}
      <div class="hidden-note">
        <Icon name="eye-off" /><span>{stream.hiddenPartial === 1 ? "1 articolo nascosto" : `${stream.hiddenPartial} articoli nascosti`} perché il sito non lascia leggere il testo completo</span>
        <button type="button" onclick={() => setFilter({ showPartial: true })}>Mostra</button>
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
  </div>
  {/if}
</section>
