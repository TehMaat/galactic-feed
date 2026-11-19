<script>
  // Riga del Notiziario (#68): «Filtri» e i preset. Quando non ci stanno tutti, il bordo sfuma e
  // una freccia fa scorrere la riga. Se i filtri in uso non sono un preset, sotto c'è il riepilogo
  // con «Salva come preset» e «Azzera».
  import { describeFilter } from "../lib/filters.js";
  import { allPresets, applyPreset, currentPreset, data, openSheet, stream } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";

  let row = $state();
  let atStart = $state(true);
  let atEnd = $state(true);
  const cur = $derived(currentPreset(stream.filter));
  const n = $derived(stream.filter.inc.length + stream.filter.exc.length + (stream.filter.unread ? 1 : 0));

  function edges() {
    if (!row) return;
    atStart = row.scrollLeft < 4;
    atEnd = row.scrollLeft + row.clientWidth >= row.scrollWidth - 4;
  }
  $effect(() => {
    allPresets().length;
    if (!row) return;
    edges();
    const ro = new ResizeObserver(edges);
    ro.observe(row);
    return () => ro.disconnect();
  });
  function more() {
    row.scrollBy({ left: row.clientWidth * 0.7, behavior: "smooth" });
  }
</script>

<div class="filter-bar">
  <button type="button" class="chip glass filter-btn" onclick={() => openSheet("filters")} aria-label={n ? `Filtri, ${n} attivi` : "Filtri"}>
    <Icon name="filter" />Filtri{#if n}<b class="filter-count">{n}</b>{/if}
  </button>
  <div class="preset-wrap" class:at-start={atStart} class:at-end={atEnd}>
    <div class="chips preset-row" bind:this={row} onscroll={edges} role="toolbar" aria-label="Preset del Notiziario">
      {#each allPresets() as p (p.id)}
        {@const t = stream.presetTally[p.id]}
        <button type="button" class="chip glass" aria-pressed={cur?.id === p.id} onclick={() => applyPreset(p.id)}>
          {#if p.icon}<Icon name={p.icon} />{/if}{p.name}{#if t}<span class="n">{p.filter.unread ? t.total : t.unread}</span>{/if}
        </button>
      {/each}
    </div>
    {#if !atEnd}
      <button type="button" class="preset-more glass" aria-label="Altri preset" onclick={more}><Icon name="chevron" /></button>
    {/if}
  </div>
</div>
{#if !cur}
  <p class="filter-sum">
    <span>{describeFilter(stream.filter, data)}</span>
    <button type="button" class="link-btn" onclick={() => openSheet("filters", "save")}>Salva come preset</button>
    <button type="button" class="link-btn" onclick={() => applyPreset("perte")}>Azzera</button>
  </p>
{/if}
