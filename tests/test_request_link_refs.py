"""The Requests and links group's document references (docs/console/doc-component.md): PayHOA requests beside their
email carry their submission's reference, and a canvas's attachments and clips carry theirs. Each reference resolves;
none carries a URL into data/ or an absolute path. Everything here is made up."""

from __future__ import annotations

import json
import re
import sqlite3

import pytest

from jason.approvals.evidence import resolve

DRIVE_ID = "1ExampleDriveFile01"
ABSOLUTE = re.compile(r"(?:^|\")(?:[A-Za-z]:[\\/]|/(?:Users|home|tmp)/)")


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A made-up data folder: a PayHOA catalog with one request, a Drive listing, a photo, a recorded PDF, and audio."""
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "payhoa.db"))
    with sqlite3.connect(tmp_path / "payhoa.db") as conn:
        conn.execute("CREATE TABLE requests (id INTEGER, form_name TEXT, unit_id INTEGER, status TEXT, created_at TEXT, "
                     "synced_at TEXT, raw_json TEXT)")
        conn.execute("INSERT INTO requests VALUES (4242, 'Maintenance', 7, 'open', '2099-01-01', '2099-01-02', '{}')")
    conn.close()
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"syncedAt": "2099-01-05T00:00:00+00:00", "files": [
        {"id": DRIVE_ID, "name": "Example Rules", "path": "Board/Example Rules", "mimeType": "application/vnd.google-apps.document"}]}),
        encoding="utf-8")
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "east-bed.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "governing").mkdir()
    (tmp_path / "governing" / "Example Declaration.pdf").write_bytes(b"%PDF-1.4 example")
    (tmp_path / "meetings").mkdir()
    (tmp_path / "meetings" / "board.m4a").write_bytes(b"\x00\x00")
    return tmp_path


def _clean(value) -> None:
    text = json.dumps(value)
    assert "/api/file" not in text and not ABSOLUTE.search(text), text


def test_request_rows_carry_their_submission(data):
    from jason.tasks.request_links import with_refs

    rows = with_refs([{"id": 4242, "form": "Maintenance", "unit": "7", "title": "Leak under the sink"},
                      {"id": "x", "title": "not a request"}], data)
    doc = rows[0]["doc"]
    assert doc["address"] == "payhoa:submission:4242" and doc["kind"] == "submission" and doc["level"] == "P2"
    assert doc["name"] == "Leak under the sink" and rows[0]["title"] == "Leak under the sink"     # the old fields stay
    assert "doc" not in rows[1]
    assert resolve(doc["address"], data_dir=data)["found"]
    _clean(rows)


def test_canvas_attachments_and_clips_carry_references(data):
    from jason.tasks import canvases as store

    c = store.create(data, "Example topic")
    attachments = [
        {"kind": "doc", "ref": f"https://docs.google.com/document/d/{DRIVE_ID}/edit", "title": "Rules"},
        {"kind": "image", "ref": "photos/east-bed.jpg", "title": "East bed"},
        {"kind": "pdf", "ref": "data/governing/Example Declaration.pdf"},
        {"kind": "audio", "ref": "meetings/board.m4a", "title": "Board meeting"},
        {"kind": "doc", "ref": "https://docs.google.com/document/d/e/2PACX-example/pub", "title": "Published"},
        {"kind": "image", "ref": "https://photos.example/a.png"},
        {"kind": "url", "ref": "https://example.com/page"},
        {"kind": "calendar", "ref": "abc@group.calendar.google.com"},
    ]
    store.update(data, c.key, attachments=attachments)
    store.add_clip(data, c.key, source="file:governing/Example Declaration.pdf", text="the recital")
    store.add_clip(data, c.key, source="data/photos/east-bed.jpg", text="the bed")
    store.add_clip(data, c.key, source="reserve_transfers", text="a row")
    store.add_clip(data, c.key, source="https://example.com/x", text="a page")
    out = store.with_refs(store.encode(store.load(data, c.key)), data)
    docs = [a.get("doc") for a in out["attachments"]]
    assert [d["address"] if d else None for d in docs] == [
        f"drive:{DRIVE_ID}", "file:photos/east-bed.jpg", "file:governing/Example Declaration.pdf",
        None, None, None, None, None]                 # audio stays the player until the evidence shows audio
    assert docs[0]["original"]["label"] == "Open in Google" and docs[1]["level"] == "P1" and docs[2]["source"] == "Recorded copy"
    assert docs[1]["name"] == "East bed"
    clips = [k.get("doc", {}).get("address") for k in out["clips"]]
    assert clips == ["file:governing/Example Declaration.pdf", "file:photos/east-bed.jpg", None, None]
    for d in [x for x in docs if x] + [k["doc"] for k in out["clips"] if "doc" in k]:
        assert resolve(d["address"], data_dir=data)["found"], d["address"]
    _clean(out)
    # A reference is built on each read, never kept: an attachment sent back with its doc is stored without it.
    store.update(data, c.key, attachments=out["attachments"][:2])
    kept = json.loads((data / "canvases" / f"{c.key}.json").read_text(encoding="utf-8"))
    assert [set(a) for a in kept["attachments"]] == [{"kind", "ref", "title"}, {"kind", "ref", "title"}]


def test_the_canvas_loader_and_writes_answer_references(data, monkeypatch):
    import jason.mcp.county as county
    from jason.web import sources

    monkeypatch.setattr(county, "_data_dir", lambda data_dir=None: data)
    made = sources.write_canvas("", {"title": "Loader topic"})
    wrote = sources.write_canvas(made["key"], {"attachments": [{"kind": "image", "ref": "photos/east-bed.jpg", "title": "Bed"}]})
    assert wrote["attachments"][0]["doc"]["address"] == "file:photos/east-bed.jpg"
    clipped = sources.write_canvas(made["key"], {"clip": {"source": "file:governing/Example Declaration.pdf", "text": "t"}})
    assert clipped["clips"][0]["doc"]["address"] == "file:governing/Example Declaration.pdf"
    loaded = sources.canvases({"key": made["key"]})["canvas"]
    assert loaded["attachments"][0]["doc"]["level"] == "P1"
    _clean(loaded)
