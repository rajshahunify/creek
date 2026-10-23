import os
import subprocess
import time

import pytest


def make_tone(path, seconds=40, freq=440, title=None, artist=None, noise=False):
    """Write a short audio file with ffmpeg, backdated so the library scanner treats it as settled."""
    src = f"anoisesrc=color=pink:a=0.2:d={seconds}" if noise else f"sine=f={freq}:d={seconds}"
    meta = []
    if title:
        meta += ["-metadata", f"title={title}"]
    if artist:
        meta += ["-metadata", f"artist={artist}"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-ac", "2", *meta, str(path)],
                   check=True)
    old = time.time() - 3600
    os.utime(path, (old, old))
    return path


@pytest.fixture
def tone():
    return make_tone
