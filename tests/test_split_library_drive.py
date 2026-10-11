"""The splitter's two new ways in: the library explorer (a listing, a search, filters, paging, masking) and a Drive file as a source
(read once, read-only, refused before anything is kept). The record-intake phase-2 world: a fake Drive that fails the test on any
write, made-up PDFs, a data folder of its own. Nothing here reaches Google, Keeper, PayHOA, or a county."""

import base64
import json
import os
import sqlite3
from pathlib import Path

import pytest

import webclient
from jason import limits
from jason.community import split_gold
from jason.tasks import library_browse as lb
from jason.tasks import split_session as ss

from test_record_intake_phase2 import FILE_A, FILE_DOC, FILE_C, FOLDER, FakeDrive, make_pdf, world  # noqa: F401  (a fixture)

BY = "A Manager"


def _add(root: Path, ident: str, name: str, *, kind="minutes", source="payhoa", path=None, pages=1, text="some words", confidential=0,
         sha="", mtime=None):
    path = path or f"Board/{name}"
    target = root / "library" / "files" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(make_pdf([f"page {i} of {name}" for i in range(pages)]))
    if mtime:
        os.utime(target, (mtime, mtime))
    if text:
        (root / "library" / "text").mkdir(parents=True, exist_ok=True)
        (root / "library" / "text" / f"{ident}.txt").write_text(text, encoding="utf-8")
    with sqlite3.connect(root / "library" / "library.db") as conn:
        conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence, sha256)"
                     " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (ident, source, path, name, kind, "x", "", "NAME", "2099-06", confidential, "", sha))
    return target


@pytest.fixture
def lib(world):  # noqa: F811
    root = world.root
    jan, jun = 4070000000, 4085000000                       # 2098-12-ish and 2099-06-ish, in seconds
    _add(root, "101", "Alpha Minutes.pdf", kind="minutes", pages=2, mtime=jun)
    _add(root, "102", "Beta Budget.pdf", kind="budget", source="ingest", pages=5, text="", mtime=jan)
    _add(root, "103", "Gamma Combined Scan.pdf", kind="", source="payhoa", pages=9, text="", mtime=jun + 86400 * 40)
    _add(root, "104", "Alpha Minutes copy.pdf", kind="minutes", pages=2, sha="same", path="Email/a.pdf", mtime=jun)
    _add(root, "105", "Alpha Minutes again.pdf", kind="minutes", pages=2, sha="same", path="Board/b.pdf", mtime=jun)
    _add(root, "106", "Delta Statement.pdf", kind="bank_statement", pages=1, confidential=1, mtime=jun)
    (root / "library" / "files" / "Board" / "Beta Budget.pdf").touch()
    with sqlite3.connect(root / "library" / "library.db") as conn:      # a row whose file this machine does not hold
        conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence)"
                     " VALUES ('107','payhoa','Gone/Missing.pdf','Missing.pdf','minutes','x','','NAME','2099-01',0,'')")
    return world


def _names(out):
    return [f["name"] for f in out["files"]]


# --- the listing -------------------------------------------------------------------------------------------------------------------

def test_the_listing_gives_each_distinct_pdf_once_with_its_facts_and_masks_the_confidential(lib):
    out = lb.files(lib.root, size=100)
    assert out["found"] and out["total"] == 7 and out["counts"]["all"] == 7          # the two copies of one hash are one row
    by = {f["name"]: f for f in out["files"]}
    alpha = by["Alpha Minutes.pdf"]
    assert alpha["id"] == "101" and alpha["kind"] == "minutes" and alpha["sourceLabel"] == "PayHOA" and alpha["pages"] == 2
    assert alpha["hasText"] is True and alpha["size"] > 0 and alpha["modified"].startswith("2099") and alpha["draft"] is None
    assert by["Beta Budget.pdf"]["sourceLabel"] == "Taken in by hand" and by["Beta Budget.pdf"]["hasText"] is False
    copy = next(f for f in out["files"] if f["name"] == "Alpha Minutes copy.pdf")
    assert copy["copies"] == 2
    held = next(f for f in out["files"] if f["held"])
    assert held["name"] == "a confidential file (kind: bank statement)" and held["id"] == "" and held["openable"] is False
    assert "Delta" not in json.dumps(out)
    gone = by["Missing.pdf"]
    assert gone["onDisk"] is False and gone["openable"] is False and "does not hold" in gone["why"]
    shown = lb.files(lib.root, private=True, size=100)
    assert any(f["name"] == "Delta Statement.pdf" and f["id"] == "106" for f in shown["files"])


def test_a_search_by_name_never_matches_a_confidential_file_outside_the_private_view(lib):
    assert _names(lb.files(lib.root, q="delta")) == []
    assert _names(lb.files(lib.root, q="delta", private=True)) == ["Delta Statement.pdf"]
    assert _names(lb.files(lib.root, q="ALPHA", sort="name", order="asc")) == ["Alpha Minutes copy.pdf", "Alpha Minutes.pdf"]
    assert lb.files(lib.root, q="x" * 101)["found"] is False


def test_filters_counts_sorting_and_paging(lib):
    out = lb.files(lib.root, kind="minutes")
    assert out["total"] == 3 and out["counts"]["kinds"]["minutes"] == 3        # kind chips count over the other filters
    assert out["counts"]["kinds"]["budget"] == 1 and out["counts"]["sources"]["payhoa"] >= 3
    assert lb.files(lib.root, source="ingest")["total"] == 1
    assert lb.files(lib.root, kind="(none)")["total"] == 1                       # a file the library has not classified
    assert lb.files(lib.root, has_text="no")["total"] == 4 and lb.files(lib.root, has_text="yes")["total"] == 3
    assert _names(lb.files(lib.root, since="2099-06-01", until="2099-06-30", sort="name", order="asc", size=100))[0] == "Alpha Minutes copy.pdf"
    assert lb.files(lib.root, since="2099-07-01")["total"] == 1                  # the scan modified forty days later
    big = lb.files(lib.root, min_pages=5, sort="pages")
    assert _names(big) == ["Gamma Combined Scan.pdf", "Beta Budget.pdf"] and big["uncounted"] == 0
    assert [f["pages"] for f in lb.files(lib.root, sort="pages", order="asc", size=100)["files"]][:2] == [1, 2]
    first = lb.files(lib.root, size=2, sort="name", order="asc")
    assert len(first["files"]) == 2 and first["next"] == "2"
    second = lb.files(lib.root, size=2, sort="name", order="asc", page=first["next"])
    assert not set(_names(first)) & set(_names(second))
    assert len(lb.files(lib.root, size=5000)["files"]) <= lb.MAX_PAGE
    assert lb.files(lib.root, kind="nothing")["empty"].startswith("Nothing in the library matches")


def test_a_draft_on_a_library_file_is_shown_and_filterable(lib):
    opened = ss.open_session({"kind": "library", "id": "102"}, by=BY, community=lib.community, root=lib.root, profile="example")
    sid = opened["session"]["id"]
    out = lb.files(lib.root, draft="yes")
    assert _names(out) == ["Beta Budget.pdf"] and out["files"][0]["draft"] == {"id": sid, "status": "draft"}
    assert out["counts"]["withDraft"] == 1 and lb.files(lib.root, draft="no")["total"] == 6


def test_without_a_library_the_answer_says_how_to_make_one(world, tmp_path):
    out = lb.files(tmp_path / "empty")
    assert out["found"] is False and "jason library" in out["why"]


def _app(world, monkeypatch, fake=None):
    from jason.web.app import create_app
    from jason.web.extra import drive_choose as web_drive
    from jason.web.extra import split as web_split
    from jason.web.sources import default_loaders

    monkeypatch.setattr(web_split, "_community", lambda: world.community)
    monkeypatch.setattr(web_split, "_root", lambda: world.root)
    monkeypatch.setattr(web_drive, "_community", lambda: world.community)
    monkeypatch.setattr(web_drive, "_root", lambda: world.root)
    monkeypatch.setattr(web_drive, "_open", lambda: fake or world.drive)
    return create_app(world.tmp, default_loaders(), sign_in=webclient.roster_sign_in(required=False))


def _signed(world, monkeypatch, **kw):
    c = webclient.client(_app(world, monkeypatch, **kw))
    webclient.sign_in(c, BY)
    return c


def test_the_routes_search_by_post_never_by_url_and_the_owner_view_is_refused(lib, monkeypatch):
    c = _signed(lib, monkeypatch)
    got = c.get("/api/library-files?kind=minutes&sort=name&order=asc&size=2")
    assert got.status_code == 200 and got.json["total"] == 3 and len(got.json["files"]) == 2 and got.json["next"] == "2"
    assert c.get("/api/library-files?q=alpha").status_code == 400
    posted = c.post("/api/write/library/files", json={"q": "alpha", "kind": "minutes", "minPages": 2})
    assert posted.status_code == 200 and posted.json["total"] == 2
    assert c.post("/api/write/library/other", json={}).status_code == 404
    assert c.get("/api/library-files?view=owner").status_code == 403
    assert c.post("/api/write/library/files?view=owner", json={}).status_code == 403
    assert lib.drive.calls == [] and lib.drive.writes == []                       # disk only
    out = webclient.client(_app(lib, monkeypatch), token=False).post("/api/write/library/files", json={})
    assert out.status_code == 403
    signed_out = webclient.client(_app(lib, monkeypatch))
    assert signed_out.get("/api/library-files").status_code == 401


def test_a_confidential_file_does_not_leak_into_the_listing_route(lib, monkeypatch):
    c = _signed(lib, monkeypatch)
    text = json.dumps(c.get("/api/library-files?size=100").json)
    assert "Delta" not in text and "bank statement" in text
    assert "Delta" not in json.dumps(c.post("/api/write/library/files", json={"q": "delta"}).json)


# --- Drive as a source -------------------------------------------------------------------------------------------------------------

def _drive_pdf(world, pages=3):
    data = make_pdf([f"Drive page {i}" for i in range(pages)])
    ident = "1DriveScanAbCdEfGhIjKlMn"
    world.drive.files[ident] = {"meta": FakeDrive.meta(ident, "Secret Drive Scan.pdf", size=len(data), parents=(FOLDER,)), "data": data}
    return ident


def test_a_dry_run_of_a_drive_file_reads_its_metadata_only_and_keeps_nothing(lib):
    ident = _drive_pdf(lib)
    out = ss.open_session({"kind": "drive", "id": ident}, by=BY, dry_run=True, community=lib.community, root=lib.root, profile="example",
                          drive=lib.drive)
    assert out["dryRun"] is True and out["would"]["source"] == "drive" and out["would"]["pages"] is None and out["would"]["size"] > 0
    assert lib.drive.downloads == 0 and lib.drive.writes == [] and not (lib.root / "split").exists()


def test_opening_a_drive_file_reads_it_once_keeps_a_copy_and_leaves_no_name_or_id_behind(lib, caplog):
    ident = _drive_pdf(lib)
    link = f"https://drive.google.com/file/d/{ident}/view"
    with caplog.at_level("DEBUG"):
        out = ss.open_session({"kind": "drive", "id": link}, by=BY, community=lib.community, root=lib.root, profile="example", drive=lib.drive)
    assert out["ok"] and out["resumed"] is False and out["session"]["source"]["pages"] == 3
    assert lib.drive.downloads == 1 and lib.drive.writes == []
    session = ss.load(lib.root, out["session"]["id"])
    assert session.source.kind == "drive" and session.source.ref == "" and ss.source_file(lib.root, session.source.sha256).is_file()
    stores = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in lib.root.rglob("*.json*") if p.is_file())
    stores += "".join(p.read_text(encoding="utf-8", errors="ignore") for p in lib.spec.rglob("*") if p.is_file())
    assert ident not in stores and "Secret Drive Scan" not in stores
    assert ident not in caplog.text and "Secret Drive Scan" not in caplog.text
    again = ss.open_session({"kind": "drive", "id": ident}, by=BY, community=lib.community, root=lib.root, profile="example", drive=lib.drive)
    assert again["resumed"] is True and again["session"]["id"] == out["session"]["id"]


def test_a_drive_file_that_cannot_be_split_is_refused_before_a_byte_moves(lib):
    drive = lib.drive
    sheet = "1SheetFileAbCdEfGhIjKl"
    refusals = {
        FOLDER: "folder",
        sheet: "PDF",
        FILE_DOC: "PDF",
        "1NotThereAbCdEfGhIjKlMn": "cannot open that",
    }
    for ident, word in refusals.items():
        with pytest.raises(ValueError) as e:
            ss.open_session({"kind": "drive", "id": ident}, by=BY, community=lib.community, root=lib.root, profile="example", drive=drive)
        assert word in str(e.value) and "Nothing was opened" in str(e.value)
        assert ident not in str(e.value)
    with pytest.raises(ValueError, match="not a Drive link"):
        ss.open_session({"kind": "drive", "id": "https://example.org/x"}, by=BY, community=lib.community, root=lib.root, profile="example", drive=drive)
    assert drive.downloads == 0 and drive.exports == 0 and not (lib.root / "split").exists()


def test_a_drive_file_over_the_fetch_limit_or_the_page_limit_leaves_nothing_behind(lib, monkeypatch):
    ident = _drive_pdf(lib, pages=60)
    monkeypatch.setenv("JASON_LIMIT_FETCH_MAX_BYTES", "1MB")
    lib.drive.files[ident]["meta"]["size"] = str(2 * 1024 * 1024)
    with pytest.raises(limits.LimitReached) as e:
        ss.open_session({"kind": "drive", "id": ident}, by=BY, community=lib.community, root=lib.root, profile="example", drive=lib.drive)
    assert "fetch" in str(e.value).lower() or "largest" in str(e.value)
    assert lib.drive.downloads == 0
    monkeypatch.delenv("JASON_LIMIT_FETCH_MAX_BYTES")
    lib.drive.files[ident]["meta"]["size"] = str(len(lib.drive.files[ident]["data"]))
    monkeypatch.setenv("JASON_LIMIT_SPLIT_MAX_PAGES", "50")
    with pytest.raises(limits.LimitReached):
        ss.open_session({"kind": "drive", "id": ident}, by=BY, community=lib.community, root=lib.root, profile="example", drive=lib.drive)
    assert lib.drive.downloads == 1                                                  # read once, then refused
    assert not list((lib.root / "split" / "sources").rglob("*.pdf")) and not (lib.root / "split" / "sessions").exists()


def test_the_temp_drive_guard_speaks_before_the_download(lib, monkeypatch):
    from jason import storage

    ident = _drive_pdf(lib)

    def short(dest, need, **kw):
        raise storage.DriveShort("The drive is nearly full; nothing was copied.")

    monkeypatch.setattr(storage, "require_room", short)
    with pytest.raises(storage.DriveShort):
        ss.open_session({"kind": "drive", "id": ident}, by=BY, community=lib.community, root=lib.root, profile="example", drive=lib.drive)
    assert lib.drive.downloads == 0


def test_the_console_opens_a_drive_file_and_says_so_when_drive_is_not_connected(lib, monkeypatch):
    from jason.tasks import drive_choose as dc
    from jason.web.extra import drive_choose as web_drive

    ident = _drive_pdf(lib)
    c = _signed(lib, monkeypatch)
    dry = c.post("/api/write/split/new", json={"act": "open", "by": BY, "dryRun": True, "ref": {"kind": "drive", "id": ident}})
    assert dry.status_code == 200 and dry.json["dryRun"] is True and lib.drive.downloads == 0 and lib.drive.closed is True
    made = c.post("/api/write/split/new", json={"act": "open", "by": BY, "ref": {"kind": "drive", "id": ident}})
    assert made.status_code == 200 and made.json["session"]["source"]["pages"] == 3 and lib.drive.downloads == 1
    assert "Secret Drive Scan" not in json.dumps(made.json) and ident not in json.dumps(made.json)

    def refuse():
        raise dc.DriveUnavailable(dc.NOT_SIGNED_IN, "jason google sign-in --name drive --interactive")

    monkeypatch.setattr(web_drive, "_open", refuse)
    off = c.post("/api/write/split/new", json={"act": "open", "by": BY, "dryRun": True, "ref": {"kind": "drive", "id": ident}})
    assert off.status_code == 200 and off.json["driveConnected"] is False and off.json["command"] and "no Google sign-in" in off.json["why"]
    owner = c.post("/api/write/split/new?view=owner", json={"act": "open", "by": BY, "ref": {"kind": "drive", "id": ident}})
    assert owner.status_code == 403
