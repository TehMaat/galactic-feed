<script>
  // Gestione dei tag delle fonti (#17): crea, rinomina, cambia colore, ordina, sceglie quali
  // chip mostrare nel Flusso, unisce due tag, elimina.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import { api } from "../lib/api.js";
  import { folderColor } from "../lib/format.js";
  import { data, loadCounts, loadSources, session, savePrefs, setFilter, stream, toast, ui } from "../lib/store.svelte.js";

  let open = $state(null);
  let newName = $state("");

  $effect(() => {
    if (ui.sheet === "tags") open = null;
  });

  async function request(path, options, message) {
    try {
      const r = await api(path, options);
      data.tags = r.tags;
      if (message) toast(message);
      await loadSources();
      loadCounts();
      return true;
    } catch (err) {
      toast(err.message);
      return false;
    }
  }

  const patch = (t, body, message) => request(`/tags/${t.id}`, { method: "PATCH", body }, message);

  function rename(t, value) {
    const name = value.trim();
    if (name && name !== t.name) patch(t, { name }, `Rinominato in #${name}`);
  }

  function move(t, delta) {
    const ids = data.tags.map((x) => x.id);
    const i = ids.indexOf(t.id);
    const j = i + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    request("/tags/order", { method: "PUT", body: { ids } });
  }

  async function merge(t, intoId) {
    const into = data.tags.find((x) => x.id === Number(intoId));
    if (!into || !confirm(`Unire #${t.name} a #${into.name}? Le fonti di #${t.name} prendono #${into.name}.`)) return;
    if (await request(`/tags/${t.id}/merge`, { method: "POST", body: { into: into.id } }, `#${t.name} unito a #${into.name}`)) {
      if (stream.tag === t.id) setFilter({ tag: null });
      open = null;
    }
  }

  async function remove(t) {
    if (!confirm(`Eliminare il tag #${t.name}? Le fonti restano, senza questo tag.`)) return;
    if (await request(`/tags/${t.id}`, { method: "DELETE" }, `#${t.name} eliminato`)) {
      if (stream.tag === t.id) setFilter({ tag: null });
      open = null;
    }
  }

  async function create(e) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    if (await request("/tags", { method: "POST", body: { name } }, `Tag #${name} creato: aggiungilo alle fonti dalla loro scheda`)) newName = "";
  }
</script>

<Sheet name="tags" title="Tag delle fonti">
  <p class="set-note top">Ogni fonte può avere più tag. Le chip dei tag accesi compaiono nel Flusso, nell'ordine di questa lista.</p>
  {#if data.tags.length}
    <div class="set-group">
      {#each data.tags as t, i (t.id)}
        <div class="preset">
          <div class="set-row">
            <button type="button" class="preset-name" aria-expanded={open === t.id} onclick={() => (open = open === t.id ? null : t.id)}>
              <b><span class="hash-c" style="--topic-c:{folderColor(t.color)}">#</span>{t.name}</b><small>{t.sources === 1 ? "1 fonte" : `${t.sources} fonti`}</small>
            </button>
            <button type="button" class="switch" role="switch" aria-checked={t.in_feed} aria-label="Mostra #{t.name} nel Flusso"
              onclick={() => patch(t, { in_feed: !t.in_feed }, t.in_feed ? `#${t.name} non è più nel Flusso` : `#${t.name} nel Flusso`)}></button>
          </div>
          {#if open === t.id}
            <div class="tag-edit">
              <input class="input" value={t.name} aria-label="Nome del tag" maxlength="30" onchange={(e) => rename(t, e.target.value)} />
              <div class="color-pick" role="group" aria-label="Colore di #{t.name}">
                {#each data.colors as c (c)}
                  <button type="button" style="--topic-c:{folderColor(c)}" aria-pressed={t.color === c} aria-label={c} onclick={() => patch(t, { color: c })}></button>
                {/each}
              </div>
              <div class="tags">
                <button type="button" class="tag" disabled={i === 0} onclick={() => move(t, -1)}>Su</button>
                <button type="button" class="tag" disabled={i === data.tags.length - 1} onclick={() => move(t, 1)}>Giù</button>
                {#if data.tags.length > 1}
                  <select class="input small-select" aria-label="Unisci #{t.name} a un altro tag" onchange={(e) => merge(t, e.target.value)}>
                    <option value="">Unisci con…</option>
                    {#each data.tags.filter((x) => x.id !== t.id) as o (o.id)}<option value={o.id}>#{o.name}</option>{/each}
                  </select>
                {/if}
              </div>
              <button type="button" class="link-row danger" onclick={() => remove(t)}><Icon name="trash" />Elimina il tag</button>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {:else}
    <p class="hint">Ancora nessun tag. Li propone l'app quando aggiungi una fonte, oppure li scegli tu nella scheda di ogni fonte.</p>
  {/if}
  <form class="add-inline mt" onsubmit={create}>
    <input bind:value={newName} placeholder="Nuovo tag" autocomplete="off" aria-label="Nome del nuovo tag" maxlength="30" />
    <button type="submit">Crea</button>
  </form>
  <div class="set-group mt">
    <div class="set-row"><span>Proponi i tag delle fonti nuove</span>
      <button type="button" class="switch" role="switch" aria-checked={session.user?.prefs?.auto_tags !== false} aria-label="Proponi i tag delle fonti nuove"
        onclick={() => savePrefs({ auto_tags: session.user?.prefs?.auto_tags === false })}></button>
    </div>
  </div>
  <p class="set-note">L'app guarda i titoli e le categorie degli articoli recenti e propone fino a tre tag. Le tue modifiche non vengono mai annullate.</p>
</Sheet>
