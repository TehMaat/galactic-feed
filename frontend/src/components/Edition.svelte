<script>
  // Edizione: testata con il cielo stellato, notizia in primo piano e sezioni per cartella,
  // come nel mockup. La compone il server agli orari scelti nelle Impostazioni.
  import { paintStars } from "../lib/art.js";
  import { folderColor } from "../lib/format.js";
  import { composeEdition, edition, foldersById, openArticle, session, ui } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";
  import SourceMeta from "./SourceMeta.svelte";
  import Thumb from "./Thumb.svelte";

  let stars = $state();
  const ed = $derived(edition.data);
  const schedule = $derived(edition.schedule);
  const MODES = { parole: "parole chiave", ai: "AI", entrambi: "parole chiave e AI" };

  $effect(() => {
    if (stars && ed) paintStars(stars, ed.number + 200);
  });

  function greeting(iso) {
    const h = new Date(iso).getHours();
    if (h < 13) return "Buongiorno.";
    if (h < 18) return "Buon pomeriggio.";
    return "Buonasera.";
  }

  function longDate(iso) {
    return new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long" }).format(new Date(iso));
  }

  function key(e, id) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openArticle(id);
    }
  }

  const color = (a) => foldersById()[a.source.folder_id]?.color || "indaco";
  const total = $derived(ed ? (ed.hero ? 1 : 0) + ed.sections.reduce((n, s) => n + s.items.length, 0) : 0);
  const mode = $derived(MODES[session.user?.prefs?.ai_mode || "parole"]);
</script>

{#if ed}
  <section class="masthead" aria-label="Edizione">
    <canvas class="stars" bind:this={stars} aria-hidden="true"></canvas>
    <p class="mast-kicker">Edizione delle {ed.slot} · n. {ed.number}</p>
    <h2 class="mast-title">{greeting(ed.created_at)}<br />Ecco cosa conta oggi.</h2>
    <p class="mast-date">{longDate(ed.created_at)}</p>
    <div class="mast-stats">
      <div><b>{ed.stats.sources}</b><span>fonti</span></div>
      <div><b>{ed.stats.new}</b><span>nuovi</span></div>
      <div class="is-star"><b>{ed.stats.selected}</b><span>per te</span></div>
      <div><b>{ed.stats.hidden}</b><span>nascosti</span></div>
    </div>
    <p class="mast-foot">Prossima alle {schedule?.next_time} · filtri: {mode}</p>
  </section>

  {#if ed.hero}
    {@const a = ed.hero}
    <article class="hero tap" class:is-read={a.read} class:is-current={ui.reader === a.id} role="button" tabindex="0"
      aria-label={a.title} onclick={() => openArticle(a.id)} onkeydown={(e) => key(e, a.id)}>
      <Thumb article={a} color={color(a)} wide />
      <div class="hero-body">
        <div class="hero-label"><span class="count">In primo piano</span>
          {#if a.match}<span class="match"><Icon name="spark" />{a.match.keyword}</span>{/if}</div>
        <h3 class="hero-title">{a.title}</h3>
        {#if a.excerpt}<p class="excerpt clamp-2">{a.excerpt}</p>{/if}
        <SourceMeta article={a} />
      </div>
    </article>
  {/if}

  {#each ed.sections as section (section.key)}
    <div class="section-h">
      <h3><span class="dot" style="--topic-c:{folderColor(section.color)}"></span>{section.title}</h3>
      <span class="count">{section.items.length}</span>
    </div>
    <div class="list">
      {#each section.items as a (a.id)}
        <article class="row tap" class:is-read={a.read} class:is-current={ui.reader === a.id} role="button" tabindex="0"
          aria-label={a.title} onclick={() => openArticle(a.id)} onkeydown={(e) => key(e, a.id)}>
          <div class="row-text">
            <h4 class="row-title clamp-3">{a.title}</h4>
            <div class="row-foot"><SourceMeta article={a} />{#if a.match}<span class="match"><Icon name="spark" />{a.match.keyword}</span>{/if}</div>
          </div>
          <Thumb article={a} color={color(a)} />
        </article>
      {/each}
    </div>
  {/each}

  <div class="edition-end">
    <Icon name="check" />
    {#if total}
      <b>Sei in pari</b><span>{ed.stats.selected} notizie scelte tra {ed.stats.new}. Il resto è nel Flusso.</span>
    {:else}
      <b>Niente di nuovo</b><span>Dall'edizione precedente non sono arrivate notizie.</span>
    {/if}
  </div>
{:else if edition.error}
  <div class="empty"><Icon name="alert" /><h3>Non riesco a caricare l'Edizione</h3><p>{edition.error}</p></div>
{:else if !edition.loading && edition.loaded}
  <div class="empty">
    <Icon name="edition" />
    <h3>La prima Edizione è in arrivo</h3>
    <p>Il server la compone {schedule ? `alle ${schedule.next_time}` : "al prossimo orario"}. Se non vuoi aspettare, componila adesso.</p>
    <button type="button" class="pill-btn" onclick={composeEdition}><Icon name="spark" />Componi adesso</button>
  </div>
{:else}
  <p class="loading">Carico l'Edizione…</p>
{/if}
