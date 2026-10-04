"""jason.tasks.document_models.run_filed: the documents filed to Drive from email, read like library files.

Every vendor, system, file, and report here is made up ("Acme Backflow", "Example Backflow Services"); none is an
association's.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from jason.community.symbols import DocumentKind
from jason.tasks import document_models as task
from jason.tasks import inspections
from jason.tasks.inspections import Coverage
from jason.tasks.library import text_for, text_path
from test_inspections import AS_OF, BACKFLOW, BACKFLOW_TEST, _one, _Profile

pymupdf = pytest.importorskip("pymupdf")

REPORT = ("Backflow Prevention Assembly Test Report\nExample Backflow Services\nContractor's Lic# 123456\n"
          "Test Date: 06/20/2026\nAssembly 1: Passed\nAssembly 2: Passed\n"
          + "The assemblies listed above were tested with a calibrated gauge and held.\n" * 3)


class FakeOcr:
    """An OCR engine that reads the same words from any page, and counts how often it is asked."""

    name = "fake-ocr"

    def __init__(self, words=REPORT):
        self.words, self.calls = words, 0

    def text_of(self, path):
        self.calls += 1
        return self.words


def _scan(path, words=""):
    """A one-page PDF: with no words it has no text layer, like a scan."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page()
    if words:
        page.insert_textbox(pymupdf.Rect(36, 36, 560, 800), words, fontsize=8)
    doc.save(str(path))
    doc.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _data(tmp_path, files):
    """A data folder with a filing log and the email files' index. ``files`` are (file id, name, kind, words or None
    for no local copy, vendor)."""
    log, index = [], []
    for n, (file_id, name, kind, words, vendor) in enumerate(files):
        message = f"m{n}"
        sha = f"missing-{n}"
        if words is not None:
            sha = _scan(tmp_path / "gmail" / "files" / message / name, words)
            # The index is written with the separators of the machine that saved the file.
            index.append({"messageId": message, "name": name, "path": f"gmail\\files\\{message}\\{name}", "sha256": sha})
        log.append({"vendor": vendor, "message_id": message, "at": "2026-06-22T17:00:00+00:00", "name": name, "sha256": sha,
                    "kind": kind, "action": "file", "where": "My Drive/Reports/Fire Protection/Backflow", "file_id": file_id})
    (tmp_path / "drive").mkdir(exist_ok=True)
    (tmp_path / "drive" / "vendor-files.jsonl").write_text("\n".join(json.dumps(r) for r in log) + "\n", encoding="utf-8")
    (tmp_path / "gmail").mkdir(exist_ok=True)
    (tmp_path / "gmail" / "files.json").write_text(json.dumps({"files": index}), encoding="utf-8")
    return tmp_path


def _stored(root):
    return {r["id"]: r for r in task.load(root)}


def test_a_filed_scan_is_read_by_local_ocr_and_becomes_a_reading_the_completeness_lens_places(tmp_path):
    root = _data(tmp_path, [("f1", "Test reports 2026.pdf", "inspection_report", "", "Acme Backflow"),
                            ("f2", "Invoice 77.pdf", "invoice", "", "Acme Backflow")])
    engine = FakeOcr()
    profile = _Profile((BACKFLOW,), (BACKFLOW_TEST,))
    result = task.run_filed(root, profile, engines=(engine,), today=AS_OF)
    assert (result["filed"], result["read"], result["how"]) == (1, ["Test reports 2026.pdf"], {"ocr: fake-ocr": 1})
    row = _stored(root)["drive-f1"]
    assert set(_stored(root)) == {"drive-f1"}                          # the invoice is another kind: not asked for
    assert row["source"] == task.FILED_SOURCE and row["kind"] == "inspection_report" and row["model"] == "inspection-report"
    assert row["filed"] == {"vendor": "Acme Backflow", "sent": "2026-06-22", "where": "My Drive/Reports/Fire Protection/Backflow",
                            "messageId": "m0", "sha256": row["filed"]["sha256"], "file": "gmail/files/m0/Test reports 2026.pdf",
                            "textFrom": "ocr: fake-ocr"}
    # The same keys a library row carries, made by the same code: the text's digest, the reader's version, the as-of
    # date, the basis, and the as-of lens.
    assert row["textSha"] == task.text_sha(REPORT) and row["asOf"] == "2026-10-04" and row["version"] and row["fieldsBasis"]
    assert row["lenses"]["as-of"]["asOf"] == "2026-10-04"
    assert any(f.get("lens") == "as-of" and f["code"] == "next-due" for f in row["findings"])
    assert row["fields"]["inspection_date"] == "2026-06-20" and row["fields"]["system"] == "backflow assembly"
    assert (root / "reviews" / "documents" / "as-of" / "2026-10-04.json").is_file()
    # The words are in the library's text cache under the row's id, where every reader of a document's text looks.
    assert text_for(root, "drive-f1") == REPORT and text_path(root, "drive-f1") == root / "library" / "text" / "drive-f1.txt"
    # The lens places it by its own fields: the backflow test's count opens on the day the report says.
    found = inspections.review(root, profile, as_of=AS_OF)
    o = _one(found, BACKFLOW, BACKFLOW_TEST)
    assert o.counted_from.isoformat() == "2026-06-20" and o.periods[0].status is Coverage.COVERED
    (placed,) = o.periods[0].reports
    assert placed.report.id == "drive-f1" and placed.report.where == "Drive" and placed.report.result == "passed"
    assert not found.systems[0].not_read and not found.unplaced
    # A second pass reads the cached words: the OCR engine is not asked again, and the row is replaced, not doubled.
    task.run_filed(root, profile, engines=(engine,), today=AS_OF)
    assert engine.calls == 1 and list(_stored(root)) == ["drive-f1"]
    task.run_filed(root, profile, engines=(engine,), today=AS_OF, refresh=True)
    assert engine.calls == 2


def test_a_text_layer_is_read_without_ocr_and_any_kind_can_be_named(tmp_path):
    root = _data(tmp_path, [("f1", "Report.pdf", "inspection_report", REPORT, "Acme Backflow"),
                            ("f2", "Invoice 77.pdf", "invoice", "", "Acme Backflow")])
    engine = FakeOcr()
    result = task.run_filed(root, _Profile(), engines=(engine,), today=AS_OF)
    assert engine.calls == 0 and result["how"] == {"text layer": 1} and _stored(root)["drive-f1"]["model"] == "inspection-report"
    # Another kind, when the caller names it: the invoice scan goes to OCR, and its row sits beside the report's.
    task.run_filed(root, _Profile(), kinds=(DocumentKind.INVOICE,), engines=(engine,), today=AS_OF)
    assert engine.calls == 1 and set(_stored(root)) == {"drive-f1", "drive-f2"}
    assert _stored(root)["drive-f2"]["kind"] == "invoice"


def test_a_filing_that_cannot_be_read_is_a_miss_that_says_why(tmp_path):
    root = _data(tmp_path, [("f1", "Scan nobody reads.pdf", "inspection_report", "", "Acme Backflow"),
                            ("f2", "Not a report.pdf", "inspection_report", "", "Acme Backflow"),
                            ("f3", "Never saved.pdf", "inspection_report", None, "Acme Backflow"),
                            ("f4", "Pest visit.pdf", "inspection_report", "", "Acme Pest")])
    profile = _Profile((BACKFLOW,), (BACKFLOW_TEST,))
    # No OCR engine at all: the scans have no words. No model is ever asked.
    result = task.run_filed(root, profile, engines=(), today=AS_OF)
    assert result["noText"] == ["Scan nobody reads.pdf", "Not a report.pdf", "Pest visit.pdf"]
    assert result["noLocalCopy"] == ["Never saved.pdf"] and not result["read"]
    assert set(_stored(root)) == {"drive-f1", "drive-f2", "drive-f4"}  # no row for the file that is not on disk
    assert all(r["model"] is None and not r["hasText"] for r in _stored(root).values())
    # An engine that reads words no reader recognizes: the file is tried again (the earlier read failed), and stays a miss.
    words = FakeOcr("Thank you for your business. " * 12)
    result = task.run_filed(root, profile, engines=(words,), today=AS_OF)
    assert words.calls == 3 and result["noModel"] == ["Scan nobody reads.pdf", "Not a report.pdf", "Pest visit.pdf"]
    found = inspections.review(root, profile, as_of=AS_OF)
    assert not _one(found, BACKFLOW, BACKFLOW_TEST).periods            # nothing is placed
    assert not found.unplaced                                          # and nothing is listed twice
    assert {f.name: f.note for f in found.systems[0].not_read} == {
        "Scan nobody reads.pdf": "no reader recognized its words (read from the ocr: fake-ocr)",
        "Not a report.pdf": "no reader recognized its words (read from the ocr: fake-ocr)",
        "Never saved.pdf": ""}
    assert found.other_filings == 1                                    # the pest vendor keeps no listed system
    text = "\n".join(inspections.lines(found))
    assert "filed, not read (3)" in text and "Never saved.pdf (sent 2026-06-22 by Acme Backflow" in text
    assert "no reader recognized its words" in text and "jason models --filed" in text


def test_a_filing_whose_bytes_the_library_holds_is_left_to_the_librarys_reading(tmp_path):
    import sqlite3

    from jason.tasks.library import COLUMNS, SCHEMA, STORE

    root = _data(tmp_path, [("f1", "Report.pdf", "inspection_report", REPORT, "Acme Backflow")])
    sha = json.loads((root / "gmail" / "files.json").read_text(encoding="utf-8"))["files"][0]["sha256"]
    (root / "library").mkdir()
    with sqlite3.connect(root / STORE) as conn:
        conn.execute(SCHEMA)
        conn.execute(f"INSERT INTO documents ({COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     ("9", "payhoa", "Reports/Report.pdf", "Report.pdf", "inspection_report", "", "", "NAME", "", 0, "", None, "", sha))
    result = task.run_filed(root, _Profile(), engines=(), today=AS_OF)
    assert result["inLibrary"] == ["Report.pdf"] and not result["rows"] and not _stored(root)


def test_a_library_run_keeps_the_rows_of_files_the_library_does_not_hold(tmp_path):
    root = _data(tmp_path, [("f1", "Report.pdf", "inspection_report", REPORT, "Acme Backflow")])
    task.run_filed(root, _Profile(), engines=(), today=AS_OF)
    store = root / task.STORE
    body = json.loads(store.read_text(encoding="utf-8"))
    body["readings"] += [{"id": "drive-m1", "name": "Minutes.gdoc", "kind": "minutes", "hasText": True, "model": "minutes",
                          "source": "Drive"},
                         {"id": "drive-x9", "name": "Some other pass's file.pdf", "kind": "contract", "hasText": True,
                          "model": None, "source": "another pass"},
                         {"id": "41", "name": "A library file since removed.pdf", "kind": "minutes", "hasText": True,
                          "model": "minutes"}]
    store.write_text(json.dumps(body), encoding="utf-8")
    assert task.outside_library(body["readings"][0]) and not task.outside_library(body["readings"][-1])
    task.run(root, _Profile(), today=AS_OF)                             # the library here is empty
    assert set(_stored(root)) == {"drive-f1", "drive-m1", "drive-x9"}  # every drive- row stays; the library's own row goes
    assert _stored(root)["drive-f1"]["fields"]["inspection_date"] == "2026-06-20"
    task.run(root, _Profile(), kinds=(DocumentKind.INSPECTION_REPORT,), today=AS_OF)   # a run over the reports' own kind
    assert "drive-f1" in _stored(root)


def test_the_vision_model_reads_a_scan_only_when_a_person_passes_it(tmp_path):
    root = _data(tmp_path, [("f1", "Scan.pdf", "inspection_report", "", "Acme Backflow"),
                            ("f2", "Typed.pdf", "inspection_report", REPORT, "Acme Backflow")])

    class Vision(FakeOcr):
        name, model = "fake-vision", "made-up-vision-model"

    vision = Vision()
    result = task.run_filed(root, _Profile(), engines=(), vision=vision, today=AS_OF)
    assert vision.calls == 1                                           # the scan only: the typed file has a text layer
    rows = _stored(root)
    assert rows["drive-f1"]["model"] == "inspection-report"
    assert rows["drive-f1"]["filed"]["textFrom"].startswith("vision model made-up-vision-model, 1 of 1 pages")
    assert rows["drive-f2"]["filed"]["textFrom"] == "text layer"
    assert sorted(result["read"]) == ["Scan.pdf", "Typed.pdf"]


def test_the_command_reads_the_filed_reports(tmp_path, monkeypatch, capsys):
    from jason.cli import build_parser

    root = _data(tmp_path, [("f1", "Report.pdf", "inspection_report", REPORT, "Acme Backflow")])
    monkeypatch.setenv("JASON_DATA_DIR", str(root))
    monkeypatch.delenv("PAYHOA_CATALOG", raising=False)
    args = build_parser().parse_args(["models", "--filed"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "Report.pdf: read by inspection-report (text layer)" in out
    assert "1 filed document(s) of kind inspection_report in the filing log: 1 read" in out
    assert "drive-f1" in _stored(root)
