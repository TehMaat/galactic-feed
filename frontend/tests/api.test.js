import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, qs, setUnauthorizedHandler } from "../src/lib/api.js";

afterEach(() => vi.unstubAllGlobals());

function reply(status, body) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status })));
}

describe("api", () => {
  it("manda JSON e restituisce la risposta", async () => {
    reply(200, { ok: true });
    expect(await api("/x", { method: "POST", body: { a: 1 } })).toEqual({ ok: true });
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe("/api/x");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(opts.body).toBe('{"a":1}');
  });

  it("usa il messaggio in italiano del server", async () => {
    reply(409, { detail: "Segui già questa fonte." });
    await expect(api("/sources", { method: "POST", body: {} })).rejects.toMatchObject({ status: 409, message: "Segui già questa fonte." });
  });

  it("ha messaggi chiari anche senza risposta del server", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("Failed to fetch"); }));
    const err = await api("/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toMatch(/Nessuna connessione/);
    reply(503);
    expect((await api("/x").catch((e) => e)).message).toMatch(/Errore del server/);
  });

  it("avvisa quando la sessione è scaduta", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    reply(401, { detail: "Accesso richiesto" });
    await api("/me").catch(() => {});
    expect(handler).toHaveBeenCalledOnce();
    await api("/me", { quiet401: true }).catch(() => {});
    expect(handler).toHaveBeenCalledOnce();
  });

  it("costruisce i parametri saltando quelli vuoti", () => {
    expect(qs({ view: "perte", q: "", folder: null, show_muted: false, source: 3 })).toBe("?view=perte&source=3");
    expect(qs({})).toBe("");
  });
});
