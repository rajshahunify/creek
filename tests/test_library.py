import os
import random
from pathlib import Path

from creek.library import Library, ShuffleBag, clean_meta


def test_every_track_once_per_cycle():
    bag = ShuffleBag(random.Random(1))
    for i in range(10):
        bag.add(i, f"artist{i}")
    first = [bag.next() for _ in range(10)]
    second = [bag.next() for _ in range(10)]
    assert sorted(first) == sorted(second) == list(range(10))
    assert first[-1] != second[0]


def test_an_album_gets_spread_out():
    # a third of the library is one album: it should almost never play back-to-back
    back_to_back = picks = 0
    for seed in range(50):
        bag = ShuffleBag(random.Random(seed))
        for i in range(12):
            bag.add(i, "Album Artist" if i < 4 else f"other{i}")
        seq = ["album" if t < 4 else t for t in (bag.next() for _ in range(60))]
        back_to_back += sum(a == b == "album" for a, b in zip(seq, seq[1:]))
        picks += len(seq)
    assert back_to_back / picks < 0.02


def test_newcomers_join_the_current_cycle_and_removed_tracks_leave():
    bag = ShuffleBag(random.Random(3))
    for i in range(5):
        bag.add(i, "")
    bag.next()
    bag.add(99, "")
    bag.remove(0)
    rest = [bag.next() for _ in range(5)]
    assert 99 in rest and 0 not in rest
    assert bag.next() is not None


def test_empty_bag():
    assert ShuffleBag().next() is None


def test_clean_meta():
    p = Path("x.webm")
    assert clean_meta("Artist - Song (Official Video)", "ArtistVEVO", p, True) == ("Song", "Artist")
    assert clean_meta("Song [Official Audio]", "Band - Topic", p, True) == ("Song", "Band")
    assert clean_meta("Live - at home", "Real Artist", p, False) == ("Live - at home", "Real Artist")
    assert clean_meta("", "", Path("my_song.mp3"), False) == ("my song", "")


def test_scan_picks_up_files_and_skips_bad_and_duplicate(tmp_path, tone):
    music = tmp_path / "music"
    (music / "sub").mkdir(parents=True)
    tone(music / "a.mp3", 40, 440, "Alpha", "One")
    tone(music / "sub" / "b.ogg", 40, 550, "Beta", "Two", noise=True)
    tone(music / "short.mp3", 5, 660, "Short", "Three")
    tone(music / "again.mp3", 40, 770, "alpha", "ONE")          # same song, different file
    (music / "notes.mp3").write_text("not audio")
    os.utime(music / "notes.mp3", (0, 0))
    lib = Library(tmp_path / "t.db", music)
    assert lib.scan() == 2
    assert {t["title"] for t in lib.list()} == {"Alpha", "Beta"}
    assert lib.counts() == {"ready": 2, "bad": 2, "dup": 1}
    picks = {lib.next_track().title for _ in range(2)}
    assert picks == {"Alpha", "Beta"}
    t = lib.next_track()
    assert t.gain_db is not None and t.duration > 39

    (music / "a.mp3").unlink()
    lib.scan()
    assert {t["title"] for t in lib.list()} == {"Beta"}


def test_remove_deletes_contributed_files_only(tmp_path, tone):
    music = tmp_path / "music"
    (music / "added").mkdir(parents=True)
    tone(music / "mine.mp3", 40, 440, "Mine", "Op")
    tone(music / "added" / "theirs.mp3", 40, 550, "Theirs", "Guest")
    lib = Library(tmp_path / "t.db", music)
    lib.scan()
    ids = {t["title"]: t["id"] for t in lib.list()}
    lib.remove(ids["Mine"])
    lib.remove(ids["Theirs"])
    assert (music / "mine.mp3").exists() and not (music / "added" / "theirs.mp3").exists()
    assert lib.list() == []
    lib.scan()                                                    # removed stays removed
    assert lib.list() == []


def test_add_file_reports_the_track_it_stands_for(tmp_path, tone):
    music = tmp_path / "music"
    (music / ".yt").mkdir(parents=True)
    lib = Library(tmp_path / "t.db", music)
    first = tone(music / ".yt" / "abcdefghijk.mp3", 40, 440, "Song", "Band")
    status, tid = lib.add_file(first)
    assert status == "ready" and lib.get(tid).title == "Song"
    copy = tone(music / ".yt" / "zyxwvutsrqp.mp3", 40, 440, "Song", "Band")
    assert lib.add_file(copy) == ("dup", tid)                    # a copy points at the original
    junk = music / "junk.mp3"
    junk.write_text("nope")
    assert lib.add_file(junk) == ("bad", None)
    assert lib.resolve_download("abcdefghijk") == tid
    assert lib.resolve_download("zyxwvutsrqp") == tid
    assert lib.resolve_download("nothinghere") is None


def test_a_requested_song_uses_up_its_turn():
    bag = ShuffleBag(random.Random(4))
    for i in range(4):
        bag.add(i, f"a{i}")
    bag.next()
    target = bag.bag[0]                       # what the shuffle would have played next
    bag.played(target)
    assert target not in [bag.next() for _ in range(2)]


def test_search_finds_songs_by_any_words(tmp_path, tone):
    music = tmp_path / "music"
    music.mkdir()
    tone(music / "a.mp3", 40, 440, "Ghadavaiya Mare Thakorji", "Aditya Gadhvi")
    tone(music / "b.mp3", 40, 550, "He Odhaaji", "Aditya Gadhvi")
    tone(music / "c.mp3", 40, 660, "Morning Tone", "Sine Quartet")
    lib = Library(tmp_path / "t.db", music)
    lib.scan()
    assert [t["title"] for t in lib.search("he odh")] == ["He Odhaaji"]
    assert {t["title"] for t in lib.search("aditya")} == {"Ghadavaiya Mare Thakorji", "He Odhaaji"}
    assert [t["title"] for t in lib.search("GADHVI thakor")] == ["Ghadavaiya Mare Thakorji"]
    assert lib.search("zzz") == [] and lib.search("  ") == []
