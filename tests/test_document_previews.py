"""Recorded copies as previews: a PDF's page-1 thumbnail (``jason.tasks.pdf_thumbs``, ``GET /api/thumb``), a file on
disk as evidence (``file:<path>``), and the governing documents' listing (``jason.web.extra.governing_documents``).
Everything is made up in a temporary data folder; nothing reaches Google, PayHOA, or the county."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

import webclient
from jason.approvals import evidence_documents
from jason.approvals.evidence import resolve
from jason.tasks import drive_copies, pdf_thumbs
from jason.web.extra import governing_documents

DECL = "artifacts/site-docs/governing_documents/Declaration.pdf"
SECRET = "legal/Counsel letter.pdf"
REQUEST = "payhoa-files/requests/7/Bid.pdf"
UNPLACED = "elsewhere/Loose.pdf"
DOC_ID = "1FakeDeclDoc0001"
PDF_ID = "1FakeDeclPdf0002"
AMEND_ID = "1FakeAmendDoc003"


def _pdf(path: Path, text: str = "Declaration of covenants", width: float = 612) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=792)
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A made-up data folder: a recorded declaration (P0) with its text extract, a confidential letter (P3), a request's
    file (P2), and a PDF in no place jason's rules name."""
    monkeypatch.setattr(drive_copies, "_template_ids", lambda r: frozenset())
    _pdf(tmp_path / DECL)
    (tmp_path / (DECL + ".md")).write_text(f"# Declaration.pdf\n- drive_id: `{PDF_ID}`\n- mime: `application/pdf`\n\n"
                                           "Article 1. Definitions.\n", encoding="utf-8")
    _pdf(tmp_path / SECRET, "Privileged")
    _pdf(tmp_path / REQUEST, "A bid")
    _pdf(tmp_path / UNPLACED, "Loose")
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"syncedAt": "2026-10-02T08:00:00+00:00", "files": [
        {"id": PDF_ID, "name": "Declaration.pdf", "mimeType": "application/pdf", "modified": "2026-01-01T00:00:00Z"}]}),
        encoding="utf-8")
    return tmp_path


# --- the thumbnail ------------------------------------------------------------------------------------------------------

def test_page_one_is_rendered_about_300_pixels_wide_and_kept(root):
    png = pdf_thumbs.thumbnail(root, DECL)
    assert png is not None and png == pdf_thumbs.cache_path(root, DECL)
    assert png.parent == root / "thumbs" and png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert abs(pymupdf.Pixmap(str(png)).width - pdf_thumbs.WIDTH) <= 2


def test_the_cached_thumbnail_is_reused_and_rebuilt_when_the_pdf_changes(root, monkeypatch):
    calls: list[Path] = []
    real = pdf_thumbs.render
    monkeypatch.setattr(pdf_thumbs, "render", lambda pdf, width=pdf_thumbs.WIDTH: calls.append(pdf) or real(pdf, width))
    first = pdf_thumbs.thumbnail(root, DECL)
    again = pdf_thumbs.thumbnail(root, DECL)
    assert first == again and len(calls) == 1                                         # read once
    pdf = root / DECL
    _pdf(pdf, "Restated declaration", width=300)
    later = pdf.stat().st_mtime_ns + 5_000_000_000
    os.utime(pdf, ns=(later, later))
    assert pdf_thumbs.thumbnail(root, DECL) == first and len(calls) == 2              # the PDF changed: rendered again
    assert first.stat().st_mtime_ns == later


def test_a_file_that_is_not_a_readable_pdf_has_no_thumbnail(root):
    (root / "governing").mkdir()
    (root / "governing" / "broken.pdf").write_bytes(b"%PDF-1.4 not really")
    assert pdf_thumbs.thumbnail(root, "governing/broken.pdf") is None
    assert pdf_thumbs.thumbnail(root, "governing/missing.pdf") is None
    assert pdf_thumbs.thumbnail(root, DECL + ".md") is None


# --- the route ------------------------------------------------------------------------------------------------------------

@pytest.fixture
def web(root, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: root)
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: root)
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html><head></head><body></body></html>", encoding="utf-8")
    app = create_app(dist, {}, sign_in=webclient.roster_sign_in())
    return SimpleNamespace(app=app, root=root, c=webclient.sign_in(webclient.client(app), "A Manager"))


def _served(root: Path) -> list[dict]:
    log = root / "access" / "served.jsonl"
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []


def test_the_thumb_route_is_signed_in_level_checked_and_logged(web):
    url = f"/api/thumb?path={DECL}"
    signed_out = webclient.client(web.app).get(url)
    assert signed_out.status_code == 401 and "signIn" in signed_out.json
    ok = web.c.get(url)
    assert ok.status_code == 200 and ok.mimetype == "image/png" and ok.data.startswith(b"\x89PNG")
    assert ok.headers["Cache-Control"] == "private, max-age=300"
    assert ok.headers["X-Content-Type-Options"] == "nosniff" and ok.headers["Content-Security-Policy"] == "sandbox"
    assert _served(web.root)[-1]["path"] == DECL and _served(web.root)[-1]["level"] == "P0"


def test_the_thumb_route_refuses_by_level_and_misses_by_path(web):
    assert web.c.get(f"/api/thumb?path={SECRET}").status_code == 403                    # P3 outside the private view
    admin = webclient.sign_in(webclient.client(web.app), "Ada Admin")
    assert admin.get(f"/api/thumb?path={REQUEST}").status_code == 403                   # P2: no office opens it
    assert admin.get(f"/api/thumb?path={DECL}").status_code == 200                      # P0: anyone on the roster
    for bad in ("", "../outside.pdf", DECL + ".md", "governing/missing.pdf"):
        assert web.c.get(f"/api/thumb?path={bad}").status_code == 404
    opened = web.c.post("/api/private", json={"reason": "counsel review", "minutes": 15})
    assert opened.status_code == 200
    assert web.c.get(f"/api/thumb?path={SECRET}").status_code == 200
    assert _served(web.root)[-1]["level"] == "P3" and _served(web.root)[-1]["reason"] == "counsel review"


def test_a_thumbnail_is_never_served_as_a_plain_file(web):
    web.c.get(f"/api/thumb?path={SECRET}")
    web.c.post("/api/private", json={"reason": "counsel review", "minutes": 15})
    web.c.get(f"/api/thumb?path={SECRET}")
    web.c.delete("/api/private")
    kept = pdf_thumbs.cache_path(web.root, SECRET).relative_to(web.root).as_posix()
    assert web.c.get(f"/api/file?path={kept}").status_code == 403                       # thumbs/* is P3


# --- the file: evidence row ------------------------------------------------------------------------------------------------

def test_a_recorded_copy_opens_as_its_pdf_and_its_text(root):
    got = resolve(f"file:{DECL}", data_dir=root)
    assert got["found"] and got["kind"] == "file" and got["refreshable"] is None and got["refresh"] == []
    assert [s["name"] for s in got["sources"]] == ["Recorded copy"]
    assert [(d["id"], d["kind"]) for d in got["documents"]] == [("pdf", "pdf"), ("text", "text")]
    opened = evidence_documents.view(f"file:{DECL}", "text", by="A Manager", data_dir=root)
    assert "Article 1. Definitions." in opened.answer["text"]
    pdf = evidence_documents.view(f"file:{DECL}", "pdf", by="A Manager", data_dir=root)
    assert pdf.path == (root / DECL).resolve() and pdf.answer["kind"] == "pdf"


def test_a_file_outside_the_rules_or_the_folder_is_a_miss(root):
    for address in (f"file:{UNPLACED}", "file:../x.pdf", "file:governing/missing.pdf", "file:"):
        got = resolve(address, data_dir=root)
        assert not got["found"] and got["documents"] == []
    (root / "spec").mkdir()
    (root / "spec" / "facts.json").write_text("{}", encoding="utf-8")
    assert not resolve("file:spec/facts.json", data_dir=root)["found"]                   # not a kind the viewer shows


def test_a_confidential_file_is_held_back_outside_the_private_view(root):
    held = resolve(f"file:{SECRET}", data_dir=root)
    assert held["documents"] == [] and "held back" in held["note"]
    shown = resolve(f"file:{SECRET}", data_dir=root, private=True)
    assert [d.get("level") for d in shown["documents"]] == ["P3"]


def test_the_view_route_judges_a_file_by_its_level(web):
    ok = web.c.post("/api/evidence/view", json={"address": f"file:{DECL}", "document": "pdf"})
    assert ok.status_code == 200 and ok.json["url"].startswith("/api/evidence/document/")
    assert web.c.get(ok.json["url"]).data == (web.root / DECL).read_bytes()
    assert _served(web.root)[-1]["level"] == "P0"
    assert web.c.post("/api/evidence/view", json={"address": f"file:{SECRET}", "document": "pdf"}).status_code == 403
    admin = webclient.sign_in(webclient.client(web.app), "Ada Admin")
    assert admin.post("/api/evidence/view", json={"address": f"file:{REQUEST}", "document": "pdf"}).status_code == 403


# --- the governing documents' listing -------------------------------------------------------------------------------------

def _community(*, citable=(), instruments=None):
    decl = SimpleNamespace(title="Declaration", drive_id=PDF_ID, kind=None, document_kind=SimpleNamespace(value="declaration"),
                           recorded=None, adopted=None, recorder_number="2001-000123")
    amend = SimpleNamespace(title="First Amendment", drive_id=AMEND_ID, kind=SimpleNamespace(value="google_doc"),
                            document_kind=SimpleNamespace(value="amendment"), recorded=None,
                            adopted=__import__("datetime").date(2020, 1, 2), recorder_number="")
    ccrs = SimpleNamespace(instruments=tuple(instruments) if instruments is not None else (decl, amend))
    return SimpleNamespace(ccrs=ccrs, citable_documents=lambda: tuple(citable), kind_rules=lambda: ())


def test_the_listing_pairs_a_recorded_pdf_with_its_drive_doc(root):
    citable = (SimpleNamespace(key="decl", title="Declaration of Covenants", drive_id=DOC_ID,
                               kind=SimpleNamespace(value="declaration"), aliases=("Declaration",), written="2001"),
               SimpleNamespace(key="rules", title="Rules", drive_id="1FakeRulesDoc04",
                               kind=SimpleNamespace(value="operating_rules"), aliases=(), written=""))
    (root / "drive" / "holdings.json").write_text(json.dumps({"rows": [         # the Doc under a Drive root's path rule
        {"id": DOC_ID, "name": "Declaration of Covenants", "pathRule": True, "confidential": False, "elsewhere": []}]}),
        encoding="utf-8")
    out = governing_documents.listing(_community(citable=citable), root)
    rows = {r["key"]: r for r in out["rows"]}
    decl = rows["decl"]                                                                  # the instrument and its Doc
    assert decl["title"] == "Declaration of Covenants" and decl["kind"] == "declaration"
    drive = decl["driveCopy"]                                                            # the working copy
    assert drive["address"] == f"drive:{DOC_ID}" and decl["driveKind"] == "doc" and drive["source"] == "Drive copy"
    assert drive["original"]["label"] == "Open in Google" and drive["level"] == "P0" and drive["thumb"] is False
    assert drive["refreshable"]["system"] == "Google Drive" and "readAt" not in drive        # no copy yet
    recorded = decl["recordedCopy"]
    assert {k: recorded[k] for k in ("address", "document", "name", "kind", "level", "source", "size", "thumb")} == {
        "address": f"file:{DECL}", "document": "pdf", "name": "Declaration.pdf", "kind": "pdf", "level": "P0",
        "source": "Recorded copy", "size": (root / DECL).stat().st_size, "thumb": True}
    assert decl["number"] == "2001-000123" and decl["written"] == "2001" and decl["level"] == "P0"
    assert rows["first-amendment"]["adopted"] == "2020-01-02" and rows["first-amendment"]["recordedCopy"] is None
    assert rows["rules"]["level"] == "P2"                                                 # a Drive file no rule opens
    assert out["heldBack"] == 0 and out["count"] == 3
    text = json.dumps(out)
    assert str(root) not in text and str(root).replace("\\", "/") not in text and "/api/file" not in text
    for row in out["rows"]:                                                               # every reference resolves
        for ref in (row["recordedCopy"], row["driveCopy"]):
            if ref and ref["address"].startswith("file:"):
                assert resolve(ref["address"], data_dir=root)["found"]


def test_a_pdf_no_document_claims_is_its_own_row(root):
    _pdf(root / "governing" / "Articles of Incorporation.pdf", "Articles")
    out = governing_documents.listing(_community(instruments=()), root)
    assert [(r["title"], r["driveCopy"], r["recordedCopy"]["address"]) for r in out["rows"]] == [
        ("Declaration", None, f"file:{DECL}"), ("Articles of Incorporation", None, "file:governing/Articles of Incorporation.pdf")]


def test_a_confidential_row_is_held_back_unless_the_private_view_is_open(root):
    (root / "drive" / "holdings.json").write_text(json.dumps({"rows": [
        {"id": AMEND_ID, "name": "First Amendment", "confidential": True, "elsewhere": []}]}), encoding="utf-8")
    out = governing_documents.listing(_community(), root)
    assert [r["title"] for r in out["rows"]] == ["Declaration"] and out["heldBack"] == 1 and "held back" in out["note"]
    shown = governing_documents.listing(_community(), root, private=True)
    assert [r["confidential"] for r in shown["rows"]] == [False, True]


def test_the_route_serves_the_listing(web, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.community.community", lambda: _community())
    app = create_app(web.root / "dist", None, sign_in=webclient.roster_sign_in())
    r = webclient.sign_in(webclient.client(app), "A Manager").get("/api/governing-documents")
    assert r.status_code == 200 and r.json["found"] and r.json["rows"][0]["recordedCopy"]["address"] == f"file:{DECL}"
