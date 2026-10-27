/** A sortable, paged table over rows the page has already searched. Sticky header, numbers right-aligned,
 * status-like columns as pills. The whole sheet sorts, not just the page on screen. */

import { useEffect, useMemo, useState } from "react";
import { formatCell, pageOf, sortRows, toneOf, type Dir } from "../../dashboard/table";
import type { Cell, ColumnInfo } from "../../dashboard/types";
import { ChevronLeft, ChevronRight, Down, Sort, Up } from "../Icons";

export function DataTable({ columns, rows, total, pills = [], pageSize = 50, empty = "Nothing to show.", label }: {
  columns: ColumnInfo[];
  rows: Cell[][];
  /** Rows before searching, so the footer can say "filtered". */
  total?: number;
  pills?: string[];
  pageSize?: number;
  empty?: string;
  label: string;
}) {
  const [sort, setSort] = useState<{ col: number; dir: Dir } | null>(null);
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [rows, sort]);
  useEffect(() => setSort(null), [columns]);

  const sorted = useMemo(() => (sort ? sortRows(rows, sort.col, sort.dir) : rows), [rows, sort]);
  const at = pageOf(sorted.length, page, pageSize);
  const shown = sorted.slice(at.start, at.end);
  const pillAt = new Set(columns.flatMap((c, i) => (pills.includes(c.name) ? [i] : [])));
  const fmt = new Intl.NumberFormat();

  const by = (col: number) => setSort((s) => (s?.col !== col ? { col, dir: "asc" } : s.dir === "asc" ? { col, dir: "desc" } : null));

  return (
    <div className="table-card">
      <div className="table-scroll">
        <table className="table" aria-label={label}>
          <thead>
            <tr>
              {columns.map((c, i) => {
                const on = sort?.col === i;
                return (
                  <th key={c.name} className={c.kind === "number" ? "num" : ""}
                      aria-sort={on ? (sort!.dir === "asc" ? "ascending" : "descending") : "none"}>
                    <button onClick={() => by(i)} title={`Sort by ${c.name}`}>
                      <span>{c.name}</span>
                      {on ? (sort!.dir === "asc" ? <Up /> : <Down />) : <Sort className="sort-hint" />}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={at.start + i}>
                {r.map((v, j) => {
                  const c = columns[j];
                  const text = formatCell(v, c);
                  return (
                    <td key={j} className={c.kind === "number" ? "num" : c.kind === "date" ? "date" : ""} title={text.length > 28 ? text : undefined}>
                      {pillAt.has(j) && text ? <span className={`pill ${toneOf(v)}`}>{text}</span> : text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="table-empty">{empty}</p>}
      </div>
      <footer className="table-foot">
        <span className="tabular">
          {rows.length ? `${fmt.format(at.start + 1)}–${fmt.format(at.end)} of ${fmt.format(rows.length)}` : "0 rows"}
          {total !== undefined && total !== rows.length && <> · <span className="accent">filtered</span> from {fmt.format(total)}</>}
        </span>
        <span className="pager">
          <button className="icon tiny" onClick={() => setPage(at.page - 1)} disabled={at.page === 0} aria-label="Previous page"><ChevronLeft /></button>
          <span className="tabular">Page {at.page + 1} of {at.pages}</span>
          <button className="icon tiny" onClick={() => setPage(at.page + 1)} disabled={at.page >= at.pages - 1} aria-label="Next page"><ChevronRight /></button>
        </span>
      </footer>
    </div>
  );
}
