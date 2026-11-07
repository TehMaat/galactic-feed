<script>
  // Un'Edizione (#18, #19): nome, quando esce, regole, quante notizie, notifica.
  // Ogni modifica si salva subito; l'anteprima dice quante notizie avrebbe adesso.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import { api } from "../lib/api.js";
  import { COUNTRIES, countryName, flag, folderColor, nextRun } from "../lib/format.js";
  import { ask, closeSheet, data, editionConfigs, setEditionConfigs, showEdition, switchTab, toast, ui } from "../lib/store.svelte.js";

  let config = $state(null);
  let preview = $state(null);
  let newTime = $state("07:30");
  let busy = $state(false);
  let previewTimer;

  const WEEKDAYS = [["L", "lunedì"], ["M", "martedì"], ["M", "mercoledì"], ["G", "giovedì"], ["V", "venerdì"], ["S", "sabato"], ["D", "domenica"]];
  const NTH = [[1, "Il primo"], [2, "Il secondo"], [3, "Il terzo"], [4, "Il quarto"], [-1, "L'ultimo"]];
  const PERIODS = [["auto", "Dall'uscita precedente"], ["day", "Ultimo giorno"], ["week", "Ultima settimana"], ["month", "Ultimo mese"]];
  const SIZES = [5, 10, 20, 30, 50, 80, 100];

  $effect(() => {
    if (ui.sheet === "edition-config" && ui.sheetArg) {
      const copy = JSON.parse(JSON.stringify(ui.sheetArg));
      config = copy;
      loadPreview(copy);
    }
  });

  // Nazioni da proporre: quelle delle proprie fonti, poi le altre più comuni.
  const countries = $derived.by(() => {
    const own = [...new Set(data.sources.map((s) => s.country).filter(Boolean))];
    return [...own, ...COUNTRIES.filter((c) => !own.includes(c))];
  });
  const groups = $derived(data.interests.groups || []);

  async function save(changes, message) {
    busy = true;
    try {
      const r = await api(`/edition-configs/${config.id}`, { method: "PATCH", body: changes });
      await setEditionConfigs(r);
      const fresh = r.configs.find((c) => c.id === config.id);
      if (fresh) config = fresh;
      if (message) toast(message);
      loadPreview(config);
    } catch (err) {
      toast(err.message);
    } finally {
      busy = false;
    }
  }

  function loadPreview(c) {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(async () => {
      try {
        preview = await api("/edition-configs/preview", {
          method: "POST",
          body: { rules: c.rules, schedule: c.schedule, max_items: c.max_items, period: c.period },
        });
      } catch {
        preview = null;
      }
    }, 150);
  }

  // ---- Pianificazione ----
  function setKind(kind) {
    if (kind === config.schedule.kind) return;
    const times = config.schedule.times;
    const sched = kind === "weekly" ? { kind, times, days: [0] } : kind === "monthly" ? { kind, times, day: 1 } : { kind, times };
    save({ schedule: sched }, kind === "daily" ? "Esce ogni giorno" : kind === "weekly" ? "Esce ogni settimana" : "Esce ogni mese");
  }

  function toggleDay(d) {
    const days = config.schedule.days || [];
    const next = days.includes(d) ? days.filter((x) => x !== d) : [...days, d].sort();
    if (!next.length) return toast("Serve almeno un giorno");
    save({ schedule: { ...config.schedule, days: next } });
  }

  function setMonthly(changes) {
    const { kind, times } = config.schedule;
    save({ schedule: { kind, times, ...changes } });
  }

  function addTime() {
    const times = config.schedule.times;
    if (!newTime || times.includes(newTime)) return;
    save({ schedule: { ...config.schedule, times: [...times, newTime] } }, `Nuovo orario: ${newTime}`);
  }

  function removeTime(t) {
    const times = config.schedule.times;
    if (times.length === 1) return toast("Serve almeno un orario");
    save({ schedule: { ...config.schedule, times: times.filter((x) => x !== t) } });
  }

  // ---- Regole ----
  function toggleRule(kind, value) {
    const list = config.rules[kind] || [];
    const next = list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
    save({ rules: { ...config.rules, [kind]: next } });
  }

  const ruleCount = $derived(config ? Object.values(config.rules).reduce((n, l) => n + l.length, 0) : 0);

  // ---- Azioni ----
  async function composeNow() {
    busy = true;
    try {
      await api("/editions", { method: "POST", body: { config_id: config.id } });
      closeSheet();
      switchTab("oggi");
      ui.oggiMode = "edizione";
      showEdition(config.id);
      toast(`«${config.name}» composta adesso`);
    } catch (err) {
      toast(err.message);
    } finally {
      busy = false;
    }
  }

  async function duplicate() {
    try {
      const r = await api(`/edition-configs/${config.id}/duplicate`, { method: "POST" });
      await setEditionConfigs(r);
      const copy = r.configs.at(-1);
      config = copy;
      loadPreview(copy);
      toast(`Copia creata, spenta: «${copy.name}»`);
    } catch (err) {
      toast(err.message);
    }
  }

  async function remove() {
    if (!(await ask("Si cancellano anche tutte le sue uscite. Per fermarla e basta, spegnila.", { title: `Eliminare «${config.name}»?` }))) return;
    try {
      const r = await api(`/edition-configs/${config.id}`, { method: "DELETE" });
      await setEditionConfigs(r);
      toast(`«${config.name}» eliminata`);
      closeSheet();
    } catch (err) {
      toast(err.message);
    }
  }
</script>

<Sheet name="edition-config" title={config?.name || "Edizione"}>
  {#if config}
    {@const s = config.schedule}
    <div class="form-stack">
      <div class="field">
        <label for="ed-name">Nome</label>
        <input class="input" id="ed-name" value={config.name} maxlength="40" onchange={(e) => e.target.value.trim() && save({ name: e.target.value.trim() }, "Nome aggiornato")} />
      </div>

      <div class="set-group">
        <div class="set-row"><span>Attiva</span>
          <button type="button" class="switch" role="switch" aria-checked={config.active} aria-label="Edizione attiva" disabled={busy}
            onclick={() => save({ active: !config.active }, config.active ? "Edizione spenta" : "Edizione accesa")}></button>
        </div>
        <div class="set-row"><span>Notifica quando è pronta</span>
          <button type="button" class="switch" role="switch" aria-checked={config.notify} aria-label="Notifica quando è pronta" disabled={busy}
            onclick={() => save({ notify: !config.notify })}></button>
        </div>
      </div>

      <div class="field">
        <span class="label">Quando esce</span>
        <div class="segmented" style="--cols:3" role="group" aria-label="Ricorrenza">
          {#each [["daily", "Ogni giorno"], ["weekly", "Ogni settimana"], ["monthly", "Ogni mese"]] as [k, l]}
            <button type="button" aria-pressed={s.kind === k} onclick={() => setKind(k)}>{l}</button>
          {/each}
        </div>
        {#if s.kind === "weekly"}
          <div class="weekdays" role="group" aria-label="Giorni della settimana">
            {#each WEEKDAYS as [short, long], d}
              <button type="button" class="day" aria-pressed={s.days.includes(d)} aria-label={long} title={long} onclick={() => toggleDay(d)}>{short}</button>
            {/each}
          </div>
        {:else if s.kind === "monthly"}
          <div class="segmented" style="--cols:2" role="group" aria-label="Tipo di giorno del mese">
            <button type="button" aria-pressed={s.nth === undefined} onclick={() => s.nth !== undefined && setMonthly({ day: 1 })}>Un giorno del mese</button>
            <button type="button" aria-pressed={s.nth !== undefined} onclick={() => s.nth === undefined && setMonthly({ nth: 1, weekday: 0 })}>Un giorno della settimana</button>
          </div>
          {#if s.nth === undefined}
            <select class="input" aria-label="Giorno del mese" value={s.day} onchange={(e) => setMonthly({ day: Number(e.target.value) })}>
              {#each Array.from({ length: 31 }, (_, i) => i + 1) as n}<option value={n}>Il giorno {n}{n > 28 ? " (o l'ultimo, nei mesi più corti)" : ""}</option>{/each}
              <option value={-1}>L'ultimo giorno del mese</option>
            </select>
          {:else}
            <div class="two-selects">
              <select class="input" aria-label="Quale" value={s.nth} onchange={(e) => setMonthly({ nth: Number(e.target.value), weekday: s.weekday })}>
                {#each NTH as [n, l]}<option value={n}>{l}</option>{/each}
              </select>
              <select class="input" aria-label="Giorno della settimana" value={s.weekday} onchange={(e) => setMonthly({ nth: s.nth, weekday: Number(e.target.value) })}>
                {#each WEEKDAYS as [, long], d}<option value={d}>{long}</option>{/each}
              </select>
            </div>
          {/if}
        {/if}
        <div class="tags">
          {#each s.times as t (t)}
            <button type="button" class="tag mono" aria-label="Togli l'orario {t}" onclick={() => removeTime(t)}>{t}<Icon name="close" /></button>
          {/each}
          {#if s.times.length < 6}
            <span class="time-add">
              <input type="time" class="input time-input" aria-label="Nuovo orario" bind:value={newTime} />
              <button type="button" class="tag" onclick={addTime}><Icon name="plus" />Orario</button>
            </span>
          {/if}
        </div>
        <p class="hint">{config.description}{config.next?.length ? `. Prossime: ${config.next.map((n) => nextRun(n.at, editionConfigs.timezone)).join("; ")}.` : config.active ? "" : ". Spenta: non esce finché non la riaccendi."}</p>
      </div>

      <div class="field">
        <span class="label">Regole {ruleCount ? "" : "· nessuna: tutte le notizie, prima quelle per te"}</span>
        {#if data.tags.length}
          <span class="sublabel">Tag delle fonti</span>
          <div class="tags">
            {#each data.tags as t (t.id)}
              <button type="button" class="tag" aria-pressed={config.rules.tags.includes(t.id)} onclick={() => toggleRule("tags", t.id)}>
                <span class="hash-c" style="--topic-c:{folderColor(t.color)}">#</span>{t.name}
              </button>
            {/each}
          </div>
        {/if}
        <span class="sublabel">Cartelle</span>
        <div class="tags">
          {#each data.folders as f (f.id)}
            <button type="button" class="tag" aria-pressed={config.rules.folders.includes(String(f.id))} onclick={() => toggleRule("folders", String(f.id))}>
              <span class="dot" style="--topic-c:{folderColor(f.color)}"></span>{f.name}
            </button>
          {/each}
          <button type="button" class="tag" aria-pressed={config.rules.folders.includes("none")} onclick={() => toggleRule("folders", "none")}>Senza cartella</button>
        </div>
        <span class="sublabel">Nazioni delle fonti</span>
        <div class="tags">
          {#each countries.slice(0, 12) as c (c)}
            <button type="button" class="tag" aria-pressed={config.rules.countries.includes(c)} onclick={() => toggleRule("countries", c)}>{flag(c)} {countryName(c)}</button>
          {/each}
          {#each config.rules.countries.filter((c) => !countries.slice(0, 12).includes(c)) as c (c)}
            <button type="button" class="tag" aria-pressed="true" onclick={() => toggleRule("countries", c)}>{flag(c)} {countryName(c)}</button>
          {/each}
        </div>
        {#if groups.length}
          <span class="sublabel">Gruppi di parole</span>
          <div class="tags">
            {#each groups as g (g.id)}
              <button type="button" class="tag" aria-pressed={config.rules.groups.includes(g.id)} onclick={() => toggleRule("groups", g.id)}>{g.name}</button>
            {/each}
          </div>
        {:else}
          <p class="hint">Per scegliere le notizie con un gruppo di parole (per esempio «Videogiochi»), prendilo prima negli Interessi.</p>
        {/if}
        <p class="hint">Tra regole di tipo diverso valgono tutte; dentro lo stesso tipo ne basta una. Per esempio #Politica e Italia: solo la politica delle fonti italiane.</p>
      </div>

      <div class="set-group">
        <div class="set-row"><label for="ed-max">Al massimo</label>
          <select class="input" id="ed-max" value={config.max_items} onchange={(e) => save({ max_items: Number(e.target.value) })}>
            {#each SIZES as n}<option value={n}>{n} notizie</option>{/each}
          </select>
        </div>
        <div class="set-row"><label for="ed-period">Notizie da</label>
          <select class="input" id="ed-period" value={config.period} onchange={(e) => save({ period: e.target.value })}>
            {#each PERIODS as [k, l]}<option value={k}>{l}</option>{/each}
          </select>
        </div>
      </div>

      {#if preview}
        <div class="preview" role="status">
          <b>{preview.selected}</b>
          <span>{preview.selected === 1 ? "notizia" : "notizie"} con queste regole, adesso{preview.available > preview.selected ? `, su ${preview.available} adatte` : ""} (ultime {preview.hours >= 48 ? `${Math.round(preview.hours / 24)} giorni` : `${preview.hours} ore`}).</span>
        </div>
      {/if}

      <button type="button" class="btn-primary" onclick={composeNow} disabled={busy}><Icon name="spark" />Componi adesso</button>
      <button type="button" class="btn-secondary" onclick={duplicate}><Icon name="copy" />Duplica</button>
      <button type="button" class="btn-secondary danger" onclick={remove}><Icon name="trash" />Elimina l'Edizione</button>
      {#if editionConfigs.timezone}<p class="hint center">Orari nel fuso {editionConfigs.timezone} (si cambia nelle Impostazioni).</p>{/if}
    </div>
  {/if}
</Sheet>
