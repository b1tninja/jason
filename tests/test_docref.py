"""Document references (``jason.approvals.docref``): the light resolve a loader builds a ``DocRef`` with, the ``library:``
evidence row, and the mapping of older stores' free-text evidence strings. Everything here is made up."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from jason.approvals import docref
from jason.approvals.evidence import resolve
from jason.approvals.evidence_documents import documents_for, view

DRIVE_ID = "1ExampleDriveFile01"
SPEC_KEYS = {"address", "document", "name", "kind", "level", "source", "readAt", "size", "thumb", "original",
             "refreshable", "stale"}
ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")


def _library(root: Path, rows) -> None:
    from jason.tasks.library import SCHEMA

    db = root / "library" / "library.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(SCHEMA)
        for doc_id, path, confidential, sha in rows:
            conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, "
                         "confidential, evidence, confidence, classified_at, sha256) VALUES "
                         "(?, 'payhoa', ?, ?, 'minutes', 'meetings', 'minutes', 'name', '2099-01', ?, '', 1.0, '', ?)",
                         (doc_id, path, Path(path).name, int(confidential), sha))
    conn.close()


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A made-up data folder: a recorded PDF, a scanned letter, a Drive copy with its listing, two library files (one
    confidential), and a PayHOA request's kept read."""
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "payhoa.db"))
    (tmp_path / "governing").mkdir()
    (tmp_path / "governing" / "Example Declaration.pdf").write_bytes(b"%PDF-1.4 example")
    (tmp_path / "mail" / "100").mkdir(parents=True)
    (tmp_path / "mail" / "100" / "contents.pdf").write_bytes(b"%PDF-1.4 letter")
    (tmp_path / "scratch-unplaced").mkdir()
    (tmp_path / "scratch-unplaced" / "unplaced.md").write_text("# a report", encoding="utf-8")
    copies = tmp_path / "drive" / "copies"
    copies.mkdir(parents=True)
    (copies / f"{DRIVE_ID}.pdf").write_bytes(b"%PDF-1.4 copy")
    (copies / f"{DRIVE_ID}.png").write_bytes(b"\x89PNG")
    (copies / f"{DRIVE_ID}.json").write_text(json.dumps({
        "readAt": "2099-01-02T00:00:00+00:00", "modifiedTime": "2099-01-01T00:00:00+00:00", "name": "Example Rules",
        "mimeType": "application/vnd.google-apps.document", "webViewLink": f"https://docs.google.com/document/d/{DRIVE_ID}/edit"}),
        encoding="utf-8")
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"syncedAt": "2099-01-05T00:00:00+00:00", "files": [
        {"id": DRIVE_ID, "name": "Example Rules", "path": "Board/Rules/Example Rules", "modified": "2099-01-03T00:00:00+00:00",
         "mimeType": "application/vnd.google-apps.document"},
        {"id": "1SameNameFileA01", "name": "Twice.pdf", "path": "A/Twice.pdf", "mimeType": "application/pdf"},
        {"id": "1SameNameFileB01", "name": "Twice.pdf", "path": "B/Twice.pdf", "mimeType": "application/pdf"}]}),
        encoding="utf-8")
    _library(tmp_path, [("abc1234", "Minutes/open minutes.pdf", False, "aaa"),
                        ("def5678", "Legal/settlement.pdf", True, "bbb")])
    for rel in ("Minutes/open minutes.pdf", "Legal/settlement.pdf"):
        (tmp_path / "library" / "files" / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "library" / "files" / rel).write_bytes(b"%PDF-1.4 lib")
    (tmp_path / "library" / "text").mkdir()
    (tmp_path / "library" / "text" / "abc1234.txt").write_text("the minutes' words", encoding="utf-8")
    req = tmp_path / "payhoa-files" / "requests" / "42"
    req.mkdir(parents=True)
    (req / "submission.json").write_text(json.dumps({"readAt": "2099-01-04T00:00:00+00:00", "submission": {}}),
                                         encoding="utf-8")
    return tmp_path


def _no_absolute(value) -> None:
    if isinstance(value, str):
        assert not ABSOLUTE.match(value), value
    elif isinstance(value, dict):
        for v in value.values():
            _no_absolute(v)
    elif isinstance(value, list):
        for v in value:
            _no_absolute(v)


# --- the light resolve ------------------------------------------------------------------------------------------------

def test_a_file_ref_is_the_specs_shape_from_metadata_only(data):
    ref = docref.file_ref("data/governing/Example Declaration.pdf", data_dir=data)
    assert set(ref) <= SPEC_KEYS
    assert ref == {"address": "file:governing/Example Declaration.pdf", "document": "pdf", "name": "Example Declaration.pdf",
                   "kind": "pdf", "level": "P0", "source": "Recorded copy", "readAt": ref["readAt"],
                   "size": len(b"%PDF-1.4 example"), "thumb": True}
    assert resolve(ref["address"], data_dir=data)["found"]          # the address resolves


def test_a_scanned_letter_is_p2_and_named_as_a_scan(data):
    ref = docref.file_ref("mail/100/contents.pdf", data_dir=data)
    assert (ref["level"], ref["source"], ref["kind"]) == ("P2", "Scan", "pdf")


def test_a_missing_file_is_still_a_reference_without_a_copy(data):
    ref = docref.doc_ref("file:governing/not-there.pdf", data_dir=data)
    assert ref["kind"] == "pdf" and ref["level"] == "P0"
    assert "readAt" not in ref and "size" not in ref and "thumb" not in ref


@pytest.mark.parametrize("bad", ["C:\\Users\\x\\data\\governing\\a.pdf", "/home/x/data/a.pdf", "../outside.pdf", ""])
def test_a_file_ref_never_carries_an_absolute_path(data, bad):
    with pytest.raises(ValueError):
        docref.file_ref(bad, data_dir=data)


def test_a_drive_ref_reads_the_copys_record_and_the_listing(data):
    ref = docref.drive_ref(DRIVE_ID, data_dir=data)
    assert set(ref) <= SPEC_KEYS
    assert ref["kind"] == "pdf" and ref["document"] == "pdf" and ref["source"] == "Drive copy"
    assert ref["name"] == "Example Rules" and ref["thumb"] is True and ref["readAt"].startswith("2099-01-02")
    assert ref["original"] == {"url": f"https://docs.google.com/document/d/{DRIVE_ID}/edit", "label": "Open in Google"}
    assert ref["refreshable"]["system"] == "Google Drive"
    assert ref["stale"] == "Changed in Drive since this copy"   # the listing's modified is newer than the copy's


def test_a_drive_file_with_no_copy_takes_its_kind_from_its_type(data):
    ref = docref.drive_ref("1SameNameFileA01", data_dir=data)
    assert ref["kind"] == "pdf" and "readAt" not in ref and "thumb" not in ref


def test_a_library_ref_and_its_level(data):
    ref = docref.library_ref("abc1234", data_dir=data)
    assert (ref["address"], ref["name"], ref["kind"], ref["level"], ref["source"]) == (
        "library:abc1234", "open minutes.pdf", "pdf", "P0", "Library copy")
    assert docref.library_ref("def5678", data_dir=data)["level"] == "P3"


def test_a_submission_ref(data):
    ref = docref.submission_ref(42, data_dir=data)
    assert (ref["kind"], ref["level"], ref["source"], ref["document"]) == ("submission", "P2", "PayHOA", "submission")
    assert ref["refreshable"]["system"] == "PayHOA"


def test_a_citation_ref_reads_no_words():
    ref = docref.citation_ref("CIV 4920(a)")
    assert ref == {"address": "CIV 4920(a)", "document": "section", "name": "CIV 4920(a)", "kind": "text", "level": "P0",
                   "source": "Statutes on disk"}
    with pytest.raises(ValueError):
        docref.citation_ref("Invoice # 123 from a vendor")


def test_a_name_with_contact_details_is_masked(data):
    ref = docref.file_ref("mail/100/contents.pdf", name="Letter from a@example.org, 916-555-0100", data_dir=data)
    assert "a@example.org" not in ref["name"] and "555-0100" not in ref["name"]


def test_a_file_named_with_two_spaces_in_a_row_keeps_them(data):
    (data / "governing" / "Two  spaces.pdf").write_bytes(b"%PDF-1.4 two spaces")
    (data / "governing" / "Two spaces.pdf").write_bytes(b"%PDF-1.4 one")
    ref = docref.file_ref("governing/Two  spaces.pdf", data_dir=data)
    assert ref["address"] == "file:governing/Two  spaces.pdf" and ref["size"] == len(b"%PDF-1.4 two spaces")
    assert docref.doc_ref(" file:governing/Two  spaces.pdf ", data_dir=data)["address"] == ref["address"]
    assert resolve(ref["address"], data_dir=data)["documents"][0]["size"] == len(b"%PDF-1.4 two spaces")
    opened = view(ref["address"], "pdf", by="Jane Example", data_dir=data)
    assert opened.path.name == "Two  spaces.pdf"                    # the file the address names, not its one-space twin
    assert docref.doc_ref("CIV   4920(a)", data_dir=data)["address"] == "CIV 4920(a)"     # other addresses still fold


# --- audio ----------------------------------------------------------------------------------------------------------------

M4A = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00made-up audio"
MEETING = "meetings/2099-01-01-abc1234567"


def _recording(root: Path) -> str:
    """A made-up open board meeting's folder with its audio and transcript; the audio's path under the data folder."""
    folder = root / "zoom" / MEETING
    folder.mkdir(parents=True)
    (folder / "audio.m4a").write_bytes(M4A)
    (folder / "transcript.txt").write_text("[7:02 PM] Chair: I call the meeting to order.\n", encoding="utf-8")
    (root / "zoom" / "meetings.json").write_text(json.dumps({"meetings": [
        {"folder": MEETING, "kind": "board meeting", "confidential": False}]}), encoding="utf-8")
    return f"zoom/{MEETING}/audio.m4a"


@pytest.mark.parametrize("ext, mime", [(".m4a", "audio/mp4"), (".mp3", "audio/mpeg"), (".wav", "audio/wav"),
                                       (".ogg", "audio/ogg")])
def test_audio_is_a_kind_of_its_own(ext, mime):
    from jason.approvals.evidence_documents import content_type, kind_of

    assert kind_of(f"recording{ext}") == "audio" and content_type(f"recording{ext}") == mime


def test_an_audio_file_resolves_plays_and_names_its_transcript(data):
    rel = _recording(data)
    ref = docref.file_ref(rel, data_dir=data)
    assert (ref["address"], ref["kind"], ref["document"], ref["level"]) == (f"file:{rel}", "audio", "audio", "P1")
    assert "thumb" not in ref
    got = resolve(ref["address"], data_dir=data)
    assert [(d["id"], d["kind"]) for d in got["documents"]] == [("audio", "audio")]
    opened = view(ref["address"], "audio", by="Jane Example", data_dir=data)
    assert opened.answer["kind"] == "audio" and opened.path.name == "audio.m4a"
    transcript = opened.answer["transcript"]
    assert (transcript["address"], transcript["name"], transcript["kind"]) == (
        f"file:zoom/{MEETING}/transcript.txt", "Transcript", "text")
    (data / "zoom" / MEETING / "transcript.txt").unlink()
    assert "transcript" not in view(ref["address"], "audio", by="Jane Example", data_dir=data).answer


def test_the_document_route_plays_audio_inline_with_ranges(data, monkeypatch):
    import webclient
    from jason.web.app import create_app

    rel = _recording(data)
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: data)
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: data)
    dist = data / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html><head></head><body></body></html>", encoding="utf-8")
    app = create_app(dist, {}, approvals_live=None, sign_in=webclient.roster_sign_in())
    c = webclient.sign_in(webclient.client(app), "A Manager")
    r = c.post("/api/evidence/view", json={"address": f"file:{rel}", "document": "audio"})
    assert r.status_code == 200 and r.json["kind"] == "audio" and r.json["url"].startswith("/api/evidence/document/")
    assert r.json["transcript"]["address"] == f"file:zoom/{MEETING}/transcript.txt"
    whole = c.get(r.json["url"])
    assert whole.status_code == 200 and whole.data == M4A and whole.mimetype == "audio/mp4"
    assert whole.headers["Content-Disposition"].startswith("inline") and whole.headers["Accept-Ranges"] == "bytes"
    part = c.get(r.json["url"], headers={"Range": "bytes=4-7"})
    assert part.status_code == 206 and part.data == M4A[4:8] and part.headers["Content-Range"] == f"bytes 4-7/{len(M4A)}"


# --- the library: evidence row ------------------------------------------------------------------------------------------

def test_the_library_row_resolves_and_lists_its_documents(data):
    from tests.test_evidence import _validator

    got = resolve("library:abc1234", data_dir=data)
    _validator("evidence.schema.json").validate(got)
    assert got["found"] and got["kind"] == "library"
    assert got["sources"][0]["name"] == "Library copy"
    assert [d["id"] for d in got["documents"]] == ["library:abc1234", "library-text:abc1234"]
    _no_absolute(got)


def test_a_confidential_library_document_is_held_back_outside_the_private_view(data):
    shut = resolve("library:def5678", data_dir=data)
    assert shut["documents"] == [] and "private view" in shut["note"]
    opened = resolve("library:def5678", data_dir=data, private=True)
    assert [d.get("level") for d in opened["documents"]] == ["P3"]
    assert documents_for("library:def5678", data)[1] == []


def test_a_library_document_opens_as_a_logged_view(data):
    opened = view("library:abc1234", "library-text:abc1234", by="Jane Example", data_dir=data)
    assert opened.answer["text"] == "the minutes' words"
    assert (data / "evidence" / "views.jsonl").is_file()


def test_an_unknown_library_id_is_a_miss_with_the_command(data):
    got = resolve("library:nope000", data_dir=data)
    assert not got["found"] and "jason library" in got["note"]


def test_the_view_route_judges_a_library_document_by_its_flag(data, monkeypatch):
    from jason.web.access import Level
    from jason.web.approvals import evidence_level

    monkeypatch.setattr("jason.tasks.drive_copies.data_root", lambda: data)
    assert evidence_level("library:abc1234") is Level.P0
    assert evidence_level("library:def5678") is Level.P3


# --- older stores' free text ----------------------------------------------------------------------------------------

def test_refs_from_strings_maps_each_form_and_never_guesses(data):
    got = docref.refs_from_strings([
        "library: Minutes/open minutes.pdf",          # a library path
        "library:abc1234",                            # a library id
        "library: open minutes.pdf",                  # its file's name, once
        "library: the minutes about the roof",        # a description: text
        "Drive: Example Rules",                       # one file by that name
        "Drive: Rules/Example Rules",                 # its path's end, folder by folder
        "Drive: Twice.pdf",                           # two files by that name: text
        "Drive: Board",                               # a folder: text
        "data/governing/Example Declaration.pdf",     # placed, on disk
        "data/scratch-unplaced/unplaced.md",          # on disk, but no rule places it: text
        "data/governing/missing.pdf",                 # placed, not on disk: text
        "jason board --sheet",                        # a command
        "CIV 4920(a)",                                # a citation
        "PayHOA: request 12, request 13",             # text
        "drive:" + DRIVE_ID,                          # an address already
        "docs/console/README.md",                     # a repository path: text
        "Ask a@example.org",                          # text, masked
    ], data_dir=data)
    kinds = [r.get("address") or ("command" if "command" in r else "text") for r in got]
    assert kinds == ["library:abc1234", "library:abc1234", "library:abc1234", "text", f"drive:{DRIVE_ID}",
                     f"drive:{DRIVE_ID}", "text", "text", "file:governing/Example Declaration.pdf", "text", "text",
                     "command", "CIV 4920(a)", "text", f"drive:{DRIVE_ID}", "text", "text"]
    assert got[11] == {"command": "jason board --sheet"}
    assert "a@example.org" not in got[-1]["text"]
    for r in got:
        _no_absolute(r)
        if "address" in r:
            assert set(r) <= SPEC_KEYS
