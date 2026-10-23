"""python -m creek [serve | now | play [id|link] | pause | next | prev | list | remove <id|current> | status]"""

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
  prev                 back to the previous song
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


def serve():
    import uvicorn

    from .server import app, lan_ip

    ip, name = lan_ip(), socket.gethostname()
    print(f"""
  creek is flowing on port {PORT}

  share this:   curl http://{ip}:{PORT}            (or http://{name}.local:{PORT})
  music folder: {MUSIC}
  links file:   {LINKS}
  controls:     uv run python -m creek play [id|link] | pause | next | prev | now | list | status
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
    elif cmd in ("next", "skip"):
        call("POST", "/op/next")
        print("on to the next one…")
    elif cmd == "prev":
        call("POST", "/op/prev")
        print("going back…")
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
        for j in s["jobs"]:
            print(f"  [{j['status']}] {j['what']}  {j['msg']}")
    else:
        print(USAGE)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
