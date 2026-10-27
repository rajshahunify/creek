/** The side rail: Overview, the reports, then Admin. A column on a desktop that
 * collapses to icons; below 768px the same list slides in as a drawer from the header's menu button. */

import { useEffect } from "react";
import { relativeAge } from "../../dashboard/table";
import { useSheetList } from "../../dashboard/data";
import { useNow } from "../../hooks";
import { href, MUSIC_SHEET, Route } from "../../router";
import { useStore } from "../../store";
import { useMusicRows } from "../../pages/MusicSheet";
import { ChevronLeft, Close, Dashboard, Shield, Table } from "../Icons";

export function Rail({ route, collapsed, onToggle, drawer, onCloseDrawer }: {
  route: Route; collapsed: boolean; onToggle: () => void; drawer: boolean; onCloseDrawer: () => void;
}) {
  useEffect(() => {
    if (!drawer) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onCloseDrawer();
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [drawer, onCloseDrawer]);
  return (
    <>
      <aside className={`nav-rail glass ${collapsed ? "collapsed" : ""}`} aria-label="Sections">
        <RailBody route={route} shrunk={collapsed} onToggle={onToggle} />
      </aside>
      {drawer && (
        <div className="drawer-wrap">
          <div className="drawer-scrim" onClick={onCloseDrawer} />
          <aside className="nav-rail drawer glass-strong" role="dialog" aria-label="Sections" onClick={(e) => (e.target as HTMLElement).closest("a") && onCloseDrawer()}>
            <RailBody route={route} shrunk={false} onClose={onCloseDrawer} />
          </aside>
        </div>
      )}
    </>
  );
}

function RailBody({ route, shrunk, onToggle, onClose }: { route: Route; shrunk: boolean; onToggle?: () => void; onClose?: () => void }) {
  const sheets = useSheetList();
  const { state, online, needKey } = useStore();
  const musicRows = useMusicRows();
  useNow(60_000);
  // TAL Master's grid is the music: its subtitle counts those rows, live
  const music = needKey ? "Needs the station key" : !online ? "Offline" : !state ? "Connecting…" : `${musicRows.toLocaleString()} rows · live`;
  return (
    <>
      <div className="rail-head">
        {!shrunk && <span className="rail-title">Navigate</span>}
        {onClose ? (
          <button className="icon tiny" onClick={onClose} aria-label="Close the menu"><Close /></button>
        ) : (
          <button className="icon tiny" onClick={onToggle} aria-label={shrunk ? "Expand the menu" : "Collapse the menu"}
                  title={shrunk ? "Expand" : "Collapse"}>
            <ChevronLeft style={{ transform: shrunk ? "rotate(180deg)" : undefined }} />
          </button>
        )}
      </div>
      <nav className="rail-nav">
        <Item to={{ page: "overview" }} route={route} icon={<Dashboard />} label="Overview" shrunk={shrunk} />

        <div className="rail-group">{shrunk ? <hr /> : "Reports"}</div>
        {sheets.map((s) => (
          <Item key={s.id} to={{ page: "report", id: s.id }} route={route} icon={<Table />} label={s.name} shrunk={shrunk}
                sub={s.id === MUSIC_SHEET ? music : `${s.row_count.toLocaleString()} rows · ${relativeAge(Date.now() - new Date(s.executed_at).getTime())}`} />
        ))}

        <div className="rail-group">{shrunk ? <hr /> : "Workspace"}</div>
        <Item to={{ page: "admin", tab: "users" }} route={route} icon={<Shield />} label="Admin" shrunk={shrunk} sub="Users and export log" />
      </nav>
    </>
  );
}

function Item({ to, route, icon, label, sub, shrunk }: {
  to: Route; route: Route; icon: JSX.Element; label: string; sub?: string; shrunk: boolean;
}) {
  const active = route.page === to.page && (to.page !== "report" || (route.page === "report" && route.id === to.id));
  return (
    <a className={`rail-item ${active ? "active" : ""}`} href={href(to)} aria-current={active ? "page" : undefined}
       title={shrunk ? (sub ? `${label}: ${sub}` : label) : sub}>
      <span className="rail-icon">{icon}</span>
      {!shrunk && (
        <span className="rail-text">
          <span className="rail-label">{label}</span>
          {sub && <span className="rail-sub">{sub}</span>}
        </span>
      )}
    </a>
  );
}
