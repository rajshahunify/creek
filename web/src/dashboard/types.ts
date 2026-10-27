/** The dashboard's data shapes. Sheets mirror the AB Demand Gen backend (`frontend/src/lib/types.ts` there), so the
 * demo data in mock.ts can be swapped for the real `/api/sheets` without touching the pages. */

export type ColumnKind = "number" | "date" | "bool" | "text";

export interface ColumnInfo {
  name: string;
  kind: ColumnKind;
  /** How a number reads (the demo's own addition: the real backend sends plain numbers). */
  format?: "pct" | "money";
}

export type Cell = string | number | boolean | null;

export interface SheetSummary {
  id: number;
  name: string;
  description: string | null;
  row_count: number;
}

export interface SheetData {
  sheet_id: number;
  name: string;
  columns: ColumnInfo[];
  rows: Cell[][];
  row_count: number;
  truncated: boolean;
  executed_at: string;
  duration_ms: number;
}

export interface UserRow {
  emp_id: string;
  name: string;
  department: string;
  role: "Admin" | "Super User" | "User";
  status: "Pending" | "Active" | "Rejected" | "Disabled";
  since: string;
}

export interface ExportEntry {
  at: string;
  who: string;
  sheet: string;
  rows: number;
  scope: "Current view" | "Whole sheet";
}

export interface Kpi {
  label: string;
  value: number;
  /** Last week's value, for the change. */
  before: number;
  format?: "pct";
}

export interface Overview {
  kpis: Kpi[];
  weeks: { week: string; mqls: number }[];
  recent: ExportEntry[];
}
