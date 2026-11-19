// Colore personalizzato (#74): qualunque colore scelto diventa leggibile in chiaro e in scuro.
import { describe, expect, it } from "vitest";
import { accentVars, contrast } from "../src/lib/color.js";

const LIGHT = ["#FFFFFF", "#F4F5F9", "#FDF6E3"];
const DARK = ["#0C0F1C", "#151A2D", "#002B36", "#000000"];

describe("colore personalizzato", () => {
  for (const hex of ["#FF7A59", "#FFFF00", "#00FFFF", "#111111", "#FFFFFF", "#4F8CFF", "#7E22CE", "#00A000"]) {
    it(`${hex}: varianti AA`, () => {
      const v = accentVars(hex);
      for (const bg of LIGHT) expect(contrast(v["--acc-l"], bg)).toBeGreaterThanOrEqual(4.5);
      for (const bg of DARK) expect(contrast(v["--acc-d"], bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(v["--acc-on-l"], v["--acc-l"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(v["--acc-on-d"], v["--acc-d"])).toBeGreaterThanOrEqual(4.5);
    });
  }

  it("colore non valido", () => {
    expect(accentVars("rosso")).toBeNull();
  });
});
