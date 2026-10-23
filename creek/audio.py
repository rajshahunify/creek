"""Pure PCM / MP3 helpers (no processes, no I/O) so they are easy to test."""

import numpy as np

from .config import FRAME_BYTES


def crossfade(tail: bytes, head: bytes) -> bytes:
    """Equal-power crossfade: `tail` fades out while `head` fades in. Output has len(tail)."""
    n = len(tail) // FRAME_BYTES
    if n == 0:
        return b""
    a = np.frombuffer(tail[: n * FRAME_BYTES], dtype="<i2").reshape(-1, 2).astype(np.float32)
    b = np.zeros_like(a)
    m = min(n, len(head) // FRAME_BYTES)
    if m:
        b[:m] = np.frombuffer(head[: m * FRAME_BYTES], dtype="<i2").reshape(-1, 2)
    t = (np.arange(n, dtype=np.float32) / n)[:, None] * (np.pi / 2)
    out = a * np.cos(t) + b * np.sin(t)
    return np.clip(out, -32768, 32767).astype("<i2").tobytes()


def fade(pcm: bytes, fade_in: bool) -> bytes:
    """Equal-power fade in or out across the whole of pcm (used for pause and resume)."""
    n = len(pcm) // FRAME_BYTES
    if n == 0:
        return b""
    x = np.frombuffer(pcm[: n * FRAME_BYTES], dtype="<i2").reshape(-1, 2).astype(np.float32)
    t = np.arange(n, dtype=np.float32) / n * (np.pi / 2)
    g = np.sin(t) if fade_in else np.cos(t)
    return (x * g[:, None]).astype("<i2").tobytes()


def audible_length(buf: bytes | bytearray, threshold: float = 0.003) -> int:
    """Length in bytes once trailing near-silence (below ~-50 dBFS) is cut off."""
    n = len(buf) // FRAME_BYTES
    if n == 0:
        return 0
    x = np.abs(np.frombuffer(memoryview(buf)[: n * FRAME_BYTES], dtype="<i2").reshape(-1, 2)).max(axis=1)
    loud = np.flatnonzero(x > threshold * 32768)
    return 0 if loud.size == 0 else (int(loud[-1]) + 1) * FRAME_BYTES


_BR_V1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
_BR_V2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
_SR = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}


def mp3_frame_len(h: bytes) -> int:
    """Byte length of the Layer III frame whose header starts h, or 0 if h is not a header."""
    if len(h) < 4 or h[0] != 0xFF or (h[1] & 0xE0) != 0xE0:
        return 0
    ver, layer = (h[1] >> 3) & 3, (h[1] >> 1) & 3
    br_i, sr_i, pad = (h[2] >> 4) & 0xF, (h[2] >> 2) & 3, (h[2] >> 1) & 1
    if ver == 1 or layer != 1 or br_i in (0, 15) or sr_i == 3:
        return 0
    if ver == 3:
        return 144 * _BR_V1[br_i] * 1000 // _SR[3][sr_i] + pad
    return 72 * _BR_V2[br_i] * 1000 // _SR[ver][sr_i] + pad


def mp3_sync_offset(data: bytes) -> int:
    """Offset of the first frame header followed by another valid header, or -1."""
    for i in range(len(data) - 3):
        if data[i] != 0xFF:
            continue
        n = mp3_frame_len(data[i : i + 4])
        if n and i + n + 4 <= len(data) and mp3_frame_len(data[i + n : i + n + 4]):
            return i
    return -1
