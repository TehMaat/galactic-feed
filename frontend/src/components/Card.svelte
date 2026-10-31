<script>
  // Articolo nel Flusso e nei Salvati: stessa struttura della «card» del mockup.
  import { readingInfo } from "../lib/format.js";
  import { foldersById, openArticle, setSaved, ui } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";
  import SourceMeta from "./SourceMeta.svelte";
  import Thumb from "./Thumb.svelte";

  let { article } = $props();
  const folderColor = $derived(foldersById()[article.source.folder_id]?.color || "indaco");

  function open() {
    openArticle(article.id);
  }
  function key(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      open();
    }
  }
  function toggleSave(e) {
    e.stopPropagation();
    setSaved(article, !article.saved);
  }
</script>

<div
  class="card tap"
  class:is-read={article.read}
  class:is-current={ui.reader === article.id}
  role="button"
  tabindex="0"
  onclick={open}
  onkeydown={key}
  aria-label={article.title}
>
  <div class="card-top">
    <SourceMeta {article} />
    {#if article.video}<span class="type-tag video">Video</span>{/if}
  </div>
  <div class="card-main">
    <div class="card-text">
      <h3 class="card-title clamp-3">{article.title}</h3>
      {#if article.excerpt}<p class="excerpt clamp-2">{article.excerpt}</p>{/if}
    </div>
    <Thumb {article} color={folderColor} />
  </div>
  <div class="card-foot">
    <div class="stats">
      <span>{readingInfo(article)}</span>
      {#if article.also_on.length}
        <span class="also">anche su {article.also_on.length === 1 ? article.also_on[0].title : `${article.also_on.length} fonti`}</span>
      {/if}
    </div>
    <div class="foot-r">
      {#if article.match}
        <span class="match"><Icon name="spark" />{article.match.keyword}</span>
      {:else if article.muted}
        <span class="match">Silenziato</span>
      {/if}
      <button
        type="button"
        class="save-btn"
        class:is-on={article.saved}
        aria-pressed={article.saved}
        aria-label={article.saved ? "Rimuovi dai salvati" : "Salva"}
        onclick={toggleSave}
        onkeydown={(e) => e.stopPropagation()}
      >
        <Icon name="bookmark" />
      </button>
    </div>
  </div>
</div>
