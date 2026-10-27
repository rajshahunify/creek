/** TAL Master, whose grid is the office's music: the song playing now, then the queue, the shuffle's pick and what
 * played before. The sheet keeps its name, place and toolbar; each tool does the music's version of its job. Queued rows are dragged (or Shift+↑/↓) into any order, and the page's search
 * box finds songs on the station and on YouTube, Refresh re-pulls the live queue, Export downloads the grid as CSV. Names only: no artwork anywhere. Its keys (Space, ←/→, 1–6…) only
 * work on this page, so typing in a report never pauses the office's music. */

import {
  closestCenter, DndContext, DragEndEvent, KeyboardSensor, PointerSensor, TouchSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { KeyboardEvent, ReactNode, useCallback, useEffect, useRef, useState } from "react";
import type { Placement, QueueItem, Song } from "../api";
import { restrictToVerticalAxis } from "../components/dndModifiers";
import { AgeBadge } from "../components/dash/AgeBadge";
import { KeyPrompt, Welcome, WhatsNew } from "../components/Dialogs";
import { Bell, ChevronLeft, ChevronRight, Close, Down, Download, Grip, ListPlus, More, PlayNext, Refresh, Search, Trash, Up, YouTube, Zap } from "../components/Icons";
import { Menu } from "../components/Menu";
import { Confirm } from "../components/Modal";
import { useStored } from "../hooks";
import { player } from "../player";
import { go } from "../router";
import { Result, useSongSearch } from "../songSearch";
import { toCsv } from "../dashboard/table";
import { connect, control, move, needsKey, post, remove, seekBy, Snapshot, toast, useStore } from "../store";
import { keyAction, mmss } from "../util";

/** The sheet the music took over (see MUSIC_SHEET in router.ts). */
export const MUSIC_TITLE = "TAL Master";
const COLUMNS = ["#", "Title", "Artist", "Length", "Status", "Added by"];

/** The grid's rows as plain text, in order: for the row counts and for Export. */
export function musicRows({ state, order, pending }: Pick<Snapshot, "state" | "order" | "pending">): string[][] {
  if (!state) return [];
  const byTid = new Map(state.queue.map((q) => [q.tid, q]));
  const queue = order ? order.flatMap((t) => byTid.get(t) ?? []) : state.queue;
  const shuffle = state.shuffle_next && !byTid.has(state.shuffle_next.tid) ? state.shuffle_next : null;
  return [
    ...(state.now ? [["▶", state.now.title || state.now.song, state.now.artist, mmss(state.dur), state.paused ? "Paused" : "Running",
      state.now.via === "shuffle" ? "Shuffle" : "A listener"]] : []),
    ...pending.map((p) => ["", p.label, "", "", "Fetching", "You"]),
    ...queue.map((q, i) => [String(i + 1), q.title || q.song, q.artist, mmss(q.duration), i ? "Queued" : "Up next", q.mine ? "You" : "A listener"]),
    ...(shuffle ? [["", shuffle.title || shuffle.song, shuffle.artist, mmss(shuffle.duration), "Shuffle pick", "Shuffle"]] : []),
    ...state.earlier.map((s) => ["", s.title || s.song, s.artist, mmss(s.duration), "Played", ""]),
  ];
}

export function useMusicRows(): number {
  return musicRows(useStore()).length;
}

function download(name: string, csv: string) {
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob), download: `${name.replace(/[^\w-]+/g, "_")}_${new Date().toISOString().slice(0, 10)}.csv`,
  });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

let searchWanted = false;
/** Put the cursor in this page's search box, from anywhere (the command palette): now, or once the page is up. */
export function requestSearch() {
  searchWanted = true;
  window.dispatchEvent(new Event("creek:search"));
}

export function MusicSheet({ blocked }: { blocked: boolean }) {
  const snap = useStore();
  const { state, online, needKey, at } = snap;
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [news, setNews] = useState(false);
  const [welcome, setWelcome] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [welcomed, setWelcomed] = useStored("creek.welcomed", "0");
  const [seenNews, setSeenNews] = useStored("creek.seenNews", "0");
  const box = useRef<HTMLInputElement>(null);
  const focusSearch = useCallback(() => box.current?.focus(), []);
  const search = useSongSearch(text);
  const searching = text.trim() !== "";
  const dialog = news || welcome || confirming;

  useEffect(() => {
    const want = () => { if (searchWanted) { searchWanted = false; focusSearch(); } };
    want();
    window.addEventListener("creek:search", want);
    return () => window.removeEventListener("creek:search", want);
  }, []);
  useEffect(() => { if (welcomed !== "1" && !searchWanted) setWelcome(true); }, []);   // first visit only

  useEffect(() => {
    const down = (e: globalThis.KeyboardEvent) => {
      if (e.defaultPrevented || dialog || blocked || needsKey()) return;
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, [contenteditable=true], tr[tabindex]")) return;   // rows have their own keys
      if ((e.key === " " || e.key === "Enter") && t.closest("button, a, [role=menuitem]")) return;   // the button's own job
      const a = keyAction(e);
      if (!a || a === "help") return;                                                                  // ? is the shell's
      e.preventDefault();
      switch (a) {
        case "toggle": case "next": case "prev": return control(a);
        case "fwd": return seekBy(5);
        case "back": return seekBy(-5);
        case "louder": return player.setVolume(player.view.volume + 0.05);
        case "quieter": return player.setVolume(player.view.volume - 0.05);
        case "mute": return player.toggleMute();
        case "search": return focusSearch();
        case "news": return setNews(true);
        case "queue": return document.querySelector<HTMLElement>("#queue tr[data-queued]")?.focus();
      }
    };
    window.addEventListener("keydown", down);
    return () => window.removeEventListener("keydown", down);
  }, [dialog, blocked]);

  const queued = state?.queue.length ?? 0;
  const unseen = state ? state.news > Number(seenNews) : false;
  const rows = musicRows(snap);
  const pulled = state ? new Date(Date.now() - (performance.now() - at)).toISOString() : null;
  const refresh = async () => {
    setBusy(true);
    await connect();
    setBusy(false);
    toast("Report refreshed");
  };
  const exportCsv = () => {
    if (searching) download(`${MUSIC_TITLE} search`, toCsv(["Title", "Artist / channel", "Length", "Source"].map((name) => ({ name, kind: "text" })),
      search.results.map((r) => [r.title, r.by, r.length, SOURCE[r.kind]])));
    else download(MUSIC_TITLE, toCsv(COLUMNS.map((name) => ({ name, kind: "text" })), rows));
  };

  return (
    <div className="page page-fill">
      <div className="page-bar">
        <div className="page-title">
          <h1>{MUSIC_TITLE}</h1>
          <p>{state
            ? `${rows.length} rows · ${COLUMNS.length} columns · live · ${queued ? `${queued} up next` : "the shuffle is picking"} · ${state.here} listening`
            : needKey ? "This station needs its key" : !online ? "Can't reach the station" : "Connecting…"}</p>
        </div>
        <div className="page-actions">
          <label className="field wide" title="Finds songs on the station and on YouTube. Paste a link to add it.">
            <Search />
            <input ref={box} value={text} onChange={(e) => setText(e.target.value)} placeholder="Search every column"
                   aria-label="Search the station and YouTube" aria-controls="queue" spellCheck={false}
                   onKeyDown={(e) => { if (e.key === "Escape" && text) { e.preventDefault(); setText(""); } }} />
            {search.busy && <span className="spinner" aria-label="Searching YouTube" />}
            {text && <button className="icon tiny" onClick={() => { setText(""); focusSearch(); }} aria-label="Clear the search"><Close /></button>}
          </label>
          <span className="hide-narrow"><AgeBadge at={pulled} /></span>
          <button className="tool" onClick={refresh} disabled={busy || needKey} title="Pull the live queue again">
            <Refresh className={busy ? "spin" : ""} /> <span className="label">Refresh</span>
          </button>
          <button className="tool primary" onClick={exportCsv} disabled={searching ? !search.results.length : !rows.length}
                  title="Download the rows on screen as CSV">
            <Download /> <span className="label">Export</span>
          </button>
          <Menu label={unseen ? "More (what's new)" : "More"} icon={<><More />{unseen && <span className="dot" />}</>} items={[
            { icon: <Bell />, text: unseen ? "What's new (new)" : "What's new", run: () => setNews(true) },
            queued > 0 && !!state?.controls_open && { icon: <Trash />, text: "Clear the queue, for everyone", run: () => setConfirming(true), danger: true },
          ]} />
        </div>
      </div>

      {!online && !needKey && <div className="offline" role="alert">Can't reach the station: trying again…</div>}
      {state && !state.controls_open && <div className="offline info">This station keeps pause, skip and the queue to itself. You can still listen and add songs.</div>}

      {searching
        ? <Results search={search} input={box} onDone={() => setText("")} />
        : <QueueTable onSearch={focusSearch} />}

      {needKey && <KeyPrompt onLeave={() => go({ page: "overview" })} />}
      {news && <WhatsNew seen={Number(seenNews)} onClose={() => { setNews(false); if (state) setSeenNews(String(state.news)); }} />}
      {welcome && !needKey && (
        <Welcome onSearch={focusSearch} onClose={() => {
          setWelcomed("1");
          if (state) setSeenNews(String(state.news));   // the welcome covers it: no "new" badge on day one
          setWelcome(false);
        }} />
      )}
      {confirming && (
        <Confirm title="Clear the queue for everyone?" yes="Clear queue" onClose={() => setConfirming(false)}
                 onYes={() => { setConfirming(false); control("clear"); }}>
          {queued} song{queued === 1 ? "" : "s"} will come off the queue. They stay on the station, in the shuffle.
        </Confirm>
      )}
    </div>
  );
}

// --- the queue, as a grid ----------------------------------------------------------------------------------------

const COLS = ["", ...COLUMNS, ""];

function QueueTable({ onSearch }: { onSearch: () => void }) {
  const { state, order, pending } = useStore();
  const byTid = new Map((state?.queue ?? []).map((q) => [q.tid, q]));
  const queue: QueueItem[] = order ? order.flatMap((t) => byTid.get(t) ?? []) : state?.queue ?? [];
  const editable = !!state?.controls_open;
  const now = state?.now;
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const dropped = (e: DragEndEvent) => {
    if (!e.over || e.active.id === e.over.id) return;
    move(Number(e.active.id), queue.findIndex((q) => q.tid === e.over!.id) + 1);
  };
  const shuffle = state?.shuffle_next && !byTid.has(state.shuffle_next.tid) ? state.shuffle_next : null;
  const rows = (now ? 1 : 0) + pending.length + queue.length + (shuffle ? 1 : 0) + (state?.earlier.length ?? 0);
  const fmt = new Intl.NumberFormat();

  return (
    <div className="table-card">
      <div className="table-scroll">
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={dropped} modifiers={[restrictToVerticalAxis]}>
          <table className="table music queue-grid" id="queue" aria-label="The music queue, in play order">
            <thead><tr>{COLS.map((c, i) => <th key={i} className={c === "Length" ? "num" : ""}><span className="th">{c}</span></th>)}</tr></thead>
            <tbody>
              {now && (
                <tr className="now" tabIndex={0} onKeyDown={rowKeys()}>
                  <td />
                  <td className="place">▶</td>
                  <td className="song-title" title={now.title || now.song}>{now.title || now.song}</td>
                  <td>{now.artist}</td>
                  <td className="num">{mmss(state!.dur)}</td>
                  <td><span className={`pill ${state!.paused ? "warn" : ""}`}>{state!.paused ? "Paused" : "Running"}</span></td>
                  <td className="muted">{now.via === "shuffle" ? "Shuffle" : now.via === "request" || now.via === "queue" ? "A listener" : "—"}</td>
                  <td className="act">{editable && <Menu label={`More for ${now.song}`} items={[{ icon: <PlayNext />, text: "Skip to the next song", run: () => control("next") }]} />}</td>
                </tr>
              )}
              {pending.map((p) => (
                <tr key={`p${p.key}`} className="fetching">
                  <td /><td className="place"><span className="spinner" /></td>
                  <td className="song-title" title={p.label}>{p.label}</td><td /><td />
                  <td><span className="pill info">Fetching…</span></td>
                  <td>You</td>
                  <td className="muted small">{p.where === "now" ? "plays when it's here" : p.where === "next" ? "then up next" : "then queued"}</td>
                </tr>
              ))}
              <SortableContext items={queue.map((q) => q.tid)} strategy={verticalListSortingStrategy}>
                {queue.map((q, i) => <QueuedRow key={q.tid} item={q} place={i + 1} last={i === queue.length - 1} editable={editable} />)}
              </SortableContext>
              {shuffle && <SongRow song={shuffle} status={<span className="pill">Shuffle pick</span>} who="Shuffle" replay={false} />}
              {(state?.earlier ?? []).map((s, i) => (
                <SongRow key={`${s.tid}-${i}`} song={s} status={<span className="pill">Played</span>} who="—" replay={editable} earlier />
              ))}
            </tbody>
          </table>
        </DndContext>
        {state && !queue.length && !pending.length && (
          <button className="table-empty as-button" onClick={onSearch}>
            Nothing queued: the shuffle is picking. <strong>Search for a song</strong> to play it next.
          </button>
        )}
      </div>
      <footer className="table-foot">
        <span className="tabular">{rows ? `1–${fmt.format(rows)} of ${fmt.format(rows)}` : "0 rows"}
          <span className="hide-narrow"> · drag a queued row, or Shift+↑/↓, to change the order</span></span>
        <span className="foot-right">
          <span className="pager hide-narrow">
            <button className="icon tiny" disabled aria-label="Previous page"><ChevronLeft /></button>
            <span className="tabular">Page 1 of 1</span>
            <button className="icon tiny" disabled aria-label="Next page"><ChevronRight /></button>
          </span>
        </span>
      </footer>
    </div>
  );
}

/** ↑/↓ walk the rows like a sheet; with Shift (or Alt) they move a queued song; Delete takes it out. */
function rowKeys(item?: { tid: number; place: number; last: boolean; editable: boolean }) {
  return (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.target !== e.currentTarget) return;
    const shift = e.shiftKey || e.altKey;
    if (item?.editable && shift && e.key === "ArrowUp") { e.preventDefault(); if (item.place > 1) move(item.tid, item.place - 1); return; }
    if (item?.editable && shift && e.key === "ArrowDown") { e.preventDefault(); if (!item.last) move(item.tid, item.place + 1); return; }
    if (item?.editable && (e.key === "Delete" || e.key === "Backspace")) { e.preventDefault(); remove(item.tid); return; }
    if (!shift && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
      e.preventDefault();
      const rows = [...e.currentTarget.closest("tbody")!.querySelectorAll<HTMLElement>("tr[tabindex]")];
      rows[rows.indexOf(e.currentTarget) + (e.key === "ArrowUp" ? -1 : 1)]?.focus();
    }
  };
}

function QueuedRow({ item, place, last, editable }: { item: QueueItem; place: number; last: boolean; editable: boolean }) {
  const s = useSortable({ id: item.tid, disabled: !editable });
  const style = { transform: CSS.Translate.toString(s.transform), transition: s.transition };
  return (
    <tr ref={s.setNodeRef} style={style} className={s.isDragging ? "dragging" : ""} tabIndex={0} data-queued
        onKeyDown={rowKeys({ tid: item.tid, place, last, editable })} aria-label={`${place}. ${item.song}`}>
      <td className="grip-cell">
        {editable && <button className="grip" {...s.attributes} {...s.listeners} tabIndex={-1} aria-label={`Drag ${item.song}`} title="Drag to move"><Grip /></button>}
      </td>
      <td className="place">{place}</td>
      <td className="song-title" title={item.title || item.song}>{item.title || item.song}</td>
      <td>{item.artist}</td>
      <td className="num">{mmss(item.duration)}</td>
      <td><span className={`pill ${place === 1 ? "info" : ""}`}>{place === 1 ? "Up next" : "Queued"}</span></td>
      <td>{item.mine ? "You" : "A listener"}</td>
      <td className="act">
        {editable && (
          <Menu label={`More for ${item.song}`} items={[
            place > 1 && { icon: <PlayNext />, text: "Play next", run: () => move(item.tid, 1) },
            { icon: <Zap />, text: "Play now, for everyone", run: () => post(item.song, { track: item.tid }, { kind: "now" }) },
            place > 1 && { icon: <Up />, text: "Move up", run: () => move(item.tid, place - 1) },
            !last && { icon: <Down />, text: "Move down", run: () => move(item.tid, place + 1) },
            { icon: <Trash />, text: "Take out of the queue", run: () => remove(item.tid), danger: true },
          ]} />
        )}
      </td>
    </tr>
  );
}

function SongRow({ song, status, who, replay, earlier }: { song: Song; status: ReactNode; who: string; replay: boolean; earlier?: boolean }) {
  return (
    <tr className={earlier ? "earlier" : ""} tabIndex={0} onKeyDown={rowKeys()}>
      <td /><td className="place">–</td>
      <td className="song-title" title={song.title || song.song}>{song.title || song.song}</td>
      <td>{song.artist}</td>
      <td className="num">{mmss(song.duration)}</td>
      <td>{status}</td>
      <td className="muted">{who}</td>
      <td className="act">
        {replay && (
          <Menu label={`More for ${song.song}`} items={[
            { icon: <PlayNext />, text: "Play again next", run: () => post(song.song, { track: song.tid }, { kind: "next" }) },
            { icon: <Zap />, text: "Play now, for everyone", run: () => post(song.song, { track: song.tid }, { kind: "now" }) },
          ]} />
        )}
      </td>
    </tr>
  );
}

// --- search results, in the same grid ----------------------------------------------------------------------------

const SOURCE: Record<Result["kind"], string> = { station: "On the station", youtube: "YouTube", link: "Link" };

function Results({ search, input, onDone }: { search: ReturnType<typeof useSongSearch>; input: React.RefObject<HTMLInputElement>; onDone: () => void }) {
  const { state } = useStore();
  const { results, waiting, error, accepting, link, words } = search;
  const [sel, setSel] = useState(0);
  const queue = state?.queue ?? [];
  useEffect(() => setSel(0), [words]);

  const pick = (r: Result | undefined, where: Placement) => {
    if (!r || r.why_not) return;
    onDone();
    post(r.title, r.target, where);
  };
  // the search box drives the list: ↑/↓ choose, Enter play next, Shift+Enter add to the queue, Ctrl+Enter play now
  useEffect(() => {
    const el = input.current;
    if (!el) return;
    const keys = (e: globalThis.KeyboardEvent) => {
      if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, results.length - 1)); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
      else if (e.key === "Enter") {
        e.preventDefault();
        pick(results[sel], e.ctrlKey || e.metaKey ? { kind: "now" } : e.shiftKey ? { kind: "end" } : { kind: "next" });
      }
    };
    el.addEventListener("keydown", keys);
    return () => el.removeEventListener("keydown", keys);
  });
  useEffect(() => { document.querySelector(`#queue [data-i="${sel}"]`)?.scrollIntoView({ block: "nearest" }); }, [sel]);

  return (
    <div className="table-card">
      <div className="table-scroll">
        <table className="table music" id="queue" aria-label="Search results">
          <thead><tr>{["Title", "Artist / channel", "Length", "Source", ""].map((c, i) => <th key={i} className={c === "Length" ? "num" : ""}><span className="th">{c}</span></th>)}</tr></thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={r.key} data-i={i} className={`${i === sel ? "sel" : ""} ${r.why_not ? "disabled" : ""}`} aria-selected={i === sel}
                  onMouseMove={() => setSel(i)} onClick={() => pick(r, { kind: "next" })}>
                <td className="song-title" title={r.title}>{r.title}</td>
                <td>{r.by}</td>
                <td className="num">{r.length}</td>
                <td>
                  <span className={`pill ${r.kind === "station" ? "good" : ""}`}>{r.kind === "youtube" && <YouTube className="yt" />} {SOURCE[r.kind]}</span>
                  {"track" in r.target && r.kind === "youtube" && <span className="muted small"> · already on the station</span>}
                </td>
                <td className="act" onClick={(e) => e.stopPropagation()}>
                  {r.why_not ? <span className="muted small why-not" title={r.why_not}>Can't go in: {r.why_not}</span> : (
                    <span className="row-actions">
                      <button className="icon small" title="Play next (Enter)" aria-label="Play next" onClick={() => pick(r, { kind: "next" })}><PlayNext /></button>
                      <button className="icon small" title="Add to the end of the queue (Shift+Enter)" aria-label="Add to the queue" onClick={() => pick(r, { kind: "end" })}><ListPlus /></button>
                      <button className="icon small" title="Play now, for everyone (Ctrl+Enter)" aria-label="Play now" onClick={() => pick(r, { kind: "now" })}><Zap /></button>
                      {queue.length > 1 && (
                        <Menu label="Play after a queued song" items={queue.slice(0, -1).map((q, n) => ({
                          icon: <span className="menu-num">{n + 2}</span>, text: `After ${q.song}`,
                          run: () => pick(r, { kind: "at", place: n + 2 }),
                        }))} />
                      )}
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {waiting && [0, 1, 2].map((i) => <tr key={`w${i}`} className="loading-row"><td colSpan={5}><span className="shimmer" /></td></tr>)}
          </tbody>
        </table>
        {!accepting && !link && <p className="table-empty">This station isn't taking new music right now: only songs already on it can be queued.</p>}
        {error && <p className="table-empty error">{error}</p>}
        {!waiting && !error && !results.length && <p className="table-empty">Nothing found for “{words}”.</p>}
      </div>
      <footer className="table-foot">
        <span className="tabular">{results.length} result{results.length === 1 ? "" : "s"}{waiting ? " · searching YouTube…" : ""}</span>
        <span className="keys-hint hide-narrow"><kbd>↑</kbd><kbd>↓</kbd> choose · <kbd>Enter</kbd> play next · <kbd>Shift</kbd>+<kbd>Enter</kbd> add to the queue · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> play now · <kbd>Esc</kbd> back to the queue</span>
      </footer>
    </div>
  );
}
