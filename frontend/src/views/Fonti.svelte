<script>
  import Icon from "../components/Icon.svelte";
  import { api } from "../lib/api.js";
  import { KIND_LABEL, initials, intervalLabel, since, sourceColor } from "../lib/format.js";
  import { data, foldersById, loadAll, openSheet, toast } from "../lib/store.svelte.js";

  let { active } = $props();
  let fileInput = $state();
  let importing = $state(false);

  const groups = $derived.by(() => {
    const out = data.folders.map((f) => ({ folder: f, sources: data.sources.filter((s) => s.folder_id === f.id) }));
    const loose = data.sources.filter((s) => s.folder_id === null || !foldersById()[s.folder_id]);
    if (loose.length) out.push({ folder: null, sources: loose });
    return out;
  });
  const broken = $derived(data.sources.filter((s) => s.status === "err").length);

  function subtitle(s) {
    if (s.status === "pending") return "In attesa del primo controllo";
    if (s.error) return `${s.error.replace(/\.$/, "")} · ${since(s.error_since)}`;
    return `${KIND_LABEL[s.kind]} · ogni ${intervalLabel(s.interval_min)}`;
  }

  function dot(s) {
    return s.status === "err" ? "err" : s.status === "warn" || s.status === "pending" ? "warn" : "";
  }

  async function importOpml(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    importing = true;
    const form = new FormData();
    form.append("file", file);
    try {
      const r = await api("/opml/import", { method: "POST", form });
      const parts = [r.added === 1 ? "1 fonte aggiunta" : `${r.added} fonti aggiunte`];
      if (r.existing) parts.push(`${r.existing} già presenti`);
      if (r.invalid) parts.push(`${r.invalid} non valide`);
      toast(parts.join(" · ") + (r.added ? ". Gli articoli arrivano tra poco." : ""));
      await loadAll();
    } catch (err) {
      toast(err.message);
    } finally {
      importing = false;
    }
  }

  function key(e, fn) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fn();
    }
  }
</script>

<section class="view" class:is-entering={active} hidden={!active} aria-label="Fonti">
  <header class="large-title">
    <div>
      <h2>Fonti</h2>
      <p class="subtitle">
        {data.sources.length === 1 ? "1 fonte" : `${data.sources.length} fonti`}{data.folders.length ? ` in ${data.folders.length === 1 ? "1 cartella" : `${data.folders.length} cartelle`}` : ""} · solo tue
      </p>
    </div>
    <button type="button" class="pill-btn" onclick={() => openSheet("add")}><Icon name="plus" />Aggiungi</button>
  </header>

  {#if broken}
    <div class="banner" role="status">
      <Icon name="alert" />
      <p><b>{broken === 1 ? "1 fonte non funziona" : `${broken} fonti non funzionano`}.</b> Tocca la fonte per vedere il motivo e cosa puoi fare.</p>
    </div>
  {/if}

  {#if data.loaded && data.sources.length === 0}
    <div class="empty">
      <Icon name="rss" />
      <h3>Ancora nessuna fonte</h3>
      <p>Incolla l'indirizzo di un sito o di un canale YouTube, oppure importa le fonti da un altro lettore.</p>
    </div>
  {/if}

  {#each groups as g (g.folder?.id ?? "none")}
    <div class="group-label">
      {#if g.folder}
        <button type="button" class="group-edit" onclick={() => openSheet("folder", g.folder)} aria-label="Modifica la cartella {g.folder.name}">
          <span class="dot" style="--topic-c:var(--c-{g.folder.color})"></span>{g.folder.name}
        </button>
      {:else}
        <span>Senza cartella</span>
      {/if}
      <span>{g.sources.reduce((n, s) => n + s.unread, 0)} non letti</span>
    </div>
    {#if g.sources.length}
      <div class="list">
        {#each g.sources as s (s.id)}
          <div class="src-row" role="button" tabindex="0" aria-label="Fonte {s.title}" onclick={() => openSheet("source", s)} onkeydown={(e) => key(e, () => openSheet("source", s))}>
            <span class="src-av" style="--src-c:{sourceColor(s, foldersById())}">{initials(s.title)}</span>
            <span class="src-text">
              <span class="src-name">{s.title}</span>
              <span class="src-sub"><span class="status-dot {dot(s)}"></span>{subtitle(s)}</span>
            </span>
            <span class="unread">{s.unread}</span>
          </div>
        {/each}
      </div>
    {:else}
      <p class="hint indent">Cartella vuota: scegli questa cartella quando aggiungi una fonte.</p>
    {/if}
  {/each}

  <div class="list mt">
    <button type="button" class="link-row" onclick={() => fileInput.click()} disabled={importing}>
      <Icon name="upload" />{importing ? "Importo le fonti…" : "Importa da un altro lettore (OPML)"}
    </button>
    {#if data.sources.length}
      <a class="link-row" href="/api/opml/export" download><Icon name="download" />Esporta le fonti (OPML)</a>
    {/if}
    <button type="button" class="link-row" onclick={() => openSheet("folder", null)}><Icon name="folder" />Nuova cartella</button>
  </div>
  <input bind:this={fileInput} type="file" accept=".opml,.xml,text/xml,text/x-opml,application/xml" hidden onchange={importOpml} />
</section>
