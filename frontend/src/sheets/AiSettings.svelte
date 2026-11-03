<script>
  // Configurazione dell'AI, solo per l'amministratore: spenta, locale (Ollama) o cloud
  // (Anthropic o un servizio compatibile con OpenAI). La chiave API non torna mai indietro
  // dal server: il campo resta vuoto e «vuoto» vuol dire «lascia quella salvata».
  import Icon from "../components/Icon.svelte";
  import { api } from "../lib/api.js";
  import { loadInterests, toast } from "../lib/store.svelte.js";

  let cfg = $state(null);
  let form = $state({ kind: "off", service: "anthropic", base_url: "", model: "", api_key: "", daily_limit: 500 });
  let busy = $state(false);
  let testResult = $state(null); // { ok, message }
  let error = $state("");

  const provider = $derived(form.kind === "off" ? "" : form.kind === "locale" ? "ollama" : form.service);
  const defaults = $derived(cfg?.providers?.[provider] || {});

  $effect(() => {
    load();
  });

  async function load() {
    try {
      cfg = await api("/admin/ai");
      fill(cfg);
    } catch (err) {
      error = err.message;
    }
  }

  function fill(c) {
    const kind = !c.provider ? "off" : c.provider === "ollama" ? "locale" : "cloud";
    form = {
      kind,
      service: c.provider === "openai" ? "openai" : "anthropic",
      base_url: c.base_url,
      model: c.model,
      api_key: "",
      daily_limit: c.daily_limit,
    };
  }

  function pick(kind, service = form.service) {
    const prev = provider;
    form.kind = kind;
    form.service = service;
    if (provider !== prev) {
      // Cambiando fornitore si ripartono dai suoi valori predefiniti.
      const d = cfg.providers[provider] || {};
      form.base_url = provider === cfg.provider ? cfg.base_url : d.base_url || "";
      form.model = provider === cfg.provider ? cfg.model : d.model || "";
      form.api_key = "";
    }
    testResult = null;
  }

  async function save() {
    busy = true;
    testResult = null;
    try {
      const body = { provider, base_url: form.base_url, model: form.model, daily_limit: Number(form.daily_limit) || 500 };
      if (form.api_key.trim()) body.api_key = form.api_key.trim();
      cfg = await api("/admin/ai", { method: "PUT", body });
      fill(cfg);
      toast(provider ? (cfg.enabled ? "AI configurata" : "Salvato: manca ancora qualcosa") : "AI spenta");
      loadInterests();
      return true;
    } catch (err) {
      toast(err.message);
      return false;
    } finally {
      busy = false;
    }
  }

  async function test() {
    if (!(await save())) return;
    busy = true;
    try {
      const r = await api("/admin/ai/test", { method: "POST" });
      testResult = { ok: true, message: r.message };
    } catch (err) {
      testResult = { ok: false, message: err.message };
    } finally {
      busy = false;
      cfg = await api("/admin/ai");
    }
  }

  const NOTES = {
    off: "Senza AI le notizie «per te» si scelgono solo con le parole chiave e non ci sono riassunti.",
    locale: "I testi non escono dalla tua rete. Su un Raspberry Pi è lento: meglio Ollama su un PC più potente della stessa rete.",
    cloud: "Veloce anche su hardware piccolo. Si paga a consumo e titoli e testi degli articoli vengono inviati al servizio.",
  };
</script>

{#if error}
  <p class="form-error" role="alert">{error}</p>
{:else if cfg}
  <div class="set-group">
    <div class="set-row"><span>AI</span>
      <div class="segmented" style="--cols:3" role="group" aria-label="Fornitore AI">
        <button type="button" aria-pressed={form.kind === "off"} onclick={() => pick("off")}>Spenta</button>
        <button type="button" aria-pressed={form.kind === "locale"} onclick={() => pick("locale")}>Locale</button>
        <button type="button" aria-pressed={form.kind === "cloud"} onclick={() => pick("cloud")}>Cloud</button>
      </div>
    </div>
    {#if form.kind === "cloud"}
      <div class="set-row"><span>Servizio</span>
        <div class="segmented" role="group" aria-label="Servizio cloud">
          <button type="button" aria-pressed={form.service === "anthropic"} onclick={() => pick("cloud", "anthropic")}>Anthropic</button>
          <button type="button" aria-pressed={form.service === "openai"} onclick={() => pick("cloud", "openai")}>OpenAI</button>
        </div>
      </div>
    {/if}
  </div>
  <p class="set-note">{NOTES[form.kind]}</p>

  {#if form.kind !== "off"}
    <form class="form-stack" onsubmit={(e) => { e.preventDefault(); save(); }}>
      {#if provider !== "anthropic"}
        <div class="field">
          <label for="ai-url">Indirizzo</label>
          <input class="input mono" id="ai-url" bind:value={form.base_url} placeholder={defaults.base_url} autocomplete="off" />
          <p class="hint">{provider === "ollama" ? "L'indirizzo di Ollama con /v1 in fondo, per esempio http://192.168.1.20:11434/v1." : "Per un servizio compatibile con OpenAI, scrivi il suo indirizzo."}</p>
        </div>
      {/if}
      <div class="field">
        <label for="ai-model">Modello</label>
        <input class="input mono" id="ai-model" bind:value={form.model} placeholder={provider === "ollama" ? "per esempio qwen3:8b" : defaults.model} autocomplete="off" />
        {#if provider === "anthropic"}
          <p class="hint">Predefinito: claude-opus-5-5, il più capace. Per scegliere e riassumere notizie basta anche claude-haiku-5-5, che costa circa 40 volte meno.</p>
        {:else if provider === "ollama"}
          <p class="hint">Il nome che vedi con «ollama list».</p>
        {/if}
      </div>
      {#if provider !== "ollama"}
        <div class="field">
          <label for="ai-key">Chiave API</label>
          <input class="input mono" id="ai-key" type="password" bind:value={form.api_key} autocomplete="off"
            placeholder={cfg.has_key && cfg.provider === provider ? "salvata: lascia vuoto per non cambiarla" : "incolla la chiave"} />
        </div>
      {/if}
      <div class="field">
        <label for="ai-limit">Richieste al giorno, al massimo</label>
        <input class="input mono" id="ai-limit" type="number" min="1" max="100000" bind:value={form.daily_limit} />
        <p class="hint">Un tetto alla spesa. Oggi: {cfg.usage_today.requests} richieste, {cfg.usage_today.input_tokens + cfg.usage_today.output_tokens} token.</p>
      </div>
      {#if cfg.last_error}<p class="form-error" role="alert">Ultimo errore: {cfg.last_error}</p>{/if}
      {#if testResult}<p class={testResult.ok ? "form-ok" : "form-error"} role="status">{testResult.message}</p>{/if}
      <button type="submit" class="btn-primary" disabled={busy}><Icon name="check" />Salva</button>
      <button type="button" class="btn-secondary" disabled={busy} onclick={test}><Icon name="spark" />Prova il collegamento</button>
    </form>
  {:else if cfg.provider}
    <button type="button" class="btn-primary" disabled={busy} onclick={save}><Icon name="check" />Spegni l'AI</button>
  {/if}
{/if}
