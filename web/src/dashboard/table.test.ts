import { describe, expect, it } from "vitest";
import { catalogue, users, weekly } from "./mock";
import { formatCell, pageOf, relativeAge, searchRows, sortRows, toCsv } from "./table";
import type { Cell } from "./types";

const rows: Cell[][] = [
  ["Acme Labs", "EMEA", 120, "2024-05-01"],
  ["blue Peak", "APAC", null, "2023-01-10"],
  ["Cedar Works", "EMEA", 9, null],
  ["acme Foods", "LATAM", 1500, "2024-02-02"],
];

describe("sorting", () => {
  it("sorts numbers as numbers and text without regard to case", () => {
    expect(sortRows(rows, 2, "asc").map((r) => r[2])).toEqual([9, 120, 1500, null]);
    expect(sortRows(rows, 0, "asc").map((r) => r[0])).toEqual(["acme Foods", "Acme Labs", "blue Peak", "Cedar Works"]);
  });

  it("keeps blanks last whichever way", () => {
    expect(sortRows(rows, 2, "desc").map((r) => r[2])).toEqual([1500, 120, 9, null]);
    const byDate = sortRows(rows, 3, "desc");
    expect(byDate[byDate.length - 1][3]).toBeNull();
  });

  it("is stable for equal values", () => {
    expect(sortRows(rows, 1, "asc").map((r) => r[0])).toEqual(["blue Peak", "Acme Labs", "Cedar Works", "acme Foods"]);
  });
});

describe("searching", () => {
  it("needs every word, in any column, ignoring case", () => {
    expect(searchRows(rows, "acme").length).toBe(2);
    expect(searchRows(rows, "ACME emea").map((r) => r[0])).toEqual(["Acme Labs"]);
    expect(searchRows(rows, "  ")).toBe(rows);
    expect(searchRows(rows, "nothing")).toEqual([]);
  });
});

describe("paging", () => {
  it("clamps to the pages there are", () => {
    expect(pageOf(120, 0, 50)).toEqual({ page: 0, pages: 3, start: 0, end: 50 });
    expect(pageOf(120, 2, 50)).toEqual({ page: 2, pages: 3, start: 100, end: 120 });
    expect(pageOf(120, 9, 50).page).toBe(2);
    expect(pageOf(0, 0, 50)).toEqual({ page: 0, pages: 1, start: 0, end: 0 });
  });
});

describe("CSV", () => {
  it("quotes only what needs it", () => {
    const csv = toCsv([{ name: "Name", kind: "text" }, { name: "Note", kind: "text" }],
      [["Plain", 'He said "hi"'], ["a,b", null], ["line\nbreak", " padded"]]);
    expect(csv).toBe('Name,Note\r\nPlain,"He said ""hi"""\r\n"a,b",\r\n"line\nbreak"," padded"');
  });
});

describe("formatting", () => {
  it("reads percentages, money and blanks", () => {
    expect(formatCell(42.5, { name: "x", kind: "number", format: "pct" })).toBe("42.5%");
    expect(formatCell(null, { name: "x", kind: "number" })).toBe("");
    expect(formatCell(1_250_000, { name: "x", kind: "number", format: "money" })).toBe("$1.3M");
  });

  it("says how old something is", () => {
    expect(relativeAge(20_000)).toBe("just now");
    expect(relativeAge(12 * 60_000)).toBe("12 min ago");
    expect(relativeAge(3 * 3_600_000)).toBe("3 h ago");
    expect(relativeAge(26 * 3_600_000)).toBe("1 day ago");
  });
});

describe("demo data", () => {
  const day = new Date(2026, 9, 27);

  it("is the same every time", () => {
    const a = catalogue(day), b = catalogue(day);
    expect(a.summaries()).toEqual(b.summaries());
    expect(a.sheet(3, 0).rows.slice(0, 20)).toEqual(b.sheet(3, 0).rows.slice(0, 20));
    expect(users(day)).toEqual(users(day));
    expect(weekly(day)).toEqual(weekly(day));
  });

  it("gives every row a cell per column", () => {
    const c = catalogue(day);
    for (const s of c.summaries()) {
      const sheet = c.sheet(s.id, 0);
      expect(sheet.rows.length).toBeGreaterThan(0);
      expect(sheet.rows.every((r) => r.length === sheet.columns.length)).toBe(true);
    }
  });

  it("counts weeks from Mondays", () => {
    const w = weekly(day);
    expect(w).toHaveLength(26);
    for (const { week } of w) expect(new Date(`${week}T12:00:00`).getDay()).toBe(1);
  });
});
