<script>
  import { initials, sourceColor, timeAgo } from "../lib/format.js";
  import { foldersById } from "../lib/store.svelte.js";

  let { article } = $props();
  const color = $derived(sourceColor(article.source, foldersById()));
</script>

<div class="meta">
  <span class="mono-av" style="--src-c:{color}">{initials(article.source.title)}</span>
  <span class="src">{article.source.title}</span>
  <span class="sep"></span>
  <span>{timeAgo(article.published_at)}</span>
</div>
