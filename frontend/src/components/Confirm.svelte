<script>
  // Finestra di conferma dell'app (vedi ask() in store.svelte.js).
  import Icon from "./Icon.svelte";
  import { answer, confirmation } from "../lib/store.svelte.js";

  let okButton = $state();
  $effect(() => {
    if (confirmation.open) setTimeout(() => okButton?.focus(), 30);
  });

  function onKey(e) {
    if (!confirmation.open) return;
    if (e.key === "Escape") {
      e.stopPropagation();
      e.preventDefault();
      answer(false);
    }
  }
</script>

<svelte:window onkeydowncapture={onKey} />

{#if confirmation.open}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="confirm-scrim" onclick={() => answer(false)}></div>
  <div class="confirm" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-text">
    <h3 id="confirm-title">{confirmation.title}</h3>
    <p id="confirm-text">{confirmation.message}</p>
    <div class="confirm-actions">
      <button type="button" class="btn-secondary" onclick={() => answer(false)}>Annulla</button>
      <button type="button" bind:this={okButton} class={confirmation.danger ? "btn-primary is-danger" : "btn-primary"} onclick={() => answer(true)}>
        {#if confirmation.danger}<Icon name="trash" />{/if}{confirmation.action}
      </button>
    </div>
  </div>
{/if}
