<script>
  // Scheda che sale dal basso (sul tablet e sul computer è una finestra centrata).
  import { closeSheet, ui } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";

  let { name, title, back = null, children } = $props();
  const open = $derived(ui.sheet === name);
  let el = $state();

  $effect(() => {
    if (open && el) {
      el.scrollTop = 0;
      setTimeout(() => el?.querySelector("[autofocus], input, button.sheet-focus")?.focus?.({ preventScroll: true }), 380);
    }
  });
</script>

<div bind:this={el} class="sheet" class:is-open={open} role="dialog" aria-modal="true" aria-label={title} aria-hidden={!open} inert={!open}>
  <div class="grabber" aria-hidden="true"></div>
  <header class="sheet-head">
    {#if back}
      <button type="button" class="back-btn" onclick={back}><Icon name="back" /><span>Indietro</span></button>
    {/if}
    <h3>{title}</h3>
    <button type="button" class="icon-btn" aria-label="Chiudi" onclick={closeSheet}><Icon name="close" /></button>
  </header>
  {#if open}{@render children()}{/if}
</div>
