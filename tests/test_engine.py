from creek import engine
from creek.config import BYTES_PER_SEC
from creek.engine import Engine, Playing
from creek.library import Library, Track
from creek.media import track_source
from creek.upnext import UpNext


def sec(n: float) -> int:
    return int(n * 44100) * 4


def playing(path) -> Playing:
    t = Track(1, str(path), "Tone", "", 40.0, 0.0)
    return Playing(t, track_source(t.path, 0.0))


def test_seek_jumps_ahead_and_back_within_a_song(tmp_path, tone):
    p = playing(tone(tmp_path / "a.flac", 40, 440, noise=True))
    try:
        p.fill(sec(10))
        heard = p.take(sec(10))
        p.seek(sec(5))
        assert p.pos == sec(15)
        p.seek(-sec(12))                      # back over what played: straight from memory
        assert p.pos == sec(3)
        assert p.take(sec(1)) == heard[sec(3):sec(4)]
        p.seek(-sec(60))                      # can't go before the start
        assert p.pos == 0
    finally:
        p.close()


def test_seek_back_further_than_memory_reopens_the_file(tmp_path, tone, monkeypatch):
    monkeypatch.setattr(engine, "HISTORY", sec(2))
    p = playing(tone(tmp_path / "a.flac", 40, 440, noise=True))
    try:
        p.fill(sec(10))
        p.take(sec(10))
        p.seek(-sec(6))
        assert p.pos == sec(4) and not p.buf
        p.fill(sec(1))
        assert len(p.take(sec(1))) == sec(1) and p.pos == sec(5)
    finally:
        p.close()


def test_seek_past_the_end_runs_out_the_song(tmp_path, tone):
    p = playing(tone(tmp_path / "a.flac", 40, 440, noise=True))
    try:
        p.seek(sec(100))
        assert p.eof and not p.buf and abs(p.pos / BYTES_PER_SEC - 40) < 0.5
    finally:
        p.close()


def test_the_shuffle_pick_shown_is_the_song_that_plays(tmp_path, tone):
    music = tmp_path / "music"
    music.mkdir()
    for i in range(4):
        tone(music / f"{i}.mp3", 40, 300 + 100 * i, f"Song {i}", f"Artist {i}")
    lib = Library(tmp_path / "t.db", music)
    lib.scan()
    e = Engine(lib, room=None, on_mp3=print, on_pcm=print, upnext=UpNext())
    for _ in range(3):
        shown = e.shuffle_pick()
        assert e.shuffle_pick() == shown      # asking again doesn't change it
        p = e._open_next()
        p.close()
        assert p.track.id == shown.id


def test_a_queued_song_goes_first_and_the_shuffle_pick_waits(tmp_path, tone):
    music = tmp_path / "music"
    music.mkdir()
    for i in range(3):
        tone(music / f"{i}.mp3", 40, 300 + 100 * i, f"Song {i}", f"Artist {i}")
    lib = Library(tmp_path / "t.db", music)
    lib.scan()
    q = UpNext()
    e = Engine(lib, room=None, on_mp3=print, on_pcm=print, upnext=q)
    pick = e.shuffle_pick()
    other = next(t for t in lib.list() if t["id"] != pick.id)
    q.add(other["id"], "ana", other["title"])
    p = e._open_next()
    p.close()
    assert p.track.id == other["id"] and e.shuffle_pick() == pick
    # someone posts the shuffle's pick itself: it plays from the queue, and the shuffle picks again
    q.add(pick.id, "ben", pick.title)
    p = e._open_next()
    p.close()
    assert p.track.id == pick.id and e.shuffle_pick().id != pick.id


def test_a_new_shuffle_cycle_doesnt_start_with_the_song_just_played(tmp_path, tone):
    music = tmp_path / "music"
    music.mkdir()
    for i in range(3):
        tone(music / f"{i}.mp3", 40, 300 + 100 * i, f"Song {i}", f"Artist {i}")
    lib = Library(tmp_path / "t.db", music)
    lib.scan()
    for _ in range(10):                      # the deal is random: try it a few times
        q = UpNext()
        e = Engine(lib, room=None, on_mp3=print, on_pcm=print, upnext=q)
        lib.bag.bag.clear()
        pick = e.shuffle_pick()              # the first song of a fresh cycle
        for t in lib.list():
            if t["id"] != pick.id:           # the rest of the cycle plays from the queue first
                q.add(t["id"], f"p{t['id']}", t["title"])
                e._open_next().close()
        e._open_next().close()               # now the pick, the last of the cycle
        assert e.shuffle_pick().id != pick.id
