<script>
  // L'app vera e propria: viste, barra di navigazione, lettore, schede e avvisi.
  // Il layout cambia con la larghezza (media query in app.css): su telefono e tablet una barra
  // in alto con il nome dell'app e le Impostazioni e la Dock in basso con le sezioni; sul
  // computer un'unica barra in alto (nome, sezioni, Impostazioni e Amministrazione a destra)
  // sopra lista e lettore affiancati.
  // Impostazioni e Amministrazione sono pagine (/impostazioni, /amministrazione), non finestre.
  // Toccando il nome dell'app si torna a Oggi.
  // Su telefono e tablet scorre il documento, così nel browser anche la barra degli indirizzi si
  // riduce (#38); le barre dell'app escono dallo schermo scorrendo giù e rientrano tornando su (#36).
  import { tick, untrack } from "svelte";
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
  import { applyUpdate, pwa } from "./lib/pwa.svelte.js";
  import { COMPACT_QUERY } from "./lib/scroll.js";
  import { closeReader, closeSheet, confirmation, data, goHome, openPage, session, switchTab, ui } from "./lib/store.svelte.js";
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
  let barsHidden = $state(false);
  let barsRef = 0; // posizione di riferimento per le barre
  // Su telefono e tablet scorre il documento (#38); sul computer ogni sezione ha il suo scroll.
  const compact = window.matchMedia(COMPACT_QUERY);
  let docMode = $state(compact.matches);
  $effect(() => {
    const sync = () => (docMode = compact.matches);
    compact.addEventListener("change", sync);
    return () => compact.removeEventListener("change", sync);
  });
  // Le posizioni le gestisce l'app (per sezione), non il browser tornando indietro nella cronologia.
  history.scrollRestoration = "manual";

  // Un solo documento che scorre per tutte le sezioni: ognuna ricorda dove eri arrivato.
  // Impostazioni e Amministrazione ripartono sempre dalla cima, come le loro sottopagine.
  const KEEP = new Set(["oggi", "fonti", "interessi", "salvati"]);
  const positions = {};
  let shownTab = ui.tab;
  let seenHome = ui.homeTick;
  $effect.pre(() => {
    // Prima che il DOM cambi: window.scrollY è ancora quella della sezione che si lascia.
    const tab = ui.tab;
    const home = ui.homeTick;
    untrack(() => {
      const from = shownTab;
      const homed = home !== seenHome;
      shownTab = tab;
      seenHome = home;
      if (tab === from || !docMode) return;
      positions[from] = window.scrollY;
      if (homed) positions.oggi = 0; // il logo riporta Oggi in cima
      const y = KEEP.has(tab) ? (positions[tab] ?? 0) : 0;
      tick().then(() => {
        barsRef = y;
        window.scrollTo(0, y);
      });
    });
  });

  // Con il lettore, una scheda o una conferma aperti la lista sotto non scorre; alla chiusura
  // torna dov'era, anche se il browser l'ha spostata (per esempio per mostrare un campo).
  $effect(() => {
    if (!docMode || !(ui.reader || ui.sheet || confirmation.open)) return;
    const root = document.documentElement;
    const y = window.scrollY;
    root.classList.add("gf-lock");
    return () => {
      root.classList.remove("gf-lock");
      if (Math.abs(window.scrollY - y) > 1) window.scrollTo(0, y);
      barsRef = window.scrollY;
    };
  });

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

  // Barre a scomparsa (#36), su telefono e tablet: sul computer la barra in alto resta ferma.
  function onWindowScroll() {
    if (!docMode || document.documentElement.classList.contains("gf-lock")) return;
    // Con il focus da tastiera su una barra il browser fa scorrere la pagina per mostrarla: quello
    // scorrimento non deve nasconderla di nuovo. (Un tocco lascia il focus sul pulsante, ma non
    // «visibile»: lì le barre continuano a nascondersi.)
    const focused = document.activeElement;
    if (focused?.closest?.(".appbar, .tabbar") && focused.matches(":focus-visible")) {
      barsRef = window.scrollY;
      barsHidden = false;
      return;
    }
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const next = barsAfterScroll(barsRef, window.scrollY, max);
    barsRef = next.ref;
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

<svelte:window onkeydown={onKey} onscroll={onWindowScroll} />

<div class="app" data-tab={ui.tab} data-bars={barsHidden ? "hidden" : undefined} style="--ts:{ts}">
  <main class="views" onfocusin={onViewFocus}>
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
      <!-- Solo per gli amministratori; su telefono e tablet si apre dalle Impostazioni. -->
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

  <!-- Versione nuova dell'app pronta (#41): si attiva con un tocco, oppure da sola alla prossima apertura. -->
  {#if pwa.ready && !pwa.dismissed}
    <div class="update-bar" role="status">
      <span>È disponibile una nuova versione</span>
      <button type="button" class="update-go" onclick={applyUpdate}>Aggiorna</button>
      <button type="button" class="icon-btn" aria-label="Più tardi" title="Più tardi" onclick={() => (pwa.dismissed = true)}><Icon name="close" /></button>
    </div>
  {/if}

  <div class="toast" class:is-on={ui.toastOn} class:above-update={pwa.ready && !pwa.dismissed} role="status" aria-live="polite">{ui.toast}</div>
</div>
