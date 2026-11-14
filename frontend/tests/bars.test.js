import { describe, expect, it } from "vitest";
import { barsAfterScroll } from "../src/lib/bars.js";

describe("barre a scomparsa (#36)", () => {
  it("scorrendo giù si nascondono, tornando su ricompaiono", () => {
    expect(barsAfterScroll(100, 200, 2000)).toEqual({ hidden: true, ref: 200 });
    expect(barsAfterScroll(200, 180, 2000)).toEqual({ hidden: false, ref: 180 });
  });

  it("piccoli spostamenti non cambiano niente", () => {
    expect(barsAfterScroll(300, 305, 2000)).toEqual({ hidden: null, ref: 300 });
    expect(barsAfterScroll(300, 293, 2000)).toEqual({ hidden: null, ref: 300 });
  });

  it("vicino alla cima restano visibili", () => {
    expect(barsAfterScroll(10, 40, 2000)).toEqual({ hidden: false, ref: 40 });
  });

  it("le pagine corte non le nascondono", () => {
    expect(barsAfterScroll(0, 90, 100)).toEqual({ hidden: false, ref: 90 });
  });

  it("in fondo alla pagina ricompaiono", () => {
    expect(barsAfterScroll(900, 1000, 1000)).toEqual({ hidden: false, ref: 1000 });
  });

  it("il rimbalzo elastico di iOS non le fa lampeggiare", () => {
    // In fondo: oltre il massimo conta come il massimo, restano visibili.
    expect(barsAfterScroll(1000, 1060, 1000)).toEqual({ hidden: false, ref: 1000 });
    // In cima: valori negativi contano come 0.
    expect(barsAfterScroll(0, -40, 1000)).toEqual({ hidden: false, ref: 0 });
  });
});
