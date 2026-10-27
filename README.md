# creek

A quiet, always-flowing music stream for the local network. One station plays continuously; anyone can
slip in mid-song from a browser or a terminal (Linux or Windows) and leave whenever they like. No accounts,
no names, no chat. It shuffles a shared pool forever, crossfading between tracks at an even volume, and
everyone listening has the same say: search YouTube and play a song next (or right now), rearrange the
queue, pause, skip, go back, or drag the progress bar. Emoji reactions are switched off (`REACTIONS` in
`creek/config.py` and `GLYPHS` in `creek/clients/client.py` bring the six back for the terminals).

## Run the station

```sh
cd ~/creek
uv run python -m creek
```

It prints the address to share. Open it in a browser for the web player, or run `curl http://<station>:7889`
in a terminal for these instructions:

| | join | keep a `creek` command (once) |
|---|---|---|
| Linux | `curl -s http://192.168.1.141:7889/join \| sh` | `curl -s http://192.168.1.141:7889/join \| sh -s install` |
| Windows (PowerShell) | `irm http://192.168.1.141:7889/win \| iex` | `irm http://192.168.1.141:7889/win/install \| iex` |

`IAAHMLAP244.local` works in place of the IP on most machines (handy if DHCP gives the laptop a new address).
Always include `http://` on Windows.

## The web player: AB SMB

Open `http://<station>:7889` in any browser. The page is a prototype of the AB SMB dashboard with the music
built in: a header (**AB SMB**, a Ctrl K "go to" palette, shortcuts, light / dark / follow-the-system theme,
account), a side rail (Overview, the reports, Admin; it collapses to icons, and on a phone it opens as a
drawer from ☰), and the music bar along the bottom of every page.

- **Overview**: this week's headline numbers, MQLs per week, recent exports and the reports.
- **Reports**: TAL Master (the music, below), then the AB Demand Gen sheets (Account Coverage, Campaign
  Leads, MQL Weekly, Intent Signals, Pipeline by Region). Search every column, sort any column, page through, refresh, export the
  rows on screen as CSV. A "Data as of" badge turns amber after an hour.
- **Admin**: users (with pending approvals) and the export log, read-only.

**Reports and Admin show demo data.** It is generated in the browser (`web/src/dashboard/mock.ts`, seeded,
so every reload shows the same numbers) because the AB dashboard's database isn't reachable from here.
`web/src/dashboard/data.ts` is the only file that would change to read the real AB backend
(`/api/sheets`, `/api/admin/...`). Music is always live, from the station.

### Music

Music isn't a page or module of its own: **TAL Master's grid is the office's music**, and the controls are on
every page. The sheet keeps its name, its place in the rail and its URL (`#/reports/1`); nothing says "music".
Songs show by name only (no cover art or thumbnails anywhere).

- **The music bar** (bottom of every page): what's playing, play/pause and skip for everyone, **Tune in**
  and your own volume, and **Up next**, which opens TAL Master. A thin, quiet progress line (one muted grey)
  runs along its top; click or drag it to jump within the song (for everyone).
- **The ♪ button in the header** hides or shows the whole music bar (so does "Hide the music bar" in Ctrl K).
  The music keeps playing while it's hidden, and the choice is remembered per browser.
- **TAL Master**: the grid's rows are the song playing now, the queue, the shuffle's next pick and what
  played earlier, with #, Title, Artist, Length, Status and Added by. The sheet's own tools do the music's
  version of their job:
  - **Search every column** finds songs, on the station (instantly) and on YouTube, and the grid shows the
    results: **play next** (Enter), **end of the queue** (Shift+Enter), **after any queued song** (⋯), or
    **play now** for everyone (Ctrl+Enter). Pasting a link works too. Esc goes back to the queue.
  - **Refresh** re-pulls the live queue; **Data as of** shows when it last changed (it's live, so it's
    always "just now"); **Export** downloads what's on screen (the queue, or the search results) as CSV.
  - **Reorder** by dragging a queued row, or select it and press **Shift+↑/↓** (Alt works too). ↑/↓ alone
    move between rows; **Delete** takes a song out. ⋯ on a row: play next, play now, move, take out.
  - **⋯** next to Export: What's new, and Clear the queue.
    First-time visitors get a short welcome.
- Pause, skip and jumping within the song work for everyone; your volume and mute are yours alone. Other
  people's actions show up as short anonymous notes ("someone skipped ahead") on any page. Media keys,
  headphone buttons and the lock screen control the stream from any page. Works on phones.

The music keys only work on TAL Master, so typing in another report (or pressing Space on it) never pauses
the office's music. **Ctrl K** and **?** work everywhere. An old `#/music` link opens TAL Master.

| key | |
|---|---|
| **Ctrl+K** | go to a page, report or action (anywhere) |
| **?** | all shortcuts (anywhere) |
| **Space** / **K** | pause or play, for everyone |
| **← / →** | jump back / ahead 5 s |
| **Shift+N** / **Shift+P**, **Ctrl+→** / **Ctrl+←** | next / previous song |
| **/** | search the station and YouTube (the sheet's search box) |
| **↑ / ↓**, **M** | your volume, mute |
| **Q** | jump to the first queued song (then **Shift+↑/↓** moves it, **Delete** takes it out) |
| **W** | what's new |
| **Esc** | in the search box: back to the queue |

## In a terminal

While listening (same keys on Linux and Windows, `?` shows them):

| key | |
|---|---|
| **a** | play a song next, ahead of the queue: paste a link, or type words to search the station and YouTube |
| **e** | add a song to the end of the queue, behind the songs already waiting (a link, or words, the same way) |
| **/** | search, then press a song's number to queue it (**!** then a number plays it now, for everyone) |
| **space** / **n** / **p** | pause or play / next / previous, for everyone (**Ctrl+→ / Ctrl+←** also next / previous) |
| **← / →** | jump back / ahead 5 s in the song, for everyone |
| **g** | jump to a time in the song (type `1:30`) |
| **l** | what's on, what's up next (including the shuffle's pick), what played before |
| **m** / **x** | move a song in the up-next queue (`3 1`: song 3 goes first) / take one out |
| **c** | clear the up-next queue for everyone (asks y/n first; the songs stay in the shuffle) |
| **w** | what's new (new things also show once, when you join) |
| **+ / -** | volume (Windows; on Linux use `--volume N` or the system volume) |
| **q** | leave (Ctrl+C works too) |

The same things work as one-off commands, handy for keyboard shortcuts: `creek pause | play | next | prev | clear`,
`creek fwd | back [seconds]`, `creek seek <m:ss>`, `creek queue`, `creek move <n> <place>`, `creek drop <n>`,
`creek find <words>` (the station and YouTube), `creek post <link | #id>` (to the back of the queue),
`creek next <link | #id>` (to the front), `creek playnow <link | #id>`, `creek news`. `creek --quiet` plays
audio only (no status line, no keys); `creek --volume N` sets the starting volume.

**Shared controls.** Anyone listening can pause, skip or go back, for everyone; others see a short anonymous
note ("someone skipped ahead"). Two guardrails keep it calm: one press per second per person (the arrow keys
can be tapped a few times a second), and when two people hit next at the same moment only one song is skipped. Start the station with `CREEK_OPEN_CONTROLS=0`
to keep the controls to the station laptop.

**How quick.** Whoever presses pause hears it at once (their own player freezes on the spot); everyone else
hears it about 1.3 s later, and play/next/prev land in about 1 s. That second is each listener's buffer
against Wi-Fi hiccups (`JOIN_BURST_SEC` in `creek/config.py`).

**What listeners need**
- Linux: `curl` plus any of `ffplay` / `mpv` / `mpg123`, or just PipeWire/PulseAudio/ALSA (`pw-play`,
  `paplay`, `aplay`), which almost every desktop has. Python 3 gives the status line; without it,
  it's plain audio.
- Windows: nothing; it plays through the built-in Windows Media Player engine. If that's missing or blocked
  by policy, the script says so and `winget install ffmpeg` (for `ffplay`) fixes it.

## Posting a song (any listener)

In the web dashboard, type in TAL Master's search box (`/`) and pick a result. In a terminal, press **a**, then type a few words (the
station's songs and YouTube's top matches come up, numbered) or paste a YouTube link, and press Enter. The station downloads it and puts
it at the **front** of the up-next queue, so it plays as soon as the current song ends (pair it with **n** to
hear it right away). Press **e** instead to add it to the **end** of the queue, behind the songs already
waiting; everyone's status line shows what's up next.

When nobody has posted anything, the shuffle plays. It picks its next song ahead of time, so the status line
and **l** show exactly which song comes next either way; a posted song goes ahead of that pick, and the pick
plays once the queue is empty again. Each person can have one song waiting at a time (post another once yours has played), the queue
holds up to 20, and posted songs must be 30 s – 30 min. Whole playlists go in with `creek add` instead.

Search results that are already on the station queue straight away; YouTube results download first (a few
seconds), then take their place. **Play now** crossfades into the song for everyone as soon as it's ready;
it counts as a skip, so the same one-press guardrails apply. Anyone can rearrange the queue or take songs out
of it (on the web by dragging TAL Master's rows or Shift+↑/↓, in the terminal with **m** and **x**). **c** clears the queue for everyone after a y/n
check; cleared songs stay in the shuffle, and a song still downloading when the queue is cleared joins the
shuffle instead of the queue.

## Adding music

- **Folder**: drop files or whole folders into `~/creek/music/`. Picked up within 30 s.
- **Links**: put YouTube (or SoundCloud, Bandcamp, …) song or playlist URLs in `~/creek/links.txt`, one per
  line. Downloaded once into `music/.yt/`; playlists (first 50 songs) are re-checked every 12 hours.
- **From any listener**: `creek add <link | file | folder> ...` adds to the shuffle (not the up-next queue),
  good for playlists and folders. Contributions must be 30 s – 30 min and ≤ 50 MB; duplicates are
  recognised and turned away.

Every track's loudness is measured once and evened out (about -16 LUFS), and leading/trailing silence is
trimmed so the 6 s crossfades land on music. With no music at all the stream plays soft "quiet water" noise
so it never stops.

## On the station laptop

The shared controls work here too (`uv run python -m creek pause | play | next | prev | fwd | back | clear |
now`), with no rate limit. A few things only the station laptop can do:

```sh
uv run python -m creek play <link>            # add a YouTube link (if new) and play it right away
uv run python -m creek play <id>              # crossfade into a song from `list` now, skipping the queue
uv run python -m creek next <id|link>         # play a song next, ahead of the up-next queue
uv run python -m creek list                   # every song in rotation, with ids
uv run python -m creek remove <id|current>    # take one out for good (contributed files are deleted)
uv run python -m creek seek 1:30              # jump to a time in this song
uv run python -m creek move 3 1               # move the 3rd song in the up-next queue to the front
uv run python -m creek drop 2                 # take the 2nd song out of the up-next queue
uv run python -m creek news                   # what listeners are told is new (edit creek/news.py)
uv run python -m creek status                 # library counts, the up-next queue, recent downloads
```

A song played on request counts as its turn, so the shuffle won't bring it straight back.

Settings (environment variables when starting the station): `CREEK_OPEN_CONTROLS=0` keeps pause/skip/clear
and queue edits to the station laptop, `CREEK_ACCEPT=0` stops new music being added (and YouTube search),
`CREEK_PORT` changes the port, `CREEK_HOME` keeps music and data somewhere else, `CREEK_KEY` asks everyone for
a key (see below), `CREEK_YT_COOKIES` points yt-dlp at a cookies.txt, `CREEK_WEB` serves the web player from
another folder.

When you add something listeners should know about, add an entry to `creek/news.py`: the web player's bell
and every terminal pick it up.

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

## Building the web player

The web player (the AB SMB dashboard) is React + TypeScript in `web/`, built to static files the station
serves (no separate server: rebuilding is enough, the station picks the new files up without a restart). Build it once after cloning, and again after changing it:

```sh
cd web && npm ci && npm run build
```

While working on it, run the station as usual and `npm run dev` in `web/`: Vite serves the page with hot
reload on :5173 and passes every station route through to :7889. `npm test` runs the unit tests,
`npm run typecheck` the type checks.

## Running it in the cloud

The `Dockerfile` builds the web player and runs the station, with music and data in a volume:

```sh
docker build -t creek .
docker run -d --name creek --restart unless-stopped -p 7889:7889 -v creek-data:/data \
  -e CREEK_KEY=choose-a-long-key creek
```

- **Set `CREEK_KEY`** on anything reachable from the internet. Without it, anyone who finds the address can
  listen, skip and post. With it, the front page only says a key is needed; share
  `http://<host>:7889/?key=<key>` instead. The web player keeps the key in a cookie, and the join commands
  shown on that page carry it into the terminal clients. The station's own machine never needs it.
- **YouTube often blocks cloud servers' addresses** ("Sign in to confirm you're not a bot"). Export
  cookies from a browser signed in to a spare account, put the file in the volume, and set
  `CREEK_YT_COOKIES=/data/cookies.txt`.
- For HTTPS, put a reverse proxy such as Caddy in front (`caddy reverse-proxy --from creek.example.com --to
  localhost:7889`). Turn off its response buffering for `/stream.mp3`, `/stream.pcm` and `/events`.
- Downloading from YouTube is against YouTube's terms, and streaming music publicly needs rights a LAN
  setup may get away without.

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
creek/server.py    HTTP: streams, the JSON API (below), the web player, the client scripts
creek/news.py      "what's new" for listeners, shared by the web player and the terminals
creek/config.py    every tunable, with CREEK_* overrides
creek/clients/     join.sh (Linux bootstrap), client.py (Linux client), win.ps1 (Windows client)
web/               the dashboard: React + TypeScript (Vite). src/App.tsx the shell, src/pages/ one file per page,
                   src/components/shell/ the header, rail and music bar, src/pages/MusicSheet.tsx TAL Master's music grid, src/store.ts the music state,
                   src/dashboard/ the demo data (data.ts is the seam)
tests/             uv run pytest (and npm test in web/)
Dockerfile         the web player built, the station run, music and data in a volume
```

### The API

Every listener (web or terminal) uses the same small HTTP API. `id` is an anonymous per-listener id.

| route | |
|---|---|
| `GET /stream.mp3`, `/stream.pcm` | the live stream |
| `GET /state?id=` | everything the web player shows: now playing, position, queue (with tids), shuffle pick, history |
| `GET /events?id=` | server-sent events: `state` whenever anything visible changes, `react` for emoji (when `REACTIONS` has any) |
| `GET /now?since=` | the compact version terminals poll every second |
| `GET /search?q=`, `/yt/search?q=` | songs on the station; YouTube's top matches (`on_station`, `why_not`) |
| `POST /post?url= or track=` | queue a song: `next=1` first, `at=N` at place N, `now=1` play now |
| `POST /queue/move?tid= or place=&to=`, `/queue/remove` | rearrange the up-next queue |
| `POST /ctl/{pause,resume,toggle,next,prev,clear,fwd,back,seek}` | shared controls (`by=` seconds, `seek` takes `to=`) |
| `POST /react?e=` | drop an emoji (refused while `REACTIONS` is empty, the default) |
| `GET /news?seen=` | what's new |
| `/op/*` | station-laptop-only commands |

