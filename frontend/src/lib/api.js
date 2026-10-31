// Client dell'API: ogni chiamata al server passa da qui.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const DEFAULT_MESSAGES = {
  0: "Nessuna connessione con il server. Controlla la rete e riprova.",
  401: "Accesso richiesto: entra con il tuo account.",
  403: "Operazione non permessa.",
  404: "Non trovato.",
  413: "Il file è troppo grande.",
  429: "Troppi tentativi. Riprova tra qualche minuto.",
  500: "Errore del server. Riprova tra poco.",
  502: "Il sito della fonte non risponde come dovrebbe.",
};

let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export async function api(path, { method = "GET", body, form, signal, quiet401 = false } = {}) {
  const headers = { Accept: "application/json" };
  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch("/api" + path, { method, headers, body: payload, credentials: "same-origin", signal });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError(0, DEFAULT_MESSAGES[0]);
  }
  if (res.status === 401 && !quiet401 && onUnauthorized) onUnauthorized();
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).detail;
    } catch {
      /* risposta senza JSON */
    }
    const fallback = DEFAULT_MESSAGES[res.status] || (res.status >= 500 ? DEFAULT_MESSAGES[500] : "Richiesta non riuscita.");
    throw new ApiError(res.status, typeof detail === "string" && detail ? detail : fallback);
  }
  if (res.status === 204) return null;
  return res.json();
}

export function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "" && v !== false) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? "?" + s : "";
}
