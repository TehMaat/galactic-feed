import { describe, expect, it } from "vitest";
import { applyPending, imageUrls, mergeAction, selectEvictions } from "../src/lib/offline-core.js";

const ORIGIN = "https://feed.example.org";

describe("selectEvictions", () => {
  it("tiene tutti i salvati e gli ultimi letti", () => {
    const metas = [
      { id: 1, saved: true, readAt: 1 },
      { id: 2, saved: false, readAt: 50 },
      { id: 3, saved: false, readAt: 10 },
      { id: 4, saved: false, readAt: 30 },
      { id: 5, saved: true, readAt: 0 },
    ];
    expect(selectEvictions(metas, 2).sort()).toEqual([3]);
    expect(selectEvictions(metas, 0).sort()).toEqual([2, 3, 4]);
    expect(selectEvictions(metas, 300)).toEqual([]);
  });

  it("toglie per primi i letti più vecchi, anche oltre i 300", () => {
    const metas = Array.from({ length: 305 }, (_, i) => ({ id: i + 1, saved: false, readAt: i + 1 }));
    expect(selectEvictions(metas).sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5]);
  });
});

describe("imageUrls", () => {
  it("prende l'immagine principale e quelle del testo che passano dal proxy", () => {
    const article = {
      image: "/api/img?u=a&s=1",
      content_html:
        '<p><img src="/api/img?u=b&amp;s=2" alt=""></p><img alt="x" src="https://altro.example/c.png"><img src="/api/img?u=a&amp;s=1">',
    };
    expect(imageUrls(article, ORIGIN)).toEqual([`${ORIGIN}/api/img?u=a&s=1`, `${ORIGIN}/api/img?u=b&s=2`]);
  });

  it("si ferma al numero massimo", () => {
    const content_html = Array.from({ length: 20 }, (_, i) => `<img src="/api/img?u=${i}&amp;s=x">`).join("");
    expect(imageUrls({ image: null, content_html }, ORIGIN, 3)).toHaveLength(3);
  });

  it("funziona anche senza testo", () => {
    expect(imageUrls({ image: null, content_html: null }, ORIGIN)).toEqual([]);
  });
});

describe("mergeAction", () => {
  it("unisce le azioni sullo stesso articolo: vale l'ultima", () => {
    let a = mergeAction(undefined, 7, { read: true });
    expect(a).toEqual({ id: 7, v: 1, read: true });
    a = mergeAction(a, 7, { saved: true });
    expect(a).toEqual({ id: 7, v: 2, read: true, saved: true });
    a = mergeAction(a, 7, { saved: false });
    expect(a).toEqual({ id: 7, v: 3, read: true, saved: false });
  });
});

describe("applyPending", () => {
  it("applica la coda agli elenchi", () => {
    const items = [
      { id: 1, read: false, saved: true },
      { id: 2, read: false, saved: false },
    ];
    const pending = new Map([[1, { id: 1, saved: false }], [2, { id: 2, read: true }]]);
    expect(applyPending(items, pending)).toEqual([
      { id: 1, read: false, saved: false },
      { id: 2, read: true, saved: false },
    ]);
  });
});
