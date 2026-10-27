/** Talking to the station: typed wrappers around its small HTTP API (see creek/server.py). */

export interface Song {
  tid: number;
  song: string;
  title: string;
  artist: string;
  duration: number;
  art: string | null;
}

export interface QueueItem extends Song {
  mine: boolean;
}

export interface State {
  now: (Song & { via: "shuffle" | "queue" | "request" | "" }) | null;
  quiet: boolean;
  paused: boolean;
  here: number;
  pos: number;
  dur: number;
  queue: QueueItem[];
  queue_version: number;
  shuffle_next: Song | null;
  earlier: Song[];
  songs: number;
  notice: [number, string];
  seq: number;
  news: number;
  controls_open: boolean;
  accepting: boolean;
  reactions: string[];
}

export interface StationHit {
  id: number;
  song: string;
  duration: number;
  art: string | null;
}

export interface YouTubeHit {
  vid: string;
  title: string;
  channel: string;
  duration: number | null;
  url: string;
  thumb: string;
  live: boolean;
  on_station: number | null;
  why_not: string;
}

export interface NewsItem {
  n: number;
  date: string;
  title: string;
  lines: string[];
}

export type Control = "toggle" | "pause" | "resume" | "next" | "prev" | "fwd" | "back" | "clear";

/** Where a posted song goes: first in line, at the end, at place N, or straight on for everyone. */
export type Placement = { kind: "next" } | { kind: "end" } | { kind: "at"; place: number } | { kind: "now" };

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

/** Anonymous, but the same for this browser, so "one song waiting per person" and "yours" work. */
export const listenerId: string = (() => {
  try {
    const saved = localStorage.getItem("creek.id");
    if (saved) return saved;
  } catch { /* private mode: a fresh id per visit is fine */ }
  const bytes = crypto.getRandomValues(new Uint8Array(8));   // (randomUUID needs https; this doesn't)
  const id = "web-" + Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  try { localStorage.setItem("creek.id", id); } catch { /* ignore */ }
  return id;
})();

type Params = Record<string, string | number | boolean | undefined>;

function query(params: Params): string {
  const q = new URLSearchParams({ id: listenerId });
  for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v === true ? 1 : v));
  return q.toString();
}

async function call<T>(method: "GET" | "POST", path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${path}?${query(params)}`, { method, signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("Can't reach the station", 0);
  }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(typeof body.detail === "string" ? body.detail : r.statusText, r.status);
  return body as T;
}

const wait = (ms: number) => new Promise((ok) => setTimeout(ok, ms));

export const api = {
  state: () => call<State>("GET", "/state"),
  control: (action: Control) =>
    call<{ notice: number; paused: boolean; cleared?: number; pos?: number; dur?: number }>("POST", `/ctl/${action}`),
  seek: (to: number) => call<{ notice: number; pos: number; dur: number }>("POST", "/ctl/seek", { to: Math.round(to) }),
  move: (tid: number, to: number) =>
    call<{ notice: number; place: number; queue_version: number }>("POST", "/queue/move", { tid, to }),
  remove: (tid: number) => call<{ notice: number; queue_version: number }>("POST", "/queue/remove", { tid }),
  search: (q: string, signal?: AbortSignal) => call<StationHit[]>("GET", "/search", { q }, signal),
  youtube: (q: string, signal?: AbortSignal) => call<YouTubeHit[]>("GET", "/yt/search", { q }, signal),
  news: (seen = 0) => call<{ version: number; news: NewsItem[] }>("GET", "/news", { seen }),
  /** A station on the open internet has a key: the right one comes back as a cookie. */
  key: (key: string) => call<{ ok: boolean }>("POST", "/key", { key }),

  /** Post a song (a link, or a track already on the station) and wait until it's in place. Resolves with the
   * station's message ("up next", "playing now: ..."), rejects with why not. */
  async post(what: { url: string } | { track: number }, where: Placement): Promise<string> {
    const params: Params = { ...what };
    if (where.kind === "next") params.next = true;
    if (where.kind === "now") params.now = true;
    if (where.kind === "at") params.at = where.place;
    const r = await call<{ msg?: string; ticket?: number }>("POST", "/post", params);
    if (r.ticket === undefined) return r.msg ?? "";
    for (;;) {
      await wait(1200);
      const t = await call<{ status: string; msg: string }>("GET", `/add/${r.ticket}`);
      if (t.status === "failed") throw new ApiError(t.msg || "couldn't get that one", 422);
      if (t.status === "done") return t.msg;
    }
  },
};
