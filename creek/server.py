"""HTTP face of the station: the streams, the little JSON API, and the client scripts."""

import asyncio
import hmac
import json
import re
import socket
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import audio
from .config import (ACCEPT_CONTRIBUTIONS, BYTES_PER_SEC, CONTRIB_MAX_BYTES, CONTRIB_MAX_SEC, CONTRIB_MIN_SEC, DATA,
                     DB, JOIN_BURST_SEC, KEY, MUSIC, OPEN_CONTROLS, PORT, REACTIONS, SCAN_EVERY_SEC, SEEK_SEC, TMP,
                     WEB_DIST)
from .engine import Engine
from .ingest import Ingest, youtube_id
from .library import Library, Track
from .news import NEWS_VERSION, news_since
from .room import Room
from .upnext import UpNext

CLIENTS = Path(__file__).parent / "clients"
_HOST_OK = re.compile(r"^[A-Za-z0-9.\-]+(:\d{1,5})?$|^\[[0-9A-Fa-f:.]+\](:\d{1,5})?$")


class AsciiJSON(JSONResponse):
    # \u-escaped so Windows PowerShell 5.1 can't mis-decode titles in any language
    media_type = "application/json; charset=utf-8"

    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=True, separators=(",", ":")).encode()


class Hub:
    """Fans one live byte stream out to many listeners; keeps a few seconds so joiners start at once."""

    def __init__(self, ring_bytes: int, max_chunks: int, mp3: bool):
        self.ring: deque[bytes] = deque()
        self.ring_size, self.ring_bytes = 0, ring_bytes
        self.max_chunks, self.mp3 = max_chunks, mp3
        self.listeners: set[asyncio.Queue] = set()

    def publish(self, chunk: bytes):
        self.ring.append(chunk)
        self.ring_size += len(chunk)
        while self.ring_size - len(self.ring[0]) >= self.ring_bytes:
            self.ring_size -= len(self.ring.popleft())
        for q in list(self.listeners):
            try:
                q.put_nowait(chunk)
            except asyncio.QueueFull:
                # this listener can't keep up: let it go, its client reconnects
                self.leave(q)
                while not q.empty():
                    q.get_nowait()
                q.put_nowait(None)

    def join(self) -> tuple[asyncio.Queue, bytes]:
        q: asyncio.Queue = asyncio.Queue(self.max_chunks)
        self.listeners.add(q)
        burst = b"".join(self.ring)
        if self.mp3:
            off = audio.mp3_sync_offset(burst)
            burst = burst[off:] if off >= 0 else b""
        return q, burst

    def leave(self, q: asyncio.Queue):
        self.listeners.discard(q)


class Station:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        for d in (MUSIC, DATA, TMP):
            d.mkdir(parents=True, exist_ok=True)
        self.loop = loop
        self.room = Room()
        self.library = Library(DB, MUSIC)
        self.mp3 = Hub(ring_bytes=int(JOIN_BURST_SEC * 16_000), max_chunks=2000, mp3=True)   # 128 kbps
        self.pcm = Hub(ring_bytes=int(JOIN_BURST_SEC * BYTES_PER_SEC), max_chunks=300, mp3=False)
        self.upnext = UpNext()
        self.engine = Engine(self.library, self.room,
                             on_mp3=lambda c: loop.call_soon_threadsafe(self.mp3.publish, c),
                             on_pcm=lambda c: loop.call_soon_threadsafe(self.pcm.publish, c),
                             upnext=self.upnext)
        self.ingest = Ingest(self.library)

    def start(self):
        self.ingest.start()
        self.engine.start()
        threading.Thread(target=self._housekeeping, name="creek-scan", daemon=True).start()

    def stop(self):
        self.engine.stop()

    def _housekeeping(self):
        while True:
            try:
                self.library.scan()
                self.ingest.check_links_file()
            except Exception as e:  # never let a weird file stop the scanning
                print(f"creek: scan problem: {e}")
            time.sleep(SCAN_EVERY_SEC)

    @property
    def here(self) -> int:
        return len(self.mp3.listeners) + len(self.pcm.listeners)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.station = st = Station(asyncio.get_running_loop())
    st.start()
    yield
    st.stop()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
if (WEB_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


def _is_local(request: Request) -> bool:
    # same machine = loopback, or a connection to one of our own addresses that also comes *from* it
    peer = request.client.host if request.client else None
    server = (request.scope.get("server") or (None,))[0]
    return peer in ("127.0.0.1", "::1") or peer == server


def _has_key(request: Request) -> bool:
    """With CREEK_KEY set, everyone needs it (as ?key=, the web player's cookie, or an X-Creek-Key header),
    except the station laptop itself."""
    if not KEY or _is_local(request):
        return True
    given = request.query_params.get("key") or request.cookies.get("creek_key") or request.headers.get("x-creek-key")
    return bool(given) and hmac.compare_digest(given.encode(), KEY.encode())


@app.middleware("http")
async def need_key(request: Request, call_next):
    # the front page (which says how to get in) and the web player's files are open; everything else needs the key
    if request.url.path in ("/", "/key") or request.url.path.startswith("/assets/") or _has_key(request):
        return await call_next(request)
    return AsciiJSON({"detail": "this station needs its key - ask whoever runs it for the link"}, status_code=401)


@app.post("/key", response_class=AsciiJSON)
def give_key(request: Request, key: str = ""):
    """The web player's passcode box: a right key becomes a cookie, so the stream and the API just work."""
    if not KEY:
        return AsciiJSON({"ok": True})
    if not hmac.compare_digest(key.encode(), KEY.encode()):
        raise HTTPException(401, "that isn't this station's key")
    r = AsciiJSON({"ok": True})
    r.set_cookie("creek_key", key, max_age=365 * 24 * 3600, httponly=True, samesite="lax")
    return r


def station(request: Request) -> Station:
    return request.app.state.station


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # no packet is sent; this just picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def host_of(request: Request) -> str:
    h = request.headers.get("host", "")
    return h if _HOST_OK.match(h) else f"{lan_ip()}:{PORT}"


def template(name: str, host: str, **extra: str) -> str:
    # (only ever served to someone who has the key, so they can carry it on)
    text = (CLIENTS / name).read_text().replace("__CREEK_HOST__", host).replace("__CREEK_KEY__", KEY)
    for k, v in extra.items():
        text = text.replace(k, v)
    return text


# --- joining -------------------------------------------------------------------------------------

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>AB SMB</title>
<body style="font:16px system-ui;max-width:40em;margin:4em auto;padding:0 1em">
<h1>AB SMB</h1><p>The dashboard (and its music) hasn't been built on this station yet. On the station laptop:</p>
<pre>cd web &amp;&amp; npm ci &amp;&amp; npm run build</pre>
<p>Terminal listeners can join meanwhile: <code>curl -s http://__HOST__/join | sh</code></p>"""


@app.get("/")
def index(request: Request):
    h, st = host_of(request), station(request)
    k, o = (f"?key={KEY}", "'") if KEY else ("", "")      # (a ? in a shell needs quotes)
    if "text/html" in request.headers.get("accept", ""):
        page = WEB_DIST / "index.html"
        if page.exists():
            return FileResponse(page, headers={"Cache-Control": "no-cache"})
        return HTMLResponse(NOT_BUILT.replace("__HOST__", h))
    if not _has_key(request):
        return PlainTextResponse(f"""
  creek  ~  a shared stream of music

  This station needs its key. Ask whoever runs it for the link (it ends in ?key=...).
""")
    now = st.room.snapshot(-1, st.here)
    flowing = "quiet water (no music yet)" if now["quiet"] else " - ".join(x for x in (now["title"], now["artist"]) if x)
    if now["paused"]:
        flowing = f"paused ({flowing})"
    return PlainTextResponse(f"""
  creek  ~  a quiet stream of music flowing through this network

  join            linux     curl -s {o}http://{h}/join{k}{o} | sh
                  windows   irm {o}http://{h}/win{k}{o} | iex

  keep a `creek` command (one time)
                  linux     curl -s {o}http://{h}/join{k}{o} | sh -s install
                  windows   irm {o}http://{h}/win/install{k}{o} | iex

  in a browser    http://{h}/{k}      (search YouTube, drag the queue around, seek)

  add music       creek add <youtube link | file | folder>

  while listening:   a  play a song next (a link, or words to search)     e  add one to the end of the queue
                     space  pause / play     n  next     p  previous     ← →  jump 5 s     g  jump to a time
                     l  what's on & up next     m  move a song     x  take one out     c  clear the queue
                     w  what's new     ?  all keys     q  leave

  now flowing:    {flowing}  ·  {now['here']} here
""")


@app.get("/join", response_class=PlainTextResponse)
def join_sh(request: Request):
    return template("join.sh", host_of(request))


@app.get("/client.py", response_class=PlainTextResponse)
def client_py(request: Request):
    return template("client.py", host_of(request))


@app.get("/win", response_class=PlainTextResponse)
def win_ps1(request: Request):
    return template("win.ps1", host_of(request))


@app.get("/win/install", response_class=PlainTextResponse)
def win_install(request: Request):
    return template("win.ps1", host_of(request), **{"$CreekInstall = $false": "$CreekInstall = $true"})


# --- listening -----------------------------------------------------------------------------------

def _stream(hub: Hub, media_type: str) -> StreamingResponse:
    # called from async routes: hubs are only ever touched on the event loop thread
    q, burst = hub.join()

    async def gen():
        try:
            if burst:
                yield burst
            while (chunk := await q.get()) is not None:
                yield chunk
        finally:
            hub.leave(q)

    return StreamingResponse(gen(), media_type=media_type,
                             headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"})


@app.get("/stream.mp3")
async def stream_mp3(request: Request):
    return _stream(station(request).mp3, "audio/mpeg")


@app.get("/stream.pcm")
async def stream_pcm(request: Request):
    return _stream(station(request).pcm, "application/octet-stream")


def _shuffle_next(st: Station) -> Track | None:
    """The shuffle's pick, unless it's queued anyway (then the shuffle picks again once it has played)."""
    t = st.engine.shuffle_pick()
    return None if t is None or any(r.tid == t.id for r in st.upnext.snapshot()) else t


def _coming_up(st: Station) -> dict:
    """The song after this one: the first posted song, or else the shuffle's pick."""
    if first := st.upnext.titles(1):
        return {"next": first[0], "next_from": "queue"}
    t = st.engine.shuffle_pick()
    return {"next": _label(t.title, t.artist) if t else "", "next_from": "shuffle"}


@app.get("/now", response_class=AsciiJSON)
def now(request: Request, since: int = -1):
    st = station(request)
    cur = st.engine.current
    return AsciiJSON({**st.room.snapshot(since, st.here), "upnext": st.upnext.titles(3), "queued": len(st.upnext),
                      **_coming_up(st), "pos": round(st.engine.position), "dur": round(cur.duration or 0) if cur else 0,
                      "news": NEWS_VERSION})


def _art(t: Track | None) -> str | None:
    """Cover art for songs that came from YouTube: the video's thumbnail. Others get drawn by the web player."""
    if t and "/.yt/" in t.path.replace("\\", "/") and len(vid := Path(t.path).stem) == 11:
        return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
    return None


def _song(t: Track) -> dict:
    return {"tid": t.id, "song": _label(t.title, t.artist), "title": t.title, "artist": t.artist,
            "duration": round(t.duration or 0), "art": _art(t)}


def _state(st: Station, who: str) -> dict:
    """Everything the web player shows, in one go."""
    engine, lib = st.engine, st.library
    room = st.room.snapshot(-1, st.here)
    cur, playing = engine.current, engine.playing
    queue = []
    for r in st.upnext.snapshot():
        if t := lib.get(r.tid):
            queue.append({**_song(t), "song": r.title, "mine": r.poster == who})
    earlier = [_song(t) for tid in reversed(engine.history[:-1][-8:]) if (t := lib.get(tid))]
    pick = _shuffle_next(st)
    return {
        "now": {**_song(cur), "via": playing.via if playing else ""} if cur else None,
        "quiet": room["quiet"], "paused": room["paused"], "here": room["here"],
        "pos": round(engine.position, 1), "dur": round(cur.duration or 0) if cur else 0,
        "queue": queue, "queue_version": st.upnext.version,
        "shuffle_next": _song(pick) if pick else None,
        "earlier": earlier, "songs": lib.counts().get("ready", 0),
        "notice": room["notice"], "seq": room["seq"],
        "news": NEWS_VERSION, "controls_open": OPEN_CONTROLS, "accepting": ACCEPT_CONTRIBUTIONS,
        "reactions": REACTIONS,
    }


@app.get("/state", response_class=AsciiJSON)
def state(request: Request, id: str = "anon"):
    return AsciiJSON(_state(station(request), id[:64]))


@app.get("/events")
async def events(request: Request, id: str = "anon"):
    """Server-sent events for the web player: `state` whenever something anyone can see changes (and every few
    seconds anyway, to keep progress bars honest), `react` when someone drops an emoji."""
    st, who = station(request), id[:64]

    async def gen():
        seq, sig, sent = st.room.snapshot(-1, 0)["seq"], None, 0.0
        yield "retry: 2000\n\n"
        while not await request.is_disconnected():
            snap = st.room.snapshot(seq, st.here)
            if snap["reactions"]:
                yield f"event: react\ndata: {json.dumps(snap['reactions'])}\n\n"
            seq = snap["seq"]
            cur = st.engine.current
            now = (cur.id if cur else None, snap["paused"], snap["notice"][0], snap["here"], st.upnext.version)
            if now != sig or time.monotonic() - sent > 5:
                body = await run_in_threadpool(_state, st, who)
                yield f"event: state\ndata: {json.dumps(body, ensure_ascii=True, separators=(',', ':'))}\n\n"
                sig, sent = now, time.monotonic()
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/news", response_class=AsciiJSON)
def news(seen: int = 0):
    return AsciiJSON({"version": NEWS_VERSION, "news": news_since(seen)})


@app.post("/react", response_class=AsciiJSON)
def react(request: Request, e: int, id: str = "anon"):
    return AsciiJSON({"ok": station(request).room.react(id[:64], e)})


# --- adding music --------------------------------------------------------------------------------

def _accepting():
    if not ACCEPT_CONTRIBUTIONS:
        raise HTTPException(403, "this station isn't taking new music right now")


@app.post("/add/link", response_class=AsciiJSON)
def add_link(request: Request, url: str):
    _accepting()
    if not re.match(r"https?://\S+$", url):
        raise HTTPException(400, "that doesn't look like a link")
    t = station(request).ingest.add_link(url)
    return AsciiJSON({"ticket": t.id, "status": t.status})


def _label(title: str, artist: str) -> str:
    return " - ".join(x for x in (title, artist) if x)


@app.post("/post", response_class=AsciiJSON)
def post(request: Request, url: str | None = None, track: int | None = None, id: str = "anon", next: bool = False,
         at: int | None = None, now: bool = False):
    """A listener posts one song (a link, or a song already on the station from /search): it queues up to
    play after the current song, behind the songs already waiting (or ahead of them, with next=1, or at place
    `at`). now=1 crossfades into it for everyone as soon as it's ready instead."""
    st, poster = station(request), id[:64]
    if track is None:
        _accepting()
        if not url or not re.match(r"https?://\S+$", url):
            raise HTTPException(400, "that doesn't look like a link")
        if "list=" in url and not youtube_id(url):
            raise HTTPException(400, "post one song at a time - whole playlists can go in with `creek add`")
    elif st.library.get(track) is None:
        raise HTTPException(404, "that song isn't on the station any more")
    if now:
        _allowed(request, st, poster, "playnow")

        def ready(tid: int) -> str:
            t, cur = st.library.get(tid), st.engine.current
            if t is None:
                return "couldn't play that one"
            if cur and cur.id == tid:
                return "that one's playing right now"
            st.upnext.remove(tid)
            st.engine.play_now(tid)
            st.room.announce("playnow")
            return f"playing now: {_label(t.title, t.artist)}"

        if track is not None:
            return AsciiJSON({"msg": ready(track)})
        t = st.ingest.add_link(url, contributed=True, on_ready=ready, single=True)
        return AsciiJSON({"ticket": t.id, "status": t.status})
    if why := st.upnext.reserve(poster):
        raise HTTPException(409, why)

    def ready(tid: int) -> str:
        t, cur = st.library.get(tid), st.engine.current
        if t is None:
            return "couldn't queue that one"
        if cur and cur.id == tid:
            return "that one's playing right now"
        place = st.upnext.add(tid, poster, _label(t.title, t.artist), front=next, at=at)
        if place == 0:
            return "the queue was cleared while it downloaded - it joined the shuffle instead"
        return "up next" if place == 1 else f"queued - plays after {place - 1} other{'s' if place > 2 else ''}"

    if track is not None:
        msg = ready(track)
        st.upnext.release(poster)
        return AsciiJSON({"msg": msg})
    t = st.ingest.add_link(url, contributed=True, on_ready=ready, single=True,
                           on_finish=lambda _: st.upnext.release(poster))
    return AsciiJSON({"ticket": t.id, "status": t.status})


@app.get("/search", response_class=AsciiJSON)
def search(request: Request, q: str):
    return AsciiJSON([{"id": t["id"], "song": _label(t["title"], t["artist"]), "duration": t["duration"],
                       "art": _art(Track(t["id"], t["path"], t["title"], t["artist"], t["duration"], 0.0))}
                      for t in station(request).library.search(q)])


def _why_not(h: dict) -> str:
    if h["live"]:
        return "live stream"
    if (d := h["duration"]) and d > CONTRIB_MAX_SEC:
        return f"longer than {CONTRIB_MAX_SEC // 60} min"
    if d and d < CONTRIB_MIN_SEC:
        return f"shorter than {CONTRIB_MIN_SEC} s"
    return ""


@app.get("/yt/search", response_class=AsciiJSON)
def yt_search(request: Request, q: str, id: str = "anon", n: int = 8):
    """Top YouTube matches for some words, ready to post: songs already downloaded say which track they are
    (on_station), and ones that can't go in say why (why_not)."""
    _accepting()
    st = station(request)
    if not q.strip():
        return AsciiJSON([])
    if not st.room.may_search(id[:64]):
        raise HTTPException(429, "easy - one search a second")
    try:
        hits = st.ingest.search_youtube(q[:200], max(1, min(n, 12)))
    except Exception as e:  # yt-dlp: no network, YouTube refusing, ...
        raise HTTPException(502, f"couldn't search YouTube just now ({str(e)[:120]})")
    return AsciiJSON([{**h, "on_station": st.library.resolve_download(h["vid"]), "why_not": _why_not(h)}
                      for h in hits])


@app.get("/queue", response_class=AsciiJSON)
def queue_view(request: Request):
    """What's playing, what's coming, and what played before."""
    st = station(request)
    cur, lib = st.engine.current, st.library
    earlier = [t for tid in reversed(st.engine.history[:-1][-5:]) if (t := lib.get(tid))]
    return AsciiJSON({
        "now": _label(cur.title, cur.artist) if cur else "quiet water",
        "paused": st.engine.paused,
        "upnext": st.upnext.titles(20),
        "items": [{"tid": r.tid, "song": r.title} for r in st.upnext.snapshot()],
        "shuffle_next": _label(pick.title, pick.artist) if (pick := _shuffle_next(st)) else "",
        "earlier": [_label(t.title, t.artist) for t in earlier],
        "songs": lib.counts().get("ready", 0),
        "here": st.here,
    })


@app.get("/add/{tid}", response_class=AsciiJSON)
def add_status(request: Request, tid: int):
    t = station(request).ingest.tickets.get(tid)
    if not t:
        raise HTTPException(404, "unknown ticket")
    return AsciiJSON({"status": t.status, "added": t.added, "msg": t.msg})


@app.post("/add/file", response_class=AsciiJSON)
async def add_file(request: Request, name: str = "song"):
    _accepting()
    if int(request.headers.get("content-length") or 0) > CONTRIB_MAX_BYTES:
        raise HTTPException(413, f"files can be at most {CONTRIB_MAX_BYTES >> 20} MB")
    tmp, size = TMP / f"upload-{uuid.uuid4().hex}{Path(name).suffix[:8]}", 0
    with open(tmp, "wb") as f:
        async for chunk in request.stream():
            size += len(chunk)
            if size > CONTRIB_MAX_BYTES:
                f.close()
                tmp.unlink(missing_ok=True)
                raise HTTPException(413, f"files can be at most {CONTRIB_MAX_BYTES >> 20} MB")
            f.write(chunk)
    ok, msg = await run_in_threadpool(station(request).ingest.add_upload, tmp, name)
    return AsciiJSON({"ok": ok, "msg": msg})


# --- operator (only from the station machine itself) ---------------------------------------------

def _local(request: Request):
    if not _is_local(request):
        raise HTTPException(403, "only the station laptop can do that")


@app.get("/op/status", response_class=AsciiJSON)
def op_status(request: Request):
    _local(request)
    st = station(request)
    cur = st.engine.current
    return AsciiJSON({
        "now": cur and {"id": cur.id, "title": cur.title, "artist": cur.artist},
        "here": st.here,
        "tracks": st.library.counts(),
        "upnext": st.upnext.titles(20),
        "shuffle_next": _label(pick.title, pick.artist) if (pick := _shuffle_next(st)) else "",
        "jobs": [vars(t) for t in list(st.ingest.tickets.values())[-10:]],
    })


@app.get("/op/list", response_class=AsciiJSON)
def op_list(request: Request):
    _local(request)
    return AsciiJSON(station(request).library.list())


CONTROLS = ("pause", "resume", "toggle", "next", "prev", "clear", "fwd", "back", "seek")


def _apply(st: Station, action: str, by: float = SEEK_SEC, to: float | None = None) -> dict:
    engine = st.engine
    if action == "toggle":
        action = "resume" if engine.paused else "pause"
    if action == "prev" and not engine.prev():
        raise HTTPException(409, "nothing has played yet")
    if action in ("fwd", "back", "seek"):
        if engine.paused:
            raise HTTPException(409, "the stream is paused - press play first")
        if not engine.current:
            raise HTTPException(409, "no song is playing")
        if action == "seek":
            if to is None:
                raise HTTPException(400, "jump to where? (to=seconds)")
            engine.seek_to(to)
        else:
            by = max(1.0, min(abs(by), 600.0))
            engine.seek(by if action == "fwd" else -by)
        return {"action": action, "notice": st.room.announce(action), "paused": False,
                "pos": round(engine.position), "dur": round(engine.current.duration or 0)}
    if action == "clear":
        if not (cleared := st.upnext.clear()):
            raise HTTPException(409, "the queue is already empty")
        return {"action": action, "notice": st.room.announce(action), "cleared": cleared,
                "paused": engine.paused}
    if action == "next":
        engine.skip()
    elif action == "pause":
        engine.pause()
    elif action == "resume":
        engine.resume()
    return {"action": action, "notice": st.room.announce(action), "paused": engine.paused}


def _allowed(request: Request, st: Station, who: str, action: str):
    """Controls are everyone's (one press at a time), or only the station laptop's with CREEK_OPEN_CONTROLS=0."""
    if not OPEN_CONTROLS:
        _local(request)
    elif why := st.room.control(who, action):
        raise HTTPException(429, why)


@app.post("/ctl/{action}", response_class=AsciiJSON)
def ctl(request: Request, action: str, id: str = "anon", by: float = SEEK_SEC, to: float | None = None):
    """pause / resume / toggle / next / prev / clear / fwd / back (by seconds) / seek (to seconds), for every
    listener (unless CREEK_OPEN_CONTROLS=0)."""
    if action not in CONTROLS:
        raise HTTPException(404, "unknown control")
    st = station(request)
    _allowed(request, st, id[:64], action)
    return AsciiJSON(_apply(st, action, by, to))


def _queued(st: Station, tid: int | None, place: int | None) -> int:
    """A song in the up-next queue, by track id or by its place in line (1 = up next)."""
    items = st.upnext.snapshot()
    if tid is None and place is not None and 1 <= place <= len(items):
        tid = items[place - 1].tid
    if tid is None or all(r.tid != tid for r in items):
        raise HTTPException(404, "that song isn't in the queue any more")
    return tid


@app.post("/queue/move", response_class=AsciiJSON)
def queue_move(request: Request, to: int, tid: int | None = None, place: int | None = None, id: str = "anon"):
    """Move a queued song (by tid, or by its place) to place `to`. Anyone can, one move at a time."""
    st = station(request)
    tid = _queued(st, tid, place)
    _allowed(request, st, id[:64], "move")
    if (landed := st.upnext.move(tid, to)) is None:
        raise HTTPException(404, "that song isn't in the queue any more")
    return AsciiJSON({"place": landed, "notice": st.room.announce("move"), "queue_version": st.upnext.version})


@app.post("/queue/remove", response_class=AsciiJSON)
def queue_remove(request: Request, tid: int | None = None, place: int | None = None, id: str = "anon"):
    """Take a song out of the up-next queue (it stays on the station, in the shuffle)."""
    st = station(request)
    tid = _queued(st, tid, place)
    _allowed(request, st, id[:64], "remove")
    if not st.upnext.remove(tid):
        raise HTTPException(404, "that song isn't in the queue any more")
    return AsciiJSON({"notice": st.room.announce("remove"), "queue_version": st.upnext.version})


@app.post("/op/play", response_class=AsciiJSON)
def op_play(request: Request, id: int | None = None, url: str | None = None):
    """No arguments: resume. id: crossfade into that song now. url: add it if new, then play it."""
    _local(request)
    st = station(request)
    if url:
        if not re.match(r"https?://\S+$", url):
            raise HTTPException(400, "that doesn't look like a link")
        def play(tid: int) -> str:
            st.engine.play_now(tid)
            return "playing now"

        t = st.ingest.add_link(url, contributed=False, on_ready=play)
        return AsciiJSON({"ticket": t.id, "status": t.status})
    if id is not None:
        t = st.library.get(id)
        if not t:
            raise HTTPException(404, "no such song in rotation (see `list`)")
        st.engine.play_now(id)
        return AsciiJSON({"playing": _label(t.title, t.artist)})
    st.engine.resume()
    return AsciiJSON({"paused": False})


@app.post("/op/playnext", response_class=AsciiJSON)
def op_play_next(request: Request, id: int | None = None, url: str | None = None):
    """Put a song first in the up-next queue: id from `list`, or a link (added if it's new)."""
    _local(request)
    st = station(request)

    def queue(tid: int) -> str:
        t, cur = st.library.get(tid), st.engine.current
        if t is None:
            return "couldn't queue that one"
        if cur and cur.id == tid:
            return "that one's playing right now"
        st.upnext.add(tid, "station", _label(t.title, t.artist), front=True)
        return f"plays next: {_label(t.title, t.artist)}"

    if url:
        if not re.match(r"https?://\S+$", url):
            raise HTTPException(400, "that doesn't look like a link")
        t = st.ingest.add_link(url, contributed=False, on_ready=queue, single=True)
        return AsciiJSON({"ticket": t.id, "status": t.status})
    if id is None or st.library.get(id) is None:
        raise HTTPException(404, "no such song in rotation (see `list`)")
    return AsciiJSON({"msg": queue(id)})


@app.post("/op/remove", response_class=AsciiJSON)
def op_remove(request: Request, id: str):
    _local(request)
    st = station(request)
    current = st.engine.current
    tid = current.id if id == "current" and current else int(id) if id.isdigit() else -1
    t = st.library.remove(tid)
    st.upnext.remove(tid)
    if not t:
        raise HTTPException(404, "no such track in rotation")
    if current and current.id == t.id:
        st.engine.skip()
    return AsciiJSON({"ok": True, "removed": f"{t.title} - {t.artist}".strip(" -")})


# last, so /op/play, /op/remove, ... above are matched first
@app.post("/op/{action}", response_class=AsciiJSON)
def op_control(request: Request, action: str, by: float = SEEK_SEC, to: float | None = None):
    if action == "skip":
        action = "next"
    if action not in CONTROLS:
        raise HTTPException(404, "unknown command")
    _local(request)
    return AsciiJSON(_apply(station(request), action, by, to))
