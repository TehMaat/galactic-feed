<script>
  // Icona della fonte (favicon del sito o avatar del canale), oppure le iniziali colorate
  // se l'icona manca, è spenta o non si carica. Le icone passano dal proxy /api/img e il
  // service worker le tiene per l'offline.
  import { initials } from "../lib/format.js";

  let { source, color, cls = "mono-av" } = $props();
  let failed = $state(null); // indirizzo dell'icona che non si è caricata
  const src = $derived(source?.icon && failed !== source.icon ? source.icon : null);
</script>

{#if src}
  <img class="{cls} is-icon" {src} alt="" decoding="async" loading="lazy" onerror={() => (failed = src)} />
{:else}
  <span class={cls} style="--src-c:{color}" aria-hidden="true">{initials(source?.title)}</span>
{/if}
