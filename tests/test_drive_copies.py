"""jason's copies of Drive files (``jason.tasks.drive_copies``), the ``drive:<id>`` evidence row, its refresh, and the
thumbnail route: a Doc to PDF, text, and thumbnail; a Sheet to PDF and CSV; a stored PDF reused from disk without a
download; restrictions and the 10 MB limit refused; ``changed`` true and false; the audit line; the route's 401, 403,
404, and 200; a missing Google sign-in naming its command.

A fake Drive client, made-up ids and names, and tmp data folders only: nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import webclient

from jason.approvals import evidence
from jason.google.errors import GoogleAuthRequired, GoogleExportTooLarge, GoogleHttpError
from jason.tasks import drive_copies
from jason.tasks.drive_copies import DOC, PDF, SHEET, SLIDES, CopyRefused

DOC_ID, SHEET_ID, PDF_ID, SECRET_ID, SLIDES_ID = "1FakeDocId0001", "1FakeSheet0002", "1FakePdf000003", \
    "1FakeSecret004", "1FakeSlides005"
PNG = b"\x89PNG\r\n\x1a\n" + b"thumb"
PDF_BYTES = b"%PDF-1.4\nfake\n"


class FakeDrive:
    """Drive as ``drive_copies.export`` reads it: metadata, exports, media, and a thumbnail link, by file id. Records
    every call; ``refuse`` lists export types it answers 400; ``too_large`` the files whose export is over the limit."""

    def __init__(self, files: dict[str, dict], *, refuse: tuple[str, ...] = (), too_large: tuple[str, ...] = ()):
        self.files, self.refuse, self.too_large, self.calls = files, refuse, too_large, []

    def file_metadata(self, file_id, fields):
        self.calls.append(("meta", file_id))
        assert "capabilities" in fields and "thumbnailLink" in fields and "downloadRestrictions" in fields
        return {k: v for k, v in self.files[file_id].items() if k not in ("exports", "media")}

    def export_file(self, file_id, mime):
        self.calls.append(("export", file_id, mime))
        if file_id in self.too_large:
            raise GoogleExportTooLarge("HTTP 403 exporting", status=403, reason="exportSizeLimitExceeded")
        if mime in self.refuse:
            raise GoogleHttpError("HTTP 400 exporting", status=400, reason="badRequest")
        return self.files[file_id]["exports"][mime]

    def download_bytes(self, file_id):
        self.calls.append(("media", file_id))
        return self.files[file_id]["media"]

    def fetch_link(self, url):
        self.calls.append(("thumb", url))
        return PNG, "image/png"


def _files() -> dict[str, dict]:
    thumb = "https://lh3.googleusercontent.com/fake-thumb"
    return {
        DOC_ID: {"id": DOC_ID, "name": "Notice of Hearing", "mimeType": DOC, "modifiedTime": "2026-10-01T10:00:00Z",
                 "webViewLink": f"https://docs.google.com/document/d/{DOC_ID}/edit", "thumbnailLink": thumb,
                 "capabilities": {"canDownload": True, "canCopy": True},
                 "exports": {PDF: PDF_BYTES, "text/markdown": b"# Notice of Hearing\n", "text/plain": b"Notice\n"}},
        SHEET_ID: {"id": SHEET_ID, "name": "Budget 2099", "mimeType": SHEET, "modifiedTime": "2026-09-01T00:00:00Z",
                   "capabilities": {"canDownload": True},
                   "exports": {PDF: PDF_BYTES, "text/csv": b"line,amount\nwater,6120\n"}},
        SLIDES_ID: {"id": SLIDES_ID, "name": "Annual meeting", "mimeType": SLIDES, "exports": {PDF: PDF_BYTES}},
        PDF_ID: {"id": PDF_ID, "name": "Declaration.pdf", "mimeType": PDF, "size": "14", "md5Checksum": "abc123",
                 "modifiedTime": "2026-08-01T00:00:00Z", "media": PDF_BYTES},
    }


@pytest.fixture
def root(tmp_path):
    """A made-up data folder: the Drive holdings (the PDF already on disk in the library; one file confidential; the
    Doc under a Drive root's path rule) and Drive's listing."""
    (tmp_path / "library" / "files" / "Governing").mkdir(parents=True)
    (tmp_path / "library" / "files" / "Governing" / "declaration.pdf").write_bytes(PDF_BYTES)
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "holdings.json").write_text(json.dumps({"rows": [
        {"id": DOC_ID, "name": "Notice of Hearing", "pathRule": True, "confidential": False, "elsewhere": []},
        {"id": PDF_ID, "name": "Declaration.pdf", "pathRule": True, "confidential": False,
         "elsewhere": [{"channel": "PayHOA library", "where": "Governing/declaration.pdf"}]},
        {"id": SECRET_ID, "name": "Counsel letter", "pathRule": True, "confidential": True, "elsewhere": []},
        {"id": SHEET_ID, "name": "Budget 2099", "pathRule": False, "confidential": False, "elsewhere": []}]}),
        encoding="utf-8")
    _listing(tmp_path, "2026-10-01T10:00:00Z")
    return tmp_path


def _listing(root: Path, doc_modified: str, synced_at: str = "2026-10-02T08:00:00+00:00") -> None:
    (root / "drive" / "files.json").write_text(json.dumps({"syncedAt": synced_at, "files": [
        {"id": DOC_ID, "name": "Notice of Hearing", "mimeType": DOC, "modified": doc_modified,
         "link": f"https://docs.google.com/document/d/{DOC_ID}/edit"},
        {"id": SHEET_ID, "name": "Budget 2099", "mimeType": SHEET, "modified": "2026-09-01T00:00:00Z", "link": ""}]}),
        encoding="utf-8")


def _copies(root: Path) -> set[str]:
    folder = root / "drive" / "copies"
    return {p.name for p in folder.iterdir()} if folder.is_dir() else set()


# --- the store -----------------------------------------------------------------------------------------------------------

def test_a_doc_is_kept_as_pdf_markdown_and_its_thumbnail(root):
    drive = FakeDrive(_files())
    record = drive_copies.export(drive, root, DOC_ID, via="console refresh by A Manager", by="A Manager")
    assert _copies(root) == {f"{DOC_ID}.pdf", f"{DOC_ID}.md", f"{DOC_ID}.png", f"{DOC_ID}.json"}
    folder = root / "drive" / "copies"
    assert (folder / f"{DOC_ID}.pdf").read_bytes() == PDF_BYTES
    assert (folder / f"{DOC_ID}.md").read_text(encoding="utf-8") == "# Notice of Hearing\n"
    assert (folder / f"{DOC_ID}.png").read_bytes() == PNG
    kept = json.loads((folder / f"{DOC_ID}.json").read_text(encoding="utf-8"))
    assert kept == record
    assert {k: kept[k] for k in ("via", "by", "modifiedTime", "mimeType", "name", "textMime")} == {
        "via": "console refresh by A Manager", "by": "A Manager", "modifiedTime": "2026-10-01T10:00:00Z",
        "mimeType": DOC, "name": "Notice of Hearing", "textMime": "text/markdown"}
    assert kept["readAt"] and kept["sizes"] == {"pdf": len(PDF_BYTES), "md": 20, "png": len(PNG)}
    assert ("thumb", "https://lh3.googleusercontent.com/fake-thumb") in drive.calls
    assert not any(c[0] == "media" for c in drive.calls)                             # a Doc is exported, never media
    assert not list(folder.glob("*.tmp"))


def test_a_doc_google_will_not_give_as_markdown_is_kept_as_plain_text(root):
    record = drive_copies.export(FakeDrive(_files(), refuse=("text/markdown",)), root, DOC_ID)
    assert record["textMime"] == "text/plain"
    assert (root / "drive" / "copies" / f"{DOC_ID}.md").read_text(encoding="utf-8") == "Notice\n"


def test_a_sheet_is_kept_as_pdf_and_its_first_sheet_as_csv_and_slides_as_pdf(root):
    drive = FakeDrive(_files())
    drive_copies.export(drive, root, SHEET_ID)
    drive_copies.export(drive, root, SLIDES_ID)
    assert _copies(root) == {f"{SHEET_ID}.pdf", f"{SHEET_ID}.csv", f"{SHEET_ID}.json",
                             f"{SLIDES_ID}.pdf", f"{SLIDES_ID}.json"}                 # no thumbnail link: none kept
    assert ("export", SHEET_ID, "text/csv") in drive.calls


def test_a_stored_pdf_already_on_disk_is_reused_without_a_download(root):
    drive = FakeDrive(_files())
    record = drive_copies.export(drive, root, PDF_ID, by="A Manager")
    assert record["reused"] == "library/files/Governing/declaration.pdf" and record["md5"] == "abc123"
    assert not any(c[0] == "media" for c in drive.calls) and _copies(root) == {f"{PDF_ID}.json"}
    from jason.approvals.evidence_documents import drive_documents

    [doc] = drive_documents(root, PDF_ID)
    assert (doc.id, doc.kind, doc.path) == ("pdf", "pdf", root / "library/files/Governing/declaration.pdf")


def test_a_stored_pdf_not_on_disk_is_downloaded(root, tmp_path):
    (root / "library" / "files" / "Governing" / "declaration.pdf").unlink()
    drive = FakeDrive(_files())
    drive_copies.export(drive, root, PDF_ID)
    assert ("media", PDF_ID) in drive.calls
    assert (root / "drive" / "copies" / f"{PDF_ID}.pdf").read_bytes() == PDF_BYTES


@pytest.mark.parametrize("limit, words", [
    ({"capabilities": {"canDownload": False}}, "turned off downloading"),
    ({"copyRequiresWriterPermission": True}, "turned off copying, printing, and downloading"),
    ({"downloadRestrictions": {"effectiveDownloadRestrictionWithContext": {"restrictedForReaders": True}}},
     "restricts downloading"),
])
def test_a_file_that_forbids_copies_is_refused_and_nothing_is_kept(root, limit, words):
    files = _files()
    files[DOC_ID].update(limit)
    drive = FakeDrive(files)
    with pytest.raises(CopyRefused) as refused:
        drive_copies.export(drive, root, DOC_ID)
    assert words in str(refused.value) and "jason keeps no copy; open it in Google" in str(refused.value)
    assert _copies(root) == set() and [c[0] for c in drive.calls] == ["meta"]


def test_a_doc_over_googles_export_limit_is_refused(root):
    with pytest.raises(CopyRefused) as refused:
        drive_copies.export(FakeDrive(_files(), too_large=(DOC_ID,)), root, DOC_ID)
    assert str(refused.value) == "Notice of Hearing is too large to export (Google exports up to 10 MB); open it in Google."
    assert _copies(root) == set()


def test_a_fresh_copy_removes_what_the_last_one_left(root):
    folder = root / "drive" / "copies"
    folder.mkdir(parents=True)
    (folder / f"{DOC_ID}.csv").write_text("old", encoding="utf-8")
    drive_copies.export(FakeDrive(_files()), root, DOC_ID)
    assert f"{DOC_ID}.csv" not in _copies(root)


def test_an_id_that_names_a_path_is_refused(root):
    with pytest.raises(ValueError):
        drive_copies.export(FakeDrive(_files()), root, "../../secrets")


def test_the_drive_client_says_an_export_over_the_limit():
    from jason.google.drive import GoogleDrive

    def answer(request):
        if request.url.path.endswith("/export"):
            return httpx.Response(403, json={"error": {"code": 403, "message": "This file is too large to be exported.",
                                                       "errors": [{"reason": "exportSizeLimitExceeded"}]}})
        return httpx.Response(200, content=b"x")

    drive = GoogleDrive("token", http=httpx.Client(transport=httpx.MockTransport(answer)))
    with pytest.raises(GoogleExportTooLarge) as err:
        drive.export_file(DOC_ID, PDF)
    assert err.value.status == 403 and err.value.reason == "exportSizeLimitExceeded"
    with pytest.raises(Exception, match="not a Google link"):
        drive.fetch_link("https://example.com/steal")                               # the token stays with Google


# --- levels ---------------------------------------------------------------------------------------------------------------

def test_levels_by_the_holdings_and_the_templates(root, monkeypatch):
    from jason.web.access import Level, level_of_path

    monkeypatch.setattr(drive_copies, "_template_ids", lambda r: frozenset({SHEET_ID}))
    assert drive_copies.level_of(root, SECRET_ID) == "P3"
    assert drive_copies.level_of(root, SHEET_ID) == "P0"                             # a template, though unruled
    assert drive_copies.level_of(root, DOC_ID) == "P0"                               # under a path rule
    assert drive_copies.level_of(root, "1FakeUnknown9") == "P2"                       # unplaced: closed
    assert level_of_path(f"drive/copies/{SECRET_ID}.png", root) is Level.P3
    assert level_of_path(f"drive/copies/{DOC_ID}.pdf", root) is Level.P0
    assert level_of_path("drive/copies/1FakeUnknown9.pdf", root) is Level.P2


# --- the evidence row -----------------------------------------------------------------------------------------------------

def test_the_drive_address_before_a_copy_says_how_to_read_it(root):
    out = evidence.resolve(f"drive:{DOC_ID}", data_dir=root)
    assert out["found"] and out["kind"] == "drive" and out["label"] == "Notice of Hearing"
    assert [s["name"] for s in out["sources"]] == ["Drive catalog"] and out["documents"] == []
    assert "no copy from Drive yet" in out["note"] and out["changed"] is None
    assert out["refreshable"] == {"system": "Google Drive", "what": "Export this file again from Drive"}
    assert out["link"] == f"https://docs.google.com/document/d/{DOC_ID}/edit"


def test_the_drive_address_with_a_copy_unchanged_in_drive(root):
    drive_copies.export(FakeDrive(_files()), root, DOC_ID, via="console refresh by A Manager", by="A Manager")
    out = evidence.resolve(f"drive:{DOC_ID}", data_dir=root)
    copy, listed = out["sources"]
    assert (copy["name"], listed["name"]) == ("Copy from Drive", "Drive catalog")
    assert copy["readAt"] and {f["name"]: f["value"] for f in copy["fields"]}["Modified in Drive"] == \
        "2026-10-01T10:00:00Z"
    assert {f["name"]: f["value"] for f in copy["fields"]}["Read by"] == "A Manager"
    assert listed["readAt"] == "2026-10-02T08:00:00+00:00"
    assert out["changed"] is False and out["changedNote"].startswith("Unchanged in Drive since this copy")
    assert [(d["id"], d["kind"]) for d in out["documents"]] == [("pdf", "pdf"), ("text", "text")]
    assert drive_copies.CAVEAT in out["caveats"]


def test_the_drive_address_changed_in_drive_since_the_copy(root):
    drive_copies.export(FakeDrive(_files()), root, DOC_ID)
    _listing(root, "2026-10-02T07:00:00Z")
    out = evidence.resolve(f"drive:{DOC_ID}", data_dir=root)
    assert out["changed"] is True and out["changedNote"].startswith("Changed in Drive since this copy")


def test_a_sheets_documents_are_its_pdf_and_csv(root):
    drive_copies.export(FakeDrive(_files()), root, SHEET_ID)
    out = evidence.resolve(f"drive:{SHEET_ID}", data_dir=root)
    assert [(d["id"], d["kind"]) for d in out["documents"]] == [("pdf", "pdf"), ("csv", "text")]
    assert out["link"] == f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"


def test_a_confidential_file_is_held_back_outside_the_private_view(root):
    files = _files()
    files[SECRET_ID] = {**files[DOC_ID], "id": SECRET_ID, "name": "Counsel letter"}
    drive_copies.export(FakeDrive(files), root, SECRET_ID)
    plain = evidence.resolve(f"drive:{SECRET_ID}", data_dir=root)
    assert plain["sources"] == [] and plain["documents"] == [] and "held back" in plain["note"]
    shown = evidence.resolve(f"drive:{SECRET_ID}", data_dir=root, private=True)
    assert {d["level"] for d in shown["documents"]} == {"P3"}


def test_viewing_the_pdf_and_the_text_is_logged(root):
    from jason.approvals.evidence_documents import view

    drive_copies.export(FakeDrive(_files()), root, DOC_ID)
    pdf = view(f"drive:{DOC_ID}", "pdf", by="A Manager", data_dir=root)
    assert pdf.answer["kind"] == "pdf" and pdf.path == (root / "drive" / "copies" / f"{DOC_ID}.pdf").resolve()
    text = view(f"drive:{DOC_ID}", "text", by="A Manager", data_dir=root)
    assert text.answer["text"] == "# Notice of Hearing\n"
    lines = (root / "evidence" / "views.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["document"] for x in lines] == ["pdf", "text"]


# --- refresh --------------------------------------------------------------------------------------------------------------

def _factory(drive, seen: list | None = None):
    @contextmanager
    def factory():
        if seen is not None:
            seen.append("signed in")
        yield SimpleNamespace(client=drive, org_id=0)
    return factory


def _refreshes(root: Path) -> list[dict]:
    log = root / "evidence" / "refreshes.jsonl"
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []


def test_refreshing_a_drive_address_exports_it_and_logs_one_line(root):
    out = evidence.refresh(f"drive:{DOC_ID}", by="A Manager", client_factory=_factory(FakeDrive(_files())),
                           data_dir=root)
    assert out["refreshed"]["system"] == "Google Drive" and out["refreshed"]["by"] == "A Manager"
    assert [s["name"] for s in out["sources"]] == ["Copy from Drive", "Drive catalog"]
    [line] = _refreshes(root)
    assert {k: line[k] for k in ("by", "address", "system", "ok", "error")} == {
        "by": "A Manager", "address": f"drive:{DOC_ID}", "system": "Google Drive", "ok": True, "error": ""}
    assert drive_copies.read_record(root, DOC_ID)["by"] == "A Manager"


def test_a_refused_copy_is_said_and_logged(root):
    files = _files()
    files[DOC_ID]["copyRequiresWriterPermission"] = True
    with pytest.raises(evidence.RefreshFailed) as failed:
        evidence.refresh(f"drive:{DOC_ID}", by="A Manager", client_factory=_factory(FakeDrive(files)), data_dir=root)
    assert "jason keeps no copy" in str(failed.value)
    assert _refreshes(root)[-1]["ok"] is False and "jason keeps no copy" in _refreshes(root)[-1]["error"]


def test_a_missing_google_sign_in_names_the_command(root):
    @contextmanager
    def signed_out():
        raise GoogleAuthRequired("Google sign-in needs a browser. Pass interactive=True.")
        yield  # pragma: no cover

    with pytest.raises(evidence.RefreshFailed) as failed:
        evidence.refresh(f"drive:{DOC_ID}", by="A Manager", client_factory=signed_out, data_dir=root)
    assert str(failed.value) == drive_copies.GOOGLE_SIGN_IN
    assert "`jason drive --sync --interactive`" in drive_copies.GOOGLE_SIGN_IN
    assert _refreshes(root)[-1]["error"] == drive_copies.GOOGLE_SIGN_IN


def test_the_drive_refresher_signs_in_to_google_by_default():
    rule = evidence.rule_for(f"drive:{DOC_ID}")[0]
    assert rule.refresher.live is evidence.drive_live and rule.refresher.system == "Google Drive"
    payhoa = evidence.rule_for("payhoa:submission:12")[0]
    assert payhoa.refresher.live is None                                             # PayHOA stays the default


def test_refresh_many_reads_each_on_one_sign_in(root):
    seen: list = []
    drive = FakeDrive(_files())
    out = evidence.refresh_many([f"drive:{DOC_ID}", f"drive:{SHEET_ID}", f"drive:{DOC_ID}", "CIV 4041"],
                                by="A Manager", client_factory=_factory(drive, seen), data_dir=root, batch="templates")
    assert out["refreshed"] == [f"drive:{DOC_ID}", f"drive:{SHEET_ID}"] and out["skipped"] == 1
    assert seen == ["signed in"] and {x["batch"] for x in _refreshes(root)} == {"templates"}
    with pytest.raises(ValueError, match="one batch reads one system"):
        evidence.refresh_many([f"drive:{DOC_ID}", "payhoa:submission:12"], by="A Manager", data_dir=root)
    with pytest.raises(ValueError, match="a list"):
        evidence.refresh_many(f"drive:{DOC_ID}", by="A Manager", data_dir=root)


# --- the routes -----------------------------------------------------------------------------------------------------------

@pytest.fixture
def web(root, monkeypatch):
    """jason-web over the made-up data folder, Google sign-in set up over a made-up roster, and a live factory that
    hands a fake Drive for Google's context (and records which context each read asked for)."""
    from jason.web.app import create_app

    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: root)
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: root)
    monkeypatch.setattr(drive_copies, "_template_ids", lambda r: frozenset())
    drive = FakeDrive(_files())
    kinds: list[str] = []

    @contextmanager
    def live(kind):
        kinds.append(kind.system)
        yield SimpleNamespace(client=drive, org_id=0)

    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html><head></head><body></body></html>", encoding="utf-8")
    app = create_app(dist, {}, approvals_live=live, sign_in=webclient.roster_sign_in())
    return SimpleNamespace(app=app, root=root, kinds=kinds, drive=drive,
                           c=webclient.sign_in(webclient.client(app), "A Manager"))


def _served(root: Path) -> list[dict]:
    log = root / "access" / "served.jsonl"
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []


def test_the_thumbnail_route(web):
    url = f"/api/drive/thumb/{DOC_ID}"
    signed_out = webclient.client(web.app).get(url)
    assert signed_out.status_code == 401 and "signIn" in signed_out.json
    none = web.c.get(url)
    assert none.status_code == 404 and none.json == {"error": "No preview yet"}
    assert web.c.get("/api/drive/thumb/..").status_code == 404
    drive_copies.export(web.drive, web.root, DOC_ID)
    ok = web.c.get(url)
    assert ok.status_code == 200 and ok.data == PNG and ok.mimetype == "image/png"
    assert ok.headers["Cache-Control"] == "private, max-age=300"
    assert ok.headers["X-Content-Type-Options"] == "nosniff" and ok.headers["Content-Security-Policy"] == "sandbox"
    assert _served(web.root)[-1]["path"] == f"drive/copies/{DOC_ID}.png" and _served(web.root)[-1]["level"] == "P0"


def test_a_confidential_thumbnail_needs_the_private_view(web):
    files = _files()
    files[SECRET_ID] = {**files[DOC_ID], "id": SECRET_ID}
    drive_copies.export(FakeDrive(files), web.root, SECRET_ID)
    r = web.c.get(f"/api/drive/thumb/{SECRET_ID}")
    assert r.status_code == 403 and "only in the private view" in r.json["error"]


def test_the_refresh_route_reads_a_drive_address_on_googles_context(web):
    named = web.c.post("/api/evidence/refresh", json={"address": f"drive:{DOC_ID}", "by": "Pat Example"})
    assert named.status_code == 403 and web.kinds == []                              # never another's name
    r = web.c.post("/api/evidence/refresh", json={"address": f"drive:{DOC_ID}"})
    assert r.status_code == 200 and r.json["refreshed"]["by"] == "A Manager"
    assert web.kinds == ["google"] and drive_copies.read_record(web.root, DOC_ID)["by"] == "A Manager"
    assert webclient.client(web.app).post("/api/evidence/refresh",
                                          json={"address": f"drive:{DOC_ID}"}).status_code == 401


def test_the_view_route_opens_the_copys_pdf(web):
    drive_copies.export(web.drive, web.root, DOC_ID)
    r = web.c.post("/api/evidence/view", json={"address": f"drive:{DOC_ID}", "document": "pdf"})
    assert r.status_code == 200 and r.json["kind"] == "pdf" and r.json["url"].startswith("/api/evidence/document/")
    assert web.c.get(r.json["url"]).data == PDF_BYTES
    assert _served(web.root)[-1]["level"] == "P0"


def _hearing(root: Path, doc_id: str) -> None:
    """A made-up saved hearing whose notice Doc is ``doc_id``."""
    (root / "zoom").mkdir(exist_ok=True)
    (root / "zoom" / "hearings.json").write_text(json.dumps({"hearings": [{
        "address": "123 Main St #1", "start": "2099-10-20T18:00", "notice": "hearings/2099-10-20-123-main-st-1.md",
        "noticeDoc": {"id": doc_id, "url": "", "unfilled": []}}]}), encoding="utf-8")


def test_a_hearings_notice_doc_is_p3_wherever_its_folder_places_it(root):
    from jason.web.access import Level, level_of_path
    from jason.web.approvals import evidence_level

    assert drive_copies.level_of(root, DOC_ID) == "P0"                               # under a path rule
    _hearing(root, DOC_ID)
    assert drive_copies.level_of(root, DOC_ID) == "P3" and drive_copies.confidential(root, DOC_ID)
    assert level_of_path(f"drive/copies/{DOC_ID}.pdf", root) is Level.P3
    assert drive_copies.level_of(root, SHEET_ID) == "P2"                             # another file: unchanged
    (root / "zoom" / "hearings.json").write_text("{not json", encoding="utf-8")
    assert drive_copies.level_of(root, DOC_ID) == "P2"                               # hearings unreadable: never P0
    _hearing(root, DOC_ID)
    from unittest import mock

    with mock.patch("jason.tasks.drive_copies.data_root", lambda: root):
        assert evidence_level(f"drive:{DOC_ID}") is Level.P3


def test_a_hearings_doc_is_refused_outside_the_private_view_and_opens_inside_it(web):
    drive_copies.export(web.drive, web.root, DOC_ID)
    _hearing(web.root, DOC_ID)
    held = evidence.resolve(f"drive:{DOC_ID}", data_dir=web.root)
    assert held["documents"] == [] and "held back" in held["note"]
    r = web.c.post("/api/evidence/view", json={"address": f"drive:{DOC_ID}", "document": "pdf"})
    assert r.status_code == 403 and "only in the private view" in r.json["error"]
    thumb = web.c.get(f"/api/drive/thumb/{DOC_ID}")
    assert thumb.status_code == 403 and "only in the private view" in thumb.json["error"]
    assert _served(web.root) == []
    assert web.c.post("/api/private", json={"reason": "hearing preparation"}).status_code == 200
    ok = web.c.post("/api/evidence/view", json={"address": f"drive:{DOC_ID}", "document": "pdf"})
    assert ok.status_code == 200 and ok.json["level"] == "P3"
    assert web.c.get(ok.json["url"]).data == PDF_BYTES
    assert web.c.get(f"/api/drive/thumb/{DOC_ID}").status_code == 200
    assert {line["level"] for line in _served(web.root)} == {"P3"}


def test_the_refresh_many_route(web):
    r = web.c.post("/api/evidence/refresh-many", json={"addresses": [f"drive:{DOC_ID}", f"drive:{SHEET_ID}"]})
    assert r.status_code == 200 and r.json["refreshed"] == [f"drive:{DOC_ID}", f"drive:{SHEET_ID}"]
    assert web.kinds == ["google"] and r.json["by"] == "A Manager"
    assert web.c.post("/api/evidence/refresh-many", json={"addresses": "x"}).status_code == 400
    assert webclient.client(web.app).post("/api/evidence/refresh-many",
                                          json={"addresses": [f"drive:{DOC_ID}"]}).status_code == 401
