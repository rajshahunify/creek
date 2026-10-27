/** One report: the AB dashboard's sheet view, cut down to what the demo needs. Search over every column, sort
 * any column, a page at a time, refresh, and export what's on screen as CSV. */

import { useEffect, useMemo, useState } from "react";
import { AgeBadge } from "../components/dash/AgeBadge";
import { DataTable } from "../components/dash/DataTable";
import { Close, Download, Refresh, Search } from "../components/Icons";
import { getSheet, NotFound, refreshSheet } from "../dashboard/data";
import { searchRows, toCsv } from "../dashboard/table";
import type { SheetData } from "../dashboard/types";
import { useDebounced } from "../hooks";
import { toast } from "../store";

const PILLS = ["Status", "Stage", "Tier"];

export function Report({ id }: { id: number }) {
  const [sheet, setSheet] = useState<SheetData | null>(null);
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [term, setTerm] = useState("");
  const q = useDebounced(term, 150);

  useEffect(() => {
    let live = true;
    setSheet(null); setMissing(false); setTerm("");
    getSheet(id).then((s) => live && setSheet(s)).catch((e) => live && e instanceof NotFound && setMissing(true));
    return () => { live = false; };
  }, [id]);

  const rows = useMemo(() => (sheet ? searchRows(sheet.rows, q) : []), [sheet, q]);

  const refresh = async () => {
    setBusy(true);
    try { setSheet(await refreshSheet(id)); toast("Report refreshed"); } finally { setBusy(false); }
  };
  const exportCsv = () => {
    if (!sheet) return;
    const blob = new Blob(["﻿" + toCsv(sheet.columns, rows)], { type: "text/csv;charset=utf-8" });
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(blob), download: `${sheet.name.replace(/[^\w-]+/g, "_")}_${new Date().toISOString().slice(0, 10)}.csv`,
    });
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  if (missing) {
    return (
      <div className="page"><div className="panel empty-state"><h2>No such report</h2><p className="muted">It may have been removed. Pick one from the list.</p></div></div>
    );
  }

  return (
    <div className="page page-fill">
      <div className="page-bar">
        <div className="page-title">
          <h1>{sheet?.name ?? <span className="skeleton-text" />}</h1>
          <p>{sheet ? `${sheet.row_count.toLocaleString()} rows · ${sheet.columns.length} columns · ran in ${sheet.duration_ms} ms` : "Loading…"}</p>
        </div>
        <div className="page-actions">
          <label className="field">
            <Search />
            <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Search every column" aria-label="Search this report" disabled={!sheet} />
            {term && <button className="icon tiny" onClick={() => setTerm("")} aria-label="Clear the search"><Close /></button>}
          </label>
          <span className="hide-narrow"><AgeBadge at={sheet?.executed_at ?? null} /></span>
          <button className="tool" onClick={refresh} disabled={!sheet || busy} title="Run the report again">
            <Refresh className={busy ? "spin" : ""} /> <span className="label">Refresh</span>
          </button>
          <button className="tool primary" onClick={exportCsv} disabled={!sheet || !rows.length} title="Download the rows on screen (search included) as CSV">
            <Download /> <span className="label">Export</span>
          </button>
        </div>
      </div>
      {sheet ? (
        <DataTable label={sheet.name} columns={sheet.columns} rows={rows} total={sheet.rows.length} pills={PILLS}
                   empty={q ? `No rows match “${q}”.` : "This report returned no rows."} />
      ) : (
        <div className="table-card"><div className="table-loading">{Array.from({ length: 10 }, (_, i) => <span key={i} className="shimmer" />)}</div></div>
      )}
    </div>
  );
}
