<script>
  // Profilo (#64, #76, #78): chi sei (nome e avatar modificabili), scorciatoie per Salvati, Fonti,
  // Interessi, Impostazioni e Amministrazione, e le statistiche di lettura. Sul telefono sotto ci
  // sono anche la ricerca e le sezioni delle Impostazioni.
  import Avatar from "../components/Avatar.svelte";
  import Icon from "../components/Icon.svelte";
  import Stats from "../components/Stats.svelte";
  import { data, loadStats, openPage, openSheet, session, switchTab, ui } from "../lib/store.svelte.js";

  let { active } = $props();
  const me = $derived(session.user);

  $effect(() => {
    if (active) loadStats();
  });

  const SECTIONS = [
    ["account", "user", "Account", "Nome, password, dispositivi"],
    ["edizioni", "edition", "Edizioni", "Rassegne, orari, fuso orario"],
    ["notifiche", "bell", "Notifiche", "Su questo dispositivo"],
    ["ai", "spark", "AI", "Fornitore e riassunti"],
    ["aspetto", "sliders", "Aspetto", "Tema, palette, colore, font"],
    ["lettura", "eye-off", "Lettura", "Preset all'apertura, articoli"],
    ["server", "devices", "Server e dati", "Indirizzo, esporta le fonti"],
    ["info", "refresh", "Informazioni", "Versione e aggiornamenti"],
  ];

  function searchSettings() {
    ui.settingsFocus = true;
    openPage("impostazioni");
  }

  // «Impostazioni» tra le scorciatoie (#81): sul telefono e sul tablet le sezioni delle Impostazioni
  // sono qui sotto, quindi la pagina scorre fin lì; sul computer non ci sono e si apre la pagina.
  let settingsTitle = $state();
  function openSettings() {
    if (!settingsTitle?.getClientRects().length) return openPage("impostazioni");
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    settingsTitle.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    settingsTitle.focus({ preventScroll: true });
  }
</script>

<section class="view profilo-view" class:is-entering={active} hidden={!active} aria-label="Profilo">
  {#if me}
    <div class="profilo-grid">
      <div class="profilo-side">
        <div class="me-card glass">
          <button type="button" class="me-edit" onclick={() => openSheet("profile")} aria-label="Cambia nome e avatar">
            <Avatar user={me} size="lg" /><span class="me-pen"><Icon name="edit" /></span>
          </button>
          <div class="me-text">
            <h1>{me.display_name}</h1>
            <span class="me-who">@{me.username}{#if me.is_admin}<span class="me-role">Amministratore</span>{/if}</span>
          </div>
        </div>

        <nav class="shortcuts" aria-label="Le tue sezioni">
          <button type="button" class="shortcut glass" onclick={() => switchTab("salvati")}><Icon name="bookmark" /><span>Salvati</span>{#if data.counts.salvati}<b>{data.counts.salvati}</b>{/if}</button>
          <button type="button" class="shortcut glass" onclick={() => switchTab("fonti")}><Icon name="rss" /><span>Fonti</span><b>{data.sources.length}</b></button>
          <button type="button" class="shortcut glass" onclick={() => switchTab("interessi")}><Icon name="spark" /><span>Interessi</span></button>
          <button type="button" class="shortcut glass" onclick={openSettings}><Icon name="sliders" /><span>Impostazioni</span></button>
          {#if me.is_admin}
            <button type="button" class="shortcut glass" onclick={() => openPage("amministrazione")}><Icon name="shield" /><span>Amministrazione</span></button>
          {/if}
        </nav>
      </div>

      <div class="profilo-main">
        <Stats wide />

        <!-- Sul telefono le Impostazioni sono qui sotto; sul computer sono nella barra in alto. -->
        <section class="compact-only profilo-settings" aria-labelledby="h-imp">
          <h2 class="sec-title small" id="h-imp" tabindex="-1" bind:this={settingsTitle}>Impostazioni</h2>
          <button type="button" class="search-field glass as-button" onclick={searchSettings}><Icon name="search" /><span>Cerca nelle impostazioni</span></button>
          <div class="set-group glass-group">
            {#each SECTIONS as [key, icon, title, sub] (key)}
              <button type="button" class="set-row as-button section-row" onclick={() => openPage("impostazioni", key)}>
                <span class="section-ico"><Icon name={icon} /></span>
                <span class="section-t"><b>{title}</b><small>{sub}</small></span>
                <Icon name="chevron" />
              </button>
            {/each}
          </div>
        </section>
      </div>
    </div>
  {/if}
</section>
