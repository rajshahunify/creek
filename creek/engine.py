"""The playout engine: one endless PCM stream, crossfaded, paced to the wall clock, encoded to MP3.

    library ─▶ decoder (ffmpeg, per track) ─▶ lookahead buffer ─▶ crossfade ─▶ pacing ─┬▶ on_pcm
                                                                                        └▶ encoder (ffmpeg) ─▶ on_mp3
"""

import os
import subprocess
import threading
import time
from collections.abc import Callable

from . import audio, media
from .config import (BLOCK_SEC, CHANNELS, CROSSFADE_SEC, FRAME_BYTES, LEAD_SEC, LOOKAHEAD_SEC,
                     MP3_BITRATE, PAUSE_FADE_SEC, RATE, RESUME_FADE_SEC, SKIP_FADE_SEC)
from .library import Library, Track
from .room import Room
from .upnext import UpNext


def _bytes(sec: float) -> int:
    return int(sec * RATE) * FRAME_BYTES


BLOCK = _bytes(BLOCK_SEC)
XFADE = _bytes(CROSSFADE_SEC)
SKIP_FADE = _bytes(SKIP_FADE_SEC)
LOOKAHEAD = _bytes(LOOKAHEAD_SEC)
PAUSE_FADE = _bytes(PAUSE_FADE_SEC)
RESUME_FADE = _bytes(RESUME_FADE_SEC)
SILENCE = bytes(BLOCK)


class Playing:
    """A track (or the ambience filler when track is None) being decoded ahead of playout."""

    def __init__(self, track: Track | None, source: media.Source):
        self.track, self.src = track, source
        self.buf = bytearray()
        self.eof = False
        self.trimmed = False

    def fill(self, want: int):
        while not self.eof and len(self.buf) < want:
            data = self.src.read(65536)
            if not data:
                self.eof = True
                del self.buf[len(self.buf) // FRAME_BYTES * FRAME_BYTES:]
                break
            self.buf += data

    def take(self, n: int) -> bytes:
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def trim_tail(self):
        if not self.trimmed:
            del self.buf[audio.audible_length(self.buf):]
            self.trimmed = True

    def close(self):
        self.src.close()


class Engine:
    def __init__(self, library: Library, room: Room, on_mp3: Callable[[bytes], None],
                 on_pcm: Callable[[bytes], None], upnext: UpNext | None = None):
        self.library, self.room = library, room
        self.upnext = upnext if upnext is not None else UpNext()   # (an empty queue is falsy)
        self.on_mp3, self.on_pcm = on_mp3, on_pcm
        self.current: Track | None = None
        self.history: list[int] = []        # ids of tracks that have played, oldest first
        self._ctl = threading.Lock()
        self._want: int | None = None       # play this one next instead of the shuffle's pick
        self._skip = threading.Event()
        self._paused = threading.Event()
        self._stop = threading.Event()
        self._enc: subprocess.Popen | None = None

    # --- control -------------------------------------------------------------------------------

    def start(self):
        self._start_encoder()
        threading.Thread(target=self._run, name="creek-playout", daemon=True).start()

    def stop(self):
        self._stop.set()
        if self._enc and self._enc.poll() is None:
            self._enc.kill()

    def skip(self):
        self._skip.set()

    def play_now(self, tid: int):
        """Crossfade into this track now (it must be in rotation)."""
        with self._ctl:
            self._want = tid
        self._skip.set()

    def prev(self) -> bool:
        """Go back to the song before this one, or restart this one if it's the first. False if neither."""
        with self._ctl:
            if len(self.history) >= 2:
                self.history.pop()
            if not self.history:
                return False
            self._want = self.history[-1]
        self._skip.set()
        return True

    def pause(self):
        self._paused.set()
        self.room.set_paused(True)       # say so right away, not once the fade is done

    def resume(self):
        self._unpause()

    def _unpause(self):
        self._paused.clear()
        self.room.set_paused(False)

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    # --- encoder -------------------------------------------------------------------------------

    def _start_encoder(self):
        self._enc = subprocess.Popen(
            [media.FFMPEG, "-nostdin", "-v", "error", "-f", "s16le", "-ar", str(RATE), "-ac", str(CHANNELS),
             "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", MP3_BITRATE, "-write_xing", "0",
             "-id3v2_version", "0", "-flush_packets", "1", "-f", "mp3", "pipe:1"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        threading.Thread(target=self._read_mp3, args=(self._enc,), name="creek-mp3", daemon=True).start()

    def _read_mp3(self, proc: subprocess.Popen):
        fd, pending, last = proc.stdout.fileno(), bytearray(), time.monotonic()
        while data := os.read(fd, 65536):
            pending += data
            if len(pending) >= 1024 or time.monotonic() - last > 0.05:    # small batches: less delay
                self.on_mp3(bytes(pending))
                pending.clear()
                last = time.monotonic()

    def _write(self, pcm: bytes):
        try:
            self._enc.stdin.write(pcm)
        except (BrokenPipeError, OSError, ValueError):
            if not self._stop.is_set():
                self._start_encoder()

    # --- playout -------------------------------------------------------------------------------

    def _open(self, track: Track | None) -> Playing | None:
        if track is None or not os.path.exists(track.path):
            return None
        p = Playing(track, media.track_source(track.path, track.gain_db))
        p.fill(BLOCK)
        if p.buf:
            return p
        p.close()
        self.library.mark_bad(track.id)
        return None

    def _open_next(self) -> Playing:
        """What plays next: the operator's pick, then songs listeners posted, then the shuffle."""
        with self._ctl:
            want, self._want = self._want, None
        if want is not None and (p := self._open(self.library.get(want))):
            self.library.mark_played(p.track.id)
            return p
        while (req := self.upnext.pop()) is not None:
            if p := self._open(self.library.get(req.tid)):
                self.library.mark_played(p.track.id)
                return p
        for _ in range(5):
            if (track := self.library.next_track()) is None:
                break
            if p := self._open(track):
                return p
        return Playing(None, media.ambience_source())

    def _announce(self, p: Playing):
        self.current = p.track
        if p.track:
            with self._ctl:
                if not self.history or self.history[-1] != p.track.id:
                    self.history.append(p.track.id)
                    del self.history[:-50]
            self.room.set_track(p.track.title, p.track.artist, quiet=False)
        else:
            self.room.set_track("quiet water", "", quiet=True)

    def _emit(self, pcm: bytes):
        if not pcm:
            return
        self._write(pcm)
        self.on_pcm(pcm)
        self._frames += len(pcm) // FRAME_BYTES
        ahead = self._t0 + self._frames / RATE - time.monotonic()
        if ahead > LEAD_SEC:
            time.sleep(ahead - LEAD_SEC)
        elif ahead < -2.0:
            # fell behind (stalled decoder, busy machine): carry on from now instead of bursting to catch up
            self._t0 = time.monotonic() - self._frames / RATE

    def _transition(self, tail: bytes) -> Playing:
        """Crossfade the outgoing tail into the next track's opening; announce it halfway through."""
        nxt = self._open_next()
        nxt.fill(len(tail))
        mixed = audio.crossfade(tail, nxt.take(len(tail)))
        half = len(mixed) // 2
        for off in range(0, len(mixed), BLOCK):
            if off <= half < off + BLOCK:
                self._announce(nxt)
            self._emit(mixed[off:off + BLOCK])
        if not mixed:
            self._announce(nxt)
        return nxt

    def _hold(self, cur: Playing) -> Playing:
        """Pause: fade out, keep listeners connected with silence, then fade back in where we left off.
        Next/prev/play while paused fade straight into the new song instead."""
        cur.fill(PAUSE_FADE)
        self._emit(audio.fade(cur.take(PAUSE_FADE), fade_in=False))
        while self._paused.is_set() and not self._skip.is_set() and not self._stop.is_set():
            self._emit(SILENCE)
        if self._skip.is_set():
            self._skip.clear()
            self._unpause()
            cur.close()
            return self._transition(bytes(SKIP_FADE))
        cur.fill(RESUME_FADE)
        self._emit(audio.fade(cur.take(RESUME_FADE), fade_in=True))
        return cur

    def _run(self):
        # the stream must not quietly die: if playout trips over something unexpected, start it again
        while not self._stop.is_set():
            try:
                self._playout()
            except Exception as e:
                print(f"creek: playout hiccup, restarting: {e!r}", flush=True)
                time.sleep(2)

    def _playout(self):
        self._t0, self._frames = time.monotonic(), 0
        cur = self._open_next()
        self._announce(cur)
        try:
            while not self._stop.is_set():
                if self._paused.is_set() and not self._skip.is_set():
                    cur = self._hold(cur)
                    continue
                if self._skip.is_set():
                    self._skip.clear()
                    self._unpause()
                    cur.fill(SKIP_FADE)
                    tail = cur.take(SKIP_FADE)
                    cur.close()
                    cur = self._transition(tail)
                    continue
                cur.fill(LOOKAHEAD)
                if not cur.eof:
                    self._emit(cur.take(BLOCK))
                    continue
                cur.trim_tail()
                if len(cur.buf) > XFADE:
                    self._emit(cur.take(min(BLOCK, len(cur.buf) - XFADE)))
                    continue
                tail = cur.take(len(cur.buf))
                cur.close()
                cur = self._transition(tail)
        finally:
            cur.close()
