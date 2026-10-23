"""The music pool: scans the folder into SQLite and deals tracks out of a shuffle bag."""

from __future__ import annotations   # Library has a method called `list`

import os
import random
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import media
from .config import AUDIO_EXTS, FOLDER_MAX_SEC, FOLDER_MIN_SEC, SETTLE_SEC

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks(
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    mtime REAL, size INTEGER, sha1 TEXT,
    title TEXT, artist TEXT, duration REAL, gain_db REAL,
    status TEXT NOT NULL,          -- ready | bad | dup | removed | gone
    note TEXT,
    added_at REAL
);
CREATE INDEX IF NOT EXISTS tracks_sha1 ON tracks(sha1);
CREATE TABLE IF NOT EXISTS links(url TEXT PRIMARY KEY, last_run REAL, note TEXT);
"""

_PARTIAL = re.compile(r"\.(part|ytdl|temp)(\.|$)|\.part-Frag", re.I)
_NOISE = re.compile(
    r"\s*[\(\[](official\s*)?(music\s*)?(video|audio|lyrics?(\s*video)?|visuali[sz]er|hd|hq|4k|mv)[\)\]]", re.I)


@dataclass
class Track:
    id: int
    path: str
    title: str
    artist: str
    duration: float
    gain_db: float


def norm(s: str) -> str:
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def clean_meta(title: str, artist: str, path: Path, from_web: bool) -> tuple[str, str]:
    """Tidy up titles, mostly for downloads ('Artist - Song (Official Video)' by 'ArtistVEVO')."""
    title = _NOISE.sub("", title or "").strip()
    artist = re.sub(r"\s+-\s+Topic$", "", (artist or "").strip())
    if from_web or not artist:
        if " - " in title:
            left, right = (p.strip() for p in title.split(" - ", 1))
            if left and right:
                artist, title = left, right
        artist = re.sub(r"VEVO$", "", artist).strip()
    if not title:
        title = path.stem.replace("_", " ").strip()
    return title, artist


class ShuffleBag:
    """Every track plays once per cycle, in random order, avoiding the same artist twice in a row."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.artists: dict[int, str] = {}
        self.bag: list[int] = []
        self.last_id: int | None = None
        self.last_artist = ""

    def add(self, tid: int, artist: str):
        if tid in self.artists:
            return
        self.artists[tid] = norm(artist)
        # newcomers join the current cycle at a random spot so they turn up soon
        self.bag.insert(self.rng.randint(0, len(self.bag)), tid)

    def remove(self, tid: int):
        self.artists.pop(tid, None)
        if tid in self.bag:
            self.bag.remove(tid)

    def __len__(self):
        return len(self.artists)

    def played(self, tid: int):
        """A track played on request (play/prev) uses up its turn in this cycle."""
        if tid in self.bag:
            self.bag.remove(tid)
        self.last_id, self.last_artist = tid, self.artists.get(tid, "")

    def _deal(self) -> list[int]:
        """A fresh cycle with each artist's songs spread evenly through it (so an album doesn't clump)."""
        groups: dict[str, list[int]] = {}
        for tid, artist in self.artists.items():
            groups.setdefault(artist or f"#{tid}", []).append(tid)
        keyed = []
        for tids in groups.values():
            self.rng.shuffle(tids)
            k, offset = len(tids), self.rng.random()
            keyed += [((i + offset) / k + self.rng.uniform(-0.1, 0.1) / k, t) for i, t in enumerate(tids)]
        return [t for _, t in sorted(keyed)]

    def next(self) -> int | None:
        if not self.bag:
            self.bag = self._deal()
            if len(self.bag) > 1 and self.bag[0] == self.last_id:
                self.bag.append(self.bag.pop(0))
        if not self.bag:
            return None
        pick = next((i for i, t in enumerate(self.bag)
                     if not self.last_artist or self.artists[t] != self.last_artist), 0)
        tid = self.bag.pop(pick)
        self.last_id, self.last_artist = tid, self.artists[tid]
        return tid


class Library:
    def __init__(self, db_path: Path, music_dir: Path):
        self.music = music_dir
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self.bag = ShuffleBag()
        with self.lock:
            for r in self.db.execute("SELECT id, path, artist FROM tracks WHERE status='ready'").fetchall():
                if os.path.exists(r["path"]):
                    self.bag.add(r["id"], r["artist"])
                else:
                    self._set_status(r["id"], "gone")

    # --- queries -------------------------------------------------------------------------------

    def _row(self, sql: str, *args):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def get(self, tid: int) -> Track | None:
        r = self._row("SELECT * FROM tracks WHERE id=? AND status='ready'", tid)
        return r and Track(r["id"], r["path"], r["title"], r["artist"], r["duration"], r["gain_db"] or 0.0)

    def find_dup(self, sha1: str | None, title: str, artist: str, path: str = "") -> sqlite3.Row | None:
        """A ready/removed track that is the same file or the same song as this one."""
        if sha1:
            r = self._row("SELECT * FROM tracks WHERE sha1=? AND path<>? AND status IN ('ready','removed')",
                          sha1, path)
            if r:
                return r
        if title and artist:
            with self.lock:
                for r in self.db.execute(
                        "SELECT * FROM tracks WHERE path<>? AND status IN ('ready','removed') AND artist<>''",
                        (path,)):
                    if norm(r["artist"]) == norm(artist) and norm(r["title"]) == norm(title):
                        return r
        return None

    def list(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT id, title, artist, duration, path FROM tracks WHERE status='ready' "
                "ORDER BY artist COLLATE NOCASE, title COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 9) -> list[dict]:
        """Songs in rotation whose title/artist contain every word of the query; best matches first."""
        words = norm(query).split()
        if not words:
            return []
        hits = []
        for t in self.list():
            hay = norm(f"{t['title']} {t['artist']}")
            if all(w in hay for w in words):
                starts = norm(t["title"]).startswith(words[0]) or norm(t["artist"]).startswith(words[0])
                hits.append((not starts, hay.find(words[0]), t))
        hits.sort(key=lambda h: (h[0], h[1]))
        return [h[2] for h in hits[:limit]]

    def counts(self) -> dict:
        with self.lock:
            return dict(self.db.execute("SELECT status, COUNT(*) FROM tracks GROUP BY status").fetchall())

    # --- playout -------------------------------------------------------------------------------

    def next_track(self) -> Track | None:
        with self.lock:
            while True:
                tid = self.bag.next()
                if tid is None:
                    return None
                t = self.get(tid)
                if t and os.path.exists(t.path):
                    return t
                self.bag.remove(tid)

    def mark_played(self, tid: int):
        with self.lock:
            self.bag.played(tid)

    def mark_bad(self, tid: int, note: str = "could not be decoded"):
        with self.lock:
            self._set_status(tid, "bad", note)
            self.bag.remove(tid)

    def remove(self, tid: int) -> Track | None:
        """Take a track out of rotation for good. Contributed files are deleted; folder files stay."""
        with self.lock:
            t = self.get(tid)
            if not t:
                return None
            self._set_status(tid, "removed")
            self.bag.remove(tid)
        p = Path(t.path)
        if self.music / "added" in p.parents or self.music / ".yt" in p.parents:
            p.unlink(missing_ok=True)
        return t

    def _set_status(self, tid: int, status: str, note: str | None = None):
        with self.lock:
            self.db.execute("UPDATE tracks SET status=?, note=? WHERE id=?", (status, note, tid))
            self.db.commit()

    # --- scanning ------------------------------------------------------------------------------

    def audio_files(self):
        for dirpath, dirs, files in os.walk(self.music):
            dirs.sort()
            for f in sorted(files):
                if Path(f).suffix.lower() in AUDIO_EXTS and not _PARTIAL.search(f):
                    yield Path(dirpath) / f

    def scan(self) -> int:
        """Pick up new/changed files and forget vanished ones. Returns how many became ready."""
        added, seen, now = 0, set(), time.time()
        for p in self.audio_files():
            seen.add(str(p))
            try:
                st = p.stat()
            except OSError:
                continue
            if now - st.st_mtime < SETTLE_SEC:
                continue
            r = self._row("SELECT id, mtime, size, status FROM tracks WHERE path=?", str(p))
            if r and (r["status"] == "removed" or (r["mtime"] == st.st_mtime and r["size"] == st.st_size)):
                continue
            added += self._ingest(p, st)[0] == "ready"
        with self.lock:
            rows = self.db.execute("SELECT id, path FROM tracks WHERE status='ready'").fetchall()
        for r in rows:
            if r["path"] not in seen and not os.path.exists(r["path"]):
                self._set_status(r["id"], "gone")
                with self.lock:
                    self.bag.remove(r["id"])
        return added

    def add_file(self, p: Path) -> tuple[str, int | None]:
        """Ingest one file right away (instead of waiting for the next scan).

        Returns its status and the id of the track in rotation it stands for: itself when it's ready,
        the original when it's a duplicate, None when it's unusable."""
        return self._ingest(p, p.stat())

    def resolve_download(self, video_id: str) -> int | None:
        """The track in rotation for an already-downloaded video id, if any."""
        r = self._row("SELECT * FROM tracks WHERE path GLOB ?", f"*/.yt/{video_id}.*")
        if r is None or r["status"] not in ("ready", "dup"):
            return None
        if r["status"] == "ready":
            return r["id"]
        dup = self.find_dup(r["sha1"], r["title"], r["artist"], r["path"])
        return dup["id"] if dup is not None and dup["status"] == "ready" else None

    def _ingest(self, p: Path, st: os.stat_result) -> tuple[str, int | None]:
        def save(status, note=None, **meta):
            with self.lock:
                self.db.execute(
                    "INSERT INTO tracks(path, mtime, size, sha1, title, artist, duration, gain_db, status, note,"
                    " added_at) VALUES(:path,:mtime,:size,:sha1,:title,:artist,:duration,:gain_db,:status,:note,"
                    ":now) ON CONFLICT(path) DO UPDATE SET mtime=:mtime, size=:size, sha1=:sha1, title=:title,"
                    " artist=:artist, duration=:duration, gain_db=:gain_db, status=:status, note=:note",
                    {"path": str(p), "mtime": st.st_mtime, "size": st.st_size, "sha1": None, "title": "",
                     "artist": "", "duration": None, "gain_db": None, "now": time.time(),
                     "status": status, "note": note, **meta})
                self.db.commit()
                return self.db.execute("SELECT id FROM tracks WHERE path=?", (str(p),)).fetchone()[0]

        info = media.probe(p)
        if not info:
            save("bad", "no playable audio")
            return "bad", None
        if not FOLDER_MIN_SEC <= info["duration"] <= FOLDER_MAX_SEC:
            save("bad", f"length {info['duration']:.0f}s is outside {FOLDER_MIN_SEC}s-{FOLDER_MAX_SEC}s")
            return "bad", None
        title, artist = clean_meta(info["title"], info["artist"], p, from_web=self.music / ".yt" in p.parents)
        digest = media.sha1(p)
        meta = dict(sha1=digest, title=title, artist=artist, duration=info["duration"])
        dup = self.find_dup(digest, title, artist, str(p))
        if dup:
            save("dup", f"same as #{dup['id']}", **meta)
            return "dup", dup["id"] if dup["status"] == "ready" else None
        gain = media.measure_gain(p)
        if gain is None:
            save("bad", "silent or unreadable", **meta)
            return "bad", None
        tid = save("ready", gain_db=gain, **meta)
        with self.lock:
            self.bag.add(tid, artist)
        return "ready", tid

    # --- links.txt bookkeeping -----------------------------------------------------------------

    def link_last_run(self, url: str) -> float | None:
        r = self._row("SELECT last_run FROM links WHERE url=?", url)
        return r and r["last_run"]

    def link_ran(self, url: str, note: str = ""):
        with self.lock:
            self.db.execute("INSERT INTO links(url, last_run, note) VALUES(?,?,?) ON CONFLICT(url) DO UPDATE"
                            " SET last_run=excluded.last_run, note=excluded.note", (url, time.time(), note))
            self.db.commit()
