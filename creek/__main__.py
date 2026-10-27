"""python -m creek [serve | now | play [id|link] | pause | next [id|link] | prev | fwd | back | clear | list | ...]"""

import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import LINKS, MUSIC, PORT

USAGE = """usage: python -m creek [command]

  serve                run the station (default)
  now                  what's flowing and how many are here
  play                 carry on after a pause
  play <id>            crossfade into that song now (ids from `list`)
  play <link>          add a YouTube link if it's new, then play it straight away
  pause                fade out for everyone; listeners stay connected
  next                 crossfade to the next song (also: skip)
  next <id|link>       play that song next, ahead of the up-next queue (a link is added if it's new)
  prev                 back to the previous song
  fwd [seconds]        jump ahead in this song (default 5 s)
  back [seconds]       jump back in this song (default 5 s)
  clear                empty the up-next queue (the songs stay on the station)
  seek <m:ss>          jump to that time in this song
  move <n> <place>     move the n-th song in the up-next queue to another place (1 = up next)
  drop <n>             take the n-th song out of the up-next queue (it stays in the shuffle)
  news                 what's new for listeners (the same list the web player and terminals show)
  list                 every song in rotation, with ids
  remove <id|current>  take a song out of rotation for good
  status               library counts and recent downloads

  These affect everyone listening, so they only work on the station laptop.
"""


def call(method: str, path: str):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"creek: {json.load(e).get('detail', e.reason)}")
    except urllib.error.URLError:
        sys.exit("creek: the station isn't running (start it with: uv run python -m creek)")


def seconds(text: str) -> int | None:
    """'1:30' or '90' -> 90."""
    parts = text.split(":")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        return None
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return total


def serve():
    import uvicorn

    from .server import app, lan_ip

    ip, name = lan_ip(), socket.gethostname()
    print(f"""
  creek is flowing on port {PORT}

  share this:   curl http://{ip}:{PORT}            (or http://{name}.local:{PORT})
  web player:   http://{ip}:{PORT}                 (open it in a browser)
  music folder: {MUSIC}
  links file:   {LINKS}
  controls:     uv run python -m creek play [id|link] | pause | next [id|link] | prev | fwd | back | clear
                uv run python -m creek now | list | status
""", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, access_log=False, log_level="warning",
                timeout_graceful_shutdown=2)


def main(argv: list[str]):
    cmd, args = (argv[0], argv[1:]) if argv else ("serve", [])
    if cmd == "serve":
        serve()
    elif cmd == "now":
        n = call("GET", "/now")
        song = "quiet water (no music yet)" if n["quiet"] else " - ".join(x for x in (n["title"], n["artist"]) if x)
        print(f"{'paused: ' if n.get('paused') else ''}{song}  ·  {n['here']} here")
        if n.get("upnext"):
            more = n["queued"] - len(n["upnext"])
            print("up next: " + ", ".join(n["upnext"]) + (f" (+{more} more)" if more > 0 else ""))
        elif n.get("next"):
            print(f"up next: {n['next']} (shuffle)")
    elif cmd in ("next", "skip") and not args:
        call("POST", "/op/next")
        print("on to the next one…")
    elif cmd == "next" and len(args) == 1 and args[0].lstrip("#").isdigit():
        print(call("POST", f"/op/playnext?id={args[0].lstrip('#')}")["msg"])
    elif cmd == "next" and len(args) == 1 and args[0].startswith(("http://", "https://")):
        ticket = call("POST", "/op/playnext?url=" + urllib.parse.quote(args[0], safe=""))["ticket"]
        print("fetching", end="", flush=True)
        while (t := call("GET", f"/add/{ticket}"))["status"] not in ("done", "failed"):
            time.sleep(1)
            print(".", end="", flush=True)
        print(f"\r{t['msg']}" + " " * 20)
    elif cmd in ("fwd", "back") and len(args) <= 1 and all(a.isdigit() for a in args):
        r = call("POST", f"/op/{cmd}" + (f"?by={args[0]}" if args else ""))
        print(f"{'⏩' if cmd == 'fwd' else '⏪'} {r['pos'] // 60}:{r['pos'] % 60:02d} / {r['dur'] // 60}:{r['dur'] % 60:02d}")
    elif cmd == "prev":
        call("POST", "/op/prev")
        print("going back…")
    elif cmd == "clear":
        n = call("POST", "/op/clear")["cleared"]
        print(f"cleared the queue ({n} song{'s' if n != 1 else ''}; they stay in the shuffle)")
    elif cmd == "pause":
        call("POST", "/op/pause")
        print("paused (listeners stay connected; `play` carries on)")
    elif cmd == "play" and not args:
        call("POST", "/op/play")
        print("playing")
    elif cmd == "play" and len(args) == 1 and args[0].isdigit():
        print(f"playing: {call('POST', f'/op/play?id={args[0]}')['playing']}")
    elif cmd == "play" and len(args) == 1 and args[0].startswith(("http://", "https://")):
        ticket = call("POST", "/op/play?url=" + urllib.parse.quote(args[0], safe=""))["ticket"]
        print("fetching", end="", flush=True)
        while (t := call("GET", f"/add/{ticket}"))["status"] not in ("done", "failed"):
            time.sleep(1)
            print(".", end="", flush=True)
        print(f"\r{t['msg']}" + " " * 20)
    elif cmd == "seek" and len(args) == 1 and (to := seconds(args[0])) is not None:
        r = call("POST", f"/op/seek?to={to}")
        print(f"⏩ {r['pos'] // 60}:{r['pos'] % 60:02d} / {r['dur'] // 60}:{r['dur'] % 60:02d}")
    elif cmd == "move" and len(args) == 2 and all(a.isdigit() for a in args):
        print(f"moved: now number {call('POST', f'/queue/move?place={args[0]}&to={args[1]}&id=station')['place']}")
    elif cmd == "drop" and len(args) == 1 and args[0].isdigit():
        call("POST", f"/queue/remove?place={args[0]}&id=station")
        print("taken out of the queue (it stays in the shuffle)")
    elif cmd == "news":
        from .news import NEWS
        for x in NEWS:
            print(f"{x.date}  {x.title}")
            for line in x.lines:
                print(f"    · {line}")
    elif cmd == "list":
        for t in call("GET", "/op/list"):
            mins, secs = divmod(int(t["duration"] or 0), 60)
            print(f"{t['id']:>5}  {mins:>2}:{secs:02}  {t['title']}" + (f" - {t['artist']}" if t["artist"] else ""))
    elif cmd == "remove" and len(args) == 1:
        print(f"removed: {call('POST', f'/op/remove?id={args[0]}')['removed']}")
    elif cmd == "status":
        s = call("GET", "/op/status")
        now = s["now"]
        print(f"now:    {now['title'] + (' - ' + now['artist'] if now['artist'] else '') if now else 'quiet water'}")
        print(f"here:   {s['here']}")
        print("tracks: " + (", ".join(f"{v} {k}" for k, v in sorted(s["tracks"].items())) or "none yet"))
        for i, title in enumerate(s["upnext"], 1):
            print(f"  up next {i}: {title}")
        if s.get("shuffle_next"):
            print(f"  {'then' if s['upnext'] else 'up next'} (shuffle): {s['shuffle_next']}")
        for j in s["jobs"]:
            print(f"  [{j['status']}] {j['what']}  {j['msg']}")
    else:
        print(USAGE)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
