<script>
  // Impostazioni, con le stesse sezioni del mockup. Edizione, notifiche e AI arrivano con la
  // seconda versione: le sezioni si vedono già, spente.
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import { api } from "../lib/api.js";
  import { initials, timeAgoLong } from "../lib/format.js";
  import { TEXT_SIZES, data, logout, savePrefs, session, toast, ui } from "../lib/store.svelte.js";

  let page = $state("main"); // main · users · user · password · sessions
  let users = $state([]);
  let invites = $state([]);
  let newLink = $state(null);
  let current = $state(null); // utente scelto nella pagina «user»
  let sessions = $state([]);
  let pw = $state({ current: "", next: "", repeat: "" });
  let pwError = $state("");

  $effect(() => {
    if (ui.sheet === "settings") {
      page = "main";
      newLink = null;
    }
  });

  const me = $derived(session.user);
  const theme = $derived(me?.prefs?.theme || "auto");
  const lastCheck = $derived(
    data.sources.map((s) => s.last_fetch_at).filter(Boolean).sort().at(-1) || null,
  );
  const TITLES = { main: "Impostazioni", users: "Utenti e inviti", user: "Utente", password: "Cambia password", sessions: "Dispositivi collegati" };

  function go(p) {
    page = p;
    if (p === "users") loadUsers();
    if (p === "sessions") loadSessions();
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

  function device(ua) {
    const os = /iPhone/.test(ua) ? "iPhone" : /iPad/.test(ua) ? "iPad" : /Android/.test(ua) ? "Android" : /Mac OS X|Macintosh/.test(ua) ? "Mac" : /Windows/.test(ua) ? "Windows" : /Linux/.test(ua) ? "Linux" : "Dispositivo";
    const br = /Edg\//.test(ua) ? "Edge" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "";
    return br ? `${os} · ${br}` : os;
  }

  function nextTextSize() {
    const i = TEXT_SIZES.indexOf(me.prefs.text_size);
    savePrefs({ text_size: TEXT_SIZES[(i + 1) % TEXT_SIZES.length] });
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
        {/if}
        <button type="button" class="link-row" onclick={() => go("password")}><Icon name="key" />Cambia password</button>
        <button type="button" class="link-row" onclick={() => go("sessions")}><Icon name="devices" />Dispositivi collegati</button>
        <button type="button" class="link-row" onclick={logout}><Icon name="logout" />Esci</button>
      </div>
      <p class="set-note">Ogni utente ha fonti, interessi, letti e salvati propri. I feed in comune vengono scaricati una volta sola.</p>

      <div class="set-label">Edizione</div>
      <div class="set-group is-later">
        <div class="set-row"><span>Componi l'Edizione</span><button type="button" class="switch" role="switch" aria-checked="false" aria-label="Componi l'Edizione" disabled></button></div>
      </div>
      <p class="set-note">Nella prossima versione: un'edizione in stile newsletter agli orari che scegli, da leggere nell'app.</p>

      <div class="set-label">Notifiche</div>
      <div class="set-group is-later">
        <div class="set-row"><span>Notizie importanti</span><button type="button" class="switch" role="switch" aria-checked="false" aria-label="Notifiche per le notizie importanti" disabled></button></div>
      </div>
      <p class="set-note">Nella prossima versione. Su iPhone le notifiche arrivano solo se l'app è aggiunta alla schermata Home (iOS 16.4 o successivo).</p>

      <div class="set-label">AI</div>
      <div class="set-group is-later">
        <div class="set-row"><span>Fornitore</span>
          <div class="segmented" role="group" aria-label="Fornitore AI"><button type="button" aria-pressed="false" disabled>Locale</button><button type="button" aria-pressed="false" disabled>Cloud</button></div>
        </div>
      </div>
      <p class="set-note">Nella prossima versione: filtri e riassunti con un modello locale (Ollama) o con un servizio cloud, a scelta.</p>

      <div class="set-label">Aspetto</div>
      <div class="set-group">
        <div class="set-row"><span>Tema</span>
          <div class="segmented" style="--cols:3" role="group" aria-label="Tema">
            {#each [["auto", "Auto"], ["light", "Chiaro"], ["dark", "Scuro"]] as [k, l]}
              <button type="button" aria-pressed={theme === k} onclick={() => savePrefs({ theme: k })}>{l}</button>
            {/each}
          </div>
        </div>
        <button type="button" class="set-row as-button" onclick={nextTextSize}><span>Dimensione del testo</span><span class="val">{Math.round((me.prefs.text_size || 1) * 100)}%</span></button>
      </div>

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
          <div class="set-row"><span>{device(s.user_agent)}{#if s.current} <span class="type-tag">questo</span>{/if}<br /><small class="muted">ultimo uso {timeAgoLong(s.last_seen_at)}</small></span>
            {#if !s.current}<button type="button" class="icon-btn" aria-label="Scollega questo dispositivo" onclick={() => endSession(s)}><Icon name="close" /></button>{/if}
          </div>
        {/each}
      </div>
      <p class="set-note">Se perdi un telefono, scollegalo da qui: dovrà rientrare con la password.</p>
    {/if}
  {/if}
</Sheet>
