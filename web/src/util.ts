/** Small pure helpers: time formatting, the key map, the progress bar's clock. Covered by util.test.ts. */

export function mmss(sec: number | null | undefined): string {
  const s = Math.max(0, Math.floor(sec ?? 0));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${r}` : `${m}:${r}`;
}

/** Total length in words, for the queue header: "12 min", "1 h 5 min". */
export function span(sec: number): string {
  const m = Math.round(sec / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

/** Where the song is now, counting on from the last word from the station (it doesn't move while paused). */
export function positionAt(pos: number, dur: number, paused: boolean, since: number, now: number): number {
  const p = paused ? pos : pos + Math.max(0, now - since) / 1000;
  return dur > 0 ? Math.min(p, dur) : p;
}

export function looksLikeLink(text: string): boolean {
  return /^https?:\/\/\S+$/i.test(text.trim());
}

export type Action =
  | "toggle" | "next" | "prev" | "fwd" | "back"
  | "search" | "mute" | "louder" | "quieter" | "help" | "news" | "queue";

export interface KeyLike {
  key: string;
  shiftKey: boolean;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
}

/** What a key press means on TAL Master, the music's sheet (not while typing in a box). The same list shows in the ? dialog.
 * Ctrl+K isn't here: it's the dashboard's "go to" palette on every page. */
export function keyAction(e: KeyLike): Action | null {
  const mod = e.ctrlKey || e.metaKey;
  if (e.altKey) return null;
  if (mod && e.key === "ArrowRight") return "next";
  if (mod && e.key === "ArrowLeft") return "prev";
  if (mod) return null;
  switch (e.key) {
    case " ": case "k": case "K": return "toggle";
    case "ArrowRight": return "fwd";
    case "ArrowLeft": return "back";
    case "ArrowUp": return "louder";
    case "ArrowDown": return "quieter";
    case "N": return e.shiftKey ? "next" : null;
    case "P": return e.shiftKey ? "prev" : null;
    case "/": return "search";
    case "m": case "M": return "mute";
    case "?": return "help";
    case "w": case "W": return "news";
    case "q": case "Q": return "queue";
  }
  return null;
}

export const SHORTCUTS: [string, [string[], string][]][] = [
  ["Anywhere", [
    [["Ctrl K"], "Go to a page, report or action"],
    [["?"], "These shortcuts"],
    [["Media keys"], "Pause, play and skip the music"],
  ]],
  ["On TAL Master (the music)", [
    [["Space", "K"], "Pause / play, for everyone"],
    [["←", "→"], "Jump back / ahead 5 s"],
    [["Shift N", "Ctrl →"], "Next song"],
    [["Shift P", "Ctrl ←"], "Previous song"],
    [["/"], "Search the station and YouTube"],
    [["↑", "↓"], "Your volume"],
    [["M"], "Mute (just you)"],
    [["Q"], "Jump to the first queued song"],
    [["↑", "↓"], "With a row selected: the row above / below"],
    [["Shift ↑", "Shift ↓"], "Move the selected song up / down the queue"],
    [["Delete"], "Take the selected song out of the queue"],
    [["W"], "What's new"],
    [["Esc"], "In the search box: back to the queue"],
  ]],
];

/** Anonymous notes about what someone else just did. */
export const SEEN: Record<string, string> = {
  pause: "Someone paused the stream",
  resume: "Someone pressed play",
  next: "Someone skipped ahead",
  prev: "Someone went back a song",
  clear: "Someone cleared the up-next queue",
  fwd: "Someone jumped ahead 5 s",
  back: "Someone jumped back 5 s",
  seek: "Someone jumped within the song",
  move: "Someone rearranged the queue",
  remove: "Someone took a song out of the queue",
  playnow: "Someone played a song now",
};
