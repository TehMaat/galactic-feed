<script>
  // Dettagli di una fonte: stato, errori, nome, cartella, intervallo; aggiorna o smetti di seguire.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import { api } from "../lib/api.js";
  import { KIND_LABEL, folderColor, intervalLabel, shortUrl, since, timeAgoLong } from "../lib/format.js";
  import { closeSheet, data, loadAll, loadCounts, loadSources, showSource, toast, ui } from "../lib/store.svelte.js";

  let source = $state(null);
  let title = $state("");
  let busy = $state(false);

  $effect(() => {
    if (ui.sheet === "source" && ui.sheetArg) {
      source = { ...ui.sheetArg };
      title = source.custom_title || "";
    }
  });

  async function patch(body, message) {
    try {
      const r = await api(`/sources/${source.id}`, { method: "PATCH", body });
      source = r.source;
      await loadSources();
      if (message) toast(message);
    } catch (err) {
      toast(err.message);
    }
  }

  function saveTitle(e) {
    e?.preventDefault?.();
    if ((title.trim() || "") === (source.custom_title || "")) return;
    patch({ title: title.trim() }, "Nome aggiornato");
  }

  async function refresh() {
    busy = true;
    try {
      const r = await api(`/sources/${source.id}/refresh`, { method: "POST" });
      source = r.source;
      toast(r.source.error ? r.source.error : r.new_articles ? `${r.new_articles} articoli nuovi` : "Nessun articolo nuovo");
      await Promise.all([loadSources(), loadCounts()]);
    } catch (err) {
      toast(err.message);
    } finally {
      busy = false;
    }
  }

  async function unfollow() {
    if (!confirm(`Smettere di seguire «${source.title}»? Gli articoli salvati restano nei Salvati.`)) return;
    try {
      await api(`/sources/${source.id}`, { method: "DELETE" });
      toast(`Non segui più ${source.title}`);
      closeSheet();
      await loadAll();
    } catch (err) {
      toast(err.message);
    }
  }

  const statusText = $derived.by(() => {
    if (!source) return "";
    if (source.status === "pending") return "Non ancora controllata: il primo controllo arriva entro un minuto.";
    if (source.error) return `${source.error} Il problema c'è ${since(source.error_since)}; il server riprova da solo, sempre meno spesso.`;
    return `Funziona. Ultimo controllo ${timeAgoLong(source.last_fetch_at)}.`;
  });
</script>

<Sheet name="source" title={source?.title || "Fonte"}>
  {#if source}
    <div class="form-stack">
      <div class="status-box" data-status={source.status}>
        <span class="status-dot {source.status === 'err' ? 'err' : source.status === 'ok' ? '' : 'warn'}"></span>
        <p>{statusText}</p>
      </div>

      <button type="button" class="btn-primary" onclick={() => showSource(source)}><Icon name="edition" />Mostra gli articoli</button>

      <form class="field" onsubmit={saveTitle}>
        <label for="src-title">Nome</label>
        <input class="input" id="src-title" bind:value={title} placeholder={source.feed_title || shortUrl(source.url)} onblur={saveTitle} maxlength="120" />
      </form>

      <div class="field">
        <span class="label">Cartella</span>
        <div class="tags">
          <button type="button" class="tag" aria-pressed={source.folder_id === null} onclick={() => patch({ folder_id: null }, "Fonte senza cartella")}>Nessuna</button>
          {#each data.folders as f (f.id)}
            <button type="button" class="tag" aria-pressed={source.folder_id === f.id} onclick={() => patch({ folder_id: f.id }, `Spostata in ${f.name}`)}>
              <span class="dot" style="--topic-c:{folderColor(f.color)}"></span>{f.name}
            </button>
          {/each}
        </div>
      </div>

      <div class="field">
        <label for="src-interval">Controlla ogni</label>
        <select class="input" id="src-interval" value={source.interval_min} onchange={(e) => patch({ interval_min: Number(e.target.value) }, `Controllo ogni ${intervalLabel(Number(e.target.value))}`)}>
          {#each data.intervals as m}<option value={m}>{intervalLabel(m)}</option>{/each}
        </select>
      </div>

      <div class="set-group">
        <div class="set-row"><span>Tipo</span><span class="val">{KIND_LABEL[source.kind]}</span></div>
        <div class="set-row"><span>Feed</span><span class="val ellipsis" title={source.url}>{shortUrl(source.url)}</span></div>
        {#if source.site_url}
          <a class="set-row link" href={source.site_url} target="_blank" rel="noopener noreferrer"><span>Sito</span><span class="val ellipsis">{shortUrl(source.site_url)} ↗</span></a>
        {/if}
        <div class="set-row"><span>Articoli</span><span class="val">{source.articles} · {source.unread} non letti</span></div>
      </div>

      <button type="button" class="btn-secondary" onclick={refresh} disabled={busy}><Icon name="refresh" />{busy ? "Controllo…" : "Controlla adesso"}</button>
      <button type="button" class="btn-secondary danger" onclick={unfollow}><Icon name="trash" />Smetti di seguire</button>
    </div>
  {/if}
</Sheet>
