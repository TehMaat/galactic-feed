<script>
  // Impostazioni, con le stesse sezioni del mockup. Edizione, notifiche e AI arrivano con la
  // seconda versione: le sezioni si vedono già, spente.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import AiSettings from "./AiSettings.svelte";
  import { folderColor } from "../lib/format.js";
  import { currentSubscription, disablePush, enablePush, isIos, isStandalone } from "../lib/push.js";
  import { api } from "../lib/api.js";
  import { ACCENTS, initials, timeAgoLong } from "../lib/format.js";
  import { data, logout, savePrefs, session, toast, ui } from "../lib/store.svelte.js";

  let page = $state("main"); // main · users · user · access · ai · password · sessions
  let users = $state([]);
  let invites = $state([]);
  let newLink = $state(null);
  let current = $state(null); // utente scelto nella pagina «user»
  let sessions = $state([]);
  let pw = $state({ current: "", next: "", repeat: "" });
  let pwError = $state("");
  let instance = $state(null); // impostazioni dell'istanza (solo amministratore)

  $effect(() => {
    if (ui.sheet === "settings") {
      page = "main";
      newLink = null;
    }
  });

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
    if (ui.sheet === "settings") currentSubscription().then((s) => (pushOn = !!s));
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
  const times = $derived(me?.prefs?.edition_times || ["07:30"]);
  let newTime = $state("19:00");

  async function addTime() {
    if (!newTime) return;
    if (times.includes(newTime)) return toast(`L'edizione delle ${newTime} c'è già`);
    if (await savePrefs({ edition_times: [...times, newTime] })) toast(`Nuova edizione alle ${newTime}`);
  }

  async function removeTime(t) {
    if (times.length === 1) return toast("Serve almeno un orario, oppure spegni l'Edizione");
    if (await savePrefs({ edition_times: times.filter((x) => x !== t) })) toast(`Edizione delle ${t} tolta`);
  }
  const theme = $derived(me?.prefs?.theme || "auto");
  const accent = $derived(me?.prefs?.accent || "galassia");
  const systemAccent = typeof CSS !== "undefined" && CSS.supports?.("color", "AccentColor");
  const font = $derived(me?.prefs?.font || "galactic");
  const fontRead = $derived(me?.prefs?.font_read || "serif");
  // Ogni scelta è scritta nel suo font, così si vede subito com'è.
  const FONTS = [
    ["galactic", "Galactic", "var(--font-brand)"],
    ["sistema", "Sistema", "var(--font-system)"],
    ["inter", "Inter", '"Inter Variable", var(--font-system)'],
    ["leggibile", "Alta leggibilità", '"Atkinson Hyperlegible", var(--font-system)'],
  ];
  const READ_FONTS = [
    ["serif", "Serif", '"Newsreader", Georgia, serif'],
    ["sans", "Come l'interfaccia", "var(--font-ui)"],
    ["sistema", "Sistema", "var(--font-system)"],
  ];
  const SIZES = [[0.92, "Piccolo"], [1, "Normale"], [1.12, "Grande"]];
  const lastCheck = $derived(
    data.sources.map((s) => s.last_fetch_at).filter(Boolean).sort().at(-1) || null,
  );
  const ai = $derived(data.interests.ai);
  const aiLabel = $derived(ai?.enabled ? `${ai.kind === "locale" ? "Locale" : "Cloud"} · ${ai.label}` : "Spenta");
  const TITLES = { ai: "AI", access: "Accesso", main: "Impostazioni", users: "Utenti e inviti", user: "Utente", password: "Cambia password", sessions: "Dispositivi collegati" };

  function go(p) {
    page = p;
    if (p === "users") loadUsers();
    if (p === "sessions") loadSessions();
    if (p === "access") loadInstance();
    if (p === "password") {
      pw = { current: "", next: "", repeat: "" };
      pwError = "";
    }
  }

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
    if (!confirm(`Eliminare l'account di ${current.display_name}? Fonti, interessi e salvati di questo utente spariscono.`)) return;
    try {
      await api(`/admin/users/${current.id}`, { method: "DELETE" });
      toast("Utente eliminato");
      go("users");
    } catch (err) {
      toast(err.message);
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

  // ---- Accesso (amministratore): durata delle sessioni ----
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
    } catch (err) {
      toast(err.message);
    }
  }

  function durationLabel(n, unit) {
    if (unit === "ore") return n === 1 ? "1 ora" : `${n} ore`;
    if (n === 7) return "1 settimana";
    if (n === 365) return "1 anno";
    return n === 1 ? "1 giorno" : `${n} giorni`;
  }

  function originNote(opt) {
    if (opt.origin === "gui") return `Scelto qui. Predefinito: ${durationLabel(opt.env_value ?? opt.default, opt.unit)}.`;
    if (opt.origin === "env") return `Dalla variabile d'ambiente ${opt.env}.`;
    return "Valore predefinito.";
  }

  function choicesOf(opt) {
    return opt.choices.includes(opt.value) ? opt.choices : [...opt.choices, opt.value].sort((a, b) => a - b);
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

<Sheet name="settings" title={TITLES[page]} back={page === "main" ? null : () => go(page === "user" ? "users" : "main")}>
  {#if me}
    {#if page === "main"}
      <div class="set-label">Account</div>
      <div class="set-group">
        <div class="set-row">
          <span class="who"><span class="user-av">{initials(me.display_name)}</span><span><b>{me.display_name}</b><br /><small>{me.is_admin ? "amministratore" : "utente"} · @{me.username}</small></span></span>
        </div>
        {#if me.is_admin}
          <button type="button" class="link-row" onclick={() => go("users")}><Icon name="plus" />Utenti e inviti</button>
          <button type="button" class="link-row" onclick={() => go("access")}><Icon name="key" />Accesso e durata delle sessioni</button>
        {/if}
        <button type="button" class="link-row" onclick={() => go("password")}><Icon name="key" />Cambia password</button>
        <button type="button" class="link-row" onclick={() => go("sessions")}><Icon name="devices" />Dispositivi collegati</button>
        <button type="button" class="link-row" onclick={logout}><Icon name="logout" />Esci</button>
      </div>
      <p class="set-note">Ogni utente ha fonti, interessi, letti e salvati propri. I feed in comune vengono scaricati una volta sola.</p>

      <div class="set-label">Edizione</div>
      <div class="set-group">
        <div class="set-row"><span>Componi l'Edizione</span>
          <button type="button" class="switch" role="switch" aria-checked={edOn} aria-label="Componi l'Edizione" onclick={() => savePrefs({ edition: !edOn })}></button>
        </div>
        {#if edOn}
          <div class="set-block">
            <span class="label">Orari</span>
            <div class="tags">
              {#each times as t (t)}
                <button type="button" class="tag mono" aria-label="Togli l'edizione delle {t}" onclick={() => removeTime(t)}>{t}<Icon name="close" /></button>
              {/each}
              {#if times.length < 6}
                <span class="time-add">
                  <input type="time" class="input time-input" aria-label="Nuovo orario" bind:value={newTime} />
                  <button type="button" class="tag" onclick={addTime}><Icon name="plus" />Orario</button>
                </span>
              {/if}
            </div>
          </div>
        {/if}
      </div>
      <p class="set-note">{edOn ? "Una selezione delle notizie per te a ogni orario, da leggere nell'app (niente email)." : "Senza Edizione la schermata Oggi mostra solo il Flusso."}</p>

      <div class="set-label">Notifiche</div>
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

      <div class="set-label">AI</div>
      <div class="set-group">
        {#if me.is_admin}
          <button type="button" class="set-row as-button" onclick={() => go("ai")}><span>Fornitore</span><span class="val">{aiLabel}</span></button>
        {:else}
          <div class="set-row"><span>Fornitore</span><span class="val">{aiLabel}</span></div>
        {/if}
      </div>
      <p class="set-note">{ai?.enabled ? "Filtri e riassunti si scelgono negli Interessi." : me.is_admin ? "Filtri e riassunti con un modello locale (Ollama) o con un servizio cloud, a scelta." : "L'AI la configura l'amministratore."}</p>

      <div class="set-label">Aspetto</div>
      <div class="set-group">
        <div class="set-row"><span>Tema</span>
          <div class="segmented" style="--cols:3" role="group" aria-label="Tema">
            {#each [["auto", "Auto"], ["light", "Chiaro"], ["dark", "Scuro"]] as [k, l]}
              <button type="button" aria-pressed={theme === k} onclick={() => savePrefs({ theme: k })}>{l}</button>
            {/each}
          </div>
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
          : "Tema, colore, font e dimensione del testo valgono su tutti i tuoi dispositivi. «Galactic» usa Unbounded per i titoli; «Sistema» il font del dispositivo."}
      </p>

      <div class="set-label">Server</div>
      <div class="set-group">
        <div class="set-row"><span>Indirizzo</span><span class="val">{location.host}</span></div>
        <div class="set-row"><span>Controllo delle fonti</span><span class="val">da 15 min a 24 h</span></div>
        <div class="set-row"><span>Ultimo controllo</span><span class="val">{lastCheck ? timeAgoLong(lastCheck) : "—"}</span></div>
      </div>

      <div class="set-label">Dati</div>
      <div class="set-group"><a class="link-row" href="/api/opml/export" download><Icon name="download" />Esporta le fonti (OPML)</a></div>
      <p class="set-note">Galactic Feed {session.version} · sola lettura: niente commenti né voti, solo il link all'articolo originale.</p>
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
            <span class="who"><span class="user-av">{initials(u.display_name)}</span><span><b>{u.display_name}</b><br /><small>{u.is_admin ? "amministratore" : "utente"}{u.disabled ? " · disattivato" : ""} · {u.last_seen_at ? "ultimo accesso " + timeAgoLong(u.last_seen_at) : "mai entrato"}</small></span></span>
            <Icon name="chevron" />
          </button>
        {/each}
      </div>
    {:else if page === "user" && current}
      <div class="set-group">
        <div class="set-row"><span class="who"><span class="user-av">{initials(current.display_name)}</span><span><b>{current.display_name}</b><br /><small>@{current.username} · {current.is_admin ? "amministratore" : "utente"}{current.disabled ? " · disattivato" : ""}</small></span></span></div>
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
      {/if}
    {:else if page === "access"}
      {#if instance}
        {@const rem = instance.remember_days}
        {@const ses = instance.session_hours}
        <div class="set-label">Con «Ricordami»</div>
        <div class="set-group">
          <div class="set-row"><label for="remember-days">La sessione dura</label>
            <select class="input" id="remember-days" value={rem.value} onchange={(e) => saveInstance("remember_days", Number(e.target.value), "Durata di «Ricordami» aggiornata")}>
              {#each choicesOf(rem) as n}<option value={n}>{durationLabel(n, rem.unit)}</option>{/each}
            </select>
          </div>
          {#if rem.origin === "gui"}
            <button type="button" class="set-row as-button" onclick={() => saveInstance("remember_days", null, "Durata predefinita")}><span>Torna al valore predefinito</span><Icon name="refresh" /></button>
          {/if}
        </div>
        <p class="set-note">Dall'ultima volta che si usa l'app su quel dispositivo. {originNote(rem)}</p>

        <div class="set-label">Senza «Ricordami»</div>
        <div class="set-group">
          <div class="set-row"><label for="session-hours">Esce dopo</label>
            <select class="input" id="session-hours" value={ses.value} onchange={(e) => saveInstance("session_hours", Number(e.target.value), "Durata delle sessioni aggiornata")}>
              {#each choicesOf(ses) as n}<option value={n}>{durationLabel(n, ses.unit)} senza usarla</option>{/each}
            </select>
          </div>
          {#if ses.origin === "gui"}
            <button type="button" class="set-row as-button" onclick={() => saveInstance("session_hours", null, "Durata predefinita")}><span>Torna al valore predefinito</span><Icon name="refresh" /></button>
          {/if}
        </div>
        <p class="set-note">La sessione finisce anche chiudendo il browser. {originNote(ses)} Le nuove durate valgono subito; le sessioni già aperte si adeguano al prossimo utilizzo.</p>
      {:else}
        <p class="loading">Carico le impostazioni…</p>
      {/if}
    {:else if page === "ai"}
      <AiSettings />
    {:else if page === "password"}
      <form class="form-stack" onsubmit={changePassword}>
        <div class="field"><label for="pw-cur">Password attuale</label><input class="input" id="pw-cur" type="password" autocomplete="current-password" bind:value={pw.current} /></div>
        <div class="field"><label for="pw-new">Nuova password</label><input class="input" id="pw-new" type="password" autocomplete="new-password" minlength="8" bind:value={pw.next} /></div>
        <div class="field"><label for="pw-rep">Ripeti la nuova password</label><input class="input" id="pw-rep" type="password" autocomplete="new-password" minlength="8" bind:value={pw.repeat} /></div>
        <p class="hint">Almeno 8 caratteri. Una frase di più parole è facile da ricordare e difficile da indovinare.</p>
        {#if pwError}<p class="form-error" role="alert">{pwError}</p>{/if}
        <button type="submit" class="btn-primary" disabled={!pw.current || pw.next.length < 8}><Icon name="check" />Cambia password</button>
      </form>
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
</Sheet>
