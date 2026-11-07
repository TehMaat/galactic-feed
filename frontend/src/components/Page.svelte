<script>
  // Pagina a tutto schermo per le Impostazioni e l'Amministrazione: sul telefono come le altre
  // sezioni, sul computer larga, con l'indice delle sezioni a sinistra (nav) e il contenuto a destra.
  import Icon from "./Icon.svelte";

  let { label, title, active, back = null, nav = null, current = null, onnav = null, scrollKey = "", children } = $props();
  let el = $state();

  // Cambiando sottopagina si torna in cima.
  $effect(() => {
    scrollKey;
    if (el) el.scrollTop = 0;
  });
</script>

<section bind:this={el} class="view page-view" class:is-entering={active} class:has-nav={!!nav} hidden={!active} aria-label={label}>
  <div class="page-wrap">
    {#if nav}
      <nav class="page-nav" aria-label="Sezioni di {label}">
        <p class="page-nav-title">{label}</p>
        {#each nav as [key, icon, text] (key)}
          <button type="button" aria-current={current === key ? "page" : undefined} onclick={() => onnav?.(key)}><Icon name={icon} /><span>{text}</span></button>
        {/each}
      </nav>
    {/if}
    <div class="page-main">
      <header class="page-head">
        {#if back}
          <button type="button" class="back-btn" onclick={back}><Icon name="back" /><span>Indietro</span></button>
        {/if}
        <h2>{title}</h2>
      </header>
      {#if active}{@render children()}{/if}
    </div>
  </div>
</section>
