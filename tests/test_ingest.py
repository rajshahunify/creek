import pytest

from creek import ingest
from creek.ingest import Ingest, parse_links
from creek.library import Library


def test_parse_links():
    text = """# a comment
    https://www.youtube.com/watch?v=abc   # trailing note

    not a link
    https://youtube.com/playlist?list=PL1
    https://www.youtube.com/watch?v=abc
    """
    assert parse_links(text) == ["https://www.youtube.com/watch?v=abc", "https://youtube.com/playlist?list=PL1"]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    music = tmp_path / "music"
    (music / "added").mkdir(parents=True)
    monkeypatch.setattr(ingest, "MUSIC", music)
    lib = Library(tmp_path / "t.db", music)
    return Ingest(lib), lib, music, tmp_path


def test_upload_validation(setup, tone):
    ing, lib, music, tmp = setup
    bad = tmp / "x.bin"
    bad.write_bytes(b"hello")
    assert ing.add_upload(bad, "x.mp3") == (False, "that doesn't look like an audio file")
    assert not bad.exists()

    short = tone(tmp / "s.mp3", 5)
    ok, msg = ing.add_upload(short, "s.mp3")
    assert not ok and "long" in msg

    good = tone(tmp / "g.mp3", 40, 440, "Good", "Song")
    assert ing.add_upload(good, "../../etc/Good Song.mp3") == (True, "joined the stream")
    assert (music / "added" / "Good Song.mp3").exists()
    assert [t["title"] for t in lib.list()] == ["Good"]      # in rotation straight away
    assert lib.scan() == 0

    again = tone(tmp / "g2.mp3", 40, 440, "Good", "Song")
    assert ing.add_upload(again, "copy.mp3") == (False, "already in the stream")
    assert not (music / "added" / "copy.mp3").exists()


def test_youtube_id():
    from creek.ingest import youtube_id
    assert youtube_id("https://youtu.be/apchB_fhvWo?si=wEEl-w_DYq-FozcN") == "apchB_fhvWo"
    assert youtube_id("https://www.youtube.com/watch?list=PL1&v=dLWMMZJ8X7M&t=3") == "dLWMMZJ8X7M"
    assert youtube_id("https://youtube.com/shorts/abcdefghijk") == "abcdefghijk"
    assert youtube_id("https://www.youtube.com/playlist?list=PLabc") is None
    assert youtube_id("https://soundcloud.com/x/y") is None


def test_filtered_msg_names_the_length():
    from creek.ingest import filtered_msg
    assert filtered_msg([{"duration": 1145}], 30, 900) == "that one is 19:05 long - songs can be up to 15 min"
    assert filtered_msg([{"duration": 12}], 30, 900).startswith("that one is only 12 s")
    assert filtered_msg([{}, {}], 30, 900).startswith("songs need to be 30 s to 15 min")
