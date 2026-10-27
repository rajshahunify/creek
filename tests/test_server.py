from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from creek import server
from creek.library import Library
from creek.room import Room
from creek.server import app
from creek.upnext import UpNext


def test_station_only_commands_refuse_other_machines():
    # TestClient connects as "testclient" to "testserver": a different machine as far as the station can tell
    client = TestClient(app)
    for path in ("/op/pause", "/op/next", "/op/prev", "/op/play", "/op/skip", "/op/remove?id=1"):
        r = client.post(path)
        assert r.status_code == 403 and r.json()["detail"] == "only the station laptop can do that"


def test_op_routes_are_not_swallowed_by_the_catch_all():
    paths = [r.path for r in app.routes]
    assert paths.index("/op/{action}") > paths.index("/op/play")
    assert paths.index("/op/{action}") > paths.index("/op/remove")


class FakeEngine:
    """Just enough of the engine for the routes: it records what it was asked to do."""

    def __init__(self, track):
        self.current, self.playing = track, SimpleNamespace(via="shuffle")
        self.paused, self.position, self.history = False, 10.0, [track.id]
        self.asked = []

    def seek_to(self, sec):
        self.asked.append(("seek_to", sec))
        self.position = sec
        return True

    def seek(self, by):
        self.asked.append(("seek", by))

    def play_now(self, tid):
        self.asked.append(("play_now", tid))

    def skip(self):
        self.asked.append(("skip",))

    def shuffle_pick(self):
        return None


class FakeIngest:
    def __init__(self):
        self.searched = []

    def search_youtube(self, words, n=8):
        self.searched.append(words)
        return [{"vid": "aaaaaaaaaaa", "title": "Short one", "channel": "x", "duration": 200, "live": False,
                 "url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "thumb": ""},
                {"vid": "bbbbbbbbbbb", "title": "Long mix", "channel": "y", "duration": 3 * 3600, "live": False,
                 "url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "thumb": ""}]


@pytest.fixture
def client(tmp_path, tone):
    music = tmp_path / "music"
    music.mkdir()
    for i in range(4):
        tone(music / f"{i}.mp3", 40, 300 + 100 * i, f"Song {i}", f"Artist {i}")
    lib = Library(tmp_path / "t.db", music)
    lib.scan()
    tracks = [lib.get(t["id"]) for t in lib.list()]
    app.state.station = SimpleNamespace(room=Room(), upnext=UpNext(), library=lib, engine=FakeEngine(tracks[0]),
                                        ingest=FakeIngest(), here=2)
    yield TestClient(app), app.state.station, tracks
    del app.state.station


def test_browsers_get_the_web_player_and_curl_gets_the_instructions(client):
    c, _, _ = client
    assert "curl -s http://" in c.get("/", headers={"accept": "*/*"}).text
    html = c.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert html.headers["content-type"].startswith("text/html")


def test_the_queue_can_be_rearranged_by_anyone(client):
    c, st, tracks = client
    for t in tracks[1:]:
        assert c.post(f"/post?track={t.id}&id=p{t.id}").status_code == 200
    queue = lambda: [x["tid"] for x in c.get("/state?id=p2").json()["queue"]]
    a, b, d = (t.id for t in tracks[1:])
    assert queue() == [a, b, d]
    assert c.post(f"/queue/move?tid={d}&to=1&id=ana").json()["place"] == 1
    assert queue() == [d, a, b]
    assert c.post("/queue/move?place=3&to=2&id=ben").status_code == 200       # by place, as the terminal does
    assert queue() == [d, b, a]
    assert c.post(f"/queue/remove?tid={b}&id=cara").status_code == 200
    assert queue() == [d, a]
    assert c.post(f"/queue/remove?tid={b}&id=cara").status_code == 404
    state = c.get(f"/state?id=p{a}").json()
    assert [x["mine"] for x in state["queue"]] == [False, True] and "poster" not in state["queue"][0]
    assert c.get("/now").json()["notice"][1] == "remove"


def test_a_song_can_be_posted_into_the_middle(client):
    c, _, tracks = client
    c.post(f"/post?track={tracks[1].id}&id=a")
    c.post(f"/post?track={tracks[2].id}&id=b")
    assert c.post(f"/post?track={tracks[3].id}&id=c&at=2").json()["msg"] == "queued - plays after 1 other"
    assert [x["tid"] for x in c.get("/state").json()["queue"]] == [tracks[1].id, tracks[3].id, tracks[2].id]


def test_play_now_crossfades_for_everyone_and_counts_as_a_jump(client):
    c, st, tracks = client
    assert c.post(f"/post?track={tracks[2].id}&id=ana&now=1").json()["msg"].startswith("playing now")
    assert st.engine.asked == [("play_now", tracks[2].id)]
    assert c.post("/ctl/next?id=ben").status_code == 429                      # two jumps at once: one
    assert c.post(f"/post?track={tracks[0].id}&id=cara&now=1").status_code == 429


def test_the_progress_bar_jumps_to_a_time(client):
    c, st, _ = client
    r = c.post("/ctl/seek?to=30&id=ana").json()
    assert st.engine.asked == [("seek_to", 30.0)] and r["pos"] == 30
    assert c.post("/ctl/seek?id=ben").status_code == 400                      # to where?
    st.engine.paused = True
    assert c.post("/ctl/seek?to=5&id=cara").status_code == 409


def test_youtube_search_says_what_can_go_in(client):
    c, st, _ = client
    hits = c.get("/yt/search?q=some+words&id=ana").json()
    assert [h["why_not"] for h in hits] == ["", "longer than 30 min"]
    assert hits[0]["on_station"] is None
    assert c.get("/yt/search?q=more&id=ana").status_code == 429               # one a second
    assert c.get("/yt/search?q=+&id=ben").json() == []


def test_news_lists_what_a_listener_hasnt_seen(client):
    c, _, _ = client
    everything = c.get("/news").json()
    assert everything["version"] == everything["news"][-1]["n"]
    assert c.get(f"/news?seen={everything['version']}").json()["news"] == []


def test_with_a_key_everything_but_the_front_page_needs_it(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(server, "KEY", "s3cret-key")
    assert c.get("/state").status_code == 401
    assert c.post("/ctl/next?id=a").status_code == 401
    assert "needs its key" in c.get("/", headers={"accept": "*/*"}).text
    assert c.get("/state?key=s3cret-key").status_code == 200
    assert c.get("/state", headers={"x-creek-key": "s3cret-key"}).status_code == 200
    assert c.post("/key?key=wrong").status_code == 401
    assert c.post("/key?key=s3cret-key").status_code == 200          # the web player's cookie from here on
    assert c.get("/state").status_code == 200
    assert "?key=s3cret-key" in c.get("/").text                        # the join lines carry the key
    assert 'KEY = "s3cret-key"' in c.get("/client.py").text
