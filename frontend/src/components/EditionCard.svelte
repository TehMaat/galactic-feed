<script>
  // Un'Edizione in Oggi (#64): copertina a tutta larghezza, più alta di quella delle notizie (#80),
  // con etichetta dalle regole, «da leggere», data, quante notizie ha e il nome grande sopra la
  // foto; sotto il titolo d'apertura. Tocco: si apre come un articolo.
  import { cover } from "../lib/art.js";
  import { openEdition, ui } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";

  let { ed } = $props();
  let failed = $state(false);
  const img = $derived(ed.lead?.image && !failed ? ed.lead.image : cover(ed.id + 1000, "viola", 640, 400));
  const day = $derived(new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "short" }).format(new Date(ed.created_at)).replace(/^./, (c) => c.toUpperCase()));
  const count = $derived(ed.count === 1 ? "1 notizia" : `${ed.count} notizie`);
</script>

<button type="button" class="ed-card glass tap" class:is-current={ui.edition === ed.id} class:is-read={ed.count && !ed.unread} onclick={() => openEdition(ed.id)}
  aria-label="{ed.name}, {day}, {count}{ed.unread ? `, ${ed.unread} da leggere` : ''}">
  <span class="ed-media">
    <img class="ed-cover" src={img} alt="" decoding="async" loading="lazy" onerror={() => (failed = true)} />
    <span class="ed-top">
      {#if ed.label}<span class="ed-tag"><Icon name="edition" />{ed.label.replace(/^./, (c) => c.toUpperCase())}</span>{/if}
      {#if ed.unread}<span class="ed-unread">{ed.unread} da leggere</span>{/if}
    </span>
    <span class="ed-head">
      <span class="ed-meta">{day} · {count}</span>
      <span class="ed-name">{ed.name}</span>
    </span>
  </span>
  {#if ed.lead}
    <span class="ed-body">
      <span class="ed-lead-wrap"><span class="ed-kicker">In apertura</span><span class="ed-lead clamp-2">{ed.lead.title}</span></span>
      <span class="ed-go"><Icon name="chevron" /></span>
    </span>
  {/if}
</button>
