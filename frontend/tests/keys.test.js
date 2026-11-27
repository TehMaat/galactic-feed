import { describe, expect, it } from "vitest";
import { isTyping, neighbour, shortcutFor } from "../src/lib/keys.js";

const press = (key, extra = {}) => ({ key, target: { tagName: "BODY" }, ...extra });

describe("scorciatoie da tastiera (#94)", () => {
  it("riconosce i tasti, anche maiuscoli, e «v» come «o»", () => {
    expect(shortcutFor(press("j"))).toBe("j");
    expect(shortcutFor(press("K"))).toBe("k");
    expect(shortcutFor(press("v"))).toBe("o");
    expect(shortcutFor(press("?", { shiftKey: true }))).toBe("?");
    expect(shortcutFor(press("x"))).toBeNull();
    expect(shortcutFor(press("Enter"))).toBeNull();
  });

  it("lascia stare Ctrl, Alt, ⌘ e i tasti già usati", () => {
    expect(shortcutFor(press("r", { ctrlKey: true }))).toBeNull();
    expect(shortcutFor(press("s", { metaKey: true }))).toBeNull();
    expect(shortcutFor(press("j", { altKey: true }))).toBeNull();
    expect(shortcutFor(press("j", { defaultPrevented: true }))).toBeNull();
  });

  it("mentre si scrive in un campo non fa niente", () => {
    expect(shortcutFor(press("j", { target: { tagName: "INPUT", type: "search" } }))).toBeNull();
    expect(shortcutFor(press("j", { target: { tagName: "TEXTAREA" } }))).toBeNull();
    expect(shortcutFor(press("j", { target: { tagName: "DIV", isContentEditable: true } }))).toBeNull();
    expect(isTyping({ tagName: "INPUT", type: "checkbox" })).toBe(false);
    expect(isTyping({ tagName: "BUTTON" })).toBe(false);
  });

  it("trova la notizia prima e dopo", () => {
    const items = [{ id: 5 }, { id: 3 }, { id: 9 }];
    expect(neighbour(items, null, 1)).toBe(5);
    expect(neighbour(items, null, -1)).toBeNull();
    expect(neighbour(items, 5, 1)).toBe(3);
    expect(neighbour(items, 3, -1)).toBe(5);
    expect(neighbour(items, 9, 1)).toBeNull();
    expect(neighbour(items, 5, -1)).toBeNull();
    expect(neighbour(items, 42, 1)).toBe(5);
    expect(neighbour([], null, 1)).toBeNull();
  });
});
