<script>
  // Ricerca nelle Impostazioni (#67). Filtra le voci sul posto: restano visibili e usabili solo
  // quelle che corrispondono, con la parola evidenziata (CSS Custom Highlight, dove il browser lo
  // conosce) e il sinonimo che le ha trovate («trovata per «dark»»). Cerca nel nome della voce,
  // nella sezione e in alcuni sinonimi. Sul telefono il campo sparisce scorrendo verso il basso e
  // torna appena si risale; sul computer sta fermo nella colonna a sinistra.
  import { tick } from "svelte";
  import { ui } from "../lib/store.svelte.js";
  import Icon from "./Icon.svelte";

  let { place = "main" } = $props();
  let box = $state();
  let input = $state();
  let hidden = $state(false);
  let result = $state(null); // { rows, sections } durante la ricerca

  // Sinonimi: [parte del nome della voce, parole che la trovano].
  const SYNONYMS = [
    ["tema", "dark light scuro chiaro notte giorno modalita"],
    ["scuro", "dark oled amoled nero solarized palette variante"],
    ["chiaro", "light bianco carta solarized palette variante"],
    ["colore", "accento tinta colori personalizzato custom"],
    ["font", "carattere caratteri tipografia dislessia testo articoli lettura"],
    ["dimensione", "grandezza zoom testo caratteri"],
    ["preset", "filtri apertura predefinito notiziario flusso"],
    ["password", "accesso sicurezza credenziali"],
    ["dispositivi", "sessioni accessi telefono computer"],
    ["account collegati", "oidc sso login provider"],
    ["esci", "logout disconnetti"],
    ["nome e avatar", "profilo foto immagine nome"],
    ["notifiche", "push avvisi"],
    ["notifica di prova", "test push"],
    ["fornitore", "ai chiave api token modello intelligenza artificiale"],
    ["nascondi gli articoli", "estratto parziale testo completo"],
    ["articolo sul computer", "lettore colonne pagina intera desktop"],
    ["esporta", "opml backup"],
    ["fuso orario", "ora orario timezone"],
    ["versione", "aggiornamento release"],
    ["aggiornamenti", "update versione"],
    ["indirizzo", "host dominio url server"],
    ["controllo delle fonti", "frequenza aggiornamento"],
    ["nuova edizione", "crea rassegna giornale"],
    ["le tue fonti", "feed rss siti"],
    ["aggiungi una fonte", "feed rss sito nuova"],
  ];
  const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

  // Le parole della voce, a inizio parola: «tema» non deve trovare «sistema» o «Guatemala».
  const words = (s) => " " + norm(s).replace(/[^a-z0-9]+/g, " ") + " ";
  const visibleText = { acceptNode: (n) => (n.parentElement?.closest("select, option") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) };

  // Il testo della voce, senza le scelte dei menu a tendina (per esempio i fusi orari).
  function rowText(row) {
    let out = "";
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT, visibleText);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) out += " " + n.nodeValue;
    return out;
  }

  function root() {
    return box?.closest(".page-view")?.querySelector(".page-main");
  }

  function apply() {
    const main = root();
    if (!main) return;
    const terms = norm(ui.settingsQuery).split(/\s+/).filter(Boolean);
    const ranges = [];
    let rows = 0;
    const sections = new Set();
    let label = null;
    for (const el of main.querySelectorAll(":scope > .set-label, :scope > .set-group, :scope > .set-note")) {
      if (el.classList.contains("set-label")) {
        label = el;
        el.removeAttribute("data-miss");
        continue;
      }
      if (el.classList.contains("set-note")) {
        el.toggleAttribute("data-miss", terms.length > 0);
        continue;
      }
      let visible = 0;
      for (const row of el.querySelectorAll(":scope > .set-row, :scope > .link-row, :scope > .set-block, :scope > form")) {
        row.removeAttribute("data-via");
        if (!terms.length) {
          row.removeAttribute("data-miss");
          visible++;
          continue;
        }
        const own = words(rowText(row) + " " + (label?.textContent || ""));
        const extra = " " + SYNONYMS.filter(([k]) => own.includes(" " + k)).map(([, w]) => w).join(" ") + " ";
        const ok = terms.every((t) => own.includes(" " + t) || extra.includes(" " + t));
        row.toggleAttribute("data-miss", !ok);
        if (!ok) continue;
        visible++;
        rows++;
        sections.add(label);
        if (!terms.some((t) => own.includes(" " + t))) row.dataset.via = extra.split(" ").find((w) => terms.some((t) => w.startsWith(t))) || terms[0];
        collect(row, terms, ranges);
      }
      el.toggleAttribute("data-miss", terms.length > 0 && visible === 0);
    }
    if (terms.length) {
      for (const l of main.querySelectorAll(":scope > .set-label")) l.toggleAttribute("data-miss", !sections.has(l));
    }
    main.toggleAttribute("data-searching", terms.length > 0);
    result = terms.length ? { rows, sections: sections.size } : null;
    if (typeof CSS !== "undefined" && CSS.highlights && typeof Highlight !== "undefined") {
      if (ranges.length) CSS.highlights.set("gf-settings", new Highlight(...ranges));
      else CSS.highlights.delete("gf-settings");
    }
  }

  // Le parole trovate nei testi della voce (non dentro i campi).
  function collect(row, terms, ranges) {
    const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT, visibleText);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = norm(node.nodeValue);
      for (const t of terms) {
        let i = text.indexOf(t);
        while (i >= 0) {
          // Solo a inizio parola, come la ricerca.
          if (i > 0 && /[a-z0-9]/.test(text[i - 1])) {
            i = text.indexOf(t, i + 1);
            continue;
          }
          const r = new Range();
          r.setStart(node, i);
          r.setEnd(node, i + t.length);
          ranges.push(r);
          i = text.indexOf(t, i + t.length);
        }
      }
    }
  }

  // Si rifà la ricerca a ogni cambio del testo e quando la pagina si ridisegna (una voce cambia).
  $effect(() => {
    ui.settingsQuery;
    tick().then(apply);
  });
  $effect(() => {
    const main = root();
    if (!main) return;
    let pending = false;
    const mo = new MutationObserver(() => {
      if (pending || !ui.settingsQuery) return;
      pending = true;
      requestAnimationFrame(() => {
        pending = false;
        apply();
      });
    });
    mo.observe(main, { childList: true, subtree: true });
    return () => {
      mo.disconnect();
      if (typeof CSS !== "undefined" && CSS.highlights) CSS.highlights.delete("gf-settings");
    };
  });

  // Dal Profilo, «Cerca nelle impostazioni»: il cursore va nel campo, una volta sola (#81). La
  // richiesta si consuma subito, altrimenti ogni apertura successiva delle Impostazioni (che
  // rimonta questo campo) aprirebbe di nuovo la tastiera.
  $effect(() => {
    if (!ui.settingsFocus || !input) return;
    const wide = window.matchMedia("(min-width: 1100px)").matches;
    if ((place === "nav") !== wide) return;
    ui.settingsFocus = false;
    input.focus();
  });

  // Telefono: sparisce scorrendo giù, torna risalendo (o in cima).
  let last = 0;
  function onScroll() {
    if (place !== "main") return;
    const y = window.scrollY;
    if (document.activeElement === input) {
      last = y;
      return;
    }
    if (y < 120) hidden = false;
    else if (y > last + 6) hidden = true;
    else if (y < last - 6) hidden = false;
    last = y;
  }

  function clear() {
    ui.settingsQuery = "";
    input?.focus();
  }
</script>

<svelte:window onscroll={onScroll} />

<div class="settings-search {place}" class:is-hidden={hidden} bind:this={box}>
  <label class="search-field glass">
    <Icon name="search" />
    <input bind:this={input} type="search" placeholder="Cerca nelle impostazioni" autocomplete="off" aria-label="Cerca nelle impostazioni" bind:value={ui.settingsQuery} />
    {#if ui.settingsQuery}<button type="button" class="clear-btn" aria-label="Cancella" onclick={clear}><Icon name="close" /></button>{/if}
  </label>
  {#if result && place === "main"}
    <p class="search-count" role="status">
      {#if result.rows}
        {result.rows === 1 ? "1 impostazione" : `${result.rows} impostazioni`} in {result.sections === 1 ? "1 sezione" : `${result.sections} sezioni`}
      {:else}
        Nessuna impostazione per «{ui.settingsQuery.trim()}». Prova con «tema», «password» o «colore».
      {/if}
    </p>
  {/if}
</div>
