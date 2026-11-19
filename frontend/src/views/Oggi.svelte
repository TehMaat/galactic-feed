<script>
  // Oggi (#64): in alto le Edizioni (l'ultima uscita di ognuna), sotto il Notiziario con i preset,
  // nello stesso scroll. Senza Edizioni c'è solo il Notiziario. Dalla Dock «Notiziario» scorre fino
  // alla sua sezione e si accende quando ci si arriva.
  import { tick } from "svelte";
  import Card from "../components/Card.svelte";
  import EditionCard from "../components/EditionCard.svelte";
  import FilterBar from "../components/FilterBar.svelte";
  import Icon from "../components/Icon.svelte";
  import { tallyText } from "../lib/filters.js";
  import { docScroll, scrollViewTo, viewScrollTop } from "../lib/scroll.js";
  import { applyPreset, data, loadStream, openSheet, refreshAll, setFilter, stream, switchTab, today, ui } from "../lib/store.svelte.js";

  let { active } = $props();
  let sentinel = $state();
  let viewEl = $state();
  let newsEl = $state();

  // Tocco sul logo: si torna in cima (se si è già in cima non succede altro).
  $effect(() => {
    if (ui.homeTick && viewEl && viewScrollTop(viewEl) > 0) scrollViewTo(viewEl, { top: 0, behavior: "smooth" });
  });

  // «Notiziario» nella Dock: si scorre fino alla sezione.
  $effect(() => {
    if (!ui.newsTick || !newsEl || !viewEl) return;
    tick().then(() => {
      const top = docScroll() ? newsEl.getBoundingClientRect().top + window.scrollY - 64 : newsEl.offsetTop - 12;
      scrollViewTo(viewEl, { top: Math.max(0, top), behavior: "smooth" });
    });
  });

  // La Dock accende «Notiziario» quando il suo titolo è salito nella parte alta dello schermo.
  $effect(() => {
    if (!newsEl || !active) return;
    const check = () => (ui.atNews = newsEl.getBoundingClientRect().top < window.innerHeight * 0.25);
    check();
    window.addEventListener("scroll", check, { passive: true });
    viewEl?.addEventListener("scroll", check, { passive: true });
    // Anche quando cambia l'altezza sopra (per esempio arrivano le Edizioni), senza scorrere.
    const ro = new ResizeObserver(check);
    if (viewEl) ro.observe(viewEl.firstElementChild || viewEl);
    return () => {
      window.removeEventListener("scroll", check);
      viewEl?.removeEventListener("scroll", check);
      ro.disconnect();
      ui.atNews = false;
    };
  });

  $effect(() => {
    if (!sentinel) return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && stream.items.length && !stream.done) loadStream();
    }, { rootMargin: "600px" });
    io.observe(sentinel);
    return () => io.disconnect();
  });

  const noSources = $derived(data.loaded && data.sources.length === 0);
  const hasEditions = $derived(today.editions.length > 0);
  const filtering = $derived(stream.filter.inc.length || stream.filter.exc.length || stream.filter.unread);
</script>

<section class="view oggi-view" bind:this={viewEl} class:is-entering={active} hidden={!active} aria-label="Oggi">
  {#if noSources}
    <div class="empty">
      <Icon name="rss" />
      <h3>Nessuna fonte, per ora</h3>
      <p>Aggiungi un sito, un feed o un canale YouTube: gli articoli compariranno qui.</p>
      <button type="button" class="pill-btn" onclick={() => openSheet("add")}><Icon name="plus" />Aggiungi una fonte</button>
    </div>
  {:else}
    <div class="oggi-stack">
      {#if hasEditions}
        <section class="oggi-sec" aria-labelledby="h-edizioni">
          <div class="sec-head"><div><p class="eyebrow">La tua rassegna</p><h2 class="sec-title" id="h-edizioni">Edizioni di oggi</h2></div></div>
          <div class="ed-list">
            {#each today.editions as ed (ed.id)}<EditionCard {ed} />{/each}
          </div>
        </section>
      {/if}

      <section class="oggi-sec" aria-labelledby="h-notiziario">
        <div class="sec-head" bind:this={newsEl}>
          <div>
            {#if hasEditions}<h2 class="sec-title" id="h-notiziario">Notiziario</h2>{:else}<h1 class="sec-title" id="h-notiziario">Notiziario</h1>{/if}
            <p class="sec-sub" aria-live="polite">{#if stream.tally}{@const parts = tallyText(stream.tally).split(" · ")}{parts[0]}{#if parts[1]}{" · "}<b>{parts[1]}</b>{/if}{/if}</p>
          </div>
          <div class="sec-actions">
            {#if !ui.online}<span class="offline-pill" title="Sei offline: vedi gli articoli già scaricati"><Icon name="cloud-off" />offline</span>{/if}
            <button type="button" class="round-btn glass" class:is-spinning={ui.refreshing} aria-label="Aggiorna le fonti" title="Aggiorna le fonti" onclick={refreshAll}><Icon name="refresh" /></button>
          </div>
        </div>

        <FilterBar />

        <div class="stack">
          {#each stream.items as article (article.id)}
            <Card {article} />
          {/each}
        </div>

        {#if stream.error}
          <div class="empty"><Icon name="alert" /><h3>Non riesco a caricare gli articoli</h3><p>{stream.error}</p>
            <button type="button" class="btn-secondary small" onclick={() => loadStream(true)}>Riprova</button></div>
        {:else if !stream.loading && stream.items.length === 0 && !filtering && stream.filter.scope === "perte" && stream.presetTally.tutte?.total}
          <div class="empty">
            <Icon name="spark" />
            <h3>Ancora niente per te</h3>
            <p>«Per te» mostra le notizie che corrispondono ai tuoi interessi. Scegline qualcuno, o guarda tutte le notizie.</p>
            <div class="empty-actions">
              <button type="button" class="btn-secondary small" onclick={() => applyPreset("tutte")}>Mostra tutte le notizie</button>
              <button type="button" class="btn-secondary small" onclick={() => switchTab("interessi")}><Icon name="spark" />Scegli i tuoi interessi</button>
            </div>
          </div>
        {:else if !stream.loading && stream.items.length === 0}
          <div class="empty">
            <Icon name={filtering ? "filter" : "check"} />
            <h3>{filtering ? "Nessuna notizia con questi filtri" : "Ancora nessun articolo"}</h3>
            <p>{filtering ? "Prova un altro preset o togli un filtro." : "Le fonti appena aggiunte arrivano entro pochi minuti."}</p>
            {#if filtering}<button type="button" class="btn-secondary small" onclick={() => applyPreset("tutte")}>Mostra tutte le notizie</button>{/if}
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
            <span>Hai visto tutto quello che c'è con questi filtri.</span>
          </div>
        {/if}
      </section>
    </div>
  {/if}
</section>
