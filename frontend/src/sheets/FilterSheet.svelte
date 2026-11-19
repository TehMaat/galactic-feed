<script>
  // Pannello Filtri del Notiziario (#68, #69): da dove partire, solo non letti, interessi, tipo,
  // cartelle, nazioni e fonti a tre stati (nascondi · nessun filtro · solo questi), i preset e
  // quale usare all'apertura. Ogni scelta vale subito.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import SourceIcon from "../components/SourceIcon.svelte";
  import { describeFilter, filterGroups, tallyText } from "../lib/filters.js";
  import { sourceColor } from "../lib/format.js";
  import {
    allPresets, changeFilter, closeSheet, currentPreset, data, deletePreset, foldersById, keyState, markAllRead,
    savePreset, savePrefs, session, setKey, stream, ui,
  } from "../lib/store.svelte.js";

  let name = $state("");
  let saveBox = $state();
  const groups = $derived(filterGroups(data));
  const cur = $derived(currentPreset(stream.filter));
  const mine = $derived(session.user?.prefs?.presets || []);
  const start = $derived(session.user?.prefs?.start_preset || "perte");
  // Le fonti sono tante: si mostrano solo se se ne apre l'elenco (o se una è già nel filtro).
  let showSources = $state(false);

  $effect(() => {
    if (ui.sheet === "filters" && ui.sheetArg === "save") setTimeout(() => saveBox?.scrollIntoView({ block: "center", behavior: "smooth" }), 320);
  });

  function setScope(scope) {
    changeFilter({ ...$state.snapshot(stream.filter), scope });
  }
  function toggleUnread() {
    changeFilter({ ...$state.snapshot(stream.filter), unread: !stream.filter.unread });
  }
  async function save(e) {
    e.preventDefault();
    if (await savePreset(name)) name = "";
  }
  const STATES = [["exc", "minus", "Nascondi"], ["", "dot", "Nessun filtro"], ["inc", "check", "Solo questi"]];
</script>

<Sheet name="filters" title="Filtri">
  <div class="filters">
    <div class="set-label">Mostra</div>
    <div class="set-group">
      <div class="set-row"><span>Notizie</span>
        <div class="segmented" style="--cols:2" role="group" aria-label="Notizie">
          <button type="button" aria-pressed={stream.filter.scope === "perte"} onclick={() => setScope("perte")}>Per te</button>
          <button type="button" aria-pressed={stream.filter.scope === "tutte"} onclick={() => setScope("tutte")}>Tutte</button>
        </div>
      </div>
      <div class="set-row"><span>Solo da leggere</span>
        <button type="button" class="switch" role="switch" aria-checked={stream.filter.unread} aria-label="Solo da leggere" onclick={toggleUnread}></button>
      </div>
    </div>

    {#each groups as group (group.id)}
      {#if group.id !== "fonti" || showSources || group.items.some((i) => keyState(i.key))}
        <div class="set-label">{group.title}</div>
        <div class="set-group">
          {#each group.items as item (item.key)}
            {@const st = keyState(item.key)}
            <div class="set-row">
              <span class="filter-name">
                {#if item.source}<SourceIcon source={item.source} color={sourceColor(item.source, foldersById())} />
                {:else if item.color}<span class="dot" style="--topic-c:{item.color}"></span>
                {:else if item.icon}<Icon name={item.icon} />{/if}
                <span>{item.label}</span>
              </span>
              <div class="tri" role="radiogroup" aria-label={item.label}>
                {#each STATES as [value, icon, label]}
                  <button type="button" class:is-exc={value === "exc"} class:is-inc={value === "inc"} role="radio" aria-checked={st === value} aria-label="{label}: {item.label}" title={label} onclick={() => setKey(item.key, value)}><Icon name={icon} /></button>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <button type="button" class="link-row" onclick={() => (showSources = true)}><Icon name="rss" />Filtra per fonte</button>
      {/if}
    {/each}
    <p class="set-note">Con «–» le notizie spariscono, con «✓» restano solo quelle. Tra gli interessi inclusi ne basta uno. I filtri, esclusioni comprese, restano salvati anche quando chiudi l'app.</p>

    <div class="set-label">Preset</div>
    <div class="set-group" bind:this={saveBox}>
      {#if cur}
        <div class="set-row"><span>Stai usando «{cur.name}»<br /><small class="muted">Cambia un filtro per salvarne uno nuovo.</small></span></div>
      {:else}
        <form class="set-block" onsubmit={save}>
          <span class="label">Salva questi filtri: {describeFilter(stream.filter, data)}</span>
          <div class="preset-save">
            <input class="input" type="text" maxlength="24" placeholder="Nome, per esempio «Sera»" aria-label="Nome del preset" bind:value={name} />
            <button type="submit" class="btn-primary small" disabled={!name.trim()}>Salva</button>
          </div>
        </form>
      {/if}
      {#each mine as p (p.id)}
        <div class="set-row">
          <span>{p.name}<br /><small class="muted">{describeFilter(p.filter, data)}</small></span>
          <button type="button" class="icon-btn" aria-label="Elimina il preset {p.name}" title="Elimina" onclick={() => deletePreset(p.id)}><Icon name="trash" /></button>
        </div>
      {/each}
    </div>

    <div class="set-label">All'apertura del Notiziario</div>
    <div class="set-group">
      <div class="set-block">
        <div class="opt-chips" role="radiogroup" aria-label="Preset all'apertura">
          {#each [...allPresets().map((p) => [p.id, p.name]), ["last", "L'ultimo usato"]] as [id, label] (id)}
            <button type="button" class="chip" role="radio" aria-checked={start === id} onclick={() => savePrefs({ start_preset: id })}>{label}</button>
          {/each}
        </div>
      </div>
    </div>

    <div class="filter-actions">
      <button type="button" class="btn-secondary small" onclick={() => { markAllRead(); closeSheet(); }}><Icon name="checks" />Segna tutte come lette</button>
      <button type="button" class="btn-primary" onclick={closeSheet}>{stream.tally ? `Mostra ${tallyText(stream.tally).split(" · ")[0]}` : "Fatto"}</button>
    </div>
  </div>
</Sheet>
