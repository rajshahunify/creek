"""Shared, anonymous room state: what's flowing by and the emoji people dropped in."""

import threading
import time
from collections import deque

from .config import (CONTROL_MIN_GAP_SEC, JUMP_GUARD_SEC, REACT_MIN_GAP_SEC, REACTIONS, SEARCH_MIN_GAP_SEC,
                     SEEK_MIN_GAP_SEC)


class Room:
    def __init__(self):
        self.lock = threading.Lock()
        self.seq = 0
        self.events: deque[tuple[int, int]] = deque(maxlen=200)   # (seq, reaction index)
        self.title, self.artist, self.quiet = "", "", True
        self.paused = False
        self.notice_seq, self.notice = 0, ""                       # last control anyone used: pause|next|fwd|...
        self._ctl_last: dict[str, float] = {}
        self._jump_at = float("-inf")
        self._last: dict[str, float] = {}                          # client id -> last reaction time
        self._searched: dict[str, float] = {}                      # client id -> last YouTube search
        self._recent: deque[float] = deque(maxlen=5)               # global cap: 5 reactions per second

    def set_track(self, title: str, artist: str, quiet: bool):
        with self.lock:
            self.title, self.artist, self.quiet = title, artist, quiet

    def set_paused(self, paused: bool):
        with self.lock:
            self.paused = paused

    def control(self, client_id: str, action: str, now: float | None = None) -> str | None:
        """May this listener use a control right now? Returns why not, or None."""
        now = time.monotonic() if now is None else now
        with self.lock:
            # arrows, the progress bar and dragging songs around can come a few a second
            gap = SEEK_MIN_GAP_SEC if action in ("fwd", "back", "seek", "move", "remove") else CONTROL_MIN_GAP_SEC
            if now - self._ctl_last.get(client_id, float("-inf")) < gap:
                return "easy - one press at a time"
            if action in ("next", "prev", "playnow") and now - self._jump_at < JUMP_GUARD_SEC:
                return "someone just changed the song"
            if len(self._ctl_last) > 1000:
                self._ctl_last = {k: t for k, t in self._ctl_last.items() if now - t < 60}
            self._ctl_last[client_id] = now
            if action in ("next", "prev", "playnow"):
                self._jump_at = now
            return None

    def may_search(self, client_id: str, now: float | None = None) -> bool:
        """YouTube searches go out to the internet: one a second per listener is plenty for typing."""
        now = time.monotonic() if now is None else now
        with self.lock:
            if now - self._searched.get(client_id, float("-inf")) < SEARCH_MIN_GAP_SEC:
                return False
            if len(self._searched) > 1000:
                self._searched = {k: t for k, t in self._searched.items() if now - t < 60}
            self._searched[client_id] = now
            return True

    def announce(self, action: str) -> int:
        """Tell everyone (anonymously) that a control was used. Returns the notice's seq."""
        with self.lock:
            self.notice_seq += 1
            self.notice = action
            return self.notice_seq

    def react(self, client_id: str, idx: int, now: float | None = None) -> bool:
        if not 0 <= idx < len(REACTIONS):
            return False
        now = time.monotonic() if now is None else now
        with self.lock:
            if now - self._last.get(client_id, float("-inf")) < REACT_MIN_GAP_SEC:
                return False
            if len(self._recent) == self._recent.maxlen and now - self._recent[0] < 1.0:
                return False
            if len(self._last) > 1000:
                self._last = {k: t for k, t in self._last.items() if now - t < 60}
            self._last[client_id] = now
            self._recent.append(now)
            self.seq += 1
            self.events.append((self.seq, idx))
            return True

    def snapshot(self, since: int, here: int) -> dict:
        """since < 0 means 'just tell me the current seq' (a client that just joined)."""
        with self.lock:
            return {
                "seq": self.seq,
                "title": self.title,
                "artist": self.artist,
                "quiet": self.quiet,
                "paused": self.paused,
                "notice": [self.notice_seq, self.notice],
                "here": here,
                "reactions": [i for s, i in self.events if s > since] if since >= 0 else [],
            }
