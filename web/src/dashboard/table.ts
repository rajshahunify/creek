/** Pure table work for the report view: sort, search, a page at a time, CSV, and how a cell reads. Covered by
 * table.test.ts. Everything runs in the browser over the whole sheet, as the AB dashboard does. */

import type { Cell, ColumnInfo } from "./types";

export type Dir = "asc" | "desc";

/** Blanks always sort last, whichever way: nobody sorts to find the empty rows. */
export function compare(a: Cell, b: Cell): number {
  const blankA = a === null || a === "", blankB = b === null || b === "";
  if (blankA || blankB) return blankA === blankB ? 0 : blankA ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

export function sortRows(rows: Cell[][], col: number, dir: Dir): Cell[][] {
  const sign = dir === "asc" ? 1 : -1;
  return rows
    .map((r, i) => [r, i] as const)
    .sort(([a, i], [b, j]) => {
      const blank = (v: Cell) => v === null || v === "";
      if (blank(a[col]) !== blank(b[col])) return blank(a[col]) ? 1 : -1;     // last in both directions
      return sign * compare(a[col], b[col]) || i - j;                          // stable
    })
    .map(([r]) => r);
}

/** Every word must appear somewhere in the row (in any column), ignoring case: `acme 2024` finds a row with
 * "Acme" in one column and "2024" in another. */
export function searchRows(rows: Cell[][], term: string): Cell[][] {
  const words = term.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return rows;
  return rows.filter((r) => {
    const line = r.map((c) => (c === null ? "" : String(c))).join("\u0000").toLowerCase();
    return words.every((w) => line.includes(w));
  });
}

/** Which rows page `page` (0-based) shows, clamped to the pages there are. */
export function pageOf(total: number, page: number, size: number) {
  const pages = Math.max(1, Math.ceil(total / size));
  const p = Math.min(Math.max(0, page), pages - 1);
  return { page: p, pages, start: p * size, end: Math.min(total, (p + 1) * size) };
}

export function toCsv(columns: ColumnInfo[], rows: Cell[][]): string {
  const field = (v: Cell) => {
    const s = v === null ? "" : String(v);
    return /[",\r\n]/.test(s) || /^\s|\s$/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map((c) => field(c.name)), ...rows.map((r) => r.map(field))].map((r) => r.join(",")).join("\r\n");
}

const num = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
// pinned to en-US: the reports are in dollars, and "$12.5L" (an Indian-locale lakh) misreads them
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });

export function formatCell(v: Cell, c: ColumnInfo): string {
  if (v === null || v === "") return "";
  if (typeof v === "number") {
    if (c.format === "pct") return `${num.format(v)}%`;
    if (c.format === "money") return money.format(v);
    return num.format(v);
  }
  if (c.kind === "date" && typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v)) return formatDay(v);
  return String(v);
}

export function formatDay(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** "just now", "12 min ago", "2 h ago", "3 days ago". */
export function relativeAge(ms: number): string {
  const min = Math.floor(ms / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.floor(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

/** How a status-like value reads at a glance. Colour is never the only cue: the pill carries the word. */
export type Tone = "good" | "warn" | "bad" | "info" | "neutral";

const TONES: Record<string, Tone> = {
  "Closed Won": "good", Active: "good", SQL: "good", Opportunity: "good",
  Engaged: "info", MQL: "info", Working: "info", "Super User": "info", Admin: "info",
  Pending: "warn", Nurture: "warn", Recycled: "warn", New: "neutral", Prospecting: "neutral",
  Disqualified: "bad", Rejected: "bad", Disabled: "bad",
};

export const toneOf = (v: Cell): Tone => (typeof v === "string" && TONES[v]) || "neutral";
