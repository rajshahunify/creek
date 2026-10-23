from creek.room import Room


def test_since_returns_only_new_reactions():
    r = Room()
    assert r.snapshot(-1, 0)["reactions"] == []
    assert r.react("a", 1, now=10)
    assert r.react("b", 2, now=10.1)
    snap = r.snapshot(0, 3)
    assert snap["reactions"] == [1, 2] and snap["seq"] == 2 and snap["here"] == 3
    assert r.snapshot(2, 3)["reactions"] == []
    assert r.snapshot(-1, 3)["reactions"] == []          # a fresh client doesn't replay history


def test_reactions_are_rate_limited_and_validated():
    r = Room()
    assert r.react("a", 0, now=0)
    assert not r.react("a", 0, now=1.0)                  # too soon for the same client
    assert r.react("a", 0, now=2.0)
    assert not r.react("a", 99, now=10)                  # not one of the six
    for i in range(5):
        r.react(f"c{i}", 0, now=20 + i * 0.01)
    assert not r.react("c9", 0, now=20.5)                # global cap: 5 a second


def test_paused_shows_in_snapshot():
    r = Room()
    assert r.snapshot(-1, 0)["paused"] is False
    r.set_paused(True)
    assert r.snapshot(-1, 0)["paused"] is True


def test_controls_are_rate_limited_but_open():
    r = Room()
    assert r.control("ana", "pause", now=0) is None
    assert "one press" in r.control("ana", "resume", now=0.5)          # same person, too quick
    assert r.control("ana", "resume", now=1.2) is None
    assert r.control("ben", "next", now=2) is None
    assert "just changed" in r.control("cara", "next", now=2.5)        # two people pressing next at once
    assert "just changed" in r.control("dan", "prev", now=3.0)
    assert r.control("dan", "next", now=4.1) is None
    assert r.control("eve", "pause", now=4.2) is None                  # pause isn't held up by a skip


def test_notices_count_up():
    r = Room()
    assert r.snapshot(-1, 0)["notice"] == [0, ""]
    assert r.announce("pause") == 1 and r.announce("next") == 2
    assert r.snapshot(-1, 0)["notice"] == [2, "next"]
