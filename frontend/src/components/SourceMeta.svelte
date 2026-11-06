<script>
  import { sourceColor, timeAgo } from "../lib/format.js";
  import { foldersById } from "../lib/store.svelte.js";
  import SourceIcon from "./SourceIcon.svelte";

  let { article } = $props();
  const color = $derived(sourceColor(article.source, foldersById()));
</script>

<div class="meta">
  <SourceIcon source={article.source} {color} />
  <span class="src">{article.source.title}</span>
  <span class="sep"></span>
  <span>{timeAgo(article.published_at)}</span>
</div>
