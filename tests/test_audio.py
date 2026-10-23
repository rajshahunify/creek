import subprocess

import numpy as np

from creek import audio


def pcm(values):
    return np.array(values, dtype="<i2").repeat(2).tobytes()   # mono values -> interleaved stereo


def test_crossfade_keeps_tail_length_and_stays_in_range():
    tail = pcm([32767] * 1000)
    head = pcm([32767] * 400)            # shorter head is padded with silence
    out = np.frombuffer(audio.crossfade(tail, head), dtype="<i2")
    assert len(out) * 2 == len(tail)
    assert out.max() <= 32767 and out.min() >= -32768
    assert out[0] == 32767               # starts fully on the outgoing track
    assert abs(int(out[-1])) < 200       # ends on the (silent) padded head, outgoing track faded out


def test_crossfade_of_nothing_is_nothing():
    assert audio.crossfade(b"", pcm([1, 2, 3])) == b""


def test_audible_length_trims_trailing_silence():
    buf = pcm([5000] * 100 + [10] * 50)
    assert audio.audible_length(buf) == 100 * 4
    assert audio.audible_length(pcm([0] * 20)) == 0


def test_mp3_sync_finds_a_frame_boundary_mid_stream():
    mp3 = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=d=2", "-ac", "2", "-b:a", "128k",
                          "-write_xing", "0", "-id3v2_version", "0", "-f", "mp3", "-"],
                         capture_output=True, check=True).stdout
    chunk = mp3[1234:]
    off = audio.mp3_sync_offset(chunk)
    assert off >= 0
    n = audio.mp3_frame_len(chunk[off:off + 4])
    assert n in (417, 418)
    assert audio.mp3_frame_len(chunk[off + n:off + n + 4])
    assert audio.mp3_sync_offset(b"\x00" * 2000) == -1


def test_fade_out_and_in():
    loud = pcm([20000] * 1000)
    out = np.frombuffer(audio.fade(loud, fade_in=False), dtype="<i2")
    inn = np.frombuffer(audio.fade(loud, fade_in=True), dtype="<i2")
    assert len(out) * 2 == len(loud) == len(inn) * 2
    assert out[0] == 20000 and abs(int(out[-1])) < 100
    assert inn[0] == 0 and inn[-1] > 19900
    assert audio.fade(b"", fade_in=True) == b""
