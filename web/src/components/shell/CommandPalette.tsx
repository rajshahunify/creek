/** Ctrl K: jump to any page or report by typing a few letters of it. */

import { KeyboardEvent, ReactNode, useMemo, useState } from "react";
import { useSheetList } from "../../dashboard/data";
import { player } from "../../player";
import { go, Route } from "../../router";
import { Dashboard, Headphones, Music, Search, Shield, Table } from "../Icons";
import { Modal } from "../Modal";

interface Item { label: string; hint: string; icon: ReactNode; run: () => void }

export function CommandPalette({ onClose, onMusicSearch, musicBar, onMusicBar }: {
  onClose: () => void; onMusicSearch: () => void; musicBar: boolean; onMusicBar: () => void;
}) {
  const sheets = useSheetList();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const to = (r: Route) => () => go(r);
  const items: Item[] = useMemo(() => [
    { label: "Overview", hint: "Page", icon: <Dashboard />, run: to({ page: "overview" }) },
    ...sheets.map((s) => ({ label: s.name, hint: "Report", icon: <Table />, run: to({ page: "report", id: s.id }) })),
    { label: "Search for a song", hint: "TAL Master", icon: <Search />, run: onMusicSearch },
    { label: musicBar ? "Hide the music bar" : "Show the music bar", hint: "Music", icon: <Music />, run: onMusicBar },
    { label: player.view.tuned ? "Stop listening" : "Tune in to the music", hint: "Music", icon: <Headphones />,
      run: () => (player.view.tuned ? player.tuneOut() : player.tuneIn()) },
    { label: "Users", hint: "Admin", icon: <Shield />, run: to({ page: "admin", tab: "users" }) },
    { label: "Export log", hint: "Admin", icon: <Shield />, run: to({ page: "admin", tab: "log" }) },
  ], [sheets, onMusicSearch, musicBar, onMusicBar]);
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = items.filter((it) => words.every((w) => `${it.label} ${it.hint}`.toLowerCase().includes(w)));
  const pick = (it?: Item) => { if (!it) return; onClose(); it.run(); };

  const keys = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(hits.length - 1, s + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); pick(hits[sel]); }
  };

  return (
    <Modal title="Go to" onClose={onClose} className="search palette" hideTitle>
      <label className="search-box">
        <Search />
        <input autoFocus value={q} placeholder="Go to a page, report or action…" aria-label="Go to"
               onChange={(e) => { setQ(e.target.value); setSel(0); }} onKeyDown={keys} />
        <kbd>Esc</kbd>
      </label>
      <div className="results" role="listbox" aria-label="Places">
        {hits.map((it, i) => (
          <div key={it.label} role="option" aria-selected={i === sel} className={`result ${i === sel ? "sel" : ""}`}
               onPointerMove={() => setSel(i)} onClick={() => pick(it)}>
            <span className="palette-icon">{it.icon}</span>
            <span className="row-title">{it.label}</span>
            <span className="muted small">{it.hint}</span>
          </div>
        ))}
        {!hits.length && <p className="hint">Nothing matches “{q}”.</p>}
      </div>
    </Modal>
  );
}
