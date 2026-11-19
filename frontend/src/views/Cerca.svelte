<script>
  // Cerca (#64): negli articoli e nei nomi delle fonti, con «X notizie · X da leggere» (#66).
  import Card from "../components/Card.svelte";
  import Icon from "../components/Icon.svelte";
  import SourceIcon from "../components/SourceIcon.svelte";
  import { tallyText } from "../lib/filters.js";
  import { sourceColor } from "../lib/format.js";
  import { changeFilter, data, foldersById, loadSearch, search, switchTab } from "../lib/store.svelte.js";

  let { active } = $props();
  let input = $state();
  let sentinel = $state();
  let timer;

  // Aprendo Cerca il cursore va nel campo (non sul telefono, dove aprirebbe subito la tastiera).
  $effect(() => {
    if (active && input && window.matchMedia("(min-width: 1100px)").matches) input.focus({ preventScroll: true });
  });

  function onInput(e) {
    search.q = e.target.value;
    clearTimeout(timer);
    timer = setTimeout(() => loadSearch(true), 250);
  }
  function quick(q) {
    search.q = q;
    loadSearch(true);
  }
  function showSourceNews(s) {
    changeFilter({ scope: "tutte", unread: false, inc: [`s:${s.id}`], exc: [] });
    switchTab("oggi");
  }

  $effect(() => {
    if (!sentinel) return;
    const io = new IntersectionObserver((e) => {
      if (e.some((x) => x.isIntersecting) && search.items.length && !search.done) loadSearch();
    }, { rootMargin: "600px" });
    io.observe(sentinel);
    return () => io.disconnect();
  });

  const matchingSources = $derived(
    search.q.trim().length > 1 ? data.sources.filter((s) => s.title.toLowerCase().includes(search.q.trim().toLowerCase())).slice(0, 6) : [],
  );
  const suggestions = $derived([...data.tags.slice(0, 4).map((t) => t.name), ...(data.interests.groups || []).filter((g) => g.mode === "interest").slice(0, 3).map((g) => g.name)]);
</script>

<section class="view cerca-view" class:is-entering={active} hidden={!active} aria-label="Cerca">
  <div class="sec-head"><div><p class="eyebrow">Cerca</p><h1 class="sec-title">Notizie e fonti</h1></div></div>
  <label class="search-field glass">
    <Icon name="search" />
    <input bind:this={input} type="search" placeholder="Cerca negli articoli e nelle fonti" autocomplete="off" aria-label="Cerca negli articoli e nelle fonti" value={search.q} oninput={onInput} />
    {#if search.q}<button type="button" class="clear-btn" aria-label="Cancella" onclick={() => quick("")}><Icon name="close" /></button>{/if}
  </label>

  {#if !search.q.trim()}
    {#if suggestions.length}
      <p class="lbl">Prova con</p>
      <div class="opt-chips">
        {#each suggestions as s (s)}<button type="button" class="chip glass" onclick={() => quick(s)}>{s}</button>{/each}
      </div>
    {/if}
  {:else}
    {#if matchingSources.length}
      <p class="lbl">Fonti</p>
      <div class="opt-chips">
        {#each matchingSources as s (s.id)}
          <button type="button" class="chip glass" onclick={() => showSourceNews(s)}><SourceIcon source={s} color={sourceColor(s, foldersById())} />{s.title}</button>
        {/each}
      </div>
    {/if}
    <p class="sec-sub" aria-live="polite">{search.tally ? tallyText(search.tally) : ""}</p>
    <div class="stack">
      {#each search.items as article (article.id)}<Card {article} />{/each}
    </div>
    {#if search.error}
      <div class="empty"><Icon name="alert" /><h3>Non riesco a cercare</h3><p>{search.error}</p></div>
    {:else if !search.loading && !search.items.length}
      <div class="empty"><Icon name="search" /><h3>Nessun risultato</h3><p>Prova un'altra parola, o l'inizio di una parola: «galass» trova anche «galassie».</p></div>
    {/if}
    <div bind:this={sentinel} class="sentinel" aria-hidden="true"></div>
    {#if search.loading}<p class="loading">Cerco…</p>{/if}
  {/if}
</section>
