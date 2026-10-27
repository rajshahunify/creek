"""Songs listeners posted: they play after the current one, in the order posted (or first in line, with
"play next", or at any place in between), one per person at a time. Anyone can move songs around."""

import threading
from collections import deque
from dataclasses import dataclass


@dataclass
class Request:
    tid: int
    poster: str
    title: str


class UpNext:
    def __init__(self, cap: int = 20):
        self.cap = cap
        self.lock = threading.Lock()
        self.items: deque[Request] = deque()
        self.pending: dict[str, int] = {}   # posters whose song is still downloading -> queue generation
        self.generation = 0                 # bumped by clear(), so downloads from before it don't sneak in
        self.version = 0                    # bumped by every change, so clients know to look again

    def reserve(self, poster: str) -> str | None:
        """Hold a place while the poster's song downloads. Returns the reason it can't, or None."""
        with self.lock:
            if poster in self.pending or any(r.poster == poster for r in self.items):
                return "you already have a song coming up - post another once it has played"
            if len(self.items) + len(self.pending) >= self.cap:
                return "the queue is full right now - try again in a bit"
            self.pending[poster] = self.generation
            return None

    def release(self, poster: str):
        with self.lock:
            self.pending.pop(poster, None)

    def add(self, tid: int, poster: str, title: str, front: bool = False, at: int | None = None) -> int:
        """Queue a song and return its place (1 = up next). front=True puts it first in line ("play next");
        at=N puts it at place N. A song that's already queued keeps its place, unless it's asked for a place.
        Returns 0 if the queue was cleared while this song was downloading: it isn't queued then."""
        if front:
            at = 1
        with self.lock:
            if self.pending.pop(poster, self.generation) != self.generation:
                return 0
            for place, r in enumerate(self.items, 1):
                if r.tid == tid:
                    if at is None:
                        return place
                    self.items.remove(r)
                    break
            req = Request(tid, poster, title)
            if at is None:
                self.items.append(req)
                place = len(self.items)
            else:
                place = max(1, min(at, len(self.items) + 1))
                self.items.insert(place - 1, req)
            self.version += 1
            return place

    def move(self, tid: int, to: int) -> int | None:
        """Move a queued song to place `to` (1 = up next). Returns where it landed, or None if it isn't queued."""
        with self.lock:
            r = next((r for r in self.items if r.tid == tid), None)
            if r is None:
                return None
            self.items.remove(r)
            place = max(1, min(to, len(self.items) + 1))
            self.items.insert(place - 1, r)
            self.version += 1
            return place

    def clear(self) -> int:
        """Empty the queue (the songs stay on the station). Songs still downloading won't be queued either.
        Returns how many were waiting or on their way."""
        with self.lock:
            n = len(self.items) + sum(g == self.generation for g in self.pending.values())
            self.items.clear()
            self.generation += 1
            self.version += 1
            return n

    def pop(self) -> Request | None:
        with self.lock:
            if not self.items:
                return None
            self.version += 1
            return self.items.popleft()

    def remove(self, tid: int) -> bool:
        """Take a song out of the queue (it stays on the station). False if it wasn't queued."""
        with self.lock:
            n = len(self.items)
            self.items = deque(r for r in self.items if r.tid != tid)
            if len(self.items) == n:
                return False
            self.version += 1
            return True

    def snapshot(self) -> list[Request]:
        with self.lock:
            return list(self.items)

    def titles(self, n: int = 3) -> list[str]:
        with self.lock:
            return [r.title for r in list(self.items)[:n]]

    def __len__(self):
        with self.lock:
            return len(self.items)
