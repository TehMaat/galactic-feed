<script>
  // «Aggiungi una fonte»: dall'indirizzo di un sito o di un canale ai feed da seguire.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import { api } from "../lib/api.js";
  import { folderColor, frequency, pathOf, timeAgoLong } from "../lib/format.js";
  import { closeSheet, data, loadAll, toast, ui } from "../lib/store.svelte.js";

  const TYPES = {
    rss: { label: "Sito o feed", ph: "https://sito.it o l'indirizzo del feed", hint: "Incolla l'indirizzo di un sito: il server cerca da solo i feed RSS o Atom disponibili." },
    youtube: { label: "Canale YouTube", ph: "Link del canale o @nome", hint: "Ogni canale YouTube ha un feed pubblico con gli ultimi video: non serve nessun account." },
  };

  let type = $state("rss");
  let url = $state("");
  let searching = $state(false);
  let adding = $state(false);
  let error = $state("");
  let found = $state(null);
  let choice = $state(0);
  let folderId = $state(null);
  let newFolder = $state("");
  let creatingFolder = $state(false);

  $effect(() => {
    if (ui.sheet === "add") {
      found = null;
      error = "";
    }
  });

  function setType(t) {
    type = t;
    url = "";
    found = null;
    error = "";
  }

  async function search(e) {
    e.preventDefault();
    if (!url.trim()) return;
    searching = true;
    error = "";
    found = null;
    try {
      const r = await api("/sources/discover", { method: "POST", body: { url: url.trim() } });
      found = r.candidates;
      choice = Math.max(0, found.findIndex((c) => !c.already_followed));
    } catch (err) {
      error = err.message;
    } finally {
      searching = false;
    }
  }

  function sub(c) {
    const parts = [c.kind === "youtube" ? "feed pubblico del canale" : pathOf(c.url)];
    const f = frequency(c.per_week);
    if (f) parts.push(f);
    else if (c.last_published) parts.push(`ultimo ${timeAgoLong(c.last_published)}`);
    if (c.kind !== "youtube") parts.push(c.full_text ? "testo completo" : "solo estratto");
    if (c.already_followed) parts.push("già tra le tue fonti");
    return parts.join(" · ");
  }

  async function makeFolder(e) {
    e.preventDefault();
    const name = newFolder.trim();
    if (!name) return;
    try {
      const r = await api("/folders", { method: "POST", body: { name } });
      data.folders = [...data.folders, r.folder];
      folderId = r.folder.id;
      newFolder = "";
      creatingFolder = false;
    } catch (err) {
      toast(err.message);
    }
  }

  async function add() {
    const c = found?.[choice];
    if (!c || c.already_followed) return;
    adding = true;
    error = "";
    try {
      const r = await api("/sources", { method: "POST", body: { url: c.url, folder_id: folderId } });
      const folder = data.folders.find((f) => f.id === folderId);
      toast(`${r.source.title} aggiunta${folder ? " a " + folder.name : ""}`);
      closeSheet();
      url = "";
      found = null;
      await loadAll();
    } catch (err) {
      error = err.message;
    } finally {
      adding = false;
    }
  }
</script>

<Sheet name="add" title="Aggiungi una fonte">
  <div class="form-stack">
    <div class="segmented" role="group" aria-label="Tipo di fonte">
      {#each Object.entries(TYPES) as [k, t]}
        <button type="button" aria-pressed={type === k} onclick={() => setType(k)}>{t.label}</button>
      {/each}
    </div>
    <form class="form-stack" onsubmit={search}>
      <div class="field">
        <label for="add-url">Indirizzo</label>
        <input class="input" id="add-url" bind:value={url} placeholder={TYPES[type].ph} autocomplete="off" autocapitalize="off" spellcheck="false" inputmode="url" />
      </div>
      <p class="hint">{TYPES[type].hint}</p>
      <button type="submit" class="btn-secondary" disabled={searching || !url.trim()}><Icon name="search" />{searching ? "Cerco i feed…" : "Cerca feed"}</button>
    </form>

    {#if error}<p class="form-error" role="alert">{error}</p>{/if}

    {#if found}
      <div class="field">
        <span class="label">{found.length === 1 ? "Feed trovato" : "Feed trovati"}</span>
        <div class="found" role="radiogroup" aria-label="Feed trovati">
          {#each found as c, i}
            <button type="button" class="found-item" role="radio" aria-checked={choice === i} disabled={c.already_followed} onclick={() => (choice = i)}>
              <span class="radio"><Icon name="check" /></span>
              <span><span class="found-name">{c.title}</span><br /><span class="found-sub">{sub(c)}</span></span>
            </button>
          {/each}
        </div>
      </div>
      <div class="field">
        <span class="label">Cartella</span>
        <div class="tags">
          <button type="button" class="tag" aria-pressed={folderId === null} onclick={() => (folderId = null)}>Nessuna</button>
          {#each data.folders as f (f.id)}
            <button type="button" class="tag" aria-pressed={folderId === f.id} onclick={() => (folderId = f.id)}><span class="dot" style="--topic-c:{folderColor(f.color)}"></span>{f.name}</button>
          {/each}
          {#if !creatingFolder}
            <button type="button" class="tag" onclick={() => (creatingFolder = true)}><Icon name="plus" />Nuova</button>
          {/if}
        </div>
        {#if creatingFolder}
          <form class="add-inline" onsubmit={makeFolder}>
            <input bind:value={newFolder} placeholder="Nome della cartella" maxlength="40" aria-label="Nome della nuova cartella" />
            <button type="submit">Crea</button>
          </form>
        {/if}
      </div>
      <button type="button" class="btn-primary" onclick={add} disabled={adding || found[choice]?.already_followed}>
        <Icon name="plus" />{adding ? "Aggiungo…" : "Aggiungi fonte"}
      </button>
    {/if}
  </div>
</Sheet>
