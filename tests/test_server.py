from fastapi.testclient import TestClient

from creek.server import app


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
