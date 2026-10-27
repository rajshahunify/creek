/** Music along the bottom of every page: the song's name, the shared controls, your own volume, a quiet progress
 * line, and the way to the queue in TAL Master. The header's music button shows or hides the whole bar; the
 * stream itself is page-wide (player.ts), so it
 * plays on whatever page you're on. Names only: no artwork. */

import { CSSProperties, PointerEvent, useRef, useState } from "react";
import { useNow } from "../../hooks";
import { player, usePlayer } from "../../player";
import { go, MUSIC_SHEET } from "../../router";
import { control, seek, useStore } from "../../store";
import { mmss, positionAt } from "../../util";
import { Headphones, ListPlus, Music, Muted, Next, Pause, Play, Prev, Volume } from "../Icons";

export function MusicBar({ here }: { here: boolean }) {
  const { state, at, online, needKey } = useStore();
  const { held } = usePlayer();
  const tick = useNow(500);
  const sheet = () => go({ page: "report", id: MUSIC_SHEET });
  const queueLink = (
    <button className={`tool ${here ? "on" : ""}`} onClick={sheet} aria-current={here ? "page" : undefined} title="The queue (in TAL Master): reorder it, search for songs">
      <ListPlus /> <span className="label">Up next</span>
      {!!state?.queue.length && <span className="count">{state.queue.length}</span>}
    </button>
  );

  if (needKey || !online || !state) {
    return (
      <div className="music-bar glass" role="region" aria-label="Music">
        <span className="bar-icon"><Music /></span>
        <span className="bar-text muted">
          {needKey ? "Music needs the station's key: open the queue to enter it." : !online ? "Can't reach the music station: trying again…" : "Connecting to music…"}
        </span>
        {queueLink}
      </div>
    );
  }

  const now = state.now;
  const paused = state.paused || held;
  const off = !state.controls_open;
  const pos = positionAt(state.pos, state.dur, state.paused, at, tick);
  return (
    <div className="music-bar glass" role="region" aria-label="Music">
      <ProgressLine pos={pos} />
      <span className="bar-icon"><Music /></span>
      <button className="bar-now" onClick={sheet} title="Open the queue">
        <strong>{now ? now.title || now.song : state.quiet ? "No music yet" : "Joining…"}</strong>
        <span className="muted">
          {now ? [now.artist, paused && "paused", state.dur && `${mmss(pos)} / ${mmss(state.dur)}`].filter(Boolean).join(" · ") : "Open the queue to add a song"}
        </span>
      </button>
      <div className="bar-controls" role="group" aria-label="Shared controls">
        <button className="icon small hide-narrow" disabled={off} onClick={() => control("prev")} aria-label="Previous song" title="Previous song"><Prev /></button>
        <button className="icon mid" disabled={off} onClick={() => control("toggle")} aria-label={paused ? "Play" : "Pause"}
                title={`${paused ? "Play" : "Pause"} for everyone`}>{paused ? <Play /> : <Pause />}</button>
        <button className="icon small" disabled={off} onClick={() => control("next")} aria-label="Next song" title="Next song"><Next /></button>
      </div>
      <Listen />
      {queueLink}
    </div>
  );
}

/** A thin, quiet line along the top of the bar. Click (or drag) it to jump within the song, for everyone. */
function ProgressLine({ pos }: { pos: number }) {
  const { state } = useStore();
  const line = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{ x: number; t: number } | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  const dur = state?.dur ?? 0;
  const seekable = !!state?.now && !state.paused && !!state.controls_open && dur > 0;
  const at = (x: number) => {
    const r = line.current!.getBoundingClientRect();
    return { x: Math.min(r.width, Math.max(0, x - r.left)), t: (Math.min(1, Math.max(0, (x - r.left) / r.width))) * dur };
  };
  const shown = drag ?? pos;
  return (
    <div ref={line} className={`bar-progress ${seekable ? "seekable" : ""} ${drag !== null ? "dragging" : ""}`}
         role="slider" aria-label="Song position" aria-valuemin={0} aria-valuemax={Math.round(dur)} aria-valuenow={Math.round(shown)}
         aria-valuetext={`${mmss(shown)} of ${mmss(dur)}`} aria-disabled={!seekable}
         onPointerDown={(e: PointerEvent<HTMLDivElement>) => { if (!seekable) return; e.currentTarget.setPointerCapture(e.pointerId); setDrag(at(e.clientX).t); }}
         onPointerMove={(e) => { if (!dur) return; const h = at(e.clientX); setHover(h); if (drag !== null) setDrag(h.t); }}
         onPointerUp={() => { if (drag !== null) { seek(drag); setDrag(null); } }}
         onPointerCancel={() => setDrag(null)} onPointerLeave={() => setHover(null)}>
      <div className="track"><div className="fill" style={{ width: dur ? `${Math.min(100, (shown / dur) * 100)}%` : 0 }} /></div>
      {hover && seekable && <span className="bar-tip" style={{ left: hover.x }}>{mmss(drag ?? hover.t)}</span>}
    </div>
  );
}

/** Listening is yours alone: tune in or out, mute, volume. */
function Listen() {
  const p = usePlayer();
  const level = p.muted ? 0 : p.volume;
  if (!p.tuned) {
    return <button className="tune" onClick={() => player.tuneIn()}><Headphones /> Tune in</button>;
  }
  return (
    <div className="volume">
      <button className="icon small" onClick={() => player.tuneOut()} title="Stop listening (just you)" aria-label="Stop listening">
        <Headphones className={p.status === "playing" ? "live" : "pulse"} />
      </button>
      <button className="icon small" onClick={() => player.toggleMute()} title="Mute, just you (M)" aria-label={p.muted ? "Unmute" : "Mute"}>
        {level ? <Volume /> : <Muted />}
      </button>
      <input type="range" min={0} max={1} step={0.01} value={level} aria-label="Your volume"
             style={{ "--level": `${level * 100}%` } as CSSProperties}
             onChange={(e) => player.setVolume(Number(e.target.value))} />
      {p.status !== "playing" && <span className="status">{p.status === "buffering" ? "buffering…" : "connecting…"}</span>}
    </div>
  );
}
