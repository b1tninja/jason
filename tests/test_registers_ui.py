"""The registers' local snapshots: the board's edits in the UI, logged and kept for the next sync."""

from __future__ import annotations

import json
import sys
import types

import pytest

from jason.community.registers import Column, Kind, Owner, Register
from jason.tasks import register_snapshots as store

REG = Register("widgets", "Widgets", "Widgets", (
    Column("id"),
    Column("title"),
    Column("amount", kind=Kind.MONEY),
    Column("status", owner=Owner.BOARD, kind=Kind.CHOICE, choices=("open", "done")),
    Column("done", owner=Owner.BOARD, kind=Kind.CHECKBOX),
    Column("due", owner=Owner.BOARD, kind=Kind.DATE),
    Column("count", owner=Owner.BOARD, kind=Kind.NUMBER),
    Column("fee", owner=Owner.BOARD, kind=Kind.MONEY),
    Column("notes", owner=Owner.BOARD),
), about="made up")

ROWS = [{"id": "w-1", "title": "First", "amount": 12.5, "status": "open", "notes": ""},
        {"id": "w-2", "title": "Second", "amount": 0, "status": "", "notes": "n"},
        {"id": "", "title": "no key: dropped"}]


def test_save_and_load(tmp_path):
    path = store.save_snapshot(tmp_path, REG, ROWS)
    assert path == tmp_path / "registers" / "widgets.json"
    snap = store.load_snapshot(tmp_path, "widgets")
    assert snap["key"] == "widgets" and snap["title"] == "Widgets" and snap["savedAt"] and snap["log"] == []
    assert [r["id"] for r in snap["rows"]] == ["w-1", "w-2"]
    assert snap["rows"][0]["done"] == "" and set(snap["rows"][0]) == set(REG.names)
    assert snap["columns"][3] == {"name": "status", "owner": "board", "kind": "choice", "choices": ["open", "done"]}
    assert store.load_all(tmp_path) == {"widgets": snap}
    assert store.load_snapshot(tmp_path, "nope") is None and store.load_all(tmp_path / "x") == {}
    with pytest.raises(ValueError):
        store.load_snapshot(tmp_path, "registers")  # the sync's own state file


def test_edit_refuses_jason_key_unknown_and_missing(tmp_path):
    store.save_snapshot(tmp_path, REG, ROWS)
    with pytest.raises(ValueError, match="jason's column"):
        store.edit(tmp_path, "widgets", "w-1", "title", "x")
    with pytest.raises(ValueError, match="the key"):
        store.edit(tmp_path, "widgets", "w-1", "id", "x")
    with pytest.raises(ValueError, match="not a column"):
        store.edit(tmp_path, "widgets", "w-1", "colour", "x")
    with pytest.raises(KeyError):
        store.edit(tmp_path, "widgets", "w-9", "notes", "x")
    with pytest.raises(KeyError):
        store.edit(tmp_path, "gadgets", "w-1", "notes", "x")
    snap = store.load_snapshot(tmp_path, "widgets")
    assert snap["log"] == [] and not any(r.get("pendingSync") for r in snap["rows"])


def test_edit_validates_kinds(tmp_path):
    store.save_snapshot(tmp_path, REG, ROWS)
    with pytest.raises(ValueError, match="one of open, done"):
        store.edit(tmp_path, "widgets", "w-1", "status", "closed")
    with pytest.raises(ValueError, match="checkbox"):
        store.edit(tmp_path, "widgets", "w-1", "done", "maybe")
    with pytest.raises(ValueError, match="date"):
        store.edit(tmp_path, "widgets", "w-1", "due", "soon")
    with pytest.raises(ValueError, match="number"):
        store.edit(tmp_path, "widgets", "w-1", "count", "many")
    with pytest.raises(ValueError, match="number"):
        store.edit(tmp_path, "widgets", "w-1", "fee", True)
    assert store.edit(tmp_path, "widgets", "w-1", "status", "done")["status"] == "done"
    assert store.edit(tmp_path, "widgets", "w-1", "done", "yes")["done"] is True
    assert store.edit(tmp_path, "widgets", "w-1", "done", False)["done"] is False
    assert store.edit(tmp_path, "widgets", "w-1", "due", "2026-10-20")["due"] == "2026-10-20"
    assert store.edit(tmp_path, "widgets", "w-1", "count", "3")["count"] == 3
    assert store.edit(tmp_path, "widgets", "w-1", "fee", "$1,250.50")["fee"] == 1250.5
    assert store.edit(tmp_path, "widgets", "w-1", "notes", "  a note ")["notes"] == "  a note "
    assert store.edit(tmp_path, "widgets", "w-1", "due", "")["due"] == ""


def test_edit_logs_and_marks_pending(tmp_path):
    store.save_snapshot(tmp_path, REG, ROWS)
    row = store.edit(tmp_path, "widgets", "w-1", "status", "done", by="Secretary")
    assert row["pendingSync"] is True and row["pendingColumns"] == ["status"]
    same = store.edit(tmp_path, "widgets", "w-1", "status", "done")  # no change, no log
    assert same["status"] == "done"
    store.edit(tmp_path, "widgets", "w-1", "notes", "call the vendor")
    snap = store.load_snapshot(tmp_path, "widgets")
    assert [(e["key"], e["column"], e["before"], e["after"], e["by"]) for e in snap["log"]] == [
        ("w-1", "status", "open", "done", "Secretary"), ("w-1", "notes", "", "call the vendor", "the board, in the UI")]
    assert all(set(e) == {"seen", "key", "column", "before", "after", "by"} for e in snap["log"])
    assert snap["rows"][0]["pendingColumns"] == ["notes", "status"] and "pendingSync" not in snap["rows"][1]
    assert store.pending_edits(tmp_path, REG) == {"w-1": {"status": "done", "notes": "call the vendor"}}
    store.edit(tmp_path, "widgets", "w-2", "done", True)
    assert store.pending_edits(tmp_path, REG)["w-2"] == {"done": "TRUE"}
    # the next sync saves what it saw: the log is kept, the pending marks are cleared
    store.save_snapshot(tmp_path, REG, [{"id": "w-1", "title": "First", "status": "done", "notes": "call the vendor"}])
    snap = store.load_snapshot(tmp_path, "widgets")
    assert len(snap["log"]) == 3 and snap["rows"] == [{**{n: "" for n in REG.names}, "id": "w-1", "title": "First", "status": "done", "notes": "call the vendor"}]
    assert store.pending_edits(tmp_path, REG) == {}
    assert store.pending(snap) == []


class _Sheets:
    """A Sheet with a header and one row; records every write."""

    def __init__(self, values):
        self.values = values
        self.writes = []

    def values_get(self, sid, rng):
        return {"values": self.values}

    def values_batch_update(self, sid, data):
        self.writes.append(("batch", data))

    def values_append(self, sid, rng, rows):
        self.writes.append(("append", rng, rows))


def test_sync_pushes_pending_edits_and_saves_a_snapshot(tmp_path):
    from jason.tasks import registers as task

    (tmp_path / "registers").mkdir()
    (tmp_path / "registers" / "registers.json").write_text(json.dumps({"widgets": {"spreadsheetId": "S1"}}))
    records = [{"id": "w-1", "title": "First", "amount": "", "status": "open", "done": "", "due": "", "count": "", "fee": "", "notes": ""}]
    applied = {}

    def apply(edits):
        applied.update(edits)
        for k, changes in edits.items():
            next(r for r in records if r["id"] == k).update(changes)

    sheets = _Sheets([list(REG.names), ["w-1", "First", "", "open", "", "", "", "", ""]])
    out = task.sync(sheets, REG, tmp_path, lambda: [dict(r) for r in records], apply)
    assert out["boardEdits"] == 0 and out["cellsWritten"] == 0 and sheets.writes == []
    snap = store.load_snapshot(tmp_path, "widgets")
    assert snap["rows"][0]["status"] == "open" and snap["log"] == []
    store.edit(tmp_path, "widgets", "w-1", "status", "done", by="Secretary")
    out = task.sync(sheets, REG, tmp_path, lambda: [dict(r) for r in records], apply)
    assert applied == {"w-1": {"status": "done"}} and out["boardEdits"] == 1 and out["logged"] == 1 and out["cellsWritten"] == 1
    kinds = [w[0] for w in sheets.writes]
    assert kinds == ["batch", "append"]
    assert sheets.writes[0][1] == [{"range": "Widgets!D2", "values": [["done"]]}]
    assert sheets.writes[1][1].startswith("Log!") and sheets.writes[1][2][0][1:] == ["w-1", "status", "open", "done", "the board, in the UI"]
    snap = store.load_snapshot(tmp_path, "widgets")
    assert snap["rows"][0]["status"] == "done" and "pendingSync" not in snap["rows"][0]
    assert [e["by"] for e in snap["log"]] == ["Secretary", "the board, in the UI"]
    assert snap["log"][1]["seen"] and snap["log"][1]["after"] == "done"


class _Community:
    def registers(self):
        return (REG, Register("empty", "Empty", "Empty", (Column("id"), Column("ok", owner=Owner.BOARD, kind=Kind.CHECKBOX)), confidential=True))


@pytest.fixture
def county(tmp_path, monkeypatch):
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    fake = types.ModuleType("jason.mcp.county")
    fake._data_dir = lambda _: tmp_path
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = fake
    sys.modules["jason.mcp"] = pkg
    sys.modules["jason.mcp.county"] = fake
    from jason.web import sources

    monkeypatch.setattr(sources, "_community", lambda: _Community())
    try:
        yield fake
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_loader_lists_and_tolerates_no_snapshots(county, tmp_path):
    from jason.web.extra.registers import registers, write
    from jason.web.sources import default_loaders

    assert "registers" in default_loaders()
    out = registers({})
    assert out["found"] is True and out["count"] == 2 and out["caveats"]
    first = out["registers"][0]
    assert first["key"] == "widgets" and first["snapshot"] is False and first["savedAt"] is None and first["rows"] == 0
    assert first["boardColumns"] == ["status", "done", "due", "count", "fee", "notes"] and first["columns"][0] == {"name": "id", "owner": "jason", "kind": "text", "choices": []}
    assert out["registers"][1]["confidential"] is True
    one = registers({"key": "widgets"})
    assert one["found"] is True and one["rows"] == [] and one["log"] == [] and one["savedAt"] is None and "no snapshot" in one["note"]
    assert one["keyColumn"] == "id" and one["syncCommand"] == "jason registers --sync widgets" and one["inSpecification"] is True
    assert registers({"key": "nope"})["found"] is False
    with pytest.raises(KeyError):
        write("widgets|w-1", {"column": "status", "value": "done"})


def test_loader_reads_the_snapshot_and_write_edits_it(county, tmp_path):
    from jason.web.extra.registers import registers, write

    store.save_snapshot(tmp_path, REG, ROWS)
    out = registers({})
    assert out["registers"][0]["snapshot"] is True and out["registers"][0]["savedAt"] and out["registers"][0]["rows"] == 2 and out["registers"][0]["pending"] == 0
    with pytest.raises(ValueError, match="<register>\\|<row key>"):
        write("widgets", {"column": "status", "value": "done"})
    with pytest.raises(ValueError, match="column"):
        write("widgets|w-1", {"value": "done"})
    with pytest.raises(ValueError, match="jason's"):
        write("widgets|w-1", {"column": "amount", "value": "1"})
    with pytest.raises(ValueError, match="one of"):
        write("widgets|w-1", {"column": "status", "value": "closed"})
    saved = write("widgets|w-1", {"column": "status", "value": "done", "by": "Secretary"})
    assert saved["key"] == "widgets" and saved["rowKey"] == "w-1" and saved["row"]["status"] == "done" and saved["row"]["pendingSync"] is True
    one = registers({"key": "widgets"})
    assert one["pending"] == 1 and one["rows"][0]["status"] == "done"
    assert one["log"][0]["before"] == "open" and one["log"][0]["after"] == "done" and one["log"][0]["by"] == "Secretary"
    assert registers({})["registers"][0]["pending"] == 1


def test_loader_without_registers_in_the_profile(county, monkeypatch):
    from jason.web import sources
    from jason.web.extra.registers import registers

    class Bare:
        pass

    monkeypatch.setattr(sources, "_community", lambda: Bare())
    out = registers({})
    assert out["found"] is True and out["count"] == 0 and out["registers"] == [] and "no registers" in out["note"]
    assert registers({"key": "widgets"})["found"] is False
