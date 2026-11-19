<script>
  // Icona e nome della fonte. L'ora di pubblicazione è solo nell'articolo aperto (#70).
  import { sourceColor } from "../lib/format.js";
  import { foldersById } from "../lib/store.svelte.js";
  import SourceIcon from "./SourceIcon.svelte";

  let { article } = $props();
  const color = $derived(sourceColor(article.source, foldersById()));
</script>

<div class="meta">
  <SourceIcon source={article.source} {color} />
  <span class="src">{article.source.title}</span>
</div>
