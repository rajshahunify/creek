/** The page's one store: the station's state (pushed over server-sent events), plus what only this page knows
 * (songs it's fetching, toasts, a queue order it's waiting on the station to confirm). */

import { useSyncExternalStore } from "react";
import { api, ApiError, Control, listenerId, Placement, State } from "./api";
import { player } from "./player";
import { SEEN } from "./util";

export interface Pending { key: number; label: string; where: Placement["kind"] }
export interface Toast { key: number; text: string; tone: "info" | "error" }

export interface Snapshot {
  state: State | null;
  at: number;                    // performance.now() when `state` arrived: the progress bar counts on from here
  online: boolean;
  pending: Pending[];
  toasts: Toast[];
  order: number[] | null;        // the queue as this page just rearranged it, until the station agrees
  needKey: boolean;              // the station has a key and this browser hasn't given it yet
}

let snap: Snapshot = { state: null, at: 0, online: true, pending: [], toasts: [], order: null, needKey: false };
const listeners = new Set<() => void>();
let keys = 0;
let lastNotice: number | null = null;
let own: { action: string; until: number } = { action: "", until: 0 };   // so we don't hear "someone paused" about ourselves
let orderVersion = Infinity;     // the queue_version that has the order in `order`

function set(patch: Partial<Snapshot>) {
  snap = { ...snap, ...patch };
  listeners.forEach((f) => f());
}

export const needsKey = () => snap.needKey;

export function useStore(): Snapshot {
  return useSyncExternalStore((f) => (listeners.add(f), () => listeners.delete(f)), () => snap);
}

// --- what the station says ---------------------------------------------------------------------

function receive(state: State) {
  const prev = snap.state;
  const [seq, action] = state.notice;
  if (lastNotice !== null && seq > lastNotice && SEEN[action]) {
    if (!(action === own.action && performance.now() < own.until)) toast(SEEN[action]);
  }
  lastNotice = seq;
  if (prev?.paused && !state.paused) player.release();          // someone pressed play: back to the live edge
  const order = snap.order && state.queue_version < orderVersion ? snap.order : null;
  set({ state, at: performance.now(), online: true, order });
}

let source: EventSource | null = null;

export async function connect() {
  // a share link with ?key=...: trade it for the cookie, and keep it out of the address bar
  const fromLink = new URLSearchParams(location.search).get("key");
  if (fromLink) {
    await api.key(fromLink).catch(() => {});
    history.replaceState(null, "", location.pathname);
  }
  try {
    receive(await api.state());
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return set({ needKey: true });
  }
  if (typeof EventSource === "undefined") return poll();
  source?.close();
  source = new EventSource(`/events?id=${encodeURIComponent(listenerId)}`);
  source.addEventListener("state", (e) => receive(JSON.parse((e as MessageEvent).data)));
  source.onerror = () => {
    set({ online: false });
    if (source?.readyState === EventSource.CLOSED) setTimeout(connect, 3000);   // otherwise it retries by itself
  };
}

async function poll() {
  for (;;) {
    try { receive(await api.state()); } catch { set({ online: false }); }
    await new Promise((ok) => setTimeout(ok, 1000));
  }
}

/** The passcode box: true if the station took it. */
export async function giveKey(key: string): Promise<boolean> {
  try {
    await api.key(key.trim());
  } catch {
    return false;
  }
  set({ needKey: false });
  connect();
  return true;
}

// --- doing things ------------------------------------------------------------------------------

export function toast(text: string, tone: Toast["tone"] = "info", ms = 4000) {
  const key = ++keys;
  set({ toasts: [...snap.toasts.slice(-3), { key, text, tone }] });
  setTimeout(() => set({ toasts: snap.toasts.filter((t) => t.key !== key) }), ms);
}

function mine(action: string) {
  own = { action, until: performance.now() + 3000 };
}

function failed(e: unknown) {
  toast(e instanceof ApiError ? e.message : "Something went wrong", "error");
}

const DONE: Partial<Record<string, string>> = {
  pause: "Paused for everyone", resume: "Playing", next: "Next song", prev: "Previous song",
};

export async function control(action: Control) {
  const state = snap.state;
  if (action === "toggle") action = state?.paused || player.held ? "resume" : "pause";
  mine(action);
  if (action === "pause") player.hold();                        // you hear it stop at once; everyone else in a second
  try {
    const r = await api.control(action);
    if (action === "clear") toast(`Queue cleared (${r.cleared} song${r.cleared === 1 ? "" : "s"}; they stay in the shuffle)`);
    else if (DONE[action]) toast(DONE[action]!, "info", 1800);
    if (action !== "pause" && player.held) player.release();
  } catch (e) {
    if (action === "pause") player.release();
    failed(e);
  }
}

export async function seek(to: number) {
  mine("seek");
  try {
    const r = await api.seek(to);
    if (snap.state) set({ state: { ...snap.state, pos: r.pos }, at: performance.now() });
  } catch (e) {
    failed(e);
  }
}

export async function seekBy(by: number) {
  const s = snap.state;
  if (!s?.now) return;
  mine(by > 0 ? "fwd" : "back");
  try {
    const r = await api.control(by > 0 ? "fwd" : "back");
    if (snap.state && r.pos !== undefined) set({ state: { ...snap.state, pos: r.pos }, at: performance.now() });
  } catch (e) {
    failed(e);
  }
}

/** Move a queued song to place `to` (1 = up next). The page shows the new order straight away. */
export async function move(tid: number, to: number) {
  const queue = snap.order ?? snap.state?.queue.map((q) => q.tid) ?? [];
  const from = queue.indexOf(tid);
  if (from < 0) return;
  const order = queue.filter((t) => t !== tid);
  order.splice(Math.max(0, Math.min(to - 1, order.length)), 0, tid);
  orderVersion = Infinity;
  set({ order });
  mine("move");
  try {
    orderVersion = (await api.move(tid, to)).queue_version;
    if ((snap.state?.queue_version ?? 0) >= orderVersion) set({ order: null });
  } catch (e) {
    set({ order: null });
    failed(e);
  }
}

export async function remove(tid: number) {
  const queue = snap.order ?? snap.state?.queue.map((q) => q.tid) ?? [];
  orderVersion = Infinity;
  set({ order: queue.filter((t) => t !== tid) });
  mine("remove");
  try {
    orderVersion = (await api.remove(tid)).queue_version;
    if ((snap.state?.queue_version ?? 0) >= orderVersion) set({ order: null });
  } catch (e) {
    set({ order: null });
    failed(e);
  }
}

/** Post a song; while it downloads it shows in the queue as "fetching". */
export async function post(label: string, what: { url: string } | { track: number }, where: Placement) {
  const key = ++keys;
  if ("url" in what) set({ pending: [...snap.pending, { key, label, where: where.kind }] });
  if (where.kind === "now") mine("playnow");
  try {
    const msg = await api.post(what, where);
    if (where.kind === "now") mine("playnow");
    toast(msg ? msg.charAt(0).toUpperCase() + msg.slice(1) : "Done");
  } catch (e) {
    failed(e);
  } finally {
    set({ pending: snap.pending.filter((p) => p.key !== key) });
  }
}
