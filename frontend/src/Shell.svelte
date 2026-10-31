<script>
  // L'app vera e propria: viste, barra di navigazione, lettore, schede e avvisi.
  // Il layout cambia con la larghezza (container query in app.css, come nel mockup):
  // barra in basso sul telefono, barra laterale sul tablet, tre colonne sul computer.
  import Icon from "./components/Icon.svelte";
  import Reader from "./components/Reader.svelte";
  import AddSource from "./sheets/AddSource.svelte";
  import FolderSheet from "./sheets/FolderSheet.svelte";
  import Settings from "./sheets/Settings.svelte";
  import SourceSheet from "./sheets/SourceSheet.svelte";
  import { closeReader, closeSheet, data, session, switchTab, ui } from "./lib/store.svelte.js";
  import Fonti from "./views/Fonti.svelte";
  import Interessi from "./views/Interessi.svelte";
  import Oggi from "./views/Oggi.svelte";
  import Salvati from "./views/Salvati.svelte";

  const TABS = [
    ["oggi", "edition", "Oggi"],
    ["fonti", "rss", "Fonti"],
    ["interessi", "spark", "Interessi"],
    ["salvati", "bookmark", "Salvati"],
  ];
  const ts = $derived(session.user?.prefs?.text_size ?? 1);
  let scrimVisible = $state(false);

  $effect(() => {
    if (ui.sheet) scrimVisible = true;
    else {
      const t = setTimeout(() => (scrimVisible = false), 260);
      return () => clearTimeout(t);
    }
  });

  function onKey(e) {
    if (e.key !== "Escape") return;
    if (ui.sheet) closeSheet();
    else if (ui.reader) closeReader();
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="app" data-tab={ui.tab} style="--ts:{ts}">
  <main class="views">
    <Oggi active={ui.tab === "oggi"} />
    <Fonti active={ui.tab === "fonti"} />
    <Interessi active={ui.tab === "interessi"} />
    <Salvati active={ui.tab === "salvati"} />
  </main>

  <nav class="tabbar" aria-label="Sezioni">
    {#each TABS as [key, icon, label]}
      <button type="button" aria-current={ui.tab === key ? "page" : undefined} onclick={() => switchTab(key)}>
        <Icon name={icon} /><span>{label}</span>
        {#if key === "salvati" && data.counts.salvati}<b class="tab-badge">{data.counts.salvati}</b>{/if}
      </button>
    {/each}
  </nav>

  <Reader />

  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="scrim" class:is-on={!!ui.sheet} hidden={!scrimVisible} onclick={closeSheet}></div>
  <AddSource />
  <SourceSheet />
  <FolderSheet />
  <Settings />

  <div class="toast" class:is-on={ui.toastOn} role="status" aria-live="polite">{ui.toast}</div>
</div>
