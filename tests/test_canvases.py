import json

import pytest

from jason.tasks import canvases as store


def test_create_update_clip_roundtrip(tmp_path):
    c = store.create(tmp_path, "Reserve loan: restore by March", question="Was 5515 met?", duty="Money")
    assert c.key == "reserve-loan-restore-by-march" and c.status is store.CanvasStatus.RESEARCH
    again = store.create(tmp_path, "Reserve loan: restore by March")
    assert again.key == "reserve-loan-restore-by-march-2"
    c = store.update(tmp_path, c.key, notes="- notice found on the 2025-02 agenda", status="preparing",
                     checklist=[{"text": "find the resolution", "done": False}], links=[{"label": "agenda", "url": "https://x"}])
    assert c.status is store.CanvasStatus.PREPARING and c.history[-1].endswith("status research -> preparing")
    c = store.add_clip(tmp_path, c.key, source="reserve_transfers", text="2025-03-01 $10,000.00 outstanding", label="the loan", args={"year": 2025})
    loaded = store.load(tmp_path, c.key)
    assert loaded.clips[0].source == "reserve_transfers" and loaded.clips[0].args == {"year": 2025}
    assert loaded.notes.startswith("- notice") and loaded.checklist[0]["text"] == "find the resolution"
    assert {x.key for x in store.load_all(tmp_path)} == {c.key, again.key}
    assert json.loads((tmp_path / "canvases" / f"{c.key}.json").read_text())["status"] == "preparing"


def test_refusals(tmp_path):
    with pytest.raises(ValueError):
        store.create(tmp_path, "   ")
    c = store.create(tmp_path, "A topic")
    with pytest.raises(ValueError):
        store.update(tmp_path, c.key, clips=[])
    with pytest.raises(ValueError):
        store.update(tmp_path, c.key, links="not a list")
    with pytest.raises(ValueError):
        store.add_clip(tmp_path, c.key, source="x", text="  ")
    with pytest.raises(KeyError):
        store.load(tmp_path, "missing")
    with pytest.raises(KeyError):
        store.load(tmp_path, "../etc")


def test_api_canvas_routes(tmp_path, monkeypatch):
    from jason.web.app import create_app

    calls = []

    def writer(key, body):
        calls.append((key, body))
        if key == "missing":
            raise KeyError(key)
        if "bad" in body:
            raise ValueError("bad")
        return {"key": key or "new", **body}

    c = create_app(tmp_path, {}, board_writer=None, canvas_writer=writer, decision_writer=None).test_client()
    assert c.post("/api/canvases", json={"title": "T"}).json == {"key": "new", "title": "T"}
    assert c.post("/api/canvases/k", json={"notes": "n"}).json["notes"] == "n"
    assert c.post("/api/canvases/k", json={"clip": {"source": "s", "text": "t"}}).status_code == 200
    assert c.post("/api/canvases/missing", json={"notes": "n"}).status_code == 404
    assert c.post("/api/canvases/k", json={"bad": 1}).status_code == 400
    assert c.get("/api/health").json["writes"] == ["canvases"]


def test_attachments_are_validated(tmp_path):
    c = store.create(tmp_path, "Photos of the east bed")
    c = store.update(tmp_path, c.key, attachments=[{"kind": "image", "ref": "photos/east-bed.jpg", "title": "before"}, {"kind": "doc", "ref": "1AbCdEfGhIjKlMnOpQ", "title": ""}])
    assert [a["kind"] for a in store.load(tmp_path, c.key).attachments] == ["image", "doc"]
    with pytest.raises(ValueError):
        store.update(tmp_path, c.key, attachments=[{"kind": "video", "ref": "x"}])
    with pytest.raises(ValueError):
        store.update(tmp_path, c.key, attachments=[{"kind": "pdf", "ref": "  "}])


def test_local_file_route_serves_only_known_types_under_data(tmp_path, monkeypatch):
    import sys

    from jason.web.app import create_app

    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "secret.db").write_bytes(b"x")
    fake = type(sys)("jason.mcp.county"); fake._data_dir = lambda _: tmp_path
    monkeypatch.setitem(sys.modules, "jason.mcp.county", fake)
    c = create_app(tmp_path, {}, board_writer=None, canvas_writer=None, decision_writer=None).test_client()
    ok = c.get("/api/file?path=photos/a.png")
    assert ok.status_code == 200 and ok.headers["Content-Type"].startswith("image/png") and ok.headers["Content-Security-Policy"] == "sandbox"
    assert c.get("/api/file?path=secret.db").status_code == 404
    assert c.get("/api/file?path=../pyproject.toml").status_code == 404
    assert c.get("/api/file?path=").status_code == 404
    assert c.get("/api/file?path=photos").status_code == 404
