<script>
  // Pannello di amministrazione, solo per gli amministratori: tutta la configurazione
  // dell'istanza dall'interfaccia. Ogni impostazione mostra da dove arriva il valore
  // (scelto qui, variabile d'ambiente o predefinito) e si può riportare al predefinito.
  // Restano variabili d'ambiente solo quelle che servono prima dell'avvio (vedi «Stato del sistema»).
  import Icon from "../components/Icon.svelte";
  import Page from "../components/Page.svelte";
  import AiSettings from "../sheets/AiSettings.svelte";
  import { api } from "../lib/api.js";
  import { ACCENTS, DARK_STYLES, LIGHT_STYLES, COUNTRIES, FONTS, READ_FONTS, SIZES, bytesLabel, countryName, durationLabel, flag, initials, timeAgoLong } from "../lib/format.js";
  import { ask, loadSources, session, toast, ui } from "../lib/store.svelte.js";

  let { active } = $props();

  // main · users · user · access · sources · presets · ai · defaults · status
  let page = $state("main");
  let users = $state([]);
  let invites = $state([]);
  let newLink = $state(null);
  let current = $state(null); // utente scelto nella pagina «user»
  let instance = $state(null); // impostazioni dell'istanza
  let defaults = $state(null); // { prefs, chosen } per i nuovi utenti
  let status = $state(null);
  let newTime = $state("19:00");
  let feeds = $state(null); // feed seguiti, con la nazione (#20)
  let oidcCfg = $state(null); // accesso con il provider (#22), come lo restituisce il server
  let oidcForm = $state(null); // le modifiche in corso
  let oidcBusy = $state(false);
  let oidcTest = $state(null); // { ok, message }
  let presets = $state(null); // gruppi di parole pronti
  let openPreset = $state(null);
  let presetWord = $state("");
  let newPreset = $state("");

  const me = $derived(session.user);
  const TITLES = {
    main: "Amministrazione",
    users: "Utenti e inviti",
    user: "Utente",
    access: "Sessioni",
    oidc: "Accesso con OIDC",
    sources: "Fonti e archivio",
    presets: "Gruppi di parole pronti",
    feeds: "Nazione delle fonti",
    ai: "AI",
    defaults: "Nuovi utenti",
    status: "Stato del sistema",
  };
  const SECTIONS = [
    ["users", "user", "Utenti e inviti", "Invita, disattiva, nuove password"],
    ["oidc", "key", "Accesso con OIDC", "Authentik, Authelia, Keycloak, Pocket ID…"],
    ["access", "devices", "Sessioni", "Durata delle sessioni e di «Ricordami»"],
    ["sources", "rss", "Fonti e archivio", "Conservazione, controlli, rete locale"],
    ["presets", "folder", "Gruppi di parole pronti", "Proposti a tutti negli Interessi"],
    ["ai", "spark", "AI", "Fornitore, modello e limite giornaliero"],
    ["defaults", "sliders", "Predefiniti per i nuovi utenti", "Tema, colore, font, Edizione"],
    ["status", "devices", "Stato del sistema", "Versione, spazio, errori recenti"],
  ];

  // A ogni apertura: la sottopagina chiesta (per esempio «ai» dalle Impostazioni) o il menu.
  $effect(() => {
    ui.pageTick;
    if (active) go(typeof ui.pageArg === "string" ? ui.pageArg : "main");
  });

  function go(p) {
    page = p;
    newLink = null;
    if (p === "users") loadUsers();
    if (["users", "access", "sources", "status"].includes(p)) loadInstance();
    if (p === "main") loadOidc();
    if (p === "defaults") loadDefaults();
    if (p === "presets") loadPresets();
    if (p === "feeds") loadFeeds();
    if (p === "oidc") loadOidc();
    if (p === "status") loadStatus();
  }

  function back() {
    go(page === "user" ? "users" : page === "feeds" ? "sources" : "main");
  }

  // ---- Accesso con un provider OIDC (#22) ----
  async function loadOidc() {
    try {
      oidcCfg = await api("/admin/oidc");
      oidcForm = { ...oidcCfg, client_secret: "" };
      oidcTest = null;
    } catch (err) {
      toast(err.message);
    }
  }

  async function saveOidc(e) {
    e?.preventDefault?.();
    oidcBusy = true;
    const keys = ["enabled", "issuer", "client_id", "scopes", "label", "auto_create", "link_email", "link_username", "admin_claim", "admin_value", "password_login", "rp_logout"];
    const body = Object.fromEntries(keys.map((k) => [k, oidcForm[k]]));
    if (oidcForm.client_secret) body.client_secret = oidcForm.client_secret;
    try {
      oidcCfg = await api("/admin/oidc", { method: "PUT", body });
      oidcForm = { ...oidcCfg, client_secret: "" };
      toast("Accesso con il provider salvato");
    } catch (err) {
      toast(err.message);
    } finally {
      oidcBusy = false;
    }
  }

  async function testOidc() {
    await saveOidc();
    oidcBusy = true;
    try {
      oidcTest = await api("/admin/oidc/test", { method: "POST" });
    } catch (err) {
      oidcTest = { ok: false, message: err.message };
    } finally {
      oidcBusy = false;
    }
  }

  // ---- Nazione delle fonti condivise (#20) ----
  async function loadFeeds() {
    try {
      feeds = (await api("/admin/feeds")).feeds;
    } catch (err) {
      toast(err.message);
    }
  }

  async function setFeedCountry(f, value) {
    const country = value === "__auto" ? null : value;
    try {
      feeds = (await api(`/admin/feeds/${f.id}`, { method: "PATCH", body: { country } })).feeds;
      toast(country === null ? `${f.title}: nazione automatica` : country === "" ? `${f.title}: nessuna nazione` : `${f.title}: ${countryName(country)}`);
      loadSources();
    } catch (err) {
      toast(err.message);
    }
  }

  // ---- Impostazioni dell'istanza ----
  async function loadInstance() {
    try {
      instance = (await api("/admin/settings")).settings;
    } catch (err) {
      toast(err.message);
    }
  }

  async function saveInstance(key, value, message) {
    try {
      instance = (await api("/admin/settings", { method: "PATCH", body: { [key]: value } })).settings;
      toast(message);
      if (key === "default_interval") loadSources();
    } catch (err) {
      toast(err.message);
    }
  }

  function valueLabel(opt, value) {
    if (opt.kind === "bool") return value ? "sì" : "no";
    if (opt.kind === "timezone") return value;
    return durationLabel(value, opt.unit);
  }

  function originNote(opt) {
    const fallback = valueLabel(opt, opt.env_value ?? opt.default);
    if (opt.origin === "gui") return `Scelto qui. Senza questa scelta: ${fallback}${opt.env_value != null ? ` (variabile ${opt.env})` : ""}.`;
    if (opt.origin === "env") return `Dalla variabile d'ambiente ${opt.env}: cambiandolo qui vale la scelta fatta qui.`;
    return "Valore predefinito.";
  }

  function choicesOf(opt) {
    return opt.choices.includes(opt.value) ? opt.choices : [...opt.choices, opt.value].sort((a, b) => a - b);
  }

  // Fusi orari: quelli che il browser conosce, oppure i più comuni.
  const ZONES = (() => {
    try {
      return Intl.supportedValuesOf("timeZone");
    } catch {
      return ["Europe/Rome", "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "America/New_York", "America/Los_Angeles", "Asia/Tokyo", "UTC"];
    }
  })();
  const zonesWith = (z) => (ZONES.includes(z) ? ZONES : [z, ...ZONES]);

  // ---- Utenti e inviti ----
  async function loadUsers() {
    try {
      const [u, i] = await Promise.all([api("/admin/users"), api("/admin/invites")]);
      users = u.users;
      invites = i.invites.filter((x) => x.status === "valido");
    } catch (err) {
      toast(err.message);
    }
  }

  async function invite() {
    try {
      const r = await api("/admin/invites", { method: "POST", body: {} });
      newLink = r.invite;
      await loadUsers();
    } catch (err) {
      toast(err.message);
    }
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast("Link copiato");
    } catch {
      toast("Copia non riuscita: tieni premuto sul link per copiarlo");
    }
  }

  async function share(link) {
    try {
      await navigator.share({ title: "Galactic Feed", text: "Ti invito su Galactic Feed", url: link });
    } catch {
      /* condivisione annullata */
    }
  }

  async function revoke(inv) {
    await api(`/admin/invites/${inv.id}`, { method: "DELETE" });
    toast("Invito annullato");
    loadUsers();
  }

  // Come entra un utente: account locale (password), provider OIDC o tutti e due.
  function accessLabel(u) {
    if (u.has_password && u.linked_identities) return "password e OIDC";
    if (u.linked_identities) return "OIDC";
    return "password";
  }

  function openUser(u) {
    current = u;
    newLink = null;
    page = "user";
  }

  async function updateUser(changes, message) {
    try {
      const r = await api(`/admin/users/${current.id}`, { method: "PATCH", body: changes });
      current = r.user;
      toast(message);
      loadUsers();
    } catch (err) {
      toast(err.message);
    }
  }

  async function resetLink() {
    try {
      const r = await api(`/admin/users/${current.id}/reset`, { method: "POST" });
      newLink = r.invite;
    } catch (err) {
      toast(err.message);
    }
  }

  async function removeUser() {
    if (!(await ask("Fonti, interessi e salvati di questo utente spariscono.", { title: `Eliminare l'account di ${current.display_name}?` }))) return;
    try {
      await api(`/admin/users/${current.id}`, { method: "DELETE" });
      toast("Utente eliminato");
      go("users");
    } catch (err) {
      toast(err.message);
    }
  }

  // ---- Predefiniti per i nuovi utenti ----
  async function loadDefaults() {
    try {
      defaults = await api("/admin/defaults");
    } catch (err) {
      toast(err.message);
    }
  }

  async function saveDefault(changes) {
    // Si mandano tutte le scelte già fatte più quella nuova: il server le sostituisce in blocco.
    const chosen = Object.fromEntries(defaults.chosen.map((k) => [k, defaults.prefs[k]]));
    try {
      defaults = await api("/admin/defaults", { method: "PUT", body: { ...chosen, ...changes } });
      toast("Predefinito salvato: vale per i nuovi utenti");
    } catch (err) {
      toast(err.message);
    }
  }

  async function resetDefaults() {
    try {
      defaults = await api("/admin/defaults", { method: "PUT", body: {} });
      toast("Tornati i valori predefiniti dell'app");
    } catch (err) {
      toast(err.message);
    }
  }

  function addDefaultTime() {
    const times = defaults.prefs.edition_times;
    if (!newTime || times.includes(newTime)) return;
    saveDefault({ edition_times: [...times, newTime] });
  }

  function removeDefaultTime(t) {
    const times = defaults.prefs.edition_times;
    if (times.length === 1) return toast("Serve almeno un orario");
    saveDefault({ edition_times: times.filter((x) => x !== t) });
  }

  // ---- Gruppi di parole pronti ----
  async function loadPresets() {
    try {
      presets = (await api("/admin/presets")).presets;
    } catch (err) {
      toast(err.message);
    }
  }

  async function presetRequest(path, options, message) {
    try {
      presets = (await api(path, options)).presets;
      if (message) toast(message);
      return true;
    } catch (err) {
      toast(err.message);
      return false;
    }
  }

  function patchPreset(p, changes, message) {
    return presetRequest(`/admin/presets/${p.id}`, { method: "PATCH", body: changes }, message);
  }

  function addPresetWord(e, p) {
    e.preventDefault();
    const word = presetWord.trim();
    if (!word) return;
    presetWord = "";
    patchPreset(p, { words: [...p.words, word] }, `«${word}» aggiunta a ${p.name}`);
  }

  function renamePreset(p, value) {
    const name = value.trim();
    if (name && name !== p.name) patchPreset(p, { name }, `Rinominato in ${name}`);
  }

  async function removePreset(p) {
    if (!p.builtin && !(await ask("Chi l'ha già preso tiene la sua copia.", { title: `Eliminare il gruppo pronto «${p.name}»?` }))) return;
    if (await presetRequest(`/admin/presets/${p.id}`, { method: "DELETE" }, p.builtin ? `${p.name} nascosto` : `${p.name} eliminato`)) openPreset = null;
  }

  async function createPreset(e) {
    e.preventDefault();
    const name = newPreset.trim();
    if (!name) return;
    if (await presetRequest("/admin/presets", { method: "POST", body: { name, words: [] } }, `Gruppo «${name}» creato: aggiungi le parole`)) {
      newPreset = "";
      openPreset = presets.find((x) => x.name.toLowerCase() === name.toLowerCase())?.id ?? null;
    }
  }

  // ---- Stato del sistema ----
  async function loadStatus() {
    try {
      status = await api("/admin/status");
    } catch (err) {
      toast(err.message);
    }
  }
</script>

{#snippet linkBox(link)}
  <div class="link-box">
    <input class="input mono" readonly value={link.url} aria-label="Link" onfocus={(e) => e.target.select()} />
    <div class="link-actions">
      <button type="button" class="btn-secondary" onclick={() => copy(link.url)}><Icon name="copy" />Copia</button>
      {#if navigator.share}<button type="button" class="btn-secondary" onclick={() => share(link.url)}><Icon name="upload" />Condividi</button>{/if}
    </div>
    <p class="set-note">Valido fino a {new Date(link.expires_at).toLocaleString("it-IT", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })} e utilizzabile una volta sola. Mandalo solo alla persona interessata.</p>
  </div>
{/snippet}

<!-- Un'impostazione dell'istanza: valore, origine e ritorno al predefinito. -->
{#snippet option(key, label, note, suffix = "")}
  {@const opt = instance[key]}
  <div class="set-group">
    {#if opt.kind === "bool"}
      <div class="set-row"><span>{label}</span>
        <button type="button" class="switch" role="switch" aria-checked={opt.value} aria-label={label}
          onclick={() => saveInstance(key, !opt.value, `${label}: ${opt.value ? "no" : "sì"}`)}></button>
      </div>
    {:else if opt.kind === "timezone"}
      <div class="set-row"><label for="opt-{key}">{label}</label>
        <select class="input" id="opt-{key}" value={opt.value} onchange={(e) => saveInstance(key, e.target.value, `Fuso orario: ${e.target.value}`)}>
          {#each zonesWith(opt.value) as z}<option value={z}>{z}</option>{/each}
        </select>
      </div>
    {:else}
      <div class="set-row"><label for="opt-{key}">{label}</label>
        <select class="input" id="opt-{key}" value={opt.value} onchange={(e) => saveInstance(key, Number(e.target.value), `${label}: ${durationLabel(Number(e.target.value), opt.unit)}`)}>
          {#each choicesOf(opt) as n}<option value={n}>{durationLabel(n, opt.unit)}{suffix}</option>{/each}
        </select>
      </div>
    {/if}
    {#if opt.origin === "gui"}
      <button type="button" class="set-row as-button" onclick={() => saveInstance(key, null, `${label}: valore predefinito`)}><span>Torna al valore predefinito</span><Icon name="refresh" /></button>
    {/if}
  </div>
  <p class="set-note">{note} {originNote(opt)}</p>
{/snippet}

{#snippet styleChoice(list, value, label, onpick)}
  <div class="theme-styles" role="group" aria-label={label}>
    {#each list as [k, name, bg, card, ink] (k)}
      <button type="button" class="theme-style" aria-pressed={value === k} onclick={() => onpick(k)} style="--ts-bg:{bg};--ts-card:{card};--ts-ink:{ink}">
        <span class="theme-preview" aria-hidden="true"><i></i><i></i></span>{name}
      </button>
    {/each}
  </div>
{/snippet}

{#snippet sectionSub(key, sub)}
  {#if key === "oidc" && oidcCfg}{oidcCfg.enabled ? `Attivo · ${oidcCfg.linked_users === 1 ? "1 utente collegato" : `${oidcCfg.linked_users} utenti collegati`}` : "Spento · la password resta sempre"}{:else}{sub}{/if}
{/snippet}

<Page label="Amministrazione" title={TITLES[page]} {active} back={page === "main" ? null : back}
  nav={SECTIONS.map(([k, icon, label]) => [k, icon, label])} current={page === "user" ? "users" : page === "feeds" ? "sources" : page} onnav={go} scrollKey={page}>
  {#if me?.is_admin}
    {#if page === "main"}
      <div class="set-group">
        {#each SECTIONS as [key, icon, label, sub] (key)}
          <button type="button" class="set-row as-button" onclick={() => go(key)}>
            <span class="admin-entry"><Icon name={icon} /><span><b>{label}</b><small>{@render sectionSub(key, sub)}</small></span></span>
            <Icon name="chevron" />
          </button>
        {/each}
      </div>
      <p class="set-note">Valgono per tutta l'istanza e per tutti gli utenti, subito e senza riavviare il server. Le preferenze personali restano nelle Impostazioni di ognuno.</p>
    {:else if page === "users"}
      <div class="set-label">Invita</div>
      <div class="set-group">
        <button type="button" class="link-row" onclick={invite}><Icon name="plus" />Crea un link d'invito</button>
      </div>
      {#if newLink}{@render linkBox(newLink)}{/if}
      {#if invites.length}
        <div class="set-label">Inviti in attesa</div>
        <div class="set-group">
          {#each invites as inv (inv.id)}
            <div class="set-row"><span>{inv.kind === "reset" ? `Nuova password per ${inv.target_user}` : "Invito"}<br /><small class="muted">scade {new Date(inv.expires_at).toLocaleString("it-IT", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</small></span>
              <button type="button" class="icon-btn" aria-label="Annulla l'invito" onclick={() => revoke(inv)}><Icon name="close" /></button></div>
          {/each}
        </div>
      {/if}
      <div class="set-label">Utenti</div>
      <div class="set-group">
        {#each users as u (u.id)}
          <button type="button" class="set-row as-button" onclick={() => openUser(u)}>
            <span class="who"><span class="user-av">{initials(u.display_name)}</span><span><b>{u.display_name}</b><br /><small>{u.is_admin ? "amministratore" : "utente"} · {accessLabel(u)}{u.disabled ? " · disattivato" : ""} · {u.last_seen_at ? "ultimo accesso " + timeAgoLong(u.last_seen_at) : "mai entrato"}</small></span></span>
            <Icon name="chevron" />
          </button>
        {/each}
      </div>
      {#if instance}
        <div class="set-label">Link</div>
        {@render option("invite_hours", "Validità dei link", "Per gli inviti e per i link che servono a scegliere una nuova password.")}
      {/if}
    {:else if page === "user" && current}
      <div class="set-group">
        <div class="set-row"><span class="who"><span class="user-av">{initials(current.display_name)}</span><span><b>{current.display_name}</b><br /><small>@{current.username} · {current.is_admin ? "amministratore" : "utente"} · {accessLabel(current)}{current.disabled ? " · disattivato" : ""}</small></span></span></div>
      </div>
      {#if current.id === me.id}
        <p class="set-note">Questo sei tu. Un altro amministratore può cambiare i tuoi permessi.</p>
      {:else}
        <div class="set-label">Azioni</div>
        <div class="set-group">
          <button type="button" class="link-row" onclick={resetLink}><Icon name="key" />Link per una nuova password</button>
          <button type="button" class="link-row" onclick={() => updateUser({ is_admin: !current.is_admin }, current.is_admin ? "Non è più amministratore" : "Ora è amministratore")}><Icon name="user" />{current.is_admin ? "Togli i permessi di amministratore" : "Rendi amministratore"}</button>
          <button type="button" class="link-row" onclick={() => updateUser({ disabled: !current.disabled }, current.disabled ? "Account riattivato" : "Account disattivato")}><Icon name="eye-off" />{current.disabled ? "Riattiva l'account" : "Disattiva l'account"}</button>
          <button type="button" class="link-row danger" onclick={removeUser}><Icon name="trash" />Elimina l'account</button>
        </div>
        {#if newLink}{@render linkBox(newLink)}{/if}
        <p class="set-note">{current.linked_identities && !current.has_password
          ? "Entra con il provider OIDC. Con il link per una nuova password può entrare anche con nome utente e password."
          : current.linked_identities ? "Entra con la password oppure con il provider OIDC." : "Account locale: entra con nome utente e password."}
          {current.is_admin && current.admin_via_group ? " Amministratore grazie al gruppo del provider." : ""}</p>
      {/if}
    {:else if page === "access"}
      {#if instance}
        <div class="set-label">Con «Ricordami»</div>
        {@render option("remember_days", "La sessione dura", "Dall'ultima volta che si usa l'app su quel dispositivo.")}
        <div class="set-label">Senza «Ricordami»</div>
        {@render option("session_hours", "Esce dopo", "La sessione finisce anche chiudendo il browser.", " senza usarla")}
        <p class="set-note">Le nuove durate valgono subito; le sessioni già aperte si adeguano al prossimo utilizzo.</p>
      {:else}
        <p class="loading">Carico le impostazioni…</p>
      {/if}
    {:else if page === "oidc"}
      {#snippet oidcSwitch(key, label)}
        <div class="set-row"><span>{label}</span>
          <button type="button" class="switch" role="switch" aria-checked={!!oidcForm[key]} aria-label={label} onclick={() => (oidcForm[key] = !oidcForm[key])}></button>
        </div>
      {/snippet}
      <div class="oidc-intro">
        <Icon name="key" />
        <p>Aggiunge il pulsante «Entra con …» nella pagina di accesso. <b>Non sostituisce gli account locali</b>: l'amministratore creato al primo avvio e gli utenti invitati continuano a entrare con nome utente e password. Gli utenti del provider sono account a parte, che rendi amministratori da <button type="button" class="inline-link" onclick={() => go("users")}>Utenti e inviti</button>.</p>
      </div>
      {#if oidcForm}
        <form class="form-stack" onsubmit={saveOidc}>
          <div class="set-group">{@render oidcSwitch("enabled", "Accesso con il provider")}</div>
          <div class="field"><label for="oidc-issuer">Issuer</label>
            <input class="input" id="oidc-issuer" bind:value={oidcForm.issuer} placeholder="https://auth.example.org/application/o/galactic-feed/" autocapitalize="off" spellcheck="false" inputmode="url" />
            <p class="hint">L'indirizzo del provider: l'app legge da sola /.well-known/openid-configuration. Funziona con Authentik, Authelia, Keycloak, Pocket ID e gli altri provider OpenID Connect.</p></div>
          <div class="field"><label for="oidc-client">Client ID</label>
            <input class="input" id="oidc-client" bind:value={oidcForm.client_id} autocapitalize="off" spellcheck="false" /></div>
          <div class="field"><label for="oidc-secret">Client secret</label>
            <input class="input" id="oidc-secret" type="password" autocomplete="new-password" bind:value={oidcForm.client_secret}
              placeholder={oidcCfg.has_secret ? "Salvato: lascia vuoto per non cambiarlo" : "Il segreto del client"} />
            <p class="hint">Salvato cifrato; non viene mai mostrato né restituito.</p></div>
          <div class="field"><label for="oidc-redirect">Indirizzo di ritorno (da copiare nel provider)</label>
            <input class="input mono" id="oidc-redirect" readonly value={oidcCfg.redirect_uri} onfocus={(e) => e.target.select()} />
            <p class="hint">Si basa su PUBLIC_URL. Nel provider va registrato esattamente così.</p></div>
          <div class="field"><label for="oidc-scopes">Scope</label>
            <input class="input" id="oidc-scopes" bind:value={oidcForm.scopes} autocapitalize="off" spellcheck="false" /></div>
          <div class="field"><label for="oidc-label">Testo del pulsante</label>
            <input class="input" id="oidc-label" bind:value={oidcForm.label} maxlength="40" placeholder="Entra con Authentik" /></div>

          <span class="sublabel">Utenti</span>
          <div class="set-group">
            {@render oidcSwitch("auto_create", "Crea gli utenti al primo accesso")}
            {@render oidcSwitch("link_email", "Collega gli utenti con la stessa email verificata")}
            {@render oidcSwitch("link_username", "Collega gli utenti con lo stesso nome utente")}
          </div>
          <p class="hint">Senza la creazione automatica serve ancora un invito; poi ognuno collega il suo account da Impostazioni → Account collegati. Il collegamento automatico non tocca mai gli amministratori: l'amministratore locale resta un account a parte (se vuoi, lo colleghi a mano dalle sue Impostazioni).</p>
          <div class="two-selects">
            <div class="field"><label for="oidc-claim">Claim dei gruppi</label><input class="input" id="oidc-claim" bind:value={oidcForm.admin_claim} placeholder="groups" autocapitalize="off" spellcheck="false" /></div>
            <div class="field"><label for="oidc-admin">Gruppo degli amministratori</label><input class="input" id="oidc-admin" bind:value={oidcForm.admin_value} placeholder="galactic-admin" autocapitalize="off" spellcheck="false" /></div>
          </div>
          <p class="hint">Facoltativo: chi è nel gruppo diventa amministratore. Uscendo dal gruppo perde solo i permessi che gli aveva dato il gruppo: chi rendi amministratore a mano da Utenti e inviti resta tale.</p>

          <span class="sublabel">Uscita</span>
          <div class="set-group">
            {@render oidcSwitch("rp_logout", "Uscendo, esci anche dal provider")}
          </div>

          <details class="advanced">
            <summary>Avanzate: solo provider</summary>
            <div class="set-group">
              {@render oidcSwitch("password_login", "Accesso anche con nome utente e password")}
            </div>
            <p class="hint">Lascialo acceso per tenere l'accesso locale. Spento, nella pagina di accesso resta solo il pulsante del provider; serve almeno un amministratore collegato al provider (ora: {oidcCfg.linked_admins}). Se il provider non risponde: <code>docker compose exec galactic-feed python -m app.emergency</code> riaccende la password, oppure la variabile EMERGENCY_PASSWORD_LOGIN=true.{#if oidcCfg.emergency} Adesso è attiva.{/if}</p>
          </details>

          <button type="submit" class="btn-primary" disabled={oidcBusy}><Icon name="check" />Salva</button>
          <button type="button" class="btn-secondary" disabled={oidcBusy || !oidcForm.issuer || !oidcForm.client_id} onclick={testOidc}><Icon name="refresh" />Prova la configurazione</button>
          {#if oidcTest}<p class={oidcTest.ok ? "form-ok" : "form-error"} role="status">{oidcTest.message}</p>{/if}
          <p class="set-note">{oidcCfg.linked_users === 1 ? "1 utente collegato" : `${oidcCfg.linked_users} utenti collegati`} al provider.</p>
        </form>
      {:else}
        <p class="loading">Carico l'accesso con il provider…</p>
      {/if}
    {:else if page === "sources"}
      {#if instance}
        <div class="set-label">Archivio</div>
        {@render option("retention_days", "Conserva gli articoli", "Dopo, quelli non salvati si cancellano. I salvati restano sempre.")}
        <div class="set-label">Fonti nuove</div>
        {@render option("default_interval", "Controlla ogni", "Proposto per le fonti aggiunte da ora, anche con l'OPML. Ognuno lo può cambiare per le sue fonti.")}
        <div class="set-label">Rete</div>
        {@render option("block_private_networks", "Vieta le fonti nella rete locale", "Con il sì non si possono seguire indirizzi della rete di casa (192.168.…, 10.…, localhost).")}
        <div class="set-label">Nazioni</div>
        <div class="set-group">
          <button type="button" class="set-row as-button" onclick={() => go("feeds")}><span>Nazione delle fonti condivise</span><Icon name="chevron" /></button>
        </div>
        <p class="set-note">L'app la propone dal dominio e dalla lingua del feed; qui la correggi per tutti. Ognuno può comunque sceglierla per sé.</p>
      {:else}
        <p class="loading">Carico le impostazioni…</p>
      {/if}
    {:else if page === "feeds"}
      {#if feeds}
        {#if feeds.length}
          <div class="set-group">
            {#each feeds as f (f.id)}
              <div class="set-row"><span class="feed-name"><b>{f.title}</b><small>{f.followers === 1 ? "1 utente" : `${f.followers} utenti`}{f.language ? ` · lingua ${f.language}` : ""}</small></span>
                <select class="input" aria-label="Nazione di {f.title}" value={f.country_admin ?? "__auto"} onchange={(e) => setFeedCountry(f, e.target.value)}>
                  <option value="__auto">{f.country_auto ? `${flag(f.country_auto)} ${countryName(f.country_auto)} (proposta)` : "Non riconosciuta"}</option>
                  {#each (f.country_admin && !COUNTRIES.includes(f.country_admin) ? [f.country_admin, ...COUNTRIES] : COUNTRIES) as c (c)}<option value={c}>{flag(c)} {countryName(c)}</option>{/each}
                  <option value="">Nessuna</option>
                </select>
              </div>
            {/each}
          </div>
        {:else}
          <p class="set-note">Ancora nessuna fonte seguita.</p>
        {/if}
      {:else}
        <p class="loading">Carico le fonti…</p>
      {/if}
    {:else if page === "presets"}
      {#if presets}
        <p class="set-note top">Ogni utente li trova negli Interessi e li accende come interesse o per silenziare con un tocco. Le modifiche valgono per chi li prende da adesso: chi li usa già tiene la sua copia.</p>
        <div class="set-group">
          {#each presets as p (p.id)}
            <div class="preset" class:is-hidden={p.hidden}>
              <div class="set-row">
                <button type="button" class="preset-name" aria-expanded={openPreset === p.id} onclick={() => (openPreset = openPreset === p.id ? null : p.id)}>
                  <b>{p.name}</b><small>{p.words.length === 1 ? "1 parola" : `${p.words.length} parole`}{p.builtin ? " · fornito con l'app" : ""}</small>
                </button>
                <button type="button" class="switch" role="switch" aria-checked={!p.hidden} aria-label="Proponi {p.name}"
                  onclick={() => patchPreset(p, { hidden: !p.hidden }, p.hidden ? `${p.name} di nuovo proposto` : `${p.name} nascosto`)}></button>
              </div>
              {#if openPreset === p.id}
                <div class="preset-body">
                  <input class="input" value={p.name} aria-label="Nome del gruppo" maxlength="40" onchange={(e) => renamePreset(p, e.target.value)} />
                  <div class="tags">
                    {#each p.words as w (w)}
                      <button type="button" class="tag" aria-label="Togli {w}" onclick={() => patchPreset(p, { words: p.words.filter((x) => x !== w) }, `«${w}» tolta`)}>{w}<Icon name="close" /></button>
                    {/each}
                  </div>
                  <form class="add-inline" onsubmit={(e) => addPresetWord(e, p)}>
                    <input bind:value={presetWord} placeholder="Parola da aggiungere" autocomplete="off" aria-label="Nuova parola per {p.name}" maxlength="60" />
                    <button type="submit">Aggiungi</button>
                  </form>
                  {#if !p.builtin}
                    <button type="button" class="link-row danger" onclick={() => removePreset(p)}><Icon name="trash" />Elimina il gruppo pronto</button>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
        <form class="add-inline mt" onsubmit={createPreset}>
          <input bind:value={newPreset} placeholder="Nome di un gruppo pronto nuovo" autocomplete="off" aria-label="Nome del nuovo gruppo pronto" maxlength="40" />
          <button type="submit">Crea</button>
        </form>
        <p class="set-note">Quelli forniti con l'app non si cancellano: si spengono e non vengono più proposti.</p>
      {:else}
        <p class="loading">Carico i gruppi…</p>
      {/if}
    {:else if page === "ai"}
      <AiSettings />
    {:else if page === "defaults"}
      {#if defaults}
        {@const p = defaults.prefs}
        <p class="set-note top">Le preferenze con cui parte chi si iscrive da adesso. Chi ha già un account non cambia; ognuno poi sceglie per sé nelle Impostazioni.</p>
        <div class="set-label">Aspetto</div>
        <div class="set-group">
          <div class="set-row"><span>Tema</span>
            <div class="segmented" style="--cols:3" role="group" aria-label="Tema predefinito">
              {#each [["auto", "Auto"], ["light", "Chiaro"], ["dark", "Scuro"]] as [k, l]}
                <button type="button" aria-pressed={p.theme === k} onclick={() => saveDefault({ theme: k })}>{l}</button>
              {/each}
            </div>
          </div>
          <div class="set-block">
            <span class="label">Scuro</span>
            {@render styleChoice(DARK_STYLES, p.dark_style, "Variante del tema scuro predefinita", (k) => saveDefault({ dark_style: k }))}
          </div>
          <div class="set-block">
            <span class="label">Chiaro</span>
            {@render styleChoice(LIGHT_STYLES, p.light_style, "Variante del tema chiaro predefinita", (k) => saveDefault({ light_style: k }))}
          </div>
          <div class="set-block">
            <span class="label" id="def-accent">Colore</span>
            <div class="swatches" role="group" aria-labelledby="def-accent">
              {#each ACCENTS as c (c.key)}
                <button type="button" class="swatch" style="--sw-l:{c.light};--sw-d:{c.dark}" aria-pressed={p.accent === c.key} aria-label={c.name} title={c.name} onclick={() => saveDefault({ accent: c.key })}><Icon name="check" /></button>
              {/each}
              <button type="button" class="swatch is-system" aria-pressed={p.accent === "system"} aria-label="Colore del sistema" title="Colore del sistema" onclick={() => saveDefault({ accent: "system" })}><Icon name="check" /></button>
            </div>
          </div>
          <div class="set-block">
            <span class="label" id="def-font">Font</span>
            <div class="tags" role="group" aria-labelledby="def-font">
              {#each FONTS as [k, label, family] (k)}
                <button type="button" class="tag" style="font-family:{family}" aria-pressed={p.font === k} onclick={() => saveDefault({ font: k })}>{label}</button>
              {/each}
            </div>
          </div>
          <div class="set-block">
            <span class="label" id="def-read">Testo degli articoli</span>
            <div class="tags" role="group" aria-labelledby="def-read">
              {#each READ_FONTS as [k, label, family] (k)}
                <button type="button" class="tag" style="font-family:{family}" aria-pressed={p.font_read === k} onclick={() => saveDefault({ font_read: k })}>{label}</button>
              {/each}
            </div>
          </div>
          <div class="set-row"><span>Dimensione del testo</span>
            <div class="segmented" style="--cols:3" role="group" aria-label="Dimensione del testo predefinita">
              {#each SIZES as [v, l]}
                <button type="button" aria-pressed={p.text_size === v} onclick={() => saveDefault({ text_size: v })}>{l}</button>
              {/each}
            </div>
          </div>
        </div>

        <div class="set-label">Lettura</div>
        <div class="set-group">
          <div class="set-row"><span>Unisci i doppioni</span>
            <button type="button" class="switch" role="switch" aria-checked={p.dedupe} aria-label="Unisci i doppioni" onclick={() => saveDefault({ dedupe: !p.dedupe })}></button>
          </div>
          <div class="set-row"><span>Riassunti automatici</span>
            <button type="button" class="switch" role="switch" aria-checked={p.summaries} aria-label="Riassunti automatici" onclick={() => saveDefault({ summaries: !p.summaries })}></button>
          </div>
        </div>

        <div class="set-label">Edizione</div>
        <div class="set-group">
          <div class="set-row"><span>Edizione accesa</span>
            <button type="button" class="switch" role="switch" aria-checked={p.edition} aria-label="Edizione accesa per i nuovi utenti" onclick={() => saveDefault({ edition: !p.edition })}></button>
          </div>
          <div class="set-block">
            <span class="label">Orari</span>
            <div class="tags">
              {#each p.edition_times as t (t)}
                <button type="button" class="tag mono" aria-label="Togli l'orario {t}" onclick={() => removeDefaultTime(t)}>{t}<Icon name="close" /></button>
              {/each}
              {#if p.edition_times.length < 6}
                <span class="time-add">
                  <input type="time" class="input time-input" aria-label="Nuovo orario predefinito" bind:value={newTime} />
                  <button type="button" class="tag" onclick={addDefaultTime}><Icon name="plus" />Orario</button>
                </span>
              {/if}
            </div>
          </div>
        </div>
        {#if defaults.chosen.length}
          <div class="set-group mt">
            <button type="button" class="set-row as-button" onclick={resetDefaults}><span>Torna ai predefiniti dell'app</span><Icon name="refresh" /></button>
          </div>
        {/if}
        <div class="set-group mt">
          <button type="button" class="set-row as-button" onclick={() => go("presets")}><span>Gruppi di parole pronti</span><Icon name="chevron" /></button>
        </div>
        <p class="set-note">I nuovi utenti trovano i gruppi pronti negli Interessi e li accendono con un tocco.</p>
      {:else}
        <p class="loading">Carico i predefiniti…</p>
      {/if}
    {:else if page === "status"}
      {#if status}
        <div class="set-group">
          <div class="set-row"><span>Versione</span><span class="val">{status.version}</span></div>
          <div class="set-row"><span>Utenti</span><span class="val">{status.users}</span></div>
          <div class="set-row"><span>Feed</span><span class="val">{status.feeds}</span></div>
          <div class="set-row"><span>Articoli</span><span class="val">{status.articles}</span></div>
          <div class="set-row"><span>Database</span><span class="val">{bytesLabel(status.database_bytes)}</span></div>
          <div class="set-row"><span>Ultimo controllo dei feed</span><span class="val">{status.last_fetch_at ? timeAgoLong(status.last_fetch_at) : "—"}</span></div>
          <div class="set-row"><span>Ultimo giro dello scheduler</span><span class="val">{status.scheduler_last_run_at ? timeAgoLong(status.scheduler_last_run_at) : "—"}</span></div>
        </div>
        {#if instance}
          <div class="set-label">Orari</div>
          {@render option("timezone", "Fuso orario", "Per gli orari dell'Edizione.")}
        {/if}

        <div class="set-label">Errori recenti</div>
        {#if status.recent_errors.length || status.ai_error}
          <div class="set-group">
            {#each status.recent_errors as e (e.url)}
              <div class="set-row"><span>{e.title}<br /><small class="muted">{e.error} · {e.followers === 1 ? "1 utente" : `${e.followers} utenti`}</small></span></div>
            {/each}
            {#if status.ai_error}
              <div class="set-row"><span>AI<br /><small class="muted">{status.ai_error.message}{status.ai_error.at ? ` · ${timeAgoLong(status.ai_error.at)}` : ""}</small></span></div>
            {/if}
          </div>
          {#if status.feeds_with_errors > status.recent_errors.length}<p class="set-note">E altri {status.feeds_with_errors - status.recent_errors.length} feed con errori.</p>{/if}
        {:else}
          <p class="set-note">Nessun errore: tutti i feed rispondono.</p>
        {/if}

        <div class="set-label">Solo all'avvio</div>
        <div class="set-group">
          {#each Object.entries(status.environment) as [name, value] (name)}
            <div class="set-row"><span class="mono small">{name}</span><span class="val ellipsis" title={value}>{value}</span></div>
          {/each}
        </div>
        <p class="set-note">Queste si cambiano solo con le variabili d'ambiente nel docker-compose.yml, poi riavviando il container: servono prima che il server parta.</p>
      {:else}
        <p class="loading">Carico lo stato…</p>
      {/if}
    {/if}
  {/if}
</Page>
