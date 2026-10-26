"""Songs listeners posted: they play after the current one, in the order posted, one per person at a time."""

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

    def add(self, tid: int, poster: str, title: str) -> int:
        """Queue a song and return its place (1 = up next). A song that's already queued keeps its place.
        Returns 0 if the queue was cleared while this song was downloading: it isn't queued then."""
        with self.lock:
            if self.pending.pop(poster, self.generation) != self.generation:
                return 0
            for place, r in enumerate(self.items, 1):
                if r.tid == tid:
                    return place
            self.items.append(Request(tid, poster, title))
            return len(self.items)

    def clear(self) -> int:
        """Empty the queue (the songs stay on the station). Songs still downloading won't be queued either.
        Returns how many were waiting or on their way."""
        with self.lock:
            n = len(self.items) + sum(g == self.generation for g in self.pending.values())
            self.items.clear()
            self.generation += 1
            return n

    def pop(self) -> Request | None:
        with self.lock:
            return self.items.popleft() if self.items else None

    def remove(self, tid: int):
        with self.lock:
            self.items = deque(r for r in self.items if r.tid != tid)

    def titles(self, n: int = 3) -> list[str]:
        with self.lock:
            return [r.title for r in list(self.items)[:n]]

    def __len__(self):
        with self.lock:
            return len(self.items)
