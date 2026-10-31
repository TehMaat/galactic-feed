<script>
  // Nuova cartella, oppure modifica (nome, colore) ed eliminazione di una cartella esistente.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import { api } from "../lib/api.js";
  import { folderColor } from "../lib/format.js";
  import { closeSheet, data, loadAll, loadSources, toast, ui } from "../lib/store.svelte.js";

  const COLOR_NAMES = { indaco: "Indaco", blu: "Blu", verde: "Verde", viola: "Viola", rosa: "Rosa", ambra: "Ambra", azzurro: "Azzurro", grigio: "Grigio" };
  let folder = $state(null);
  let name = $state("");
  let color = $state(null);

  $effect(() => {
    if (ui.sheet === "folder") {
      folder = ui.sheetArg ? { ...ui.sheetArg } : null;
      name = folder?.name || "";
      color = folder?.color || null;
    }
  });

  async function save(e) {
    e.preventDefault();
    try {
      if (folder) {
        await api(`/folders/${folder.id}`, { method: "PATCH", body: { name, color } });
        toast("Cartella aggiornata");
      } else {
        await api("/folders", { method: "POST", body: { name, color } });
        toast(`Cartella ${name.trim()} creata`);
      }
      closeSheet();
      await loadSources();
    } catch (err) {
      toast(err.message);
    }
  }

  async function remove() {
    if (!confirm(`Eliminare la cartella «${folder.name}»? Le sue fonti restano, senza cartella.`)) return;
    try {
      await api(`/folders/${folder.id}`, { method: "DELETE" });
      toast("Cartella eliminata");
      closeSheet();
      await loadAll();
    } catch (err) {
      toast(err.message);
    }
  }
</script>

<Sheet name="folder" title={folder ? "Cartella" : "Nuova cartella"}>
  <form class="form-stack" onsubmit={save}>
    <div class="field">
      <label for="folder-name">Nome</label>
      <input class="input" id="folder-name" bind:value={name} maxlength="40" placeholder="Spazio, Tech, Italia…" />
    </div>
    <div class="field">
      <span class="label">Colore</span>
      <div class="tags">
        {#each data.colors as c}
          <button type="button" class="tag" aria-pressed={color === c} onclick={() => (color = c)}><span class="dot" style="--topic-c:{folderColor(c)}"></span>{COLOR_NAMES[c] || c}</button>
        {/each}
      </div>
    </div>
    <button type="submit" class="btn-primary" disabled={!name.trim()}><Icon name="check" />{folder ? "Salva" : "Crea la cartella"}</button>
    {#if folder}
      <button type="button" class="btn-secondary danger" onclick={remove}><Icon name="trash" />Elimina la cartella</button>
    {/if}
  </form>
</Sheet>
