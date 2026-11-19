<script>
  // Notizia nel Notiziario, nei Salvati e in Cerca (#70): sopra la foto a tutta larghezza con il
  // titolo sovrapposto e la fonte in alto a destra, sotto l'estratto e «salva». Niente tempo di
  // lettura, etichette o ora: l'ora di pubblicazione è nell'articolo aperto.
  import { cover } from "../lib/art.js";
  import { sourceColor } from "../lib/format.js";
  import { foldersById, openArticle, setSaved, ui } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";
  import SourceIcon from "./SourceIcon.svelte";

  let { article } = $props();
  let failed = $state(false);
  const folderColor = $derived(foldersById()[article.source.folder_id]?.color || "indaco");
  const src = $derived(article.image && !failed ? article.image : cover(article.id, article.video ? "video" : folderColor, 640, 360));

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
  class="card glass tap"
  class:is-read={article.read}
  class:is-current={ui.reader === article.id}
  role="button"
  tabindex="0"
  onclick={open}
  onkeydown={key}
  aria-label={article.read ? article.title : `${article.title}, da leggere`}
>
  <div class="card-media">
    <img class="card-img" {src} alt="" decoding="async" loading="lazy" onerror={() => (failed = true)} />
    {#if !article.read}<span class="unread-dot" title="Da leggere"></span>{/if}
    <span class="src-pill">
      <SourceIcon source={article.source} color={sourceColor(article.source, foldersById())} />
      <span>{article.source.title}</span>
    </span>
    {#if article.video}<span class="card-play"><span><Icon name="play" /></span></span>{/if}
    <h3 class="card-title">{article.title}</h3>
  </div>
  <div class="card-body">
    {#if article.excerpt}<p class="excerpt clamp-3">{article.excerpt}</p>{:else}<span></span>{/if}
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
