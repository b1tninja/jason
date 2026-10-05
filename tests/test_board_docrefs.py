"""The board group's loaders return document references (docs/console/doc-component.md): a board item's evidence
strings, a decision brief's sources (the agenda plan's candidates), and Ask's and the Scratchpad's sources. Each
reference resolves; nothing carries an absolute path or a raw /api/file URL. Everything here is made up."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import types
from datetime import date
from pathlib import Path

import pytest

from jason.approvals.evidence import resolve

DRIVE_ID = "1ExampleDriveFile01"
ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
EVIDENCE = [
    "library: Minutes/open minutes.pdf",          # a library path
    "Drive: Example Rules",                       # one Drive file by that name
    "data/governing/Example Declaration.pdf",     # a file on disk, placed
    "CIV 4920(a)",                                # a citation
    "jason board --sheet",                        # a command
    "PayHOA: request 12",                         # text
]


def _no_raw(value) -> None:
    """No absolute path and no /api/file URL anywhere in a loader's answer."""
    if isinstance(value, str):
        assert not ABSOLUTE.match(value), value
        assert "/api/file" not in value, value
    elif isinstance(value, dict):
        for v in value.values():
            _no_raw(v)
    elif isinstance(value, list):
        for v in value:
            _no_raw(v)


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A made-up data folder: a recorded PDF, a Drive copy with its listing, and a library file."""
    from jason.tasks.library import SCHEMA

    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "payhoa.db"))
    (tmp_path / "governing").mkdir()
    (tmp_path / "governing" / "Example Declaration.pdf").write_bytes(b"%PDF-1.4 example")
    copies = tmp_path / "drive" / "copies"
    copies.mkdir(parents=True)
    (copies / f"{DRIVE_ID}.pdf").write_bytes(b"%PDF-1.4 copy")
    (copies / f"{DRIVE_ID}.json").write_text(json.dumps({
        "readAt": "2099-01-02T00:00:00+00:00", "modifiedTime": "2099-01-01T00:00:00+00:00", "name": "Example Rules",
        "mimeType": "application/vnd.google-apps.document"}), encoding="utf-8")
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"syncedAt": "2099-01-05T00:00:00+00:00", "files": [
        {"id": DRIVE_ID, "name": "Example Rules", "path": "Board/Rules/Example Rules", "modified": "2099-01-01T00:00:00+00:00",
         "mimeType": "application/vnd.google-apps.document"}]}), encoding="utf-8")
    db = tmp_path / "library" / "library.db"
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        conn.execute(SCHEMA)
        conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, "
                     "evidence, confidence, classified_at, sha256) VALUES ('abc1234', 'payhoa', 'Minutes/open minutes.pdf', "
                     "'open minutes.pdf', 'minutes', 'meetings', 'minutes', 'name', '2099-01', 0, '', 1.0, '', 'aaa')")
    conn.close()
    lib = tmp_path / "library" / "files" / "Minutes"
    lib.mkdir(parents=True)
    (lib / "open minutes.pdf").write_bytes(b"%PDF-1.4 lib")
    return tmp_path


def _assert_entries(entries, root: Path) -> list[str]:
    """Each entry is a reference that resolves, a command, or text; the kinds in order."""
    kinds = []
    for e in entries:
        if "address" in e:
            got = resolve(e["address"], data_dir=root)
            if e.get("source") == "Statutes on disk":       # the citation row takes it; no statutes are on this disk
                assert got["kind"] == "citation", e["address"]
            else:
                assert got["found"], e["address"]
            assert e.get("level"), e                    # the inline rule needs the server's level
            kinds.append(e["address"])
        else:
            kinds.append("command" if "command" in e else "text")
    _no_raw(entries)
    return kinds


# --- board items -----------------------------------------------------------------------------------------------------

def test_board_items_carry_evidence_refs_beside_the_strings(data):
    from jason.community.board_items import BoardItem, ItemCategory
    from jason.tasks.board_items import upsert
    from jason.web import sources

    upsert(data, [BoardItem("example-item", title="A matter", summary="s", ask="Decide it.", category=ItemCategory.FINANCE,
                            evidence=tuple(EVIDENCE))], today=date(2099, 1, 1))
    out = sources.board_items({})
    item = out["items"][0]
    assert item["evidence"] == EVIDENCE                 # the strings stay for the other callers
    kinds = _assert_entries(item["evidenceRefs"], data)
    assert kinds == ["library:abc1234", f"drive:{DRIVE_ID}", "file:governing/Example Declaration.pdf", "CIV 4920(a)",
                     "command", "text"]
    assert item["evidenceRefs"][4] == {"command": "jason board --sheet"}
    assert item["evidenceRefs"][2]["level"] == "P0" and item["evidenceRefs"][3]["level"] == "P0"
    _no_raw(out)

    saved = sources.set_board_item("example-item", {"status": "proposed"})   # the board's write answers the same refs
    assert saved["status"] == "proposed" and _assert_entries(saved["evidenceRefs"], data) == kinds


# --- the decision brief's sources --------------------------------------------------------------------------------------

def test_agenda_plan_candidates_carry_evidence_refs(data, monkeypatch):
    from jason.web import sources
    from jason.web.extra.agenda_plan import agenda_plan

    item = {"id": "example-item", "title": "A matter", "ask": "Decide it", "agendaSession": "open session", "authority": "",
            "priority": "high", "evidence": EVIDENCE}
    meeting = {"found": True, "date": "2099-10-21", "today": "2099-10-03", "noticeBy": "2099-10-17", "executiveNoticeBy": "2099-10-19",
               "directors": [], "decisions": [], "items": [item], "packetMarkdown": "", "commands": {}, "caveats": []}
    monkeypatch.setattr(sources, "meeting", lambda args, **_: meeting)
    out = agenda_plan({})
    c = out["candidates"][0]
    assert c["evidence"] == EVIDENCE
    assert _assert_entries(c["evidenceRefs"], data)[:4] == ["library:abc1234", f"drive:{DRIVE_ID}",
                                                            "file:governing/Example Declaration.pdf", "CIV 4920(a)"]


# --- Ask and the Scratchpad ------------------------------------------------------------------------------------------

@pytest.fixture
def dock(data, monkeypatch):
    """The dock loader against a fake county module whose library search answers rows with their ids."""
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county")}
    fake = types.ModuleType("jason.mcp.county")
    fake._data_dir = lambda d=None: data
    fake.association_calendar = lambda: {"obligations": [], "caveats": []}
    fake.records_inventory = lambda: {"records": [{"record": "minutes", "citation": "CIV 5200(a)(8)", "folders": ["Minutes"], "files": 1, "newest": "", "gap": ""}]}

    def library_search(**kw):
        return {"found": True, "count": 1, "rows": [{"id": "abc1234", "path": "Minutes/open minutes.pdf", "kind": "minutes", "period": "2099-01"}]}
    fake.library_search = library_search
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = fake
    sys.modules["jason.mcp"], sys.modules["jason.mcp.county"] = pkg, fake
    from jason.web.extra import dock as mod

    monkeypatch.setattr(mod, "_today", lambda: date(2099, 10, 3))
    monkeypatch.setattr(mod, "_q_next_meeting", lambda: {"answer": "The next board meeting is 2099-10-21.", "sources": ["meeting()", "CIV 4920"]})
    try:
        yield mod
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_ask_sources_are_refs_and_keep_the_library_id(dock, data):
    ask = dock.dock({"part": "ask"})
    by_q = {c["question"]: c for c in ask["common"]}
    meeting = by_q["When is the next board meeting?"]
    assert meeting["sources"] == ["meeting()", "CIV 4920"]
    assert meeting["sourceRefs"][0] == {"command": "meeting()"}
    assert _assert_entries(meeting["sourceRefs"], data) == ["command", "CIV 4920"]
    minutes = by_q["Where are the minutes?"]
    assert "Minutes/open minutes.pdf" in minutes["sources"]           # the library hit is a source now, by its id
    assert len(minutes["sourceRefs"]) == len(minutes["sources"])
    assert "library:abc1234" in _assert_entries(minutes["sourceRefs"], data)
    assert by_q["What is overdue?"]["sourceRefs"] == [{"command": "association_calendar()"}]

    hit = dock.write("", {"action": "ask", "by": "A Manager", "question": "open minutes words"})
    assert hit["routed"] is False and _assert_entries(hit["sourceRefs"], data) == ["command", "library:abc1234"]
    assert "not a finding" in hit["answer"]                            # the caveat stays where it was
    again = dock.dock({"part": "ask"})["asks"][0]                      # read back from the store: the path finds the id
    assert _assert_entries(again["sourceRefs"], data) == ["command", "library:abc1234"]
    _no_raw(again)


def test_scratchpad_sources_are_refs_one_for_one(dock, data):
    sources = ["CIV 5550", "library: Minutes/open minutes.pdf", "Drive: Example Rules", "a note about the roof", "meeting()"]
    n = dock.write("", {"action": "note_add", "by": "A Manager", "title": "Example", "sources": sources})
    assert _assert_entries(n["sourceRefs"], data) == ["CIV 5550", "library:abc1234", f"drive:{DRIVE_ID}", "text", "command"]
    notes = dock.dock({"part": "notes"})["notes"]
    assert notes[0]["sources"] == sources and len(notes[0]["sourceRefs"]) == len(sources)
    _no_raw(notes)
    assert dock.source_ref("Ask a@example.org") == {"text": dock.source_ref("Ask a@example.org")["text"]}
    assert "a@example.org" not in dock.source_ref("Ask a@example.org")["text"]
