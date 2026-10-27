/** This browser's own audio: the live MP3 stream in an <audio> element. Volume and mute are yours alone;
 * pause/play/next are the station's (store.ts), this just keeps up with them. */

import { useSyncExternalStore } from "react";

export interface PlayerView {
  tuned: boolean;        // the listener asked to hear the stream
  status: "off" | "connecting" | "playing" | "buffering";
  volume: number;        // 0..1
  muted: boolean;
  held: boolean;         // we pressed pause: silent here at once, before the station's fade reaches us
}

const read = (k: string, d: string) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const write = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } };

class Player {
  private audio: HTMLAudioElement | null = null;
  private listeners = new Set<() => void>();
  private retry = 0;
  private retryTimer = 0;
  view: PlayerView = {
    tuned: false, status: "off", held: false,
    volume: Math.min(1, Math.max(0, Number(read("creek.volume", "0.7")) || 0.7)),
    muted: read("creek.muted", "0") === "1",
  };

  get held() { return this.view.held; }
  /** Was this browser listening last time? Then try to carry on (the browser may want a click first). */
  get wasTuned() { return read("creek.tuned", "0") === "1"; }

  subscribe = (f: () => void) => (this.listeners.add(f), () => { this.listeners.delete(f); });

  private set(patch: Partial<PlayerView>) {
    this.view = { ...this.view, ...patch };
    this.listeners.forEach((f) => f());
  }

  private el(): HTMLAudioElement {
    if (this.audio) return this.audio;
    const a = (this.audio = new Audio());
    a.preload = "none";
    a.volume = this.view.volume;
    a.muted = this.view.muted;
    a.addEventListener("playing", () => { this.retry = 0; this.set({ status: "playing" }); });
    a.addEventListener("waiting", () => this.view.tuned && this.set({ status: "buffering" }));
    const lost = () => {
      if (!this.view.tuned) return;
      this.set({ status: "connecting" });
      clearTimeout(this.retryTimer);
      this.retryTimer = window.setTimeout(() => this.connect(), Math.min(30_000, 1000 * 2 ** this.retry++));
    };
    a.addEventListener("error", lost);
    a.addEventListener("ended", lost);
    // a live stream should stay live: if the browser has fallen behind what it has buffered, catch up
    setInterval(() => {
      if (!this.view.tuned || a.paused || !a.buffered.length) return;
      const edge = a.buffered.end(a.buffered.length - 1);
      if (edge - a.currentTime > 3) a.currentTime = edge - 0.4;
    }, 2000);
    return a;
  }

  private connect() {
    const a = this.el();
    a.src = `/stream.mp3?t=${Date.now()}`;      // a fresh connection starts at the live edge
    a.muted = this.view.muted || this.view.held;
    a.play().catch((e: Error) => {
      if (e.name === "NotAllowedError") this.set({ tuned: false, status: "off" });   // needs a click first
    });
  }

  tuneIn() {
    write("creek.tuned", "1");
    this.set({ tuned: true, status: "connecting" });
    this.connect();
  }

  tuneOut() {
    write("creek.tuned", "0");
    clearTimeout(this.retryTimer);
    this.set({ tuned: false, status: "off", held: false });
    const a = this.el();
    a.pause();
    a.removeAttribute("src");
    a.load();
  }

  hold() {
    this.set({ held: true });
    if (this.audio) this.audio.muted = true;
  }

  release() {
    if (!this.view.held) return;
    this.set({ held: false });
    if (this.view.tuned) this.connect();          // drop the stale buffer: rejoin where everyone is
  }

  setVolume(v: number) {
    const volume = Math.min(1, Math.max(0, v));
    write("creek.volume", String(volume));
    if (this.audio) this.audio.volume = volume;
    this.set({ volume, muted: volume === 0 ? this.view.muted : false });
    if (this.audio) this.audio.muted = this.view.muted || this.view.held;
    write("creek.muted", this.view.muted ? "1" : "0");
  }

  toggleMute() {
    const muted = !this.view.muted;
    write("creek.muted", muted ? "1" : "0");
    if (this.audio) this.audio.muted = muted || this.view.held;
    this.set({ muted });
  }
}

export const player = new Player();

export function usePlayer(): PlayerView {
  return useSyncExternalStore(player.subscribe, () => player.view);
}
