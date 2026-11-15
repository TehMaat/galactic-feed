import { describe, expect, it } from "vitest";
import { SWIPE, canStart, lockAxis, offset, release, target } from "../src/lib/swipe.js";

describe("swipe tra Edizione e Flusso (#29)", () => {
  it("lascia i bordi ai gesti di sistema", () => {
    expect(canStart(5, 390)).toBe(false);
    expect(canStart(SWIPE.edge - 1, 390)).toBe(false);
    expect(canStart(390 - SWIPE.edge + 1, 390)).toBe(false);
    expect(canStart(200, 390)).toBe(true);
  });

  it("decide l'asse solo dopo qualche pixel, preferendo lo scorrimento", () => {
    expect(lockAxis(4, 3)).toBe(null);
    expect(lockAxis(20, 5)).toBe("x");
    expect(lockAxis(-20, 5)).toBe("x");
    expect(lockAxis(15, 12)).toBe("y"); // diagonale: scorre la pagina
    expect(lockAxis(2, 30)).toBe("y");
  });

  it("verso sinistra il Flusso, verso destra l'Edizione", () => {
    expect(target("edizione", -50)).toBe("flusso");
    expect(target("flusso", 50)).toBe("edizione");
    expect(target("edizione", 50)).toBe(null);
    expect(target("flusso", -50)).toBe(null);
    expect(target("edizione", 0)).toBe(null);
  });

  it("agli estremi il contenuto segue il dito solo un po'", () => {
    expect(offset("edizione", -100)).toBe(-100);
    expect(offset("edizione", 100)).toBe(100 * SWIPE.rubber);
    expect(offset("flusso", -100)).toBe(-100 * SWIPE.rubber);
  });

  it("cambia oltre il 30% della larghezza o con uno swipe veloce", () => {
    expect(release("edizione", -130, -0.1, 390)).toBe("flusso");
    expect(release("edizione", -60, -0.1, 390)).toBe(null);
    expect(release("edizione", -60, -0.8, 390)).toBe("flusso");
    expect(release("edizione", -20, -0.8, 390)).toBe(null); // tocco appena mosso
    expect(release("edizione", -60, 0.8, 390)).toBe(null); // tornato indietro alla fine
    expect(release("flusso", 200, 0, 390)).toBe("edizione");
    expect(release("edizione", 300, 1, 390)).toBe(null);
  });
});
