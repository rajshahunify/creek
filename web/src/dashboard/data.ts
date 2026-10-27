/** Where the dashboard's pages get their data: the one seam between them and the demo data. Pointing it at the
 * real AB backend (`GET /api/sheets`, `GET /api/sheets/{id}`, `/api/admin/users`, `/api/admin/export-log`)
 * means changing this file and nothing else. Music never comes through here: it is live, from the station. */

import { useEffect, useState, useSyncExternalStore } from "react";
import { catalogue, exportLog, users as mockUsers, weekly } from "./mock";
import type { ExportEntry, Overview, SheetData, SheetSummary, UserRow } from "./types";

const book = catalogue();
const pulledAt = new Map<number, number>();          // when each sheet was last "run", as the badge shows it
const listeners = new Set<() => void>();
let version = 0;

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const executedAt = (id: number) => {
  if (!pulledAt.has(id)) pulledAt.set(id, Date.now() - book.ageMin(id) * 60_000);
  return pulledAt.get(id)!;
};

export class NotFound extends Error {}

export async function listSheets(): Promise<(SheetSummary & { executed_at: string })[]> {
  return book.summaries().map((s) => ({ ...s, executed_at: new Date(executedAt(s.id)).toISOString() }));
}

export async function getSheet(id: number): Promise<SheetData> {
  if (!book.has(id)) throw new NotFound(`no report ${id}`);
  await wait(220);
  return book.sheet(id, executedAt(id));
}

/** Re-run a report: the real thing queries the database again; here the rows stay and the clock resets. */
export async function refreshSheet(id: number): Promise<SheetData> {
  await wait(650);
  pulledAt.set(id, Date.now());
  version++;
  listeners.forEach((f) => f());
  return book.sheet(id, executedAt(id));
}

export async function listUsers(): Promise<UserRow[]> {
  await wait(160);
  return mockUsers();
}

export async function listExports(): Promise<ExportEntry[]> {
  await wait(160);
  return exportLog(book.summaries().map((s) => s.name));
}

export async function getOverview(): Promise<Overview> {
  await wait(120);
  const weeks = weekly().slice(-12);
  const [prev, last] = weeks.slice(-2);
  const sheets = book.summaries();
  const tal = sheets.find((s) => s.id === 1)!.row_count;
  const log = exportLog(sheets.map((s) => s.name));
  const today = new Date().toDateString();
  const exportsOn = (day: string) => log.filter((e) => new Date(e.at).toDateString() === day).length;
  const yesterday = new Date(Date.now() - 86_400_000).toDateString();
  return {
    kpis: [
      { label: "Accounts in TAL", value: tal, before: tal - 18 },
      { label: "MQLs this week", value: last.mqls, before: prev.mqls },
      { label: "Lead → MQL", value: Math.round((last.mqls / last.leads) * 1000) / 10, before: Math.round((prev.mqls / prev.leads) * 1000) / 10, format: "pct" },
      { label: "Exports today", value: exportsOn(today), before: exportsOn(yesterday) },
    ],
    weeks: weeks.map(({ week, mqls }) => ({ week, mqls })),
    recent: log.slice(0, 6),
  };
}

/** The report list, kept current when one is refreshed (the rail's "2h ago" depends on it). */
export function useSheetList() {
  const v = useSyncExternalStore((f) => (listeners.add(f), () => listeners.delete(f)), () => version);
  const [sheets, setSheets] = useState<Awaited<ReturnType<typeof listSheets>>>([]);
  useEffect(() => { listSheets().then(setSheets); }, [v]);
  return sheets;
}
