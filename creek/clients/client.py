#!/usr/bin/env python3
"""creek: listen to the music stream from a terminal. Python 3 standard library only."""

from __future__ import annotations

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
GLYPHS = ["🌊", "💛", "✨", "🔥", "😌", "🎶"]
WATER = "~~ ~~~ ~ ~~~~  ~~ ~ ~~~ ~~  ~ ~~~~ ~ "
RIVER_WIDTH = 26
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".webm", ".wma", ".mka"}
MAX_UPLOAD = 50 * 1024 * 1024

USAGE = """creek                      join the stream (press ? while listening for the keys)
creek --quiet              audio only: no status line, no keys (fine to run in the background)
creek --volume N           start at volume N, 0-100 (default 60)
creek pause | play | next | prev | clear    control the stream for everyone
creek queue                what's on, what's up next, what played before
creek find <words>         look for a song on the station
creek post <link | number from find>   queue a song to play soon
creek add <link|file|folder> ...   add music to the shuffle"""

HELP = [
    "  keys   a  post a song link (plays soon)      /  find a song on the station to queue",
    "         space  pause / play    n  next    p  previous    l  what's on & up next    c  clear the queue",
    "         1-6  drop an emoji     ?  this help    q  leave",
]
DONE = {"pause": "⏸ paused for everyone", "resume": "▶ playing", "next": "⏭ next song", "prev": "⏮ previous song",
        "clear": "queue cleared"}
SEEN = {"pause": "⏸ someone paused the stream", "resume": "▶ someone pressed play",
        "next": "⏭ someone skipped ahead", "prev": "⏮ someone went back a song",
        "clear": "someone cleared the up-next queue"}


def url(path: str) -> str:
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


def cleared_text(n: int) -> str:
    return f"queue cleared ({n} song{'s' if n != 1 else ''}; they stay in the shuffle)"


def queue_lines(q: dict) -> list[str]:
    lines = [f"  now      {'⏸ ' if q['paused'] else '♪ '}{q['now']}"]
    for i, song in enumerate(q["upnext"], 1):
        lines.append(f"  {'up next' if i == 1 else '':8} {i}. {song}" + ("      (c clears the queue)" if i == 1 else ""))
    if not q["upnext"]:
        lines.append("  up next  nothing posted yet, so the shuffle picks")
    lines.append(f"  then     the shuffle, {q['songs']} songs")
    if q["earlier"]:
        lines.append("  earlier  " + "  ·  ".join(q["earlier"][:3]))
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
        self.typing: tuple[str, str] | None = None   # ("post" | "find", text so far)
        self.picks: list[dict] | None = None         # search results waiting for a number
        self.asking: tuple[str, str] | None = None   # (question, control) waiting for y/n
        self.mine: set[int] = set()          # notices we caused ourselves (no "someone paused" for those)
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
        self.say_soon("~ a post a song · / find one · space pause · n next · ? all keys · q leave ~", 6)
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
                if self.last_notice is not None and seq > self.last_notice and seq not in self.mine:
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

    def post(self, link: str):
        """Send a song link; it downloads on the station and queues up to play after the current song."""
        if not re.match(r"https?://", link):
            return self.say_soon("that doesn't look like a link", 4)
        self.say_soon("~ fetching your song… ~", 600)
        try:
            ticket = call(f"/post?url={urllib.parse.quote(link, safe='')}&id={self.id}", method="POST",
                          data=b"")["ticket"]
            status = {}
            while not self.stop.is_set() and status.get("status") not in ("done", "failed"):
                self.stop.wait(1.5)
                status = call(f"/add/{ticket}")
            self.say_soon(f"~ {status.get('msg', '')} ~", 6)
        except (OSError, ValueError, KeyError) as e:
            self.say_soon(error_text(e), 6)
        self.poke.set()

    def find(self, words: str):
        try:
            hits = call(f"/search?q={urllib.parse.quote(words)}")
        except (OSError, ValueError) as e:
            return self.say_soon(error_text(e), 4)
        if not hits:
            return self.say_soon(f"no songs on the station match '{words}' (a posts a link instead)", 5)
        self.say([f"  {i}. {h['song']}  ({mmss(h['duration'])})" for i, h in enumerate(hits, 1)])
        self.picks = hits

    def queue_pick(self, hit: dict):
        try:
            r = call(f"/post?track={hit['id']}&id={self.id}", method="POST", data=b"")
            self.say_soon(f"~ {r['msg']} ~", 5)
        except (OSError, ValueError, KeyError) as e:
            self.say_soon(error_text(e), 5)
        self.poke.set()

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
            while not self.stop.is_set():
                if select.select([fd], [], [], 0.2)[0]:
                    self.key(os.read(fd, 1).decode(errors="ignore"))
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            os.close(fd)

    def key(self, ch: str):
        bg = lambda f, *a: threading.Thread(target=f, args=a, daemon=True).start()
        if self.typing is not None:
            return self.type_key(ch)
        if self.picks is not None:
            hits, self.picks = self.picks, None
            if ch.isdigit() and 1 <= int(ch) <= len(hits):
                return bg(self.queue_pick, hits[int(ch) - 1])
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
            self.typing = ("post", "")
        elif ch == "/":
            self.typing = ("find", "")
        elif ch and ch in "123456":
            bg(self.react, int(ch) - 1)
        elif ch in (" ", "n", "p"):
            bg(self.control, {" ": "toggle", "n": "next", "p": "prev"}[ch])
        elif ch in ("l", "L"):
            bg(self.show_queue)
        elif ch in ("c", "C"):
            self.asking = ("clear the up-next queue for everyone? (y/n)", "clear")
        elif ch in ("?", "h"):
            self.say(HELP)

    def type_key(self, ch: str):
        kind, text = self.typing
        if ch in ("\r", "\n"):
            self.typing = None
            if text.strip():
                threading.Thread(target=self.post if kind == "post" else self.find, args=(text.strip(),),
                                 daemon=True).start()
        elif ch == "\x1b":
            self.typing = None
        elif ch in ("\x7f", "\b"):
            self.typing = (kind, text[:-1])
        elif ch.isprintable():
            self.typing = (kind, text + ch)

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
            kind, text = self.typing
            label = ("post a song link" if kind == "post" else "find a song") + " (Enter goes, Esc cancels): "
            return label + text[-max(10, cols - RIVER_WIDTH - len(label) - 4):] + "_"
        if self.picks is not None:
            return f"press 1-{len(self.picks)} to queue one of those, any other key to cancel"
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
        text = f"{'⏸ paused ·' if n.get('paused') else '♪'} {song}  {dim}·  {n['here']} here"
        if n.get("upnext"):
            more = n.get("queued", 1) - 1
            text += f"  ·  up next: {n['upnext'][0]}" + (f" +{more}" if more > 0 else "")
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
        elif cmd == "queue" and not args:
            print("\n".join(queue_lines(call("/queue"))))
        elif cmd == "find" and args:
            hits = call("/search?q=" + urllib.parse.quote(" ".join(args)))
            for i, h in enumerate(hits, 1):
                print(f"  {i}. {h['song']}  ({mmss(h['duration'])})   creek post #{h['id']}")
            if not hits:
                print("no songs on the station match that")
        elif cmd == "post" and len(args) == 1:
            if args[0].lstrip("#").isdigit():
                print(call(f"/post?track={args[0].lstrip('#')}&id={listener_id()}", method="POST", data=b"")["msg"])
            else:
                q = urllib.parse.quote(args[0], safe="")
                t = call(f"/post?url={q}&id={listener_id()}", method="POST", data=b"")["ticket"]
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
