<script>
  // Primo avvio, accesso, invito e nuova password: stesso stile della testata del mockup.
  import { onMount } from "svelte";
  import Icon from "../components/Icon.svelte";
  import { api } from "../lib/api.js";
  import { paintStars } from "../lib/art.js";
  import { checkSession, enter, session } from "../lib/store.svelte.js";

  let stars = $state();
  let busy = $state(false);
  let error = $state("");
  let f = $state({ code: "", display_name: "", username: "", password: "", repeat: "" });

  const mode = $derived(session.phase);
  const linkBroken = $derived((mode === "invite" || mode === "reset") && !session.invite);

  onMount(() => {
    const paint = () => stars && paintStars(stars, 214);
    paint();
    window.addEventListener("resize", paint);
    return () => window.removeEventListener("resize", paint);
  });

  async function submit(e) {
    e.preventDefault();
    error = "";
    if ((mode === "reset" || mode === "setup" || mode === "invite") && f.password !== f.repeat) {
      error = "Le due password non coincidono.";
      return;
    }
    busy = true;
    try {
      let r;
      if (mode === "setup") {
        r = await api("/auth/setup", { method: "POST", body: { code: f.code.trim(), username: f.username.trim(), display_name: f.display_name.trim(), password: f.password } });
      } else if (mode === "login") {
        r = await api("/auth/login", { method: "POST", body: { username: f.username.trim(), password: f.password }, quiet401: true });
      } else if (mode === "invite") {
        r = await api(`/invites/${session.token}/accept`, { method: "POST", body: { username: f.username.trim(), display_name: f.display_name.trim(), password: f.password } });
      } else {
        r = await api(`/invites/${session.token}/accept`, { method: "POST", body: { password: f.password } });
      }
      enter(r.user, { goHome: true });
    } catch (err) {
      error = err.message;
    } finally {
      busy = false;
    }
  }

  function toLogin() {
    history.replaceState({ gf: true }, "", "/");
    session.token = null;
    session.invite = null;
    session.inviteError = "";
    session.phase = "loading";
    checkSession();
  }

  const date = new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  const greeting = (() => {
    const h = new Date().getHours();
    return h < 13 ? "Buongiorno." : h < 18 ? "Buon pomeriggio." : "Buonasera.";
  })();
</script>

<div class="auth">
  <div class="auth-col">
    <section class="masthead">
      <canvas class="stars" bind:this={stars} aria-hidden="true"></canvas>
      <p class="mast-kicker"><Icon name="orbit" /> galactic feed</p>
      {#if mode === "setup"}
        <h1 class="mast-title">Primo avvio.<br />Creiamo l'amministratore.</h1>
        <p class="mast-date">Il primo account può invitare gli altri.</p>
      {:else if mode === "login"}
        <h1 class="mast-title">{greeting}<br />Entra per leggere.</h1>
        <p class="mast-date">{date}</p>
      {:else if mode === "invite"}
        <h1 class="mast-title">Un invito<br />per te.</h1>
        <p class="mast-date">{session.invite?.invited_by ? `Da ${session.invite.invited_by}, su Galactic Feed.` : "Su Galactic Feed."}</p>
      {:else}
        <h1 class="mast-title">Una nuova<br />password.</h1>
        <p class="mast-date">{session.invite?.username ? `Per l'account @${session.invite.username}.` : "Scegline una che ricordi."}</p>
      {/if}
    </section>

    {#if linkBroken}
      <section class="panel">
        <p class="form-error" role="alert">{session.inviteError || "Questo link non è valido."}</p>
        <button type="button" class="btn-secondary" onclick={toLogin}>Vai all'accesso</button>
      </section>
    {:else}
      <form class="panel form-stack" onsubmit={submit}>
        {#if mode === "setup"}
          <div class="field">
            <label for="code">Codice di primo avvio</label>
            <input class="input mono" id="code" bind:value={f.code} inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000" required />
            <p class="hint">Lo trovi nel log del server: <code>docker compose logs galactic-feed</code></p>
          </div>
        {/if}
        {#if mode === "setup" || mode === "invite"}
          <div class="field">
            <label for="name">Il tuo nome</label>
            <input class="input" id="name" bind:value={f.display_name} autocomplete="name" placeholder="Come ti chiamano" maxlength="60" />
          </div>
        {/if}
        {#if mode !== "reset"}
          <div class="field">
            <label for="username">Nome utente</label>
            <input class="input" id="username" bind:value={f.username} autocomplete="username" autocapitalize="off" spellcheck="false" required />
            {#if mode !== "login"}<p class="hint">Da 3 a 32 caratteri: lettere, numeri, punto o trattino.</p>{/if}
          </div>
        {/if}
        <div class="field">
          <label for="password">{mode === "reset" ? "Nuova password" : "Password"}</label>
          <input class="input" id="password" type="password" bind:value={f.password} autocomplete={mode === "login" ? "current-password" : "new-password"} required minlength={mode === "login" ? undefined : 8} />
        </div>
        {#if mode !== "login"}
          <div class="field">
            <label for="repeat">Ripeti la password</label>
            <input class="input" id="repeat" type="password" bind:value={f.repeat} autocomplete="new-password" required minlength="8" />
            <p class="hint">Almeno 8 caratteri.</p>
          </div>
        {/if}
        {#if error}<p class="form-error" role="alert">{error}</p>{/if}
        <button type="submit" class="btn-primary" disabled={busy}>
          {busy ? "Un momento…" : mode === "setup" ? "Crea l'account" : mode === "login" ? "Entra" : mode === "invite" ? "Crea il mio account" : "Salva la password"}
        </button>
        {#if mode === "login"}
          <p class="hint center">Password dimenticata? Chiedi all'amministratore un link per sceglierne una nuova.</p>
        {/if}
      </form>
    {/if}
    {#if session.version}<p class="auth-foot">Galactic Feed {session.version}</p>{/if}
  </div>
</div>
