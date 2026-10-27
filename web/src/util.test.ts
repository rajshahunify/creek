import { describe, expect, it } from "vitest";
import { keyAction, looksLikeLink, mmss, positionAt, span } from "./util";

const key = (k: string, mods: Partial<Record<"shiftKey" | "ctrlKey" | "metaKey" | "altKey", boolean>> = {}) =>
  keyAction({ key: k, shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, ...mods });

describe("time", () => {
  it("formats like a player", () => {
    expect(mmss(0)).toBe("0:00");
    expect(mmss(65.9)).toBe("1:05");
    expect(mmss(3725)).toBe("1:02:05");
    expect(mmss(undefined)).toBe("0:00");
    expect(span(125 * 60)).toBe("2 h 5 min");
  });

  it("counts on between updates, but not while paused or past the end", () => {
    expect(positionAt(10, 200, false, 1000, 3500)).toBe(12.5);
    expect(positionAt(10, 200, true, 1000, 3500)).toBe(10);
    expect(positionAt(199, 200, false, 0, 10_000)).toBe(200);
  });
});

describe("keys", () => {
  it("arrows seek, with Ctrl they change the song", () => {
    expect(key("ArrowRight")).toBe("fwd");
    expect(key("ArrowLeft")).toBe("back");
    expect(key("ArrowRight", { ctrlKey: true })).toBe("next");
    expect(key("ArrowLeft", { metaKey: true })).toBe("prev");
  });

  it("Shift+N / Shift+P, space, and nothing for digits or Alt", () => {
    expect(key("N", { shiftKey: true })).toBe("next");
    expect(key("n")).toBeNull();
    expect(key("P", { shiftKey: true })).toBe("prev");
    expect(key(" ")).toBe("toggle");
    expect(key("3")).toBeNull();
    expect(key("7")).toBeNull();
    expect(key("ArrowUp", { altKey: true })).toBeNull();
    expect(key("/")).toBe("search");
    expect(key("k", { ctrlKey: true })).toBeNull();      // Ctrl+K belongs to the dashboard's palette
  });
});

describe("misc", () => {
  it("knows a link when it sees one", () => {
    expect(looksLikeLink(" https://youtu.be/abc ")).toBe(true);
    expect(looksLikeLink("tum hi ho")).toBe(false);
  });
});
