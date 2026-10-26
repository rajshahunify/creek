# creek

A quiet, always-flowing music stream for the local network. One station plays continuously; anyone can
slip in from a terminal mid-song (Linux or Windows, no browser) and leave whenever they like. No accounts,
no names, no chat. It shuffles a shared pool forever, crossfading between tracks at an even volume, and
everyone listening has the same say: post a song to play soon, pause, skip, go back, or clear the queue.
Listeners can also drop one of six emoji (🌊 💛 ✨ 🔥 😌 🎶) that drift along everyone's status line.

## Run the station

```sh
cd ~/creek
uv run python -m creek
```

It prints the address to share. Anyone who runs `curl http://<station>:7889` gets these instructions:

| | join | keep a `creek` command (once) |
|---|---|---|
| Linux | `curl -s http://192.168.1.141:7889/join \| sh` | `curl -s http://192.168.1.141:7889/join \| sh -s install` |
| Windows (PowerShell) | `irm http://192.168.1.141:7889/win \| iex` | `irm http://192.168.1.141:7889/win/install \| iex` |

`IAAHMLAP244.local` works in place of the IP on most machines (handy if DHCP gives the laptop a new address).
Always include `http://` on Windows.

While listening (same keys on Linux and Windows, `?` shows them):

| key | |
|---|---|
| **a** | post a song link: it plays soon, after anything already queued |
| **/** | find a song already on the station, then press its number to queue it |
| **space** / **n** / **p** | pause or play / next / previous, for everyone |
| **l** | what's on, what's up next, what played before |
| **c** | clear the up-next queue for everyone (asks y/n first; the songs stay in the shuffle) |
| **1–6** | drop an emoji |
| **+ / -** | volume (Windows; on Linux use `--volume N` or the system volume) |
| **q** | leave (Ctrl+C works too) |

The same things work as one-off commands, handy for keyboard shortcuts: `creek pause | play | next | prev | clear`,
`creek queue`, `creek find <words>`, `creek post <link | #id>`. `creek --quiet` plays audio only (no status
line, no keys); `creek --volume N` sets the starting volume.

**Shared controls.** Anyone listening can pause, skip or go back, for everyone; others see a short anonymous
note ("someone skipped ahead"). Two guardrails keep it calm: one press per second per person, and when two
people hit next at the same moment only one song is skipped. Start the station with `CREEK_OPEN_CONTROLS=0`
to keep the controls to the station laptop.

**How quick.** Whoever presses pause hears it at once (their own player freezes on the spot); everyone else
hears it about 1.3 s later, and play/next/prev land in about 1 s. That second is each listener's buffer
against Wi-Fi hiccups (`JOIN_BURST_SEC` in `creek/config.py`).

**What listeners need**
- Linux: `curl` plus any of `ffplay` / `mpv` / `mpg123`, or just PipeWire/PulseAudio/ALSA (`pw-play`,
  `paplay`, `aplay`), which almost every desktop has. Python 3 gives the status line and emoji; without it,
  it's plain audio.
- Windows: nothing; it plays through the built-in Windows Media Player engine. If that's missing or blocked
  by policy, the script says so and `winget install ffmpeg` (for `ffplay`) fixes it.

## Posting a song (any listener)

Press **a** in the player, paste a YouTube link to one song, press Enter. The station downloads it and queues
it to play **after the current song**, in the order songs were posted; everyone's status line shows what's
up next. Each person can have one song waiting at a time (post another once yours has played), the queue
holds up to 20, and posted songs must be 30 s – 15 min. Whole playlists go in with `creek add` instead.

Songs already on the station can be queued the same way: press **/**, type a few words, then the song's
number (or `creek find <words>` and `creek post #<id>`). **c** clears the queue for everyone after a y/n
check; cleared songs stay in the shuffle, and a song still downloading when the queue is cleared joins the
shuffle instead of the queue.

## Adding music

- **Folder**: drop files or whole folders into `~/creek/music/`. Picked up within 30 s.
- **Links**: put YouTube (or SoundCloud, Bandcamp, …) song or playlist URLs in `~/creek/links.txt`, one per
  line. Downloaded once into `music/.yt/`; playlists (first 50 songs) are re-checked every 12 hours.
- **From any listener**: `creek add <link | file | folder> ...` adds to the shuffle (not the up-next queue),
  good for playlists and folders. Contributions must be 30 s – 15 min and ≤ 50 MB; duplicates are
  recognised and turned away.

Every track's loudness is measured once and evened out (about -16 LUFS), and leading/trailing silence is
trimmed so the 6 s crossfades land on music. With no music at all the stream plays soft "quiet water" noise
so it never stops.

## On the station laptop

The shared controls work here too (`uv run python -m creek pause | play | next | prev | clear | now`), with
no rate limit. A few things only the station laptop can do:

```sh
uv run python -m creek play <link>            # add a YouTube link (if new) and play it right away
uv run python -m creek play <id>              # crossfade into a song from `list` now, skipping the queue
uv run python -m creek list                   # every song in rotation, with ids
uv run python -m creek remove <id|current>    # take one out for good (contributed files are deleted)
uv run python -m creek status                 # library counts, the up-next queue, recent downloads
```

A song played on request counts as its turn, so the shuffle won't bring it straight back.

Settings (environment variables when starting the station): `CREEK_OPEN_CONTROLS=0` keeps pause/skip/clear
to the station laptop, `CREEK_ACCEPT=0` stops new music being added, `CREEK_PORT` changes the port,
`CREEK_HOME` keeps music and data somewhere else.

## Keeping it running

- If `ufw` is enabled, open the port once: `sudo ufw allow 7889/tcp`.
- The stream pauses while the laptop sleeps or is off the network; listeners show "waiting for the stream"
  and reconnect on their own when it's back.
- To start it automatically when you log in, save this as `~/.config/systemd/user/creek.service`, then run
  `systemctl --user enable --now creek`:

  ```ini
  [Unit]
  Description=creek music stream

  [Service]
  WorkingDirectory=%h/creek
  Environment=PATH=%h/.local/bin:%h/.nvm/versions/node/v24.18.0/bin:/usr/bin:/bin
  ExecStart=%h/.local/bin/uv run python -m creek
  Restart=on-failure

  [Install]
  WantedBy=default.target
  ```

  (Node on the PATH lets yt-dlp solve YouTube's JavaScript challenges.)

## Good to know

- Anonymous by design: no access log, no IPs or names stored; reactions are counted, not attributed.
- A terminal player needs no browser tab, but it isn't invisible: monitoring tools still see the process and
  the network traffic.
- Downloading from YouTube is against YouTube's terms, and playing commercial music on a work network may
  need an OK from whoever runs it.
- Spotify links aren't supported (Spotify audio is DRM-protected); add the YouTube link for the same song.

## Layout

```
creek/engine.py    playout: decode → crossfade → pace to wall clock → MP3 encoder; pause, next, prev
creek/library.py   folder scanner (SQLite), search, balanced shuffle bag
creek/upnext.py    the up-next queue listeners post into
creek/room.py      shared state: now playing, reactions, control rate limits, notices
creek/ingest.py    links.txt, yt-dlp downloads, uploads
creek/media.py     ffmpeg/ffprobe: probing, loudness, decoding
creek/audio.py     crossfades, fades, silence trimming, MP3 frame sync
creek/server.py    HTTP: /stream.mp3 /stream.pcm /now /queue /search /post /ctl/* /react /add/* /op/*
creek/config.py    every tunable, with CREEK_* overrides
creek/clients/     join.sh (Linux bootstrap), client.py (Linux client), win.ps1 (Windows client)
tests/             uv run pytest
```
