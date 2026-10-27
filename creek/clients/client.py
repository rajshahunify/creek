#!/usr/bin/env python3
"""creek: listen to the music stream from a terminal. Python 3 standard library only."""

from __future__ import annotations

import codecs
import json
import os
import random
import re
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HOST = "__CREEK_HOST__"
KEY = "__CREEK_KEY__"          # the station's key, when it has one
# GLYPHS = ["🌊", "💛", "✨", "🔥", "😌", "🎶"]
GLYPHS = []
WATER = "~~ ~~~ ~ ~~~~  ~~ ~ ~~~ ~~  ~ ~~~~ ~ "
RIVER_WIDTH = 26
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".webm", ".wma", ".mka"}
MAX_UPLOAD = 50 * 1024 * 1024
KEY = re.compile(r"\x1b\[[0-9;]*[~A-Za-z]|\x1bO[A-Za-z]|.", re.S)   # one keypress: an escape sequence or a character

USAGE = """creek                      join the stream (press ? while listening for the keys)
creek --quiet              audio only: no status line, no keys (fine to run in the background)
creek --volume N           start at volume N, 0-100 (default 60)
creek pause | play | next | prev | clear    control the stream for everyone
creek fwd | back [seconds]                 jump ahead / back in this song (5 s), for everyone
creek seek <m:ss>          jump to that time in this song, for everyone
creek queue                what's on, what's up next, what played before
creek move <n> <place>     move the n-th song in the queue to another place (numbers from `creek queue`)
creek drop <n>             take the n-th song out of the queue (it stays in the shuffle)
creek find <words>         look for a song on the station and on YouTube
creek post <link | #id>    queue a song (it plays after the songs already waiting)
creek next <link | #id>    play a song next, ahead of the queue
creek playnow <link | #id> play a song right now, for everyone
creek news                 what's new on creek
creek add <link|file|folder> ...   add music to the shuffle
(also in a browser: http://__CREEK_HOST__)"""

HELP = [
    "  keys   a  play a song next (a link, or words: the station and YouTube)    e  add one to the end of the queue",
    "         space  pause / play    n or Ctrl+→  next    p or Ctrl+←  previous    ← →  jump 5 s    g  jump to a time",
    "         l  what's on & up next    m  move a song in the queue    x  take one out    c  clear the queue",
    "         / find    w  what's new    ?  this help    q  leave",
    f"         in a browser: http://{HOST}  (buttons, a progress bar to drag, the queue to drag around)",
]
DONE = {"pause": "⏸ paused for everyone", "resume": "▶ playing", "next": "⏭ next song", "prev": "⏮ previous song",
        "clear": "queue cleared"}
SEEN = {"pause": "⏸ someone paused the stream", "resume": "▶ someone pressed play",
        "next": "⏭ someone skipped ahead", "prev": "⏮ someone went back a song",
        "clear": "someone cleared the up-next queue",
        "fwd": "⏩ someone jumped ahead 5 s", "back": "⏪ someone jumped back 5 s",
        "seek": "⏩ someone jumped within the song", "move": "someone rearranged the up-next queue",
        "remove": "someone took a song out of the queue", "playnow": "⚡ someone played a song now"}
ARROWS = {"\x1b[C": "fwd", "\x1bOC": "fwd", "\x1b[D": "back", "\x1bOD": "back",
          "\x1b[1;5C": "next", "\x1b[1;5D": "prev"}     # Ctrl+→ / Ctrl+← change the song


def url(path: str) -> str:
    if KEY:
        path += ("&" if "?" in path else "?") + "key=" + urllib.parse.quote(KEY)
    return f"http://{HOST}{path}"


def call(path: str, method: str = "GET", data=None, headers=None, timeout: float = 5):
    req = urllib.request.Request(url(path), data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def error_text(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        try:
            return json.load(e).get("detail", e.reason)
        except ValueError:
            return str(e.reason)
    return f"can't reach the stream at {HOST}"


def listener_id() -> str:
    """Anonymous but stable for this person on this machine, so 'one posted song each' means something."""
    import getpass
    import hashlib
    import uuid
    return hashlib.sha1(f"creek|{uuid.getnode()}|{getpass.getuser()}".encode()).hexdigest()[:16]


def mmss(sec) -> str:
    return "%d:%02d" % divmod(int(sec or 0), 60)


def seconds(text: str) -> int | None:
    """'1:30' or '90' -> 90."""
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        return None
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return total


def progress(pos, dur, width: int = 10) -> str:
    done = round(width * min(1.0, (pos or 0) / dur)) if dur else 0
    return "▕" + "█" * done + "░" * (width - done) + "▏"


def seen_file() -> str:
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "creek", "seen")


def news_lines(items: list[dict]) -> list[str]:
    lines = []
    for x in items:
        lines.append(f"  new on creek  ·  {x['title']}")
        lines += [f"     · {line}" for line in x["lines"]]
    return lines


def find_hits(words: str) -> tuple[list[dict], str]:
    """Up to 9 songs for some words: the station's own first (instant), then YouTube's top matches.
    Returns them and a note when YouTube couldn't be searched."""
    q = urllib.parse.quote(words)
    hits = [{"song": h["song"], "duration": h["duration"], "track": h["id"], "where": "station"}
            for h in call(f"/search?q={q}")[:4]]
    note = ""
    try:
        for h in call(f"/yt/search?q={q}&n=6&id={listener_id()}", timeout=20):
            if len(hits) >= 9:
                break
            if h["why_not"] or (h["on_station"] is not None and any(x["track"] == h["on_station"] for x in hits)):
                continue
            hits.append({"song": " · ".join(x for x in (h["title"], h["channel"]) if x), "duration": h["duration"],
                         "track": h["on_station"], "url": h["url"], "where": "youtube"})
    except (OSError, ValueError, KeyError) as e:
        note = f"(couldn't search YouTube: {error_text(e)})"
    return hits, note


def hit_lines(hits: list[dict]) -> list[str]:
    lines, where = [], None
    for i, h in enumerate(hits, 1):
        if h["where"] != where:
            where = h["where"]
            lines.append("  on the station" if where == "station" else "  on YouTube")
        lines.append(f"   {i}. {h['song']}  ({mmss(h['duration'])})")
    return lines


def cleared_text(n: int) -> str:
    return f"queue cleared ({n} song{'s' if n != 1 else ''}; they stay in the shuffle)"


def queue_lines(q: dict) -> list[str]:
    lines = [f"  now      {'⏸ ' if q['paused'] else '♪ '}{q['now']}"]
    for i, song in enumerate(q["upnext"], 1):
        lines.append(f"  {'up next' if i == 1 else '':8} {i}. {song}" + ("      (c clears the queue)" if i == 1 else ""))
    pick, rest = q.get("shuffle_next"), f"the shuffle, {q['songs']} songs"
    if not q["upnext"]:
        lines.append(f"  up next  {pick}   (the shuffle's pick)" if pick else
                     "  up next  nothing posted yet, so the shuffle picks")
        lines.append(f"  then     {'the rest of ' if pick else ''}{rest}")
    else:
        lines.append(f"  then     {pick}   (the shuffle's pick), then the rest of {rest}" if pick else
                     f"  then     {rest}")
    if q["earlier"]:
        lines.append("  earlier  " + "  ·  ".join(q["earlier"][:3]))
    if len(q["upnext"]) > 1:
        lines.append("           (m moves a song to another place, x takes one out)")
    return lines


# --- playing -------------------------------------------------------------------------------------

def choose_player(volume: int) -> tuple[str, list[str]] | None:
    """('mp3', argv) players fetch the stream themselves; ('pcm', argv) players read raw audio on stdin."""
    mp3 = url("/stream.mp3")
    if shutil.which("ffplay"):
        return "mp3", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", str(volume),
                       "-rw_timeout", "15000000", "-probesize", "4096", "-analyzeduration", "0",
                       "-fflags", "nobuffer", "-i", mp3]
    if shutil.which("mpv"):
        return "mp3", ["mpv", "--no-video", "--really-quiet", "--no-terminal", f"--volume={volume}",
                       "--network-timeout=15", mp3]
    if shutil.which("mpg123"):
        return "mp3", ["mpg123", "-q", "-f", str(volume * 32768 // 100), mp3]
    if shutil.which("pw-play"):
        return "pcm", ["pw-play", "--format", "s16", "--rate", "44100", "--channels", "2",
                       "--volume", f"{volume / 100:.2f}", "-"]
    if shutil.which("paplay"):
        return "pcm", ["paplay", "--raw", "--format=s16le", "--rate=44100", "--channels=2",
                       f"--volume={volume * 65536 // 100}"]
    if shutil.which("aplay"):
        return "pcm", ["aplay", "-q", "-t", "raw", "-f", "cd"]
    return None


class Listener:
    def __init__(self, volume: int, quiet: bool):
        self.quiet = quiet
        self.player = choose_player(volume)
        self.stop = threading.Event()
        self.poke = threading.Event()        # poll /now right away
        self.jump = threading.Event()        # restart the player at once (back to the live edge)
        self.id = listener_id()
        self.proc: subprocess.Popen | None = None
        self.held = False                    # our player is frozen because we pressed pause
        self.held_at = 0.0
        self.now: dict = {}
        self.offline = False
        self.trouble = ""
        self.flash = ("", 0.0)               # short-lived message and when it expires
        self.typing: tuple[str, str, int] | None = None   # (what the line is for, text so far, cursor)
        self.picks: list[dict] | None = None         # search results waiting for a number
        self.picks_next = False                      # ...and whether the chosen one plays next
        self.picks_now = False                       # ...or right now (! was pressed)
        self.asking: tuple[str, str] | None = None   # (question, control) waiting for y/n
        self.mine: set[int] = set()          # notices we caused ourselves (no "someone paused" for those)
        self.mine_action = ("", 0.0)         # ...or an action of ours whose notice number we never got back
        self.last_notice: int | None = None
        self.drops: list[list] = []          # [position, glyph]
        self.lock = threading.Lock()
        self.out = threading.Lock()          # one writer at a time on the terminal
        self.color = sys.stdout.isatty() and os.environ.get("TERM") != "dumb" and "NO_COLOR" not in os.environ

    def run(self):
        if not self.player:
            sys.exit("creek: no audio player found. Install ffmpeg (for ffplay) or mpv, then try again.")
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, lambda *_: self.stop.set())
        threads = [threading.Thread(target=self.play, daemon=True)]
        if not self.quiet:
            threads += [threading.Thread(target=f, daemon=True) for f in (self.poll, self.keys, self.draw)]
        for t in threads:
            t.start()
        self.say_soon("~ a play a song next · e add one to the queue · space pause · ? all keys · q leave ~", 6)
        if not self.quiet:
            threading.Thread(target=self.show_news, daemon=True).start()
        while not self.stop.is_set():
            self.stop.wait(0.5)
        for t in threads:
            t.join(2)
        if not self.quiet:
            sys.stdout.write("\r\x1b[2K\x1b[?25h")
            sys.stdout.flush()

    def play(self):
        kind, argv = self.player
        backoff, quick_fails = 2.0, 0
        while not self.stop.is_set():
            started = time.monotonic()
            proc = None
            try:
                if kind == "mp3":
                    proc = self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    while proc.poll() is None and not self.stop.is_set():
                        self.stop.wait(0.1)
                else:
                    with urllib.request.urlopen(url("/stream.pcm"), timeout=15) as r:
                        proc = self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        while not self.stop.is_set() and (chunk := r.read(17640)):
                            proc.stdin.write(chunk)
            except (OSError, ValueError):
                pass
            finally:
                if proc and proc.poll() is None:
                    if self.held:
                        proc.kill()          # it's frozen: a polite SIGTERM would wait for SIGCONT
                    else:
                        proc.terminate()
                    try:
                        proc.wait(2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            if self.stop.is_set():
                return
            if self.jump.is_set():           # we restarted it on purpose: no waiting
                self.jump.clear()
                backoff, quick_fails = 2.0, 0
                continue
            # the player stopped on its own: the station is away, or the player can't open audio
            quick_fails = quick_fails + 1 if time.monotonic() - started < 3 else 0
            if quick_fails >= 3 and not self.offline:
                self.trouble = f"{os.path.basename(argv[0])} keeps stopping - is your audio output working?"
            if time.monotonic() - started > 30:
                backoff = 2.0
            self.stop.wait(backoff)
            backoff = min(backoff * 2, 30)

    def hold(self):
        """Freeze our own player now, so whoever pressed pause hears it at once (everyone else gets the
        station's fade a moment later)."""
        self.held, self.held_at = True, time.monotonic()
        if self.proc and self.proc.poll() is None:
            os.kill(self.proc.pid, signal.SIGSTOP)

    def release(self):
        """Throw away the frozen player and start a fresh one at the live edge."""
        self.held = False
        self.jump.set()
        if self.proc and self.proc.poll() is None:
            self.proc.kill()

    # --- talking to the station ----------------------------------------------------------------

    def poll(self):
        since = -1
        while not self.stop.is_set():
            try:
                n = call(f"/now?since={since}", timeout=4)
                with self.lock:
                    for i in n["reactions"]:
                        if 0 <= i < len(GLYPHS):
                            self.drops.append([0.0, GLYPHS[i]])
                    self.now, self.offline, since = n, False, n["seq"]
                seq, action = n.get("notice") or (0, "")
                ours = action == self.mine_action[0] and time.monotonic() - self.mine_action[1] < 60
                if self.last_notice is not None and seq > self.last_notice and seq not in self.mine and not ours:
                    self.say_soon(SEEN.get(action, ""), 3)
                self.last_notice = seq
                if self.held and not n.get("paused") and time.monotonic() - self.held_at > 2:
                    self.release()           # someone else pressed play (or next) while we were paused
                if n["here"]:
                    self.trouble = ""
            except (OSError, ValueError, KeyError, TypeError):
                self.offline = True
            self.poke.wait(1.0)
            self.poke.clear()

    def control(self, action: str):
        if action == "toggle":
            action = "resume" if self.held or self.now.get("paused") else "pause"
        try:
            r = call(f"/ctl/{action}?id={self.id}", method="POST", data=b"")
        except (OSError, ValueError) as e:
            return self.say_soon(error_text(e), 3)
        self.mine.add(r.get("notice"))
        if action == "clear":
            return self.say_soon(cleared_text(r["cleared"]), 4)
        if action in ("fwd", "back"):
            self.say_soon(f"{'⏩' if action == 'fwd' else '⏪'} {mmss(r.get('pos'))} / {mmss(r.get('dur'))}", 2)
            return self.poke.set()
        if action == "pause":
            self.hold()
        elif self.held:
            self.release()
        self.say_soon(DONE[action], 2.5)
        self.poke.set()

    def react(self, i: int):
        try:
            call(f"/react?e={i}&id={self.id}", method="POST", data=b"")
            self.poke.set()
        except (OSError, ValueError):
            pass

    def post(self, link: str, front: bool = False, now: bool = False):
        """Send a song link; it downloads on the station and queues up to play after the current song
        (behind the songs already waiting, or ahead of them when front=True; or straight away with now)."""
        if not re.match(r"https?://", link):
            return self.say_soon("that doesn't look like a link", 4)
        self.say_soon("~ fetching your song… ~", 600)
        how = "&now=1" if now else "&next=1" if front else ""
        if now:
            self.mine_action = ("playnow", time.monotonic())
        try:
            ticket = call(f"/post?url={urllib.parse.quote(link, safe='')}&id={self.id}{how}",
                          method="POST", data=b"")["ticket"]
            status = {}
            while not self.stop.is_set() and status.get("status") not in ("done", "failed"):
                self.stop.wait(1.5)
                status = call(f"/add/{ticket}")
            self.say_soon(f"~ {status.get('msg', '')} ~", 6)
        except (OSError, ValueError, KeyError) as e:
            self.say_soon(error_text(e), 6)
        self.poke.set()

    def find(self, words: str, front: bool = False):
        self.say_soon(f"~ looking for '{words}' on the station and YouTube… ~", 20)
        try:
            hits, note = find_hits(words)
        except (OSError, ValueError, KeyError) as e:
            return self.say_soon(error_text(e), 4)
        if not hits:
            return self.say_soon(f"nothing found for '{words}' {note}".strip(), 5)
        self.say(hit_lines(hits) + ([f"  {note}"] if note else []))
        self.flash = ("", 0.0)
        self.picks, self.picks_next, self.picks_now = hits, front, False

    def queue_pick(self, hit: dict, front: bool, now: bool = False):
        if hit.get("track") is None:                 # from YouTube, not downloaded yet
            return self.post(hit["url"], front, now)
        how = "&now=1" if now else "&next=1" if front else ""
        if now:
            self.mine_action = ("playnow", time.monotonic())
        try:
            r = call(f"/post?track={hit['track']}&id={self.id}{how}", method="POST", data=b"")
            self.say_soon(f"~ {r['msg']} ~", 5)
        except (OSError, ValueError, KeyError) as e:
            self.say_soon(error_text(e), 5)
        self.poke.set()

    def edit_queue(self, action: str, place: int, to: int = 0):
        """m and x: move the song at `place` (as numbered by l) to `to`, or take it out."""
        path = f"/queue/move?place={place}&to={to}" if action == "move" else f"/queue/remove?place={place}"
        try:
            r = call(f"{path}&id={self.id}", method="POST", data=b"")
            self.mine.add(r.get("notice"))
            self.say_soon(f"~ moved: now number {r['place']} ~" if action == "move" else "~ taken out of the queue ~", 3)
        except (OSError, ValueError, KeyError) as e:
            self.say_soon(error_text(e), 4)
        self.poke.set()

    def seek_to(self, sec: int):
        try:
            r = call(f"/ctl/seek?to={sec}&id={self.id}", method="POST", data=b"")
            self.mine.add(r.get("notice"))
            self.say_soon(f"⏩ {mmss(r.get('pos'))} / {mmss(r.get('dur'))}", 2)
        except (OSError, ValueError, KeyError) as e:
            self.say_soon(error_text(e), 4)
        self.poke.set()

    def show_news(self, everything: bool = False):
        """On joining: what's new since this person last looked (just the latest, the very first time)."""
        path = seen_file()
        try:
            with open(path) as f:
                seen = int(f.read().strip() or 0)
        except (OSError, ValueError):
            seen = -1
        try:
            r = call(f"/news?seen={0 if everything else max(seen, 0)}")
        except (OSError, ValueError):
            return
        items = r["news"][-2:] if everything else r["news"][-1:] if seen < 0 else r["news"]
        if items:
            self.say(news_lines(items) + ([f"     (w shows this again · also in a browser: http://{HOST})"]
                                           if not everything else []))
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(str(r["version"]))
        except OSError:
            pass

    def show_queue(self):
        try:
            self.say(queue_lines(call("/queue")))
        except (OSError, ValueError, KeyError) as e:
            self.say_soon(error_text(e), 4)

    # --- keys ----------------------------------------------------------------------------------

    def keys(self):
        try:
            import termios
            import tty
            fd = os.open("/dev/tty", os.O_RDONLY)
        except (ImportError, OSError):
            return
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            decode = codecs.getincrementaldecoder("utf-8")(errors="ignore").decode
            while not self.stop.is_set():
                if not select.select([fd], [], [], 0.2)[0]:
                    continue
                buf = decode(os.read(fd, 1024))
                # an arrow key is several bytes (ESC [ D); make sure we have all of it, not a lone Esc
                while re.search(r"\x1b(\[[0-9;]*|O)?$", buf) and select.select([fd], [], [], 0.05)[0]:
                    buf += decode(os.read(fd, 1024))
                for ch in KEY.findall(buf):
                    self.key(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            os.close(fd)

    def key(self, ch: str):
        bg = lambda f, *a: threading.Thread(target=f, args=a, daemon=True).start()
        if self.typing is not None:
            return self.type_key(ch)
        if self.picks is not None:
            if ch == "!":
                self.picks_now = not self.picks_now
                return
            hits, self.picks = self.picks, None
            if ch.isdigit() and 1 <= int(ch) <= len(hits):
                return bg(self.queue_pick, hits[int(ch) - 1], self.picks_next, self.picks_now)
            return self.say_soon("~ never mind ~", 1.5)
        if self.asking is not None:
            _, action = self.asking
            self.asking = None
            if ch in ("y", "Y"):
                return bg(self.control, action)
            return self.say_soon("~ never mind ~", 1.5)
        if ch in ("q", "Q"):
            self.stop.set()
        elif ch in ("a", "A"):
            self.typing = ("next", "", 0)
        elif ch in ("e", "E"):
            self.typing = ("post", "", 0)
        elif ch == "/":
            self.typing = ("find", "", 0)
        elif ch in ARROWS:
            bg(self.control, ARROWS[ch])
        elif ch and ch in "123456":
            bg(self.react, int(ch) - 1)
        elif ch in (" ", "n", "p"):
            bg(self.control, {" ": "toggle", "n": "next", "p": "prev"}[ch])
        elif ch in ("l", "L"):
            bg(self.show_queue)
        elif ch in ("m", "M", "x", "X"):
            bg(self.show_queue)                      # the numbers to type
            self.typing = ("move" if ch in "mM" else "drop", "", 0)
        elif ch in ("g", "G"):
            self.typing = ("seek", "", 0)
        elif ch in ("w", "W"):
            bg(self.show_news, True)
        elif ch in ("c", "C"):
            self.asking = ("clear the up-next queue for everyone? (y/n)", "clear")
        elif ch in ("?", "h"):
            self.say(HELP)

    def type_key(self, ch: str):
        kind, text, at = self.typing
        if ch in ("\r", "\n"):
            self.typing = None
            text, front = text.strip(), kind == "next"
            nums = [int(x) for x in re.findall(r"\d+", text)]
            if not text:
                return
            if kind == "move":
                if len(nums) != 2:
                    return self.say_soon("~ two numbers: the song's, then where it goes (e.g. 3 1) ~", 4)
                target, args = self.edit_queue, ("move", nums[0], nums[1])
            elif kind == "drop":
                if len(nums) != 1:
                    return self.say_soon("~ the song's number from the list ~", 3)
                target, args = self.edit_queue, ("remove", nums[0])
            elif kind == "seek":
                if (sec := seconds(text)) is None:
                    return self.say_soon("~ a time like 1:30 ~", 3)
                target, args = self.seek_to, (sec,)
            else:
                # a or e: a link, or words to find a song on the station or YouTube
                link = kind != "find" and re.match(r"https?://", text)
                target, args = (self.post if link else self.find), (text, front)
            threading.Thread(target=target, args=args, daemon=True).start()
        elif ch == "\x1b":
            self.typing = None
        elif ch in ("\x7f", "\b"):
            self.typing = (kind, text[:at - 1] + text[at:], at - 1) if at else self.typing
        elif ch == "\x1b[3~":                          # Delete
            self.typing = (kind, text[:at] + text[at + 1:], at)
        elif ch == "\x15":                             # Ctrl+U
            self.typing = (kind, "", 0)
        elif ch.startswith("\x1b") or ch in ("\x01", "\x05"):
            move = {"D": at - 1, "C": at + 1, "H": 0, "1~": 0, "7~": 0, "F": len(text), "4~": len(text),
                    "8~": len(text), "\x01": 0, "\x05": len(text)}.get(ch.lstrip("\x1b[O"), at)
            self.typing = (kind, text, max(0, min(len(text), move)))
        elif ch.isprintable():
            self.typing = (kind, text[:at] + ch + text[at:], at + 1)

    # --- the screen ----------------------------------------------------------------------------

    def say(self, lines: list[str]):
        """Print a few lines above the status line (they scroll up like normal terminal output)."""
        if self.quiet:
            return
        cols = shutil.get_terminal_size((80, 20)).columns
        with self.out:
            sys.stdout.write("".join("\r\x1b[2K" + fit(l, cols - 1) + "\n" for l in lines))
            sys.stdout.flush()

    def say_soon(self, text: str, seconds: float):
        self.flash = (text, time.monotonic() + seconds)

    def river(self, t: float) -> str:
        with self.lock:
            for d in self.drops:
                d[0] += 1                  # one cell per redraw, ~5 cells a second
            self.drops = [d for d in self.drops if d[0] < RIVER_WIDTH - 1]
            at = {int(d[0]): d[1] for d in self.drops}
        shift, out, i = int(t * 2), [], 0
        while i < RIVER_WIDTH:
            if i in at and i < RIVER_WIDTH - 1:
                out.append(at[i])
                i += 2
            else:
                out.append(WATER[(i - shift) % len(WATER)])
                i += 1
        return "".join(out)

    def status(self, cols: int) -> str:
        dim, reset = ("\x1b[2m", "\x1b[0m") if self.color else ("", "")
        n = self.now
        if self.typing is not None:
            kind, text, at = self.typing
            label = {"post": "add to the end of the queue - a link, or words to find a song", "find": "find a song",
                     "next": "play next - a link, or words to find a song",
                     "move": "move which song where? its number, then the new place (e.g. 3 1)",
                     "drop": "take which song out of the queue? its number", "seek": "jump to (m:ss)",
                     }[kind] + " (Enter goes, Esc cancels): "
            room = max(10, cols - RIVER_WIDTH - len(label) - 4)
            start = max(0, at - room + 1)            # keep the cursor in view
            shown, here = text[start:start + room], at - start
            if not self.color:
                return label + shown[:here] + ("_" if here == len(shown) else "|") + shown[here:]
            under = shown[here] if here < len(shown) else " "
            return label + shown[:here] + f"\x1b[7m{under}\x1b[27m" + shown[here + 1:]
        if self.picks is not None:
            if self.picks_now:
                return f"⚡ press 1-{len(self.picks)} to play one of those now, for everyone (! again: don't)"
            what = "play one of those next" if self.picks_next else "queue one of those"
            return f"press 1-{len(self.picks)} to {what} (! first: play it now), any other key to cancel"
        if self.asking is not None:
            return self.asking[0]
        if self.offline:
            return "~ waiting for the stream ~"
        if self.flash[0] and time.monotonic() < self.flash[1]:
            return self.flash[0]
        if self.trouble:
            return self.trouble
        if not n:
            return "~ joining ~"
        if n.get("quiet"):
            return f"quiet water - no music yet (a posts a song)  {dim}·  {n['here']} here{reset}"
        song = " - ".join(x for x in (n.get("title"), n.get("artist")) if x)
        text = f"{'⏸ paused ·' if n.get('paused') else '♪'} {song}  {dim}"
        if n.get("dur"):
            text += f"{mmss(n.get('pos'))} {progress(n.get('pos'), n['dur'])} {mmss(n['dur'])}  ·  "
        text += f"{n['here']} here"
        if n.get("upnext"):
            more = n.get("queued", 1) - 1
            text += f"  ·  up next: {n['upnext'][0]}" + (f" +{more}" if more > 0 else "")
        elif n.get("next"):
            text += f"  ·  up next: {n['next']} (shuffle)"
        return text + reset

    def draw(self):
        sys.stdout.write("\x1b[?25l")
        cyan, reset = ("\x1b[36m", "\x1b[0m") if self.color else ("", "")
        while not self.stop.is_set():
            cols = shutil.get_terminal_size((80, 20)).columns
            line = f"{cyan}{self.river(time.monotonic())}{reset}  {self.status(cols)}"
            with self.out:
                sys.stdout.write("\r\x1b[2K" + fit(line, cols - 1) + reset)
                sys.stdout.flush()
            self.stop.wait(0.2)


def fit(s: str, cols: int) -> str:
    """Cut s to `cols` terminal cells, counting wide characters (emoji, CJK) as two, escapes as zero."""
    out, used, i = [], 0, 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            j = len(s) if j < 0 else j + 1
            out.append(s[i:j])
            i = j
            continue
        w = 2 if unicodedata.east_asian_width(s[i]) in "WF" else 0 if unicodedata.combining(s[i]) else 1
        if used + w > cols:
            break
        out.append(s[i])
        used += w
        i += 1
    return "".join(out)


# --- adding music --------------------------------------------------------------------------------

def add(items: list[str]):
    if not items:
        sys.exit("usage: creek add <youtube link | file | folder> ...")
    for item in items:
        if re.match(r"https?://", item):
            add_link(item)
        elif os.path.isdir(item):
            files = sorted(os.path.join(d, f) for d, _, fs in os.walk(item) for f in fs
                           if os.path.splitext(f)[1].lower() in AUDIO_EXTS)
            if not files:
                print(f"{item}: no audio files in there")
            for f in files:
                upload(f)
        elif os.path.isfile(item):
            upload(item)
        else:
            print(f"{item}: not a link, file or folder")


def add_link(link: str):
    try:
        t = call("/add/link?url=" + urllib.parse.quote(link, safe=""), method="POST", data=b"")["ticket"]
        print(f"{link}: queued", end="", flush=True)
        status = {}
        while status.get("status") not in ("done", "failed"):
            time.sleep(2)
            status = call(f"/add/{t}")
            print(".", end="", flush=True)
        print(f"\r\x1b[2K{link}: {status['msg']}")
    except (OSError, ValueError, KeyError) as e:
        print(f"\r\x1b[2K{link}: {error_text(e)}")


def upload(path: str):
    name = os.path.basename(path)
    size = os.path.getsize(path)
    if size > MAX_UPLOAD:
        print(f"{name}: too big (max {MAX_UPLOAD >> 20} MB)")
        return
    try:
        with open(path, "rb") as f:
            r = call("/add/file?name=" + urllib.parse.quote(name), method="POST", data=f, timeout=120,
                     headers={"Content-Length": str(size), "Content-Type": "application/octet-stream"})
        print(f"{name}: {r['msg']}")
    except (OSError, ValueError, KeyError) as e:
        print(f"{name}: {error_text(e)}")


def command(argv: list[str]) -> bool:
    """One-shot commands; returns False when argv isn't one."""
    cmd, args = argv[0], argv[1:]
    try:
        if cmd in ("pause", "play", "next", "prev", "clear") and not args:
            action = "resume" if cmd == "play" else cmd
            r = call(f"/ctl/{action}?id={listener_id()}", method="POST", data=b"")
            print(cleared_text(r["cleared"]) if action == "clear" else DONE[action])
        elif cmd in ("fwd", "back") and len(args) <= 1 and all(a.isdigit() for a in args):
            r = call(f"/ctl/{cmd}?id={listener_id()}" + (f"&by={args[0]}" if args else ""), method="POST", data=b"")
            print(f"{'⏩' if cmd == 'fwd' else '⏪'} {mmss(r['pos'])} / {mmss(r['dur'])}")
        elif cmd == "queue" and not args:
            print("\n".join(queue_lines(call("/queue"))))
        elif cmd == "seek" and len(args) == 1 and (to := seconds(args[0])) is not None:
            r = call(f"/ctl/seek?to={to}&id={listener_id()}", method="POST", data=b"")
            print(f"⏩ {mmss(r['pos'])} / {mmss(r['dur'])}")
        elif cmd == "move" and len(args) == 2 and all(a.isdigit() for a in args):
            r = call(f"/queue/move?place={args[0]}&to={args[1]}&id={listener_id()}", method="POST", data=b"")
            print(f"moved: now number {r['place']}")
        elif cmd == "drop" and len(args) == 1 and args[0].isdigit():
            call(f"/queue/remove?place={args[0]}&id={listener_id()}", method="POST", data=b"")
            print("taken out of the queue (it stays in the shuffle)")
        elif cmd == "news" and not args:
            print("\n".join(news_lines(call("/news?seen=0")["news"])))
        elif cmd == "find" and args:
            hits, note = find_hits(" ".join(args))
            where = None
            for i, h in enumerate(hits, 1):
                if h["where"] != where:
                    where = h["where"]
                    print("on the station" if where == "station" else "on YouTube")
                how = f"#{h['track']}" if h.get("track") is not None else h["url"]
                print(f"  {i}. {h['song']}  ({mmss(h['duration'])})   creek next {how}")
            if not hits:
                print("nothing found for that")
            if note:
                print(note)
        elif cmd in ("post", "next", "playnow") and len(args) == 1:
            front = {"next": "&next=1", "playnow": "&now=1"}.get(cmd, "")
            if args[0].lstrip("#").isdigit():
                print(call(f"/post?track={args[0].lstrip('#')}&id={listener_id()}{front}", method="POST",
                           data=b"")["msg"])
            else:
                q = urllib.parse.quote(args[0], safe="")
                t = call(f"/post?url={q}&id={listener_id()}{front}", method="POST", data=b"")["ticket"]
                print("fetching", end="", flush=True)
                while (s := call(f"/add/{t}"))["status"] not in ("done", "failed"):
                    time.sleep(1.5)
                    print(".", end="", flush=True)
                print("\r\x1b[2K" + s["msg"])
        else:
            return False
    except (OSError, ValueError, KeyError) as e:
        sys.exit(f"creek: {error_text(e)}")
    return True


def main(argv: list[str]):
    if argv and argv[0] == "add":
        return add(argv[1:])
    if argv and not argv[0].startswith("-") and command(argv):
        return
    quiet, volume = False, 60
    it = iter(argv)
    for a in it:
        if a in ("-q", "--quiet"):
            quiet = True
        elif a in ("-v", "--volume"):
            try:
                volume = max(0, min(100, int(next(it))))
            except (StopIteration, ValueError):
                sys.exit("creek: --volume needs a number from 0 to 100")
        else:
            print(USAGE)
            return
    Listener(volume, quiet).run()


if __name__ == "__main__":
    main(sys.argv[1:])
