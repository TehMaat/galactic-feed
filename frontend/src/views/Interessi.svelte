<script>
  import Icon from "../components/Icon.svelte";
  import { api } from "../lib/api.js";
  import { ask, data, loadCounts, loadStream, savePrefs, session, toast } from "../lib/store.svelte.js";

  let { active } = $props();
  let newKeyword = $state("");
  let newMuted = $state("");
  const LEVEL = { alta: "alta", media: "media", spento: "spento" };
  const NEXT = { alta: "media", media: "spento", spento: "alta" };

  async function apply(promise, message) {
    try {
      data.interests = await promise;
      if (message) toast(message);
      // Le regole cambiano cosa compare nel Flusso: si ricarica tutto.
      const [p] = await Promise.all([api("/interests/preview"), loadStream(true), loadCounts()]);
      data.preview = p;
    } catch (err) {
      toast(err.message);
    }
  }

  function cycle(k) {
    const level = NEXT[k.level];
    k.level = level;
    apply(api(`/interests/keywords/${k.id}`, { method: "PATCH", body: { level } }), `${k.keyword}: priorità ${LEVEL[level]}`);
  }

  function removeKeyword(k) {
    apply(api(`/interests/keywords/${k.id}`, { method: "DELETE" }), `«${k.keyword}» tolto dagli interessi`);
  }

  function addKeyword(e) {
    e.preventDefault();
    const value = newKeyword.trim();
    if (!value) return;
    newKeyword = "";
    apply(api("/interests/keywords", { method: "POST", body: { keyword: value } }), `${value}: aggiunto agli interessi`);
  }

  function addMuted(e) {
    e.preventDefault();
    const value = newMuted.trim();
    if (!value) return;
    newMuted = "";
    apply(api("/interests/muted", { method: "POST", body: { word: value } }), `«${value}» silenziata`);
  }

  function unmute(w) {
    apply(api(`/interests/muted/${w.id}`, { method: "DELETE" }), `«${w.word}» non è più silenziata`);
  }

  // ---- Gruppi di parole (#16): i propri e quelli pronti, accesi come interesse o per silenziare ----
  const GROUP_MODES = [["off", "Spento"], ["interest", "Interesse"], ["mute", "Silenzia"]];
  let openGroup = $state(null); // chiave del gruppo aperto: «g12» (proprio) o «p3» (pronto)
  let newWord = $state("");
  let newGroup = $state("");
  const groupRows = $derived([
    ...(data.interests.groups || []).map((g) => ({ ...g, key: "g" + g.id, preset: false })),
    ...(data.interests.presets || []).map((p) => ({ ...p, key: "p" + p.id, preset: true, mode: "off", level: "media" })),
  ]);
  const activeGroups = $derived((data.interests.groups || []).filter((g) => g.mode !== "off").length);

  function preview(words) {
    const shown = words.slice(0, 5).join(", ");
    return words.length > 5 ? `${shown}…` : shown || "nessuna parola";
  }

  async function groupChange(g, changes, message) {
    // Un gruppo pronto si prende (copia personale) alla prima modifica.
    const promise = g.preset
      ? api("/groups", { method: "POST", body: { preset_id: g.id, ...changes } })
      : api(`/groups/${g.id}`, { method: "PATCH", body: changes });
    try {
      const r = await promise;
      data.interests.groups = r.groups;
      data.interests.presets = r.presets;
      if (g.preset) {
        const taken = r.groups.find((x) => x.preset_id === g.id);
        if (taken && openGroup === g.key) openGroup = "g" + taken.id;
      }
      if (message) toast(message);
      if ("mode" in changes || g.mode !== "off") await refreshLists();
    } catch (err) {
      toast(err.message);
    }
  }

  function setGroupMode(g, mode) {
    if (mode === g.mode) return;
    const label = mode === "interest" ? "acceso come interesse" : mode === "mute" ? "silenzia i suoi articoli" : "spento";
    groupChange(g, { mode }, `${g.name}: ${label}`);
  }

  function addGroupWord(e, g) {
    e.preventDefault();
    const word = newWord.trim();
    if (!word) return;
    newWord = "";
    groupChange(g, { words: [...g.words, word] }, `«${word}» aggiunta a ${g.name}`);
  }

  function removeGroupWord(g, word) {
    groupChange(g, { words: g.words.filter((w) => w !== word) }, `«${word}» tolta da ${g.name}`);
  }

  async function deleteGroup(g) {
    if (!(await ask(g.preset_id ? `Tornerà tra i gruppi pronti con le parole originali.` : `Le sue parole non varranno più come interessi o per silenziare.`, { title: g.preset_id ? `Togliere «${g.name}»?` : `Eliminare il gruppo «${g.name}»?`, action: g.preset_id ? "Togli" : "Elimina" }))) return;
    try {
      const r = await api(`/groups/${g.id}`, { method: "DELETE" });
      data.interests.groups = r.groups;
      data.interests.presets = r.presets;
      openGroup = null;
      toast(`${g.name} tolto`);
      await refreshLists();
    } catch (err) {
      toast(err.message);
    }
  }

  async function createGroup(e) {
    e.preventDefault();
    const name = newGroup.trim();
    if (!name) return;
    try {
      const r = await api("/groups", { method: "POST", body: { name, words: [] } });
      data.interests.groups = r.groups;
      data.interests.presets = r.presets;
      newGroup = "";
      const created = r.groups.find((x) => x.name.toLowerCase() === name.toLowerCase());
      if (created) openGroup = "g" + created.id;
      toast(`Gruppo «${name}» creato: aggiungi le sue parole`);
    } catch (err) {
      toast(err.message);
    }
  }

  const MODES = [["parole", "Parole chiave"], ["ai", "AI"], ["entrambi", "Entrambi"]];
  const HINTS = {
    parole: "Un articolo è «per te» se il titolo, l'estratto o le categorie contengono un tuo interesse.",
    ai: "Un modello AI legge titolo e inizio di ogni articolo e lo confronta con la tua descrizione.",
    entrambi: "Prima le parole chiave, poi l'AI recupera gli articoli pertinenti che non le contengono.",
  };
  const aiOn = $derived(!!data.interests.ai?.enabled);
  const mode = $derived(session.user?.prefs?.ai_mode || "parole");
  let aiText = $state(session.user?.prefs?.ai_text || "");

  async function refreshLists() {
    const [p] = await Promise.all([api("/interests/preview"), loadStream(true), loadCounts()]);
    data.preview = p;
  }

  async function setMode(k) {
    if (k === mode) return;
    if (await savePrefs({ ai_mode: k })) {
      toast(k === "parole" ? "Solo parole chiave" : k === "ai" ? "Notizie scelte dall'AI" : "Parole chiave e AI");
      refreshLists();
      if (k !== "parole") setTimeout(refreshLists, 8000);
    }
  }

  async function saveText() {
    if (await savePrefs({ ai_text: aiText.trim() })) {
      toast("Descrizione salvata: l'AI rivaluta le notizie recenti");
      refreshLists();
      // L'AI lavora sul server in sottofondo: gli elenchi si aggiornano di nuovo tra poco.
      setTimeout(refreshLists, 8000);
      setTimeout(refreshLists, 25000);
    }
  }

  async function toggleDedupe() {
    await savePrefs({ dedupe: !session.user.prefs.dedupe });
    await Promise.all([loadStream(true), loadCounts()]);
  }
</script>

<section class="view" class:is-entering={active} hidden={!active} aria-label="Interessi">
  <header class="large-title">
    <div><h2>Interessi</h2><p class="subtitle">Quello che corrisponde finisce in «Per te». Il resto resta nel Flusso.</p></div>
  </header>

  {#if data.preview}
    <div class="preview">
      <b>{data.preview.matching}</b>
      <span>{data.preview.matching === 1 ? "notizia" : "notizie"} delle ultime 24 ore {data.preview.matching === 1 ? "è" : "sono"} per te con queste regole, su {data.preview.total} arrivate.</span>
    </div>
  {/if}

  <section class="panel">
    <h3>Come scegliere le notizie</h3>
    <div class="segmented" style="--cols:3" role="group" aria-label="Metodo di selezione">
      {#each MODES as [k, label]}
        <button type="button" aria-pressed={mode === k} disabled={k !== "parole" && !aiOn && mode === "parole"} onclick={() => setMode(k)}>{label}</button>
      {/each}
    </div>
    <p class="hint">{HINTS[mode]}{#if !aiOn} {session.user?.is_admin ? "Per usare l'AI, configurala in Impostazioni → AI." : "Per usare l'AI serve che l'amministratore la configuri."}{/if}</p>
  </section>

  {#if mode !== "parole"}
    <section class="panel">
      <h3>Descrivi cosa ti interessa <span class="count">per l'AI</span></h3>
      <textarea class="textarea" rows="4" maxlength="1500" aria-label="Descrizione degli interessi per l'AI" bind:value={aiText}
        placeholder="Per esempio: esplorazione spaziale e astronomia, soprattutto le missioni europee; self-hosting e Raspberry Pi. Niente gossip né calcio."></textarea>
      <p class="hint">Scrivi come lo diresti a un amico. L'AI valuta gli articoli delle ultime 48 ore e poi quelli nuovi, man mano che arrivano.</p>
      {#if aiText.trim() !== (session.user?.prefs?.ai_text || "").trim()}
        <button type="button" class="btn-secondary small" onclick={saveText}><Icon name="check" />Salva la descrizione</button>
      {/if}
    </section>
  {/if}

  <section class="panel">
    <h3>Parole chiave <span class="count">tocca per la priorità</span></h3>
    {#if data.interests.keywords.length}
      <div class="tags">
        {#each data.interests.keywords as k (k.id)}
          <span class="tag-pair" data-level={k.level === "spento" ? "off" : k.level}>
            <button type="button" class="tag" data-level={k.level === "spento" ? "off" : k.level} onclick={() => cycle(k)} aria-label="{k.keyword}, priorità {LEVEL[k.level]}: tocca per cambiarla">
              {k.keyword}<span class="lvl">{LEVEL[k.level]}</span>
            </button>
            <button type="button" class="tag-x" aria-label="Togli {k.keyword}" onclick={() => removeKeyword(k)}><Icon name="close" /></button>
          </span>
        {/each}
      </div>
    {:else}
      <p class="hint">Aggiungi le parole e gli argomenti che ti interessano. Si riconoscono anche singolare e plurale: «razzo» trova «razzi».</p>
    {/if}
    <form class="add-inline" onsubmit={addKeyword}>
      <input bind:value={newKeyword} placeholder="Parola o argomento" autocomplete="off" aria-label="Nuovo interesse" maxlength="60" />
      <button type="submit">Aggiungi</button>
    </form>
  </section>

  <section class="panel">
    <h3>Gruppi di parole <span class="count">{activeGroups ? `${activeGroups} accesi` : "pronti da accendere"}</span></h3>
    <p class="hint">Un gruppo raccoglie le parole di un argomento. Accendilo come interesse o per silenziare i suoi articoli; tocca il nome per vederne e cambiarne le parole.</p>
    <div class="wgroups">
      {#each groupRows as g (g.key)}
        <div class="wg" data-mode={g.mode}>
          <div class="wg-row">
            <button type="button" class="wg-name" aria-expanded={openGroup === g.key} onclick={() => (openGroup = openGroup === g.key ? null : g.key)}>
              <b>{g.name}</b><small>{preview(g.words)}</small>
            </button>
            <div class="segmented wg-mode" style="--cols:3" role="group" aria-label="Gruppo {g.name}">
              {#each GROUP_MODES as [k, label]}
                <button type="button" aria-pressed={g.mode === k} onclick={() => setGroupMode(g, k)}>{label}</button>
              {/each}
            </div>
          </div>
          {#if openGroup === g.key}
            <div class="wg-body">
              <div class="tags">
                {#each g.words as w (w)}
                  <button type="button" class="tag" aria-label="Togli {w} da {g.name}" onclick={() => removeGroupWord(g, w)}>{w}<Icon name="close" /></button>
                {/each}
              </div>
              <form class="add-inline" onsubmit={(e) => addGroupWord(e, g)}>
                <input bind:value={newWord} placeholder="Parola da aggiungere" autocomplete="off" aria-label="Nuova parola per {g.name}" maxlength="60" />
                <button type="submit">Aggiungi</button>
              </form>
              {#if g.mode === "interest"}
                <div class="wg-level"><span>Priorità</span>
                  <div class="segmented" style="--cols:2" role="group" aria-label="Priorità di {g.name}">
                    <button type="button" aria-pressed={g.level === "alta"} onclick={() => groupChange(g, { level: "alta" }, `${g.name}: priorità alta`)}>Alta</button>
                    <button type="button" aria-pressed={g.level === "media"} onclick={() => groupChange(g, { level: "media" }, `${g.name}: priorità media`)}>Media</button>
                  </div>
                </div>
              {/if}
              {#if !g.preset}
                <button type="button" class="link-row danger" onclick={() => deleteGroup(g)}><Icon name="trash" />{g.preset_id ? "Togli e torna al gruppo pronto" : "Elimina il gruppo"}</button>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
    <form class="add-inline" onsubmit={createGroup}>
      <input bind:value={newGroup} placeholder="Nome di un gruppo nuovo" autocomplete="off" aria-label="Nome del nuovo gruppo" maxlength="40" />
      <button type="submit">Crea</button>
    </form>
  </section>

  <section class="panel">
    <h3>Silenzia</h3>
    <p class="hint">Gli articoli che contengono queste parole spariscono dal Flusso. Puoi sempre mostrarli con un tocco.</p>
    {#if data.interests.muted.length}
      <div class="tags">
        {#each data.interests.muted as w (w.id)}
          <button type="button" class="tag" onclick={() => unmute(w)} aria-label="Smetti di silenziare {w.word}">{w.word}<Icon name="close" /></button>
        {/each}
      </div>
    {/if}
    <form class="add-inline" onsubmit={addMuted}>
      <input bind:value={newMuted} placeholder="Parola da silenziare" autocomplete="off" aria-label="Nuova parola da silenziare" maxlength="60" />
      <button type="submit">Aggiungi</button>
    </form>
  </section>

  <section class="panel">
    <h3>Regole</h3>
    <div class="rule">
      <div><div class="rule-title">Unisci i doppioni</div><div class="rule-sub">La stessa notizia da più fonti compare una volta sola.</div></div>
      <button type="button" class="switch" role="switch" aria-checked={!!session.user?.prefs?.dedupe} aria-label="Unisci i doppioni" onclick={toggleDedupe}></button>
    </div>
    <div class="rule" class:is-later={!aiOn}>
      <div><div class="rule-title">Riassunto automatico</div><div class="rule-sub">Tre punti in cima agli articoli lunghi, scritti dall'AI.{#if !aiOn} Serve l'AI configurata.{/if}</div></div>
      <button type="button" class="switch" role="switch" aria-checked={aiOn && !!session.user?.prefs?.summaries} aria-label="Riassunto automatico" disabled={!aiOn}
        onclick={() => savePrefs({ summaries: !session.user.prefs.summaries })}></button>
    </div>
  </section>
</section>
