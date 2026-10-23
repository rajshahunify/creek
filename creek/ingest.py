"""Getting music in: links (yt-dlp), uploaded files, and the operator's links.txt."""

import itertools
import queue
import re
import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import media
from .config import (CONTRIB_MAX_SEC, CONTRIB_MIN_SEC, DATA, FOLDER_MAX_SEC, LINKS, LINKS_REFRESH_SEC, MUSIC,
                     PLAYLIST_CAP, TMP)
from .library import Library, clean_meta

LINKS_HEADER = """\
# creek links: one YouTube (or SoundCloud, Bandcamp, ...) song or playlist URL per line.
# Saved changes are picked up automatically; each playlist is checked again every 12 hours.
# Lines starting with # are ignored.
"""


def youtube_id(url: str) -> str | None:
    m = re.search(r"(?:[?&]v=|youtu\.be/|/shorts/|/live/|/embed/)([\w-]{11})(?![\w-])", url)
    return m.group(1) if m else None


def parse_links(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        url = line.split()[0]
        if re.match(r"https?://", url) and url not in out:
            out.append(url)
    return out


@dataclass
class Ticket:
    id: int
    what: str
    status: str = "queued"          # queued | working | done | failed
    added: int = 0
    msg: str = ""
    created: float = field(default_factory=time.time)


class _Log:
    """Collects yt-dlp's complaints instead of printing them, and notes why songs were skipped."""

    def __init__(self):
        self.errors: list[str] = []
        self.archived = False      # downloaded on an earlier occasion
        self.filtered = False      # too short, too long, or live

    def debug(self, msg):
        self.archived |= "recorded in the archive" in msg
        self.filtered |= "does not pass filter" in msg

    def info(self, msg): pass
    def warning(self, msg): pass

    def error(self, msg):
        self.errors.append(re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*)?", "", str(msg)).strip())


OnReady = Callable[[int], str]          # gets the track id, returns the message for the person waiting
OnFinish = Callable[[Ticket], None]


class Ingest:
    def __init__(self, library: Library):
        self.library = library
        self.jobs: queue.Queue[tuple] = queue.Queue()
        self.tickets: dict[int, Ticket] = {}
        self._ids = itertools.count(1)
        self._links_mtime = 0.0
        self.js_runtimes = {name: {"path": path} for name in ("deno", "node", "bun")
                            if (path := shutil.which(name))}

    def start(self):
        (MUSIC / ".yt").mkdir(parents=True, exist_ok=True)
        (MUSIC / "added").mkdir(parents=True, exist_ok=True)
        TMP.mkdir(parents=True, exist_ok=True)
        if not LINKS.exists():
            LINKS.write_text(LINKS_HEADER)
        threading.Thread(target=self._worker, name="creek-ingest", daemon=True).start()

    def _ticket(self, what: str) -> Ticket:
        t = Ticket(next(self._ids), what)
        self.tickets[t.id] = t
        cutoff = time.time() - 24 * 3600
        for k in [k for k, v in self.tickets.items() if v.created < cutoff]:
            del self.tickets[k]
        return t

    # --- links ---------------------------------------------------------------------------------

    def add_link(self, url: str, contributed: bool = True, on_ready: OnReady | None = None,
                 single: bool = False, on_finish: OnFinish | None = None) -> Ticket:
        """Queue a download. on_ready is handed the (first) song as soon as it's in rotation; on_finish runs
        when the job is over either way. single=True ignores any playlist the link points into."""
        t = self._ticket(url)
        self.jobs.put((t, url, contributed, on_ready, single, on_finish))
        return t

    def check_links_file(self):
        """Queue links.txt entries that are new, or due for a playlist refresh."""
        try:
            mtime = LINKS.stat().st_mtime
        except FileNotFoundError:
            return
        changed, self._links_mtime = mtime != self._links_mtime, mtime
        for url in parse_links(LINKS.read_text(errors="replace")):
            last = self.library.link_last_run(url)
            if (last is None and changed) or (last is not None and time.time() - last > LINKS_REFRESH_SEC):
                self.library.link_ran(url, "queued")
                self.add_link(url, contributed=False)

    def _worker(self):
        while True:
            t, url, contributed, on_ready, single, on_finish = self.jobs.get()
            t.status = "working"
            try:
                self._download(t, url, contributed, on_ready, single)
            except Exception as e:  # keep the worker alive whatever yt-dlp throws
                t.status, t.msg = "failed", str(e)[:200]
            if not contributed and on_ready is None:
                self.library.link_ran(url, t.msg or t.status)
            if on_finish:
                on_finish(t)

    def _download(self, t: Ticket, url: str, contributed: bool, on_ready: OnReady | None = None,
                  single: bool = False):
        if "spotify.com" in url:
            t.status, t.msg = "failed", "Spotify links aren't supported yet - try a YouTube link for the same song"
            return
        if on_ready and (vid := youtube_id(url)) and (tid := self.library.resolve_download(vid)) is not None:
            t.status, t.msg = "done", on_ready(tid)     # already downloaded: no need to touch the network
            return
        import yt_dlp
        from yt_dlp.utils import match_filter_func

        max_sec = CONTRIB_MAX_SEC if contributed else FOLDER_MAX_SEC

        handed = False

        def done(path: str):
            # runs after each song's download + tagging; put it in rotation now rather than on the next scan
            nonlocal handed
            status, tid = self.library.add_file(Path(path))
            t.added += status == "ready"
            if on_ready and not handed and tid is not None:
                t.msg = on_ready(tid)
                handed = True

        log = _Log()
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(MUSIC / ".yt" / "%(id)s.%(ext)s"),
            "paths": {"temp": str(TMP)},
            "download_archive": str(DATA / "yt-archive.txt"),
            "playlistend": PLAYLIST_CAP,
            "match_filter": match_filter_func(f"!is_live & duration >= {CONTRIB_MIN_SEC} & duration <= {max_sec}"),
            "postprocessors": [{"key": "FFmpegMetadata", "add_chapters": False, "add_infojson": False}],
            "post_hooks": [done],
            "ignoreerrors": True,
            "quiet": True, "no_warnings": True, "noprogress": True,
            "logger": log,
        }
        if single:
            opts.update(noplaylist=True, playlistend=1)
        if self.js_runtimes:
            opts["js_runtimes"] = self.js_runtimes
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        if handed:
            t.status = "done"
        elif t.added:
            t.status, t.msg = "done", f"{t.added} song{'s' if t.added != 1 else ''} joined the stream"
        elif log.errors:
            t.status, t.msg = "failed", log.errors[-1][:200]
        elif log.filtered:
            t.status, t.msg = "failed", (f"songs need to be {CONTRIB_MIN_SEC} s to {max_sec // 60} min long, "
                                         "and not a live stream")
        elif log.archived and on_ready:
            t.status, t.msg = "failed", "that one was taken out of the stream"
        elif log.archived:
            t.status, t.msg = "done", "already in the stream"
        else:
            t.status, t.msg = "done", "nothing new"

    # --- uploads -------------------------------------------------------------------------------

    def add_upload(self, tmp: Path, name: str) -> tuple[bool, str]:
        """Validate an uploaded file and move it into music/added/. tmp is consumed either way."""
        try:
            info = media.probe(tmp)
            if not info:
                return False, "that doesn't look like an audio file"
            if not CONTRIB_MIN_SEC <= info["duration"] <= CONTRIB_MAX_SEC:
                return False, f"songs need to be {CONTRIB_MIN_SEC}s to {CONTRIB_MAX_SEC // 60} min long"
            safe = re.sub(r"[^\w.\- ()&,']+", "_", Path(name).name).strip(". ") or "song"
            title, artist = clean_meta(info["title"], info["artist"], Path(safe), from_web=False)
            dup = self.library.find_dup(media.sha1(tmp), title, artist)
            if dup is not None:
                return False, ("already in the stream" if dup["status"] == "ready"
                               else "that one was taken out of the stream")
            dest = MUSIC / "added" / safe
            for i in itertools.count(2):
                if not dest.exists():
                    break
                dest = dest.with_name(f"{Path(safe).stem} ({i}){Path(safe).suffix}")
            shutil.move(tmp, dest)
            # ingest right away, so a second copy uploaded straight after is caught as a duplicate
            status, _ = self.library.add_file(dest)
            if status != "ready":
                dest.unlink(missing_ok=True)
                return False, "already in the stream" if status == "dup" else "couldn't use that file"
            return True, "joined the stream"
        finally:
            tmp.unlink(missing_ok=True)
