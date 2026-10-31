<script>
  // Immagine dell'articolo, oppure una copertina generativa come nel mockup.
  import { cover } from "../lib/art.js";
  import Icon from "./Icon.svelte";

  let { article, color = "indaco", wide = false } = $props();
  let failed = $state(false);
  const w = $derived(wide ? 480 : 96);
  const h = $derived(wide ? 300 : 96);
  const src = $derived(article.image && !failed ? article.image : cover(article.id, article.video ? "video" : color, w, h));
</script>

{#if article.video}
  <span class="thumb-wrap">
    <img class="thumb" {src} alt="" decoding="async" loading="lazy" onerror={() => (failed = true)} />
    <span class="play"><Icon name="play" /></span>
  </span>
{:else}
  <img class="thumb" {src} alt="" decoding="async" loading="lazy" onerror={() => (failed = true)} />
{/if}
