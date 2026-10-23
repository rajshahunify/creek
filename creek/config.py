"""Paths and tunables. Everything can be overridden with CREEK_* environment variables."""

import os
from pathlib import Path

ROOT = Path(os.environ.get("CREEK_HOME", Path(__file__).resolve().parent.parent))
MUSIC = ROOT / "music"
LINKS = ROOT / "links.txt"
DATA = ROOT / "data"
DB = DATA / "creek.db"
TMP = DATA / "tmp"

PORT = int(os.environ.get("CREEK_PORT", "7889"))
ACCEPT_CONTRIBUTIONS = os.environ.get("CREEK_ACCEPT", "1") != "0"
OPEN_CONTROLS = os.environ.get("CREEK_OPEN_CONTROLS", "1") != "0"   # 0: only the station laptop can pause/skip

# audio format shared by the whole pipeline: signed 16-bit little-endian stereo
RATE = 44100
CHANNELS = 2
FRAME_BYTES = 2 * CHANNELS
BYTES_PER_SEC = RATE * FRAME_BYTES

BLOCK_SEC = 0.1           # playout granularity
CROSSFADE_SEC = 6.0       # overlap between consecutive tracks
SKIP_FADE_SEC = 0.6       # quick crossfade for next / prev / play
PAUSE_FADE_SEC = 0.3      # pause and resume fade just enough not to click
RESUME_FADE_SEC = 0.3
LOOKAHEAD_SEC = 16.0      # decoded ahead so trailing silence can be trimmed before the crossfade
LEAD_SEC = 0.2            # how far playout may run ahead of the wall clock (controls can't undo what's out)
JOIN_BURST_SEC = 1.0      # audio a joining listener gets at once: their buffer, so also their delay
MP3_BITRATE = "128k"

TARGET_LUFS = -16.0
MAX_GAIN_DB = 10.0
MIN_GAIN_DB = -20.0

AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".webm", ".wma", ".mka", ".mp4"}
SCAN_EVERY_SEC = 30
SETTLE_SEC = 10           # ignore files modified more recently than this (still being copied/downloaded)

# folder music (the operator's own) is trusted a bit more than contributions
FOLDER_MIN_SEC, FOLDER_MAX_SEC = 30, 60 * 60
CONTRIB_MIN_SEC, CONTRIB_MAX_SEC = 30, 15 * 60
CONTRIB_MAX_BYTES = 50 * 1024 * 1024
PLAYLIST_CAP = 50
LINKS_REFRESH_SEC = 12 * 3600

# reactions: index -> glyph; clients map indices to their own glyphs
REACTIONS = ["🌊", "💛", "✨", "🔥", "😌", "🎶"]
REACT_MIN_GAP_SEC = 1.5
CONTROL_MIN_GAP_SEC = 1.0  # per listener, between pause/next/prev presses
JUMP_GUARD_SEC = 2.0       # two people pressing next at once skip one song, not two
