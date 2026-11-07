import { describe, expect, it } from "vitest";
import { countryName, flag, frequency, initials, intervalLabel, matchLabel, nextRun, pathOf, since, sourceColor, timeAgo, timeAgoLong } from "../src/lib/format.js";

const NOW = new Date("2026-10-31T12:00:00Z").getTime();
const ago = (s) => new Date(NOW - s * 1000).toISOString();

describe("tempi relativi", () => {
  it("come nel mockup", () => {
    expect(timeAgo(ago(20), NOW)).toBe("adesso");
    expect(timeAgo(ago(25 * 60), NOW)).toBe("25 min");
    expect(timeAgo(ago(3 * 3600), NOW)).toBe("3 h");
    expect(timeAgo(ago(30 * 3600), NOW)).toBe("ieri");
    expect(timeAgo(ago(4 * 86400), NOW)).toBe("4 giorni");
    expect(timeAgo("2026-10-12T10:00:00Z", NOW)).toBe("12 ott");
    expect(timeAgo("2025-03-02T10:00:00Z", NOW)).toBe("2 mar 2025");
    expect(timeAgo(null, NOW)).toBe("");
  });
  it("nelle frasi", () => {
    expect(timeAgoLong(ago(25 * 60), NOW)).toBe("25 min fa");
    expect(timeAgoLong(ago(30 * 3600), NOW)).toBe("ieri");
    expect(timeAgoLong("2026-10-12T10:00:00Z", NOW)).toBe("il 12 ott");
    expect(since(ago(2 * 86400), NOW)).toBe("da 2 giorni");
    expect(since(ago(3 * 3600), NOW)).toBe("da 3 ore");
  });
});

describe("fonti", () => {
  it("iniziali come nel mockup", () => {
    expect(initials("Orbita")).toBe("Or");
    expect(initials("Bit & Byte")).toBe("BB");
    expect(initials("Cronache Spaziali")).toBe("CS");
    expect(initials("https://www.example.org")).toBe("EO");
    expect(initials("")).toBe("·");
  });
  it("intervalli e frequenze", () => {
    expect(intervalLabel(15)).toBe("15 min");
    expect(intervalLabel(180)).toBe("3 h");
    expect(frequency(175)).toBe("circa 25 articoli al giorno");
    expect(frequency(3)).toBe("3 a settimana");
    expect(frequency(0.3)).toBe("meno di uno a settimana");
    expect(frequency(null)).toBe("");
  });
  it("colori: YouTube arancio, altrimenti la cartella", () => {
    const folders = { 1: { color: "verde" } };
    expect(sourceColor({ kind: "youtube", folder_id: 1 }, folders)).toBe("var(--c-video)");
    expect(sourceColor({ kind: "rss", folder_id: 1 }, folders)).toBe("var(--c-verde)");
    expect(sourceColor({ kind: "rss", folder_id: null }, folders)).toBe("var(--c-grigio)");
  });
  it("percorso del feed", () => {
    expect(pathOf("https://orbita.example/feed.xml")).toBe("/feed.xml");
    expect(pathOf("non un url")).toBe("non un url");
  });
});

describe("gruppi, nazioni e uscite", () => {
  it("la corrispondenza mostra il gruppo", () => {
    expect(matchLabel({ keyword: "iPhone", group: "Tecnologia" })).toBe("Tecnologia · iPhone");
    expect(matchLabel({ keyword: "Luna", group: null })).toBe("Luna");
    expect(matchLabel(null)).toBe("");
  });
  it("nomi e bandiere delle nazioni", () => {
    expect(countryName("IT")).toBe("Italia");
    expect(flag("IT")).toBe("🇮🇹");
    expect(flag("")).toBe("");
  });
  it("prossima uscita", () => {
    const now = new Date(2026, 10, 7, 10, 0).getTime();
    expect(nextRun(new Date(2026, 10, 7, 19, 0).toISOString(), undefined, now)).toBe("oggi alle 19:00");
    expect(nextRun(new Date(2026, 10, 8, 7, 30).toISOString(), undefined, now)).toBe("domani alle 07:30");
    expect(nextRun(new Date(2026, 10, 9, 7, 30).toISOString(), undefined, now)).toBe("lunedì 9 novembre alle 07:30");
    // Nel fuso dell'Edizione, qualunque sia quello del dispositivo: 06:30 UTC sono le 07:30 a Roma.
    expect(nextRun("2026-11-09T06:30:00Z", "Europe/Rome", Date.parse("2026-11-07T10:00:00Z"))).toBe("lunedì 9 novembre alle 07:30");
  });
});
