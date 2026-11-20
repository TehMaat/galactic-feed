<script>
  // Statistiche di lettura (#78): articoli aperti, salvati, giorni di fila, letti nel tempo,
  // interessi e fonti più letti, ore del giorno, Edizioni aperte. Periodo (#83): settimana, mese,
  // anno o di sempre; il grafico va per giorno, per mese o per anno.
  // Una serie sola per grafico, nel colore principale; i numeri sono nel testo, non solo nel colore.
  import { loadStats, stats } from "../lib/store.svelte.js";

  let { wide = false } = $props();
  const s = $derived(stats.data);
  const WD = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"];
  const MONTHS = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
  const PERIODS = [
    ["settimana", "Settimana"],
    ["mese", "Mese"],
    ["anno", "Anno"],
    ["sempre", "Sempre"],
  ];
  // Come si dice il periodo nei riquadri e nel confronto con quello prima.
  const SPAN = { settimana: "negli ultimi 7 giorni", mese: "negli ultimi 30 giorni", anno: "negli ultimi 12 mesi", sempre: "da sempre" };
  const BEFORE = { settimana: "sui 7 giorni prima", mese: "sui 30 giorni prima", anno: "sui 12 mesi prima" };
  const PER = { day: "Letti al giorno", month: "Letti al mese", year: "Letti all'anno" };

  const articles = (n) => (n === 1 ? "1 articolo" : `${n} articoli`);
  const days = $derived(
    s
      ? s.series.map((d, i, all) => {
          const date = new Date(d.start + "T12:00:00");
          const last = i === all.length - 1;
          const n = all.length;
          let label, when;
          if (s.unit === "year") {
            label = when = String(date.getFullYear());
          } else if (s.unit === "month") {
            const step = n > 12 ? 3 : n > 6 ? 2 : 1;
            label = (n - 1 - i) % step === 0 ? MONTHS[date.getMonth()] : "";
            when = `${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
          } else {
            label = last ? "oggi" : n <= 7 ? WD[date.getDay()] : i % 10 === 0 ? `${date.getDate()} ${MONTHS[date.getMonth()]}` : "";
            when = last ? "Oggi" : `${WD[date.getDay()]} ${date.getDate()} ${MONTHS[date.getMonth()]}`;
          }
          return { ...d, label, tip: `${when}: ${articles(d.n)}`, last };
        })
      : [],
  );
  const max = $derived(Math.max(1, ...days.map((d) => d.n)));
  const hmax = $derived(s ? Math.max(1, ...s.hours) : 1);
  const delta = $derived(s && s.read_prev ? Math.round(((s.read - s.read_prev) / s.read_prev) * 100) : null);
  const peaks = $derived(
    s && s.read
      ? s.hours.map((n, h) => [n, h]).filter(([n]) => n).sort((a, b) => b[0] - a[0]).slice(0, 2).map(([, h]) => h).sort((a, b) => a - b)
      : [],
  );
  const avg = $derived(s ? (s.read / s.days).toLocaleString("it-IT", { maximumFractionDigits: 1 }) : "");

  $effect(() => {
    if (!stats.data && !stats.loading) loadStats();
  });
</script>

<section class="stats" class:is-wide={wide} aria-labelledby="h-stats">
  <div class="sec-head">
    <h2 class="sec-title small" id="h-stats">Statistiche</h2>
    <div class="segmented" style="--cols:4" role="group" aria-label="Periodo">
      {#each PERIODS as [key, name] (key)}
        <button type="button" aria-pressed={stats.period === key} onclick={() => loadStats(key)}>{name}</button>
      {/each}
    </div>
  </div>

  {#if stats.error && !s}
    <p class="hint">{stats.error}</p>
  {:else if s}
    <div class="stat-grid">
      <div class="tiles span-2">
        <div class="tile glass"><span>Letti</span><b>{s.read}</b>
          <small>{delta === null ? SPAN[s.period] : `${delta >= 0 ? "+" : "−"}${Math.abs(delta)}% ${BEFORE[s.period]}`}</small></div>
        <div class="tile glass"><span>Salvati</span><b>{s.saved}</b><small>{SPAN[s.period]}</small></div>
        <div class="tile glass"><span>Giorni di fila</span><b>{s.streak}</b><small>record: {s.best_streak}</small></div>
      </div>

      <div class="stat-card glass span-2">
        <h3>{PER[s.unit]}<small>media {avg} al giorno</small></h3>
        <div class="bars" role="img" aria-label="{PER[s.unit]}: {days.map((d) => d.tip).join('; ')}">
          {#each days as d (d.start)}
            <div class="bar-col" class:is-today={d.last} title={d.tip}>
              <div class="bar-well"><span class="bar" style="height:{(d.n / max) * 100}%">{#if d.n && (d.last || d.n === max)}<span class="bar-v">{d.n}</span>{/if}</span></div>
              <span class="bar-l">{d.label}</span>
            </div>
          {/each}
        </div>
      </div>

      <div class="stat-card glass">
        <h3>Interessi più letti</h3>
        {#if s.interests.length}
          <div class="hbars">
            {#each s.interests as it (it.name)}
              <div class="hbar"><span class="hbar-n">{it.name}</span><span class="hbar-t"><span style="width:{(it.n / s.interests[0].n) * 100}%"></span></span><b>{it.share}%</b></div>
            {/each}
          </div>
        {:else}
          <p class="hint">Si riempie quando leggi articoli di fonti con un tag o che corrispondono ai tuoi interessi.</p>
        {/if}
      </div>

      <div class="stat-card glass">
        <h3>Fonti più lette<small>articoli</small></h3>
        {#if s.sources.length}
          <ol class="top-sources">
            {#each s.sources as src (src.id)}<li><span>{src.title}</span><b>{src.n}</b></li>{/each}
          </ol>
        {:else}
          <p class="hint">Ancora nessun articolo aperto in questo periodo.</p>
        {/if}
      </div>

      <div class="stat-card glass">
        <h3>Quando leggi</h3>
        <div class="hours" role="img" aria-label={peaks.length ? `Leggi di più verso le ${peaks.join(" e le ")}` : "Ancora nessuna lettura"}>
          {#each s.hours as n, h}<i style="--o:{(0.1 + (0.9 * n) / hmax).toFixed(2)}" title="dalle {h} alle {h + 1}: {n}"></i>{/each}
        </div>
        <div class="hours-l" aria-hidden="true"><span>0</span><span>6</span><span>12</span><span>18</span><span>24</span></div>
        <p class="hint">{peaks.length ? `Leggi di più verso le ${peaks.join(" e le ")}.` : "Le ore compaiono quando apri qualche articolo."}</p>
      </div>

      <div class="stat-card glass">
        <h3>Edizioni aperte<small>{s.editions.opened} su {s.editions.issued}</small></h3>
        <div class="progress" aria-hidden="true"><i style="width:{s.editions.issued ? (s.editions.opened / s.editions.issued) * 100 : 0}%"></i></div>
        <p class="hint">{s.editions.issued ? `Hai aperto il ${Math.round((s.editions.opened / s.editions.issued) * 100)}% delle uscite del periodo.` : "Nessuna uscita in questo periodo."}</p>
      </div>
    </div>
    <p class="set-note">Contano gli articoli che apri, una volta sola; «Segna tutti come letti» no. Niente misura di quanto tempo leggi.</p>
  {:else}
    <p class="loading">Calcolo le statistiche…</p>
  {/if}
</section>
