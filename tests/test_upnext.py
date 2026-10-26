from creek.ingest import _Log
from creek.upnext import UpNext


def test_posts_play_in_order_one_per_person():
    q = UpNext()
    assert q.reserve("ana") is None
    assert q.add(10, "ana", "Song A") == 1
    assert "already have a song" in q.reserve("ana")         # one at a time
    assert q.reserve("ben") is None
    assert "already have a song" in q.reserve("ben")         # still downloading counts too
    assert q.add(20, "ben", "Song B") == 2
    assert q.titles() == ["Song A", "Song B"] and len(q) == 2
    assert q.pop().tid == 10
    assert q.reserve("ana") is None                          # ana's song played, she can post again
    assert q.pop().tid == 20 and q.pop() is None


def test_same_song_twice_keeps_its_place_and_frees_the_poster():
    q = UpNext()
    q.reserve("ana")
    q.add(10, "ana", "Song A")
    q.reserve("ben")
    assert q.add(10, "ben", "Song A") == 1                   # already coming up: no second copy
    assert len(q) == 1 and q.reserve("ben") is None


def test_queue_cap_and_release():
    q = UpNext(cap=2)
    assert q.reserve("a") is None and q.reserve("b") is None
    assert "full" in q.reserve("c")
    q.release("b")                                           # b's download failed
    assert q.reserve("c") is None


def test_remove_drops_a_song_from_the_queue():
    q = UpNext()
    q.add(1, "a", "x")
    q.add(2, "b", "y")
    q.remove(1)
    assert q.titles() == ["y"]


def test_ytdlp_log_tells_why_nothing_came_in():
    log = _Log()
    log.debug("[download] abc: Song has already been recorded in the archive")
    log.debug("[download] Long Mix does not pass filter (duration <= 900), skipping ..")
    log.error("ERROR: [youtube] abc: Video unavailable")
    assert log.archived and log.filtered and log.errors == ["abc: Video unavailable"]


def test_engine_uses_the_queue_it_is_given_even_when_empty():
    from creek.engine import Engine
    q = UpNext()
    assert Engine(library=None, room=None, on_mp3=print, on_pcm=print, upnext=q).upnext is q


def test_clear_empties_the_queue_and_stops_downloads_in_flight_from_landing():
    q = UpNext()
    q.reserve("ana")
    q.add(1, "ana", "Song A")
    q.reserve("ben")                                   # ben's song is still downloading
    assert q.clear() == 2
    assert q.titles() == [] and q.pop() is None
    assert q.add(2, "ben", "Song B") == 0              # finished after the clear: not queued
    assert len(q) == 0
    assert q.reserve("ben") is None and q.reserve("ana") is None   # both can post again
    assert q.add(3, "ana", "Song C") == 1              # new posts queue as normal
    assert q.clear() == 2                              # ana's queued + ben's reservation
    assert q.clear() == 0                              # nothing left


def test_ben_can_post_again_after_his_cleared_download_lands():
    q = UpNext()
    q.reserve("ben")
    q.clear()
    q.add(2, "ben", "late")
    assert q.reserve("ben") is None
