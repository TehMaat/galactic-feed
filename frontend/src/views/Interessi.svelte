<script>
  import Icon from "../components/Icon.svelte";
  import { api } from "../lib/api.js";
  import { data, loadCounts, loadStream, savePrefs, session, toast } from "../lib/store.svelte.js";

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
      <button type="button" aria-pressed="true">Parole chiave</button>
      <button type="button" aria-pressed="false" disabled title="Nella prossima versione">AI</button>
      <button type="button" aria-pressed="false" disabled title="Nella prossima versione">Entrambi</button>
    </div>
    <p class="hint">Un articolo è «per te» se il titolo, l'estratto o le categorie contengono un tuo interesse. La scelta con l'AI arriva nella prossima versione.</p>
  </section>

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
    <div class="rule is-later">
      <div><div class="rule-title">Riassunto automatico</div><div class="rule-sub">Tre punti in cima agli articoli lunghi, scritti dall'AI. Nella prossima versione.</div></div>
      <button type="button" class="switch" role="switch" aria-checked="false" aria-label="Riassunto automatico" disabled></button>
    </div>
  </section>
</section>
