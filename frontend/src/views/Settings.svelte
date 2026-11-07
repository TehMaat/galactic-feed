<script>
  // Impostazioni personali, con le stesse sezioni del mockup. Quelle di tutta l'istanza
  // (utenti, accesso, AI, archivio…) sono nel pannello Amministrazione (Admin.svelte).
  import { tick } from "svelte";
  import Icon from "../components/Icon.svelte";
  import Page from "../components/Page.svelte";
  import { folderColor } from "../lib/format.js";
  import { currentSubscription, disablePush, enablePush, isIos, isStandalone } from "../lib/push.js";
  import { api } from "../lib/api.js";
  import { ACCENTS, DARK_STYLES, LIGHT_STYLES, FONTS, READ_FONTS, SIZES, countryName, initials, timeAgoLong } from "../lib/format.js";
  import { ask, data, editionConfigs, loadEditionConfigs, logout, openPage, openSheet, savePrefs, session, setEditionConfigs, toast, ui } from "../lib/store.svelte.js";

  let { active } = $props();
  let page = $state("main"); // main · password · sessions · identities
  let identities = $state(null); // account del provider collegati (#22)
  let sessions = $state([]);
  let pw = $state({ current: "", next: "", repeat: "" });
  let pwError = $state("");

  // A ogni apertura si riparte dalla prima schermata.
  $effect(() => {
    ui.pageTick;
    if (active) page = "main";
  });

  // Indice delle sezioni, a sinistra sul computer.
  const NAV = [
    ["account", "user", "Account"],
    ["edizioni", "edition", "Edizioni"],
    ["notifiche", "bell", "Notifiche"],
    ["ai", "spark", "AI"],
    ["aspetto", "sliders", "Aspetto"],
    ["server", "devices", "Server e dati"],
  ];
  let section = $state("account");
  async function jump(key) {
    if (page !== "main") {
      page = "main";
      await tick();
    }
    section = key;
    document.getElementById(`set-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const me = $derived(session.user);

  // ---- Notifiche ----
  let pushOn = $state(false);
  let pushBusy = $state(false);
  let pushError = $state("");
  const notifyFolders = $derived(me?.prefs?.notify_folders || []);
  const categories = $derived([
    ...data.folders.map((f) => ({ key: String(f.id), name: f.name, color: folderColor(f.color) })),
    { key: "none", name: "Senza cartella", color: folderColor("grigio") },
  ]);
  const pushNote = $derived(
    pushError ||
      (pushOn
        ? notifyFolders.length
          ? "Ti avviso quando arriva una notizia per te in queste categorie, al massimo una volta ogni 10 minuti. Sull'icona dell'app compare il numero di non letti."
          : "Scegli almeno una categoria importante: ti avviso quando arriva una notizia per te."
        : isIos() && !isStandalone()
          ? "Su iPhone le notifiche arrivano solo se l'app è aggiunta alla schermata Home (iOS 16.4 o successivo)."
          : "Ogni dispositivo si accende a parte: telefono, tablet e computer."),
  );

  $effect(() => {
    if (active) currentSubscription().then((s) => (pushOn = !!s));
  });

  async function togglePush() {
    pushBusy = true;
    pushError = "";
    try {
      if (pushOn) {
        await disablePush();
        pushOn = false;
        toast("Notifiche spente su questo dispositivo");
      } else {
        const error = await enablePush();
        if (error) pushError = error;
        else {
          pushOn = true;
          toast("Notifiche accese su questo dispositivo");
        }
      }
    } finally {
      pushBusy = false;
    }
  }

  function toggleCategory(key) {
    const next = notifyFolders.includes(key) ? notifyFolders.filter((k) => k !== key) : [...notifyFolders, key];
    savePrefs({ notify_folders: next });
  }

  async function testPush() {
    try {
      await api("/push/test", { method: "POST" });
      toast("Notifica di prova inviata");
    } catch (err) {
      toast(err.message);
    }
  }
  const edOn = $derived(Boolean(me?.prefs?.edition));

  // ---- Edizioni (#18, #19) ----
  $effect(() => {
    if (active) loadEditionConfigs();
  });

  function ruleSummary(c) {
    const parts = [];
    const tagNames = c.rules.tags.map((id) => data.tags.find((t) => t.id === id)?.name).filter(Boolean).map((n) => "#" + n);
    parts.push(...tagNames);
    parts.push(...c.rules.countries.map((code) => countryName(code)));
    parts.push(...c.rules.folders.map((f) => (f === "none" ? "Senza cartella" : data.folders.find((x) => String(x.id) === f)?.name)).filter(Boolean));
    parts.push(...c.rules.groups.map((id) => data.interests.groups?.find((g) => g.id === id)?.name).filter(Boolean));
    return parts.length ? parts.join(", ") : "tutte le notizie";
  }

  async function toggleConfig(c) {
    try {
      await setEditionConfigs(await api(`/edition-configs/${c.id}`, { method: "PATCH", body: { active: !c.active } }));
      toast(c.active ? `«${c.name}» spenta` : `«${c.name}» accesa`);
    } catch (err) {
      toast(err.message);
    }
  }

  async function removeConfig(c) {
    if (!(await ask("Si cancellano anche tutte le sue uscite. Per fermarla e basta, spegnila.", { title: `Eliminare «${c.name}»?` }))) return;
    try {
      await setEditionConfigs(await api(`/edition-configs/${c.id}`, { method: "DELETE" }));
      toast(`«${c.name}» eliminata`);
    } catch (err) {
      toast(err.message);
    }
  }

  async function newConfig() {
    try {
      const r = await api("/edition-configs", { method: "POST", body: {} });
      await setEditionConfigs(r);
      openSheet("edition-config", r.configs.at(-1));
    } catch (err) {
      toast(err.message);
    }
  }

  const ZONES = (() => {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch {
      return ["Europe/Rome", "Europe/London", "Europe/Paris", "America/New_York", "America/Los_Angeles", "Asia/Tokyo", "UTC"];
    }
  })();
  const theme = $derived(me?.prefs?.theme || "auto");
  const accent = $derived(me?.prefs?.accent || "galassia");
  const systemAccent = typeof CSS !== "undefined" && CSS.supports?.("color", "AccentColor");
  // Ogni scelta di font è scritta nel suo font, così si vede subito com'è (FONTS in format.js).
  const font = $derived(me?.prefs?.font || "galactic");
  const fontRead = $derived(me?.prefs?.font_read || "serif");
  const lastCheck = $derived(
    data.sources.map((s) => s.last_fetch_at).filter(Boolean).sort().at(-1) || null,
  );
  const ai = $derived(data.interests.ai);
  const aiLabel = $derived(ai?.enabled ? `${ai.kind === "locale" ? "Locale" : "Cloud"} · ${ai.label}` : "Spenta");
  const TITLES = { main: "Impostazioni", password: identities && !identities.has_password ? "Scegli una password" : "Cambia password", sessions: "Dispositivi collegati", identities: "Account collegati" };

  function go(p) {
    page = p;
    if (p === "sessions") loadSessions();
    if (p === "identities" || p === "password") loadIdentities();
    if (p === "password") {
      pw = { current: "", next: "", repeat: "" };
      pwError = "";
    }
  }

  async function changePassword(e) {
    e.preventDefault();
    pwError = "";
    if (pw.next !== pw.repeat) {
      pwError = "Le due password nuove non coincidono.";
      return;
    }
    try {
      await api("/me/password", { method: "POST", body: { current: pw.current, new: pw.next } });
      toast("Password cambiata. Gli altri dispositivi dovranno rientrare.");
      go("main");
    } catch (err) {
      pwError = err.message;
    }
  }

  // ---- Account del provider collegati (#22) ----
  async function loadIdentities() {
    try {
      identities = await api("/me/identities");
    } catch (err) {
      toast(err.message);
    }
  }

  async function unlinkIdentity(i) {
    if (!(await ask("Non potrai più entrare con quello finché non lo ricolleghi.", { title: "Scollegare questo account del provider?", action: "Scollega" }))) return;
    try {
      identities = await api(`/me/identities/${i.id}`, { method: "DELETE" });
      toast("Account scollegato");
    } catch (err) {
      toast(err.message);
    }
  }

  async function loadSessions() {
    try {
      sessions = (await api("/me/sessions")).sessions;
    } catch (err) {
      toast(err.message);
    }
  }

  async function endSession(s) {
    await api(`/me/sessions/${s.id}`, { method: "DELETE" });
    toast("Dispositivo scollegato");
    loadSessions();
  }

  function expiry(s) {
    const when = new Date(s.expires_at).toLocaleString("it-IT", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
    return s.remember ? `ricordato, scade il ${when} se non lo usi` : `fino alla chiusura del browser, al massimo il ${when}`;
  }

  function device(ua) {
    const os = /iPhone/.test(ua) ? "iPhone" : /iPad/.test(ua) ? "iPad" : /Android/.test(ua) ? "Android" : /Mac OS X|Macintosh/.test(ua) ? "Mac" : /Windows/.test(ua) ? "Windows" : /Linux/.test(ua) ? "Linux" : "Dispositivo";
    const br = /Edg\//.test(ua) ? "Edge" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "";
    return br ? `${os} · ${br}` : os;
  }

</script>

{#snippet styleChoice(list, value, label, onpick)}
  <div class="theme-styles" role="group" aria-label={label}>
    {#each list as [k, name, bg, card, ink] (k)}
      <button type="button" class="theme-style" aria-pressed={value === k} onclick={() => onpick(k)} style="--ts-bg:{bg};--ts-card:{card};--ts-ink:{ink}">
        <span class="theme-preview" aria-hidden="true"><i></i><i></i></span>{name}
      </button>
    {/each}
  </div>
{/snippet}

<Page label="Impostazioni" title={TITLES[page]} {active} back={page === "main" ? null : () => go("main")} nav={NAV} current={page === "main" ? section : "account"} onnav={jump} scrollKey={page}>
  {#if me}
    {#if page === "main"}
      <div class="set-label" id="set-account">Account</div>
      <div class="set-group">
        <div class="set-row">
          <span class="who"><span class="user-av">{initials(me.display_name)}</span><span><b>{me.display_name}</b><br /><small>{me.is_admin ? "amministratore" : "utente"} · @{me.username}</small></span></span>
        </div>
        {#if me.is_admin}
          <button type="button" class="link-row" onclick={() => openPage("amministrazione")}><Icon name="shield" />Amministrazione</button>
        {/if}
        <button type="button" class="link-row" onclick={() => go("password")}><Icon name="key" />Cambia password</button>
        {#if session.oidc?.enabled}
          <button type="button" class="link-row" onclick={() => go("identities")}><Icon name="user" />Account collegati · {session.oidc.label.replace(/^Entra con /i, "")}</button>
        {/if}
        <button type="button" class="link-row" onclick={() => go("sessions")}><Icon name="devices" />Dispositivi collegati</button>
        <button type="button" class="link-row" onclick={logout}><Icon name="logout" />Esci</button>
      </div>
      <p class="set-note">Ogni utente ha fonti, interessi, letti e salvati propri. I feed in comune vengono scaricati una volta sola.</p>

      <div class="set-label" id="set-edizioni">Edizioni</div>
      <div class="set-group">
        {#each editionConfigs.list as c (c.id)}
          <div class="set-row">
            <button type="button" class="preset-name" onclick={() => openSheet("edition-config", c)}>
              <b>{c.name}</b><small>{c.description} · {ruleSummary(c)}</small>
            </button>
            <span class="row-actions">
              <button type="button" class="icon-btn" aria-label="Elimina l'Edizione {c.name}" title="Elimina" onclick={() => removeConfig(c)}><Icon name="trash" /></button>
              <button type="button" class="switch" role="switch" aria-checked={c.active} aria-label="Edizione {c.name} attiva" onclick={() => toggleConfig(c)}></button>
            </span>
          </div>
        {/each}
        <button type="button" class="link-row" onclick={newConfig}><Icon name="plus" />{editionConfigs.list.length ? "Nuova Edizione" : "Crea la tua Edizione"}</button>
        <div class="set-row"><label for="user-tz">Fuso orario</label>
          <select class="input" id="user-tz" value={me.prefs.timezone || ""} onchange={(e) => savePrefs({ timezone: e.target.value }).then(loadEditionConfigs)}>
            <option value="">Come il server</option>
            {#each ZONES as z}<option value={z}>{z}</option>{/each}
          </select>
        </div>
      </div>
      <p class="set-note">{editionConfigs.list.length ? "Ogni Edizione è una selezione delle notizie con nome, regole (tag, cartelle, nazioni, gruppi di parole) e uscite proprie: ogni giorno, in alcuni giorni della settimana o una volta al mese. Si leggono in Oggi." : "Una selezione delle notizie per te, agli orari che scegli, da leggere nell'app (niente email). Senza Edizioni, Oggi mostra solo il Flusso."}</p>

      <div class="set-label" id="set-notifiche">Notifiche</div>
      <div class="set-group">
        <div class="set-row"><span>Notifiche su questo dispositivo</span>
          <button type="button" class="switch" role="switch" aria-checked={pushOn} aria-label="Notifiche su questo dispositivo" disabled={pushBusy} onclick={togglePush}></button>
        </div>
        {#if pushOn}
          <div class="set-block">
            <span class="label">Categorie importanti</span>
            <div class="tags">
              {#each categories as c (c.key)}
                <button type="button" class="tag" aria-pressed={notifyFolders.includes(c.key)} onclick={() => toggleCategory(c.key)}>
                  <span class="dot" style="--topic-c:{c.color}"></span>{c.name}
                </button>
              {/each}
            </div>
          </div>
          {#if edOn}
            <div class="set-row"><span>Quando l'Edizione è pronta</span>
              <button type="button" class="switch" role="switch" aria-checked={!!me.prefs.notify_edition} aria-label="Notifica quando l'Edizione è pronta" onclick={() => savePrefs({ notify_edition: !me.prefs.notify_edition })}></button>
            </div>
          {/if}
          <button type="button" class="set-row as-button" onclick={testPush}><span>Invia una notifica di prova</span><Icon name="bell" /></button>
        {/if}
      </div>
      <p class="set-note">{pushNote}</p>

      <div class="set-label" id="set-ai">AI</div>
      <div class="set-group">
        {#if me.is_admin}
          <button type="button" class="set-row as-button" onclick={() => openPage("amministrazione", "ai")}><span>Fornitore</span><span class="val">{aiLabel}</span></button>
        {:else}
          <div class="set-row"><span>Fornitore</span><span class="val">{aiLabel}</span></div>
        {/if}
      </div>
      <p class="set-note">{ai?.enabled ? "Filtri e riassunti si scelgono negli Interessi." : me.is_admin ? "Filtri e riassunti con un modello locale (Ollama) o con un servizio cloud: si configura in Amministrazione." : "L'AI la configura l'amministratore."}</p>

      <div class="set-label" id="set-aspetto">Aspetto</div>
      <div class="set-group">
        <div class="set-row"><span>Tema</span>
          <div class="segmented" style="--cols:3" role="group" aria-label="Tema">
            {#each [["auto", "Auto"], ["light", "Chiaro"], ["dark", "Scuro"]] as [k, l]}
              <button type="button" aria-pressed={theme === k} onclick={() => savePrefs({ theme: k })}>{l}</button>
            {/each}
          </div>
        </div>
        <div class="set-block">
          <span class="label" id="dark-label">Scuro</span>
          {@render styleChoice(DARK_STYLES, me.prefs.dark_style || "notte", "Variante del tema scuro", (k) => savePrefs({ dark_style: k }))}
        </div>
        <div class="set-block">
          <span class="label" id="light-label">Chiaro</span>
          {@render styleChoice(LIGHT_STYLES, me.prefs.light_style || "neutro", "Variante del tema chiaro", (k) => savePrefs({ light_style: k }))}
        </div>
        <div class="set-block">
          <span class="label" id="accent-label">Colore</span>
          <div class="swatches" role="group" aria-labelledby="accent-label">
            {#each ACCENTS as c (c.key)}
              <button type="button" class="swatch" style="--sw-l:{c.light};--sw-d:{c.dark}" aria-pressed={accent === c.key} aria-label={c.name} title={c.name} onclick={() => savePrefs({ accent: c.key })}><Icon name="check" /></button>
            {/each}
            <button type="button" class="swatch is-system" aria-pressed={accent === "system"} aria-label="Colore del sistema" title="Colore del sistema" onclick={() => savePrefs({ accent: "system" })}><Icon name="check" /></button>
          </div>
        </div>
        <div class="set-block">
          <span class="label" id="font-label">Font</span>
          <div class="tags" role="group" aria-labelledby="font-label">
            {#each FONTS as [k, label, family] (k)}
              <button type="button" class="tag" style="font-family:{family}" aria-pressed={font === k} onclick={() => savePrefs({ font: k })}>{label}</button>
            {/each}
          </div>
        </div>
        <div class="set-block">
          <span class="label" id="read-label">Testo degli articoli</span>
          <div class="tags" role="group" aria-labelledby="read-label">
            {#each READ_FONTS as [k, label, family] (k)}
              <button type="button" class="tag" style="font-family:{family}" aria-pressed={fontRead === k} onclick={() => savePrefs({ font_read: k })}>{label}</button>
            {/each}
          </div>
        </div>
        <div class="set-row"><span>Dimensione del testo</span>
          <div class="segmented" style="--cols:3" role="group" aria-label="Dimensione del testo">
            {#each SIZES as [v, l]}
              <button type="button" aria-pressed={(me.prefs.text_size || 1) === v} onclick={() => savePrefs({ text_size: v })}>{l}</button>
            {/each}
          </div>
        </div>
      </div>
      <p class="set-note">
        {accent === "system"
          ? systemAccent
            ? "Colore del sistema: lo prende dalle impostazioni del dispositivo."
            : "Questo browser non fa conoscere il colore del sistema (succede su iPhone, iPad e Android): resta il colore Galassia."
          : "Tema, colore, font e dimensione del testo valgono su tutti i tuoi dispositivi. La variante «Scuro» vale con il tema Scuro e con Auto quando il dispositivo è in modo scuro; «Nero» spegne i pixel degli schermi OLED. «Galactic» usa Unbounded per i titoli; «Sistema» il font del dispositivo."}
      </p>

      <div class="set-label" id="set-server">Server</div>
      <div class="set-group">
        <div class="set-row"><span>Indirizzo</span><span class="val">{location.host}</span></div>
        <div class="set-row"><span>Controllo delle fonti</span><span class="val">da 15 min a 24 h</span></div>
        <div class="set-row"><span>Ultimo controllo</span><span class="val">{lastCheck ? timeAgoLong(lastCheck) : "—"}</span></div>
      </div>

      <div class="set-label">Dati</div>
      <div class="set-group"><a class="link-row" href="/api/opml/export" download><Icon name="download" />Esporta le fonti (OPML)</a></div>
      <p class="set-note">Sola lettura: niente commenti né voti, solo il link all'articolo originale.</p>
      {#if session.version}<p class="app-version">Galactic Feed <span>versione {session.version}</span></p>{/if}
    {:else if page === "password"}
      <form class="form-stack" onsubmit={changePassword}>
        {#if !identities || identities.has_password}
          <div class="field"><label for="pw-cur">Password attuale</label><input class="input" id="pw-cur" type="password" autocomplete="current-password" bind:value={pw.current} /></div>
        {:else}
          <p class="set-note top">Sei entrato con il provider e non hai ancora una password: sceglila per poter entrare anche con nome utente e password.</p>
        {/if}
        <div class="field"><label for="pw-new">Nuova password</label><input class="input" id="pw-new" type="password" autocomplete="new-password" minlength="8" bind:value={pw.next} /></div>
        <div class="field"><label for="pw-rep">Ripeti la nuova password</label><input class="input" id="pw-rep" type="password" autocomplete="new-password" minlength="8" bind:value={pw.repeat} /></div>
        <p class="hint">Almeno 8 caratteri. Una frase di più parole è facile da ricordare e difficile da indovinare.</p>
        {#if pwError}<p class="form-error" role="alert">{pwError}</p>{/if}
        <button type="submit" class="btn-primary" disabled={(identities?.has_password !== false && !pw.current) || pw.next.length < 8}><Icon name="check" />Cambia password</button>
      </form>
    {:else if page === "identities"}
      {#if identities}
        {#if identities.identities.length}
          <div class="set-group">
            {#each identities.identities as i (i.id)}
              <div class="set-row"><span class="feed-name"><b>{i.username || i.email || "Account collegato"}</b><small>{i.email ? i.email + " · " : ""}{i.issuer}</small></span>
                <button type="button" class="icon-btn" aria-label="Scollega questo account" onclick={() => unlinkIdentity(i)}><Icon name="close" /></button>
              </div>
            {/each}
          </div>
        {:else}
          <p class="set-note top">Nessun account del provider collegato.</p>
        {/if}
        <div class="set-group mt">
          <a class="link-row" href="/api/auth/oidc/start?link=1&remember=1"><Icon name="plus" />Collega un account</a>
        </div>
        <p class="set-note">Dopo averlo collegato puoi entrare con «{session.oidc.label}» oltre che con la password. Ti porta alla pagina del provider e poi torna qui.</p>
      {:else}
        <p class="loading">Carico gli account…</p>
      {/if}
    {:else if page === "sessions"}
      <div class="set-group">
        {#each sessions as s (s.id)}
          <div class="set-row"><span>{device(s.user_agent)}{#if s.current} <span class="type-tag">questo</span>{/if}<br /><small class="muted">ultimo uso {timeAgoLong(s.last_seen_at)} · {expiry(s)}</small></span>
            {#if !s.current}<button type="button" class="icon-btn" aria-label="Scollega questo dispositivo" onclick={() => endSession(s)}><Icon name="close" /></button>{/if}
          </div>
        {/each}
      </div>
      <p class="set-note">Se perdi un telefono, scollegalo da qui: dovrà rientrare con la password. Ogni utilizzo sposta in avanti la scadenza.</p>
    {/if}
  {/if}
</Page>
