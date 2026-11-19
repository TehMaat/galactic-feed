<script>
  // Un'Edizione in Oggi (#64): etichetta dalle regole, nome, data e quante notizie ha, titolo
  // d'apertura e copertina. Tocco: si apre come un articolo.
  import { cover } from "../lib/art.js";
  import { openEdition, ui } from "../lib/store.svelte.js";

  let { ed } = $props();
  let failed = $state(false);
  const img = $derived(ed.lead?.image && !failed ? ed.lead.image : cover(ed.id + 1000, "viola", 240, 320));
  const day = $derived(new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "short" }).format(new Date(ed.created_at)).replace(/^./, (c) => c.toUpperCase()));
  const count = $derived(ed.count === 1 ? "1 notizia" : `${ed.count} notizie`);
</script>

<button type="button" class="ed-card glass tap" class:is-current={ui.edition === ed.id} class:is-read={ed.count && !ed.unread} onclick={() => openEdition(ed.id)}
  aria-label="{ed.name}, {day}, {count}{ed.unread ? `, ${ed.unread} da leggere` : ''}">
  <span class="ed-text">
    {#if ed.label}<span class="ed-tag">{ed.label.replace(/^./, (c) => c.toUpperCase())}</span>{/if}
    <span class="ed-name">{ed.name}</span>
    <span class="ed-meta">{day} · {count}</span>
    {#if ed.lead}<span class="ed-lead clamp-2">{ed.lead.title}</span>{/if}
  </span>
  <img class="ed-cover" src={img} alt="" decoding="async" loading="lazy" onerror={() => (failed = true)} />
</button>
