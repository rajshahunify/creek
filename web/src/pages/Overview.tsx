/** The landing page: this week's headline numbers, the MQL trend, recent exports and the reports. */

import { useEffect, useState } from "react";
import { BarChart } from "../components/dash/BarChart";
import { Kpi } from "../components/dash/Kpi";
import { Activity, ChevronRight, Table } from "../components/Icons";
import { getOverview, useSheetList } from "../dashboard/data";
import { relativeAge } from "../dashboard/table";
import type { Overview as O } from "../dashboard/types";
import { href, MUSIC_SHEET } from "../router";
import { useMusicRows } from "./MusicSheet";

export function Overview() {
  const [data, setData] = useState<O | null>(null);
  const sheets = useSheetList();
  const musicRows = useMusicRows();
  useEffect(() => { getOverview().then(setData); }, []);
  const hour = new Date().getHours();

  return (
    <div className="page">
      <div className="page-bar">
        <div className="page-title">
          <h1>Good {hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening"}</h1>
          <p>Here's how demand gen is tracking this week.</p>
        </div>
      </div>

      <section className="kpis" aria-label="This week">
        {data ? data.kpis.map((k) => <Kpi key={k.label} kpi={k} />) : Array.from({ length: 4 }, (_, i) => <div key={i} className="kpi panel shimmer-panel" />)}
      </section>

      <div className="overview-grid">
        <section className="panel chart-panel">
          <header className="panel-head">
            <h2>MQLs per week</h2>
            <span className="muted">Last 12 weeks, all regions</span>
            <a className="panel-link" href={href({ page: "report", id: 4 })}>MQL Weekly <ChevronRight /></a>
          </header>
          {data ? <BarChart label="MQLs per week, last 12 weeks" data={data.weeks.map((w) => ({ x: w.week, y: w.mqls }))} /> : <div className="chart shimmer-panel" />}
        </section>

        <RecentExports recent={data?.recent ?? []} />

        <section className="panel span-all">
          <header className="panel-head"><h2>Reports</h2><span className="muted">Live from the database (demo)</span></header>
          <ul className="list">
            {sheets.map((s) => (
              <li key={s.id}>
                <a href={href({ page: "report", id: s.id })}>
                  <span className="list-icon"><Table /></span>
                  <span className="list-text"><strong>{s.name}</strong><span className="muted">{s.description}</span></span>
                  <span className="muted small tabular">{(s.id === MUSIC_SHEET ? musicRows : s.row_count).toLocaleString()} rows</span>
                </a>
              </li>
            ))}
          </ul>
        </section>

      </div>
    </div>
  );
}

function RecentExports({ recent }: { recent: O["recent"] }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Recent exports</h2>
        <a className="panel-link" href={href({ page: "admin", tab: "log" })}>Export log <ChevronRight /></a>
      </header>
      <ul className="list">
        {recent.map((e) => (
          <li key={e.at}>
            <div>
              <span className="list-icon"><Activity /></span>
              <span className="list-text"><strong>{e.who}</strong><span className="muted">{e.sheet} · {e.rows.toLocaleString()} rows</span></span>
              <span className="muted small">{relativeAge(Date.now() - new Date(e.at).getTime())}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
