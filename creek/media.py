"""Everything that shells out to ffmpeg / ffprobe."""

import hashlib
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

from .config import CHANNELS, MAX_GAIN_DB, MIN_GAIN_DB, RATE, TARGET_LUFS

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
_NICE = [shutil.which("nice"), "-n", "10"] if shutil.which("nice") else []

PCM_OUT = ["-f", "s16le", "-acodec", "pcm_s16le", "-ac", str(CHANNELS), "-ar", str(RATE), "pipe:1"]


def probe(path: Path) -> dict | None:
    """Duration and tags of the first audio stream, or None if there is no usable audio."""
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
             "-select_streams", "a:0", str(path)],
            capture_output=True, timeout=60, check=True,
        ).stdout
        info = json.loads(out)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None
    if not info.get("streams"):
        return None
    fmt = info.get("format", {})
    try:
        duration = float(fmt.get("duration") or info["streams"][0].get("duration"))
    except (TypeError, ValueError):
        return None
    tags = {}
    for src in (info["streams"][0].get("tags", {}), fmt.get("tags", {})):
        for k, v in src.items():
            tags.setdefault(k.lower(), v)
    return {"duration": duration, "title": tags.get("title", ""), "artist": tags.get("artist", "")}


def measure_gain(path: Path) -> float | None:
    """dB to apply so the track lands near TARGET_LUFS without peaking. None if silent/unreadable."""
    try:
        err = subprocess.run(
            [*_NICE, FFMPEG, "-nostdin", "-hide_banner", "-i", str(path), "-vn",
             "-af", "ebur128=peak=sample:framelog=quiet", "-f", "null", "-"],
            capture_output=True, timeout=600,
        ).stderr.decode(errors="replace")
    except (subprocess.SubprocessError, OSError):
        return None
    summary = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    if not i:
        return None
    gain = TARGET_LUFS - float(i.group(1))
    peak = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    if peak:
        gain = min(gain, -1.0 - float(peak.group(1)))
    return round(max(MIN_GAIN_DB, min(MAX_GAIN_DB, gain)), 2)


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Source:
    """Raw PCM from an ffmpeg process. read() blocks and returns b"" at the end."""

    def __init__(self, args: list[str]):
        self.proc = subprocess.Popen([FFMPEG, "-nostdin", "-v", "error", *args, *PCM_OUT],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)

    def read(self, n: int) -> bytes:
        return self.proc.stdout.read(n)

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.stdout.close()
        self.proc.wait()


def track_source(path: str, gain_db: float, start: float = 0.0) -> Source:
    # leading silence is dropped so the crossfade lands on actual music (but not when starting mid-song)
    if start > 0:
        return Source(["-ss", f"{start:.3f}", "-i", path, "-map", "0:a:0", "-vn", "-sn", "-dn",
                       "-af", f"volume={gain_db}dB"])
    return Source(["-i", path, "-map", "0:a:0", "-vn", "-sn", "-dn",
                   "-af", f"silenceremove=start_periods=1:start_threshold=-50dB,volume={gain_db}dB"])


def ambience_source(seconds: int = 20) -> Source:
    """Soft brown-noise 'quiet water' that fills the stream while there is no music."""
    seed = random.randrange(1 << 31)
    return Source(["-f", "lavfi", "-i",
                   f"anoisesrc=color=brown:amplitude=0.5:duration={seconds}:sample_rate={RATE}:seed={seed}",
                   "-af", "highpass=f=80,lowpass=f=1400,tremolo=f=0.1:d=0.35,volume=-4dB"])
