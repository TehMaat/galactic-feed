<script>
  // Dettagli di una fonte: stato, errori, nome, cartella, intervallo; aggiorna o smetti di seguire.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import SourceIcon from "../components/SourceIcon.svelte";
  import { api } from "../lib/api.js";
  import { COUNTRIES, KIND_LABEL, countryName, flag, folderColor, intervalLabel, shortUrl, since, sourceColor, timeAgoLong } from "../lib/format.js";
  import { ask, closeSheet, data, foldersById, loadAll, loadCounts, loadSources, patchSourceInLists, showSource, toast, ui } from "../lib/store.svelte.js";

  let source = $state(null);
  let title = $state("");
  let busy = $state(false);
  let iconBusy = $state(false);
  let customOpen = $state(false);
  let customUrl = $state("");
  let customError = $state("");
  let newTag = $state("");
  let tagBusy = $state(false);

  $effect(() => {
    if (ui.sheet === "source" && ui.sheetArg) {
      // Si legge solo la copia, non «source»: altrimenti ogni aggiornamento della scheda
      // (tag, icona, nome) farebbe ripartire questo effetto e la riporterebbe ai dati iniziali.
      const copy = { ...ui.sheetArg };
      source = copy;
      title = copy.custom_title || "";
      customOpen = false;
      customUrl = copy.icon_custom || "";
      customError = "";
    }
  });

  // ---- Tag (#17) ----
  const otherTags = $derived(data.tags.filter((t) => !source?.tags?.some((x) => x.id === t.id)));

  async function setTags(names, message) {
    tagBusy = true;
    try {
      const r = await api(`/sources/${source.id}/tags`, { method: "PUT", body: { tags: names } });
      source = r.source;
      await loadSources();
      loadCounts();
      if (message) toast(message);
    } catch (err) {
      toast(err.message);
    } finally {
      tagBusy = false;
    }
  }

  function addTag(e) {
    e?.preventDefault?.();
    const name = newTag.trim();
    if (!name) return;
    newTag = "";
    if (source.tags.some((t) => t.name.toLowerCase() === name.toLowerCase())) return;
    setTags([...source.tags.map((t) => t.name), name], `Tag #${name} aggiunto`);
  }

  function removeTag(tag) {
    setTags(source.tags.filter((t) => t.id !== tag.id).map((t) => t.name), `Tag #${tag.name} tolto`);
  }

  async function suggestTags() {
    tagBusy = true;
    try {
      const r = await api(`/sources/${source.id}/tags/suggest`, { method: "POST" });
      source = r.source;
      await loadSources();
      toast(r.added.length ? `Proposti: ${r.added.map((n) => "#" + n).join(", ")}` : "Nessun tag nuovo da proporre");
    } catch (err) {
      toast(err.message);
    } finally {
      tagBusy = false;
    }
  }

  // ---- Nazione (#20) ----
  const LANGUAGES = { it: "italiano", en: "inglese", fr: "francese", de: "tedesco", es: "spagnolo", pt: "portoghese", nl: "olandese" };
  const countryChoices = $derived(source?.country && !COUNTRIES.includes(source.country) ? [source.country, ...COUNTRIES] : COUNTRIES);
  const countryValue = $derived(source ? (source.country_origin === "user" ? (source.country ?? "") : "__auto") : "__auto");

  function setCountry(value) {
    const country = value === "__auto" ? null : value;
    const label = country === null ? "Nazione automatica" : country === "" ? "Nessuna nazione" : `Nazione: ${countryName(country)}`;
    patch({ country }, label);
  }

  // ---- Icona ----
  async function iconRequest(path, options, message) {
    iconBusy = true;
    try {
      const r = await api(path, options);
      source = r.source;
      patchSourceInLists(source.id, { icon: source.icon });
      await loadSources();
      toast(typeof message === "function" ? message(r) : message);
      return true;
    } catch (err) {
      if (customOpen) customError = err.message;
      else toast(err.message);
      return false;
    } finally {
      iconBusy = false;
    }
  }

  function setIconMode(mode) {
    if (mode === "custom") {
      customOpen = true;
      return;
    }
    customOpen = false;
    iconRequest(`/sources/${source.id}/icon`, { method: "PUT", body: { mode } }, mode === "none" ? "Ora mostra le iniziali" : "Icona automatica");
  }

  async function saveCustom(e) {
    e.preventDefault();
    customError = "";
    if (!customUrl.trim()) return;
    const ok = await iconRequest(`/sources/${source.id}/icon`, { method: "PUT", body: { mode: "custom", url: customUrl.trim() } }, "Icona cambiata");
    if (ok) customOpen = false;
  }

  function refreshIcon() {
    customOpen = false;
    iconRequest(`/sources/${source.id}/icon/refresh`, { method: "POST" }, (r) =>
      r.found ? (source.icon_mode === "auto" ? "Icona aggiornata" : "Icona automatica aggiornata: resta quella che hai scelto") : "Nessuna icona trovata sul sito",
    );
  }

  const iconNote = $derived.by(() => {
    if (!source) return "";
    if (source.icon_mode === "none") return "Al posto dell'icona ci sono le iniziali.";
    if (source.icon_mode === "custom") return "Immagine scelta da te: l'aggiornamento automatico non la cambia.";
    if (source.icon_auto) return "Trovata in automatico sul sito. Si ricontrolla ogni settimana.";
    return source.icon_checked_at ? "Sul sito non ho trovato un'icona: restano le iniziali." : "La cerco sul sito tra pochi secondi.";
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
    if (!(await ask("Gli articoli salvati restano nei Salvati.", { title: `Smettere di seguire «${source.title}»?`, action: "Smetti di seguire" }))) return;
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
        <span class="label" id="tags-label">Tag</span>
        {#if source.tags.length}
          <div class="tags" role="group" aria-labelledby="tags-label">
            {#each source.tags as t (t.id)}
              <button type="button" class="tag" style="--topic-c:{folderColor(t.color)}" aria-label="Togli il tag {t.name}" disabled={tagBusy} onclick={() => removeTag(t)}>
                <span class="dot" style="--topic-c:{folderColor(t.color)}"></span>{t.name}{#if t.origin === "auto"}<span class="auto">auto</span>{/if}<Icon name="close" />
              </button>
            {/each}
          </div>
        {/if}
        {#if otherTags.length}
          <div class="tags">
            {#each otherTags.slice(0, 10) as t (t.id)}
              <button type="button" class="tag" disabled={tagBusy} onclick={() => setTags([...source.tags.map((x) => x.name), t.name], `Tag #${t.name} aggiunto`)}><Icon name="plus" />{t.name}</button>
            {/each}
          </div>
        {/if}
        <form class="add-inline" onsubmit={addTag}>
          <input bind:value={newTag} placeholder="Nuovo tag" autocomplete="off" aria-label="Nuovo tag per questa fonte" maxlength="30" />
          <button type="submit" disabled={tagBusy}>Aggiungi</button>
        </form>
        <p class="hint">{source.tags.some((t) => t.origin === "auto") ? "I tag «auto» li ha proposti l'app: tienili o toglili, non torneranno." : "Una fonte può avere più tag: li usi come filtri nel Flusso e per le Edizioni."}
          <button type="button" class="link-btn" disabled={tagBusy} onclick={suggestTags}>Proponi i tag</button></p>
      </div>

      <div class="field">
        <label for="src-country">Nazione</label>
        <select class="input" id="src-country" value={countryValue} onchange={(e) => setCountry(e.target.value)}>
          <option value="__auto">{(() => { const auto = source.country_admin ?? source.country_auto; return auto ? `${flag(auto)} ${countryName(auto)} (${source.country_admin != null ? "scelta dall'amministratore" : "proposta"})` : "Automatica: non riconosciuta"; })()}</option>
          {#each countryChoices as c (c)}<option value={c}>{flag(c)} {countryName(c)}</option>{/each}
          <option value="">Nessuna nazione</option>
        </select>
        <p class="hint">{source.language ? `Lingua: ${LANGUAGES[source.language] || source.language}. ` : ""}Serve per filtrare il Flusso e per le Edizioni (per esempio «Politica · Italia»). La tua scelta vale solo per te.</p>
      </div>

      <div class="field">
        <span class="label" id="icon-label">Icona</span>
        <div class="icon-preview">
          <SourceIcon {source} color={sourceColor(source, foldersById())} cls="src-av" />
          <p class="hint">{iconNote}</p>
        </div>
        <div class="tags" role="group" aria-labelledby="icon-label">
          <button type="button" class="tag" aria-pressed={source.icon_mode === "auto" && !customOpen} disabled={iconBusy} onclick={() => setIconMode("auto")}>Automatica</button>
          <button type="button" class="tag" aria-pressed={source.icon_mode === "custom" || customOpen} disabled={iconBusy} onclick={() => setIconMode("custom")}>Un'altra immagine</button>
          <button type="button" class="tag" aria-pressed={source.icon_mode === "none" && !customOpen} disabled={iconBusy} onclick={() => setIconMode("none")}>Iniziali</button>
        </div>
        {#if customOpen}
          <form class="form-stack" onsubmit={saveCustom}>
            <input class="input" type="url" inputmode="url" aria-label="Indirizzo dell'immagine" placeholder="https://esempio.it/logo.png" bind:value={customUrl} autocapitalize="off" spellcheck="false" />
            {#if customError}<p class="form-error" role="alert">{customError}</p>{/if}
            <button type="submit" class="btn-secondary" disabled={iconBusy || !customUrl.trim()}><Icon name="check" />{iconBusy ? "Controllo l'immagine…" : "Usa questa immagine"}</button>
          </form>
        {/if}
        <button type="button" class="btn-secondary" onclick={refreshIcon} disabled={iconBusy}><Icon name="refresh" />{iconBusy && !customOpen ? "Cerco l'icona…" : "Aggiorna icona"}</button>
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
