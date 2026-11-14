<script>
  // L'app vera e propria: viste, barra di navigazione, lettore, schede e avvisi.
  // Il layout cambia con la larghezza (container query in app.css, come nel mockup):
  // barra in basso sul telefono, barra laterale sul tablet, tre colonne sul computer.
  // Il nome dell'app sta nella barra in alto sul telefono e in cima alla barra laterale
  // altrove; le Impostazioni in fondo alla barra laterale (in alto a destra sul telefono).
  // Impostazioni e Amministrazione sono pagine (/impostazioni, /amministrazione), non finestre.
  // Toccando il nome dell'app si torna a Oggi.
  // Sul telefono le barre escono dallo schermo scorrendo giù e rientrano tornando su (#36).
  import Confirm from "./components/Confirm.svelte";
  import Icon from "./components/Icon.svelte";
  import Reader from "./components/Reader.svelte";
  import AddSource from "./sheets/AddSource.svelte";
  import EditionSheet from "./sheets/EditionSheet.svelte";
  import Admin from "./views/Admin.svelte";
  import FolderSheet from "./sheets/FolderSheet.svelte";
  import Settings from "./views/Settings.svelte";
  import SourceSheet from "./sheets/SourceSheet.svelte";
  import TagsSheet from "./sheets/TagsSheet.svelte";
  import { barsAfterScroll } from "./lib/bars.js";
  import { closeReader, closeSheet, data, goHome, openPage, session, switchTab, ui } from "./lib/store.svelte.js";
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
  let appEl = $state();
  let barsHidden = $state(false);
  const barsRef = new WeakMap(); // posizione di riferimento di ogni sezione

  // Cambiando sezione o pagina, aprendo o chiudendo il lettore o una scheda, toccando il logo:
  // le barre tornano visibili.
  $effect(() => {
    ui.tab;
    ui.reader;
    ui.sheet;
    ui.homeTick;
    ui.pageTick;
    barsHidden = false;
  });

  // Lo scorrimento è dentro ogni sezione (.view), non nella pagina: lo si ascolta in fase di
  // cattura su <main>, così un solo listener basta per tutte. Solo sul telefono (sotto i 700px,
  // come i container query in app.css): su tablet e computer la barra è laterale e resta ferma.
  function onViewScroll(e) {
    const el = e.target;
    if (!(el instanceof HTMLElement) || !el.classList.contains("view")) return;
    if (!appEl || appEl.clientWidth >= 700) {
      barsHidden = false;
      return;
    }
    const next = barsAfterScroll(barsRef.get(el) ?? 0, el.scrollTop, el.scrollHeight - el.clientHeight);
    barsRef.set(el, next.ref);
    if (next.hidden !== null) barsHidden = next.hidden;
  }

  // Un elemento con il focus non deve restare fuori schermo (tastiera, campo di ricerca).
  function showBars() {
    barsHidden = false;
  }
  function onViewFocus(e) {
    if (e.target instanceof HTMLElement && e.target.matches("input, textarea, select")) barsHidden = false;
  }

  $effect(() => {
    if (ui.sheet) scrimVisible = true;
    else {
      const t = setTimeout(() => (scrimVisible = false), 260);
      return () => clearTimeout(t);
    }
  });

  // Il logo è un link a «/»: con un clic normale si resta nell'app; con Ctrl/⌘ si apre una scheda nuova.
  function home(e) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    goHome();
  }

  // L'Amministrazione è solo per gli amministratori (anche aprendo /amministrazione a mano).
  $effect(() => {
    if (ui.tab === "amministrazione" && session.user && !session.user.is_admin) switchTab("impostazioni");
  });

  function onKey(e) {
    if (e.key !== "Escape") return;
    if (ui.sheet) closeSheet();
    else if (ui.reader) closeReader();
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="app" bind:this={appEl} data-tab={ui.tab} data-bars={barsHidden ? "hidden" : undefined} style="--ts:{ts}">
  <main class="views" onscrollcapture={onViewScroll} onfocusin={onViewFocus}>
    <Oggi active={ui.tab === "oggi"} />
    <Fonti active={ui.tab === "fonti"} />
    <Interessi active={ui.tab === "interessi"} />
    <Salvati active={ui.tab === "salvati"} />
    <Settings active={ui.tab === "impostazioni"} />
    {#if session.user?.is_admin}<Admin active={ui.tab === "amministrazione"} />{/if}
  </main>

  <header class="appbar" onfocusin={showBars}>
    <a class="wordmark" href="/" aria-label="galactic feed: vai a Oggi" title="Vai a Oggi" onclick={home}><Icon name="orbit" /><span>galactic feed</span></a>
    <button type="button" class="icon-btn" aria-label="Impostazioni" aria-pressed={ui.tab === "impostazioni" || ui.tab === "amministrazione"} onclick={() => openPage("impostazioni")}><Icon name="sliders" /></button>
  </header>

  <nav class="tabbar" aria-label="Sezioni" onfocusin={showBars}>
    <a class="nav-brand wordmark" href="/" aria-label="galactic feed: vai a Oggi" title="Vai a Oggi" onclick={home}><Icon name="orbit" /><span>galactic feed</span></a>
    {#each TABS as [key, icon, label]}
      <button type="button" aria-current={ui.tab === key ? "page" : undefined} onclick={() => switchTab(key)}>
        <Icon name={icon} /><span>{label}</span>
        {#if key === "salvati" && data.counts.salvati}<b class="tab-badge">{data.counts.salvati}</b>{/if}
      </button>
    {/each}
    <button type="button" class="nav-settings" aria-current={ui.tab === "impostazioni" ? "page" : undefined} onclick={() => openPage("impostazioni")}>
      <Icon name="sliders" /><span>Impostazioni</span>
    </button>
    {#if session.user?.is_admin}
      <!-- Solo per gli amministratori; sul telefono si apre dalle Impostazioni. -->
      <button type="button" class="nav-admin" aria-current={ui.tab === "amministrazione" ? "page" : undefined} onclick={() => openPage("amministrazione")}>
        <Icon name="shield" /><span>Amministrazione</span>
      </button>
    {/if}
  </nav>

  <Reader />

  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="scrim" class:is-on={!!ui.sheet} hidden={!scrimVisible} onclick={closeSheet}></div>
  <AddSource />
  <SourceSheet />
  <TagsSheet />
  <EditionSheet />
  <FolderSheet />
  <Confirm />

  <div class="toast" class:is-on={ui.toastOn} role="status" aria-live="polite">{ui.toast}</div>
</div>
