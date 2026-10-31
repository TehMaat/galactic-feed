<script>
  import Card from "../components/Card.svelte";
  import Icon from "../components/Icon.svelte";
  import { loadSaved, saved } from "../lib/store.svelte.js";

  let { active } = $props();
  let sentinel = $state();
  let started = false;

  $effect(() => {
    if (active && !started) {
      started = true;
      loadSaved(true);
    }
  });

  $effect(() => {
    if (!sentinel) return;
    const io = new IntersectionObserver((e) => {
      if (e.some((x) => x.isIntersecting) && saved.items.length && !saved.done) loadSaved();
    }, { rootMargin: "600px" });
    io.observe(sentinel);
    return () => io.disconnect();
  });
</script>

<section class="view" class:is-entering={active} hidden={!active} aria-label="Salvati">
  <header class="large-title">
    <div><h2>Salvati</h2><p class="subtitle">Disponibili anche offline</p></div>
  </header>
  {#if saved.items.length}
    <div class="stack">
      {#each saved.items as article (article.id)}
        <Card {article} />
      {/each}
    </div>
  {:else if saved.error}
    <div class="empty"><Icon name="alert" /><h3>Non riesco a caricare i salvati</h3><p>{saved.error}</p></div>
  {:else if !saved.loading}
    <div class="empty"><Icon name="bookmark" /><h3>Ancora niente</h3><p>Tocca il segnalibro su un articolo per ritrovarlo qui, anche senza connessione.</p></div>
  {/if}
  <div bind:this={sentinel} class="sentinel" aria-hidden="true"></div>
</section>
