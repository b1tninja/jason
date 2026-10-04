"""A legal case's file as its own confidential catalog in the passage index: fetched from the Drive listing, medical
records held back, and searched only when a person names the case's catalog."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community import passage_index as pi
from jason.community.legal_cases import CaseRole, CaseStatus, Forum, LegalCase
from jason.tasks.case_files import fetch, index_sources, is_case_catalog, plan

CASE = LegalCase("example-26cv000001", "Example suit", Forum.SUPERIOR_COURT, CaseRole.DEFENDANT, CaseStatus.PENDING,
                 case_number="26CV000001", drive_folder="26CV000001 - Example", held_back=("*VCA *", "*Medical*"))
NO_FOLDER = LegalCase("other", "No folder", Forum.SUPERIOR_COURT, CaseRole.DEFENDANT, CaseStatus.PENDING)


def _listing(data: Path) -> None:
    root = "My Drive/26CV000001 - Example/"
    files = [
        {"id": "1", "name": "Complaint.pdf", "mimeType": "application/pdf", "md5": "a", "modified": "t1"},
        {"id": "2", "name": "20250623 VCA Invoice.pdf", "mimeType": "application/pdf", "md5": "b", "modified": "t1"},
        {"id": "3", "name": "Defense Request", "mimeType": "application/vnd.google-apps.document", "md5": "", "modified": "t1"},
        {"id": "4", "name": "Meeting.transcript.vtt", "mimeType": "text/vtt", "md5": "c", "modified": "t1", "sub": "Recordings/"},
        {"id": "5", "name": "photo.jpeg", "mimeType": "image/jpeg", "md5": "d", "modified": "t1"},
        {"id": "6", "name": "Bylaws.pdf", "mimeType": "application/vnd.google-apps.shortcut", "md5": "", "modified": "t1"},
        {"id": "7", "name": "Q: what?.pdf", "mimeType": "application/pdf", "md5": "e", "modified": "t1"},
    ]
    rows = [{**f, "path": root + f.pop("sub", "") + f["name"]} for f in files]
    rows.append({"id": "9", "name": "Bylaws.pdf", "mimeType": "application/pdf", "md5": "z", "modified": "t1", "path": "My Drive/GD/Bylaws.pdf"})
    (data / "drive").mkdir(parents=True)
    (data / "drive" / "files.json").write_text(json.dumps({"files": rows}), encoding="utf-8")


class Drive:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def download(self, file_id: str, dest: Path) -> Path:
        self.calls.append(("download", file_id))
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"%PDF-1.4 " + file_id.encode())
        return Path(dest)

    def export_pdf(self, file_id: str, dest: Path) -> Path:
        self.calls.append(("export", file_id))
        return self.download(file_id, dest)


def test_the_plan_takes_the_readable_files_and_lists_the_rest(tmp_path: Path) -> None:
    _listing(tmp_path)
    rows = {r["name"]: r for r in plan(tmp_path, CASE)}
    assert set(rows) == {"Complaint.pdf", "20250623 VCA Invoice.pdf", "Defense Request", "Meeting.transcript.vtt", "photo.jpeg",
                         "Bylaws.pdf", "Q: what?.pdf"}
    assert (rows["Defense Request"]["action"], rows["Defense Request"]["local"]) == ("export", "Defense Request.pdf")
    assert rows["Meeting.transcript.vtt"]["local"] == "Recordings/Meeting.transcript.vtt.txt"
    assert rows["photo.jpeg"]["action"] == "listed" and rows["Bylaws.pdf"]["action"] == "listed"
    assert rows["20250623 VCA Invoice.pdf"]["heldBack"] and not rows["Complaint.pdf"]["heldBack"]
    assert rows["Q: what?.pdf"]["local"] == "Q_ what_.pdf"


def test_fetch_holds_back_medical_records_and_keeps_an_unchanged_copy(tmp_path: Path) -> None:
    _listing(tmp_path)
    drive = Drive()
    counts = fetch(drive, tmp_path, CASE)
    assert counts == {"files": 7, "downloaded": 4, "kept": 0, "heldBack": 1, "listed": 2, "errors": 0}
    assert ("download", "2") not in drive.calls and ("export", "3") in drive.calls
    files = tmp_path / "cases" / CASE.key / "files"
    assert not (files / "20250623 VCA Invoice.pdf").exists()

    drive.calls.clear()
    assert fetch(drive, tmp_path, CASE)["kept"] == 4 and drive.calls == []

    # A person may ask for the held records; a later plain fetch takes jason's copy back out.
    fetch(drive, tmp_path, CASE, include_held=True)
    assert (files / "20250623 VCA Invoice.pdf").is_file()
    fetch(drive, tmp_path, CASE)
    assert not (files / "20250623 VCA Invoice.pdf").exists()
    manifest = json.loads((tmp_path / "cases" / CASE.key / "manifest.json").read_text(encoding="utf-8"))
    assert {r["name"]: r["action"] for r in manifest["files"]}["20250623 VCA Invoice.pdf"] == "held back"


def test_a_case_is_its_own_confidential_catalog_in_the_index() -> None:
    (source,) = index_sources((CASE, NO_FOLDER))
    assert (source.catalog, source.folder) == ("case-example-26cv000001", "cases/example-26cv000001/files")
    assert source.confidential and source.standing is pi.Standing.EVIDENCE and not source.generated
    assert is_case_catalog("case-example-26cv000001") and not is_case_catalog("records")


def test_a_case_file_is_searched_only_when_its_catalog_is_named(tmp_path: Path) -> None:
    from jason.mcp.county import document_search

    _listing(tmp_path)
    fetch(Drive(), tmp_path, CASE)
    files = tmp_path / "cases" / CASE.key / "files"
    (files / "Recordings" / "Meeting.transcript.vtt.txt").write_text(
        "The board agreed to preserve all video of the garage.\n", encoding="utf-8")
    (tmp_path / "governing").mkdir()
    (tmp_path / "governing" / "rules.md").write_text("# Rules\n\nNo video recording in the pool area.\n", encoding="utf-8")
    sources = (pi.IndexSource("records", "governing", pi.Standing.RECORD), *index_sources((CASE,)))
    report = pi.build(tmp_path, sources=sources, kind_of=lambda name: "")
    # The PDFs have no text extract: only the transcript and the rules are cut.
    assert report.files == 2

    shared = document_search("preserve video", data_dir=tmp_path, mode="keyword")
    assert {h["catalog"] for h in shared["hits"]} == {"records"}
    case = document_search("preserve video", data_dir=tmp_path, mode="keyword", catalog="case-example-26cv000001")
    assert [h["file"] for h in case["hits"]] == ["Meeting.transcript.vtt.txt"]
    assert case["hits"][0]["confidential"] and case["hits"][0]["standing"] == "evidence"
    assert any("directors and counsel" in c for c in case["caveats"])


# --- text extracts: made-up PDFs, a fake OCR engine, no Tesseract and no GPU ------------------------------------------

TYPED = ("The association received the letter on the first of the month and the board agreed to preserve every "
         "recording of the garage gate. The manager wrote to the carrier the same week and asked for a claim number. "
         "Nothing in this made-up page is a real matter; it only has to be longer than two hundred characters.")
SCANNED = "Exhibit A is a scanned notice that the gate camera keeps thirty days of footage before it writes over it."


def _typed_page(document, text: str = TYPED) -> None:
    import pymupdf

    document.new_page().insert_textbox(pymupdf.Rect(40, 40, 560, 760), text, fontsize=10)


def _scanned_page(document) -> None:
    import pymupdf

    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 40, 40))
    pix.clear_with(255)
    page = document.new_page()
    page.insert_image(page.rect, pixmap=pix)


def _pdf(path: Path, *pages) -> Path:
    import pymupdf

    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    for add in pages:
        add(document)
    document.save(path)
    document.close()
    return path


class FakeOcr:
    """An engine that reads any page as the same words, and keeps what it was given."""

    name = "fake-ocr"

    def __init__(self, text: str = SCANNED) -> None:
        self.text = text
        self.given: list[str] = []

    def text_of(self, path: Path) -> str:
        self.given.append(Path(path).name)
        return self.text


def _files(tmp_path: Path) -> Path:
    return tmp_path / "cases" / CASE.key / "files"


def _manifest(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "cases" / CASE.key / "manifest.json").read_text(encoding="utf-8"))


def test_a_text_layer_pdf_is_extracted_beside_it_and_indexed_as_confidential_evidence(tmp_path: Path) -> None:
    from jason.mcp.county import document_search
    from jason.tasks.case_files import ReadMethod, extract_text

    files = _files(tmp_path)
    _pdf(files / "Letters" / "Preservation letter.pdf", _typed_page)
    engine = FakeOcr()
    report = extract_text(tmp_path, CASE, engines=(engine,))
    assert report.extracted == {"text layer": 1} and not report.unreadable and engine.given == []
    # The extract sits in the PDF's own subfolder and keeps the PDF's name.
    extract = files / "Letters" / "Preservation letter.pdf.txt"
    assert "preserve every" in extract.read_text(encoding="utf-8")
    row = _manifest(tmp_path)["extracts"]["Letters/Preservation letter.pdf"]
    assert row["method"] == ReadMethod.TEXT_LAYER.value and row["text"] == "Letters/Preservation letter.pdf.txt"
    assert len(row["sha256"]) == 64 and row["pages"] == 1 and "engine" not in row

    (entry,) = index_sources((CASE,))[0].entries(tmp_path)
    assert entry.path == extract and entry.confidential and entry.standing is pi.Standing.EVIDENCE
    assert entry.context == "Letters/Preservation letter.pdf: text layer"
    pi.build(tmp_path, sources=index_sources((CASE,)), kind_of=lambda name: "")
    assert document_search("preserve recording", data_dir=tmp_path, mode="keyword")["hits"] == []
    found = document_search("preserve recording", data_dir=tmp_path, mode="keyword", catalog="case-example-26cv000001")
    (hit,) = found["hits"]
    assert hit["file"] == "Preservation letter.pdf.txt" and hit["confidential"] and hit["standing"] == "evidence"
    assert hit["context"] == "Letters/Preservation letter.pdf: text layer"


def test_an_unchanged_pdf_is_not_read_again_and_a_changed_one_is(tmp_path: Path, monkeypatch) -> None:
    from jason.tasks import case_files

    pdf = _pdf(_files(tmp_path) / "Complaint.pdf", _typed_page)
    assert case_files.extract_text(tmp_path, CASE, engines=()).extracted == {"text layer": 1}
    reads: list[str] = []
    real = case_files._read
    monkeypatch.setattr(case_files, "_read", lambda path, *a: reads.append(path.name) or real(path, *a))

    again = case_files.extract_text(tmp_path, CASE, engines=())
    assert again.extracted == {} and again.unchanged == 1 and reads == []
    assert [row.source for row in again.rows] == ["Complaint.pdf"]

    before = _manifest(tmp_path)["extracts"]["Complaint.pdf"]["sha256"]
    _pdf(pdf, lambda document: _typed_page(document, TYPED.replace("garage gate", "pool gate")))
    changed = case_files.extract_text(tmp_path, CASE, engines=())
    assert changed.extracted == {"text layer": 1} and changed.unchanged == 0 and reads == ["Complaint.pdf"]
    assert _manifest(tmp_path)["extracts"]["Complaint.pdf"]["sha256"] != before
    assert "pool gate" in (pdf.parent / "Complaint.pdf.txt").read_text(encoding="utf-8")

    # A person asking reads every file again.
    assert case_files.extract_text(tmp_path, CASE, engines=(), refresh=True).extracted == {"text layer": 1}


def test_a_held_back_file_is_never_extracted_even_with_a_copy_on_disk(tmp_path: Path) -> None:
    from jason.tasks.case_files import extract_text

    _listing(tmp_path)
    fetch(Drive(), tmp_path, CASE, include_held=True)          # a person had the held records fetched
    files = _files(tmp_path)
    held = _pdf(files / "20250623 VCA Invoice.pdf", _typed_page)
    _pdf(files / "Complaint.pdf", _typed_page)
    (files / "Notes.txt").write_text("Typed notes of the call with the carrier.\n", encoding="utf-8")
    (files / "Medical notes.txt").write_text("A held record a person had fetched.\n", encoding="utf-8")
    engine, vision = FakeOcr(), FakeOcr()
    report = extract_text(tmp_path, CASE, engines=(engine,), vision=vision)
    assert report.held_back == 1 and held.is_file() and not (files / "20250623 VCA Invoice.pdf.txt").exists()
    assert engine.given == [] and vision.given == []
    assert "20250623 VCA Invoice.pdf" not in _manifest(tmp_path)["extracts"]
    assert "Complaint.pdf" in _manifest(tmp_path)["extracts"]

    # Text of a held file on disk (a copy a person had fetched, or an extract other code left) is never indexed.
    stale = files / "20250623 VCA Invoice.pdf.txt"
    stale.write_text("Words of a held record that must not be searched.\n", encoding="utf-8")
    source = index_sources((CASE,))[0]
    plan = source.plan(tmp_path)
    assert sorted(e.path.name for e in plan.entries) == ["Complaint.pdf.txt", "Meeting.transcript.vtt.txt", "Notes.txt"]
    assert plan.left_out["held back by the case's rule"] == 2          # the invoice, and the held notes
    assert all(e.confidential and e.standing is pi.Standing.EVIDENCE for e in plan.entries)

    # A plain fetch takes jason's copy back out, and its text with it.
    fetch(Drive(), tmp_path, CASE)
    assert not held.exists() and not stale.exists()


def test_an_extract_of_a_file_that_is_now_held_or_gone_is_removed(tmp_path: Path) -> None:
    from dataclasses import replace

    from jason.tasks.case_files import extract_text

    files = _files(tmp_path)
    _pdf(files / "Clinic summary.pdf", _typed_page)
    gone = _pdf(files / "Old draft.pdf", _typed_page)
    assert extract_text(tmp_path, CASE, engines=()).extracted == {"text layer": 2}
    gone.unlink()
    stricter = replace(CASE, held_back=(*CASE.held_back, "*Clinic*"))
    report = extract_text(tmp_path, stricter, engines=())
    assert report.removed == 2 and report.held_back == 1 and report.rows == []
    assert not (files / "Clinic summary.pdf.txt").exists() and not (files / "Old draft.pdf.txt").exists()
    assert _manifest(tmp_path)["extracts"] == {}


def test_a_scanned_pdf_with_no_ocr_engine_is_listed_as_unreadable_not_skipped(tmp_path: Path) -> None:
    from jason.tasks.case_files import ReadMethod, extract_text

    files = _files(tmp_path)
    _pdf(files / "Scan.pdf", _scanned_page)
    (files / "Sheet.xlsx").write_bytes(b"not a workbook")
    report = extract_text(tmp_path, CASE, engines=())
    assert report.extracted == {} and dict(report.unreadable) == {
        "Scan.pdf": "image-only; no OCR engine is installed", "Sheet.xlsx": "no text reader for this type"}
    assert any(line.startswith("unreadable: Scan.pdf (image-only") for line in report.lines())
    assert _manifest(tmp_path)["extracts"]["Scan.pdf"]["method"] == ReadMethod.UNREADABLE.value
    assert not (files / "Scan.pdf.txt").exists()
    plan = index_sources((CASE,))[0].plan(tmp_path)
    assert plan.entries == [] and plan.left_out == {"no reader could read it": 2}

    # The miss stays listed on a second run, and the file is read once an engine is there to read it.
    assert len(extract_text(tmp_path, CASE, engines=()).unreadable) == 2
    engine = FakeOcr()
    report = extract_text(tmp_path, CASE, engines=(engine,))
    assert report.extracted == {"OCR: fake-ocr": 1} and [name for name, _ in report.unreadable] == ["Sheet.xlsx"]
    (entry,) = index_sources((CASE,))[0].entries(tmp_path)
    assert entry.context == "Scan.pdf: OCR: fake-ocr; may misread"
    assert "[page 1: OCR: fake-ocr; may misread]" in entry.path.read_text(encoding="utf-8")
    # Read in full by a local engine: it is not read again.
    assert extract_text(tmp_path, CASE, engines=(engine,)).unchanged == 1 and len(engine.given) == 1


def test_only_the_scanned_pages_of_a_typed_filing_go_to_ocr_and_noise_is_left_out(tmp_path: Path) -> None:
    from jason.tasks.case_files import extract_text

    files = _files(tmp_path)
    _pdf(files / "Filing.pdf", _typed_page, _scanned_page, _typed_page)
    engine = FakeOcr()
    report = extract_text(tmp_path, CASE, engines=(engine,))
    assert report.extracted == {"text layer, scanned pages by OCR: fake-ocr": 1} and engine.given == ["page-1.pdf"]
    text = (files / "Filing.pdf.txt").read_text(encoding="utf-8")
    assert text.count("preserve every") == 2 and "[page 2: OCR: fake-ocr; may misread]\nExhibit A" in text
    (entry,) = index_sources((CASE,))[0].entries(tmp_path)
    assert entry.context == "Filing.pdf: text layer; 1 of 3 pages read by OCR: fake-ocr, which may misread"

    # What an engine makes of a photograph is not words: the page is left unread and the file is listed as partly read.
    _pdf(files / "Photos.pdf", _typed_page, _scanned_page)
    noise = FakeOcr("a ee | ~ 1l .. ;; oo = _ rn 4 x")
    report = extract_text(tmp_path, CASE, engines=(noise,))
    assert report.extracted == {"text layer": 1} and report.unchanged == 1
    (partial,) = report.partial
    assert (partial.source, partial.unread_pages, partial.pages) == ("Photos.pdf", 1, 2)
    assert "rn 4 x" not in (files / "Photos.pdf.txt").read_text(encoding="utf-8")
    assert partial.context == "Photos.pdf: text layer; 1 of 2 pages are images no reader gave words for"


def test_one_text_a_file_a_word_file_is_read_and_a_text_already_beside_a_file_is_kept(tmp_path: Path) -> None:
    import zipfile

    from jason.tasks.case_files import extract_text

    _listing(tmp_path)
    fetch(Drive(), tmp_path, CASE)
    files = _files(tmp_path)
    for name in ("Defense Request.pdf", "Q_ what_.pdf", "Recordings/Meeting.transcript.vtt.txt"):
        (files / name).unlink()
    with zipfile.ZipFile(files / "Memo.docx", "w") as archive:
        archive.writestr("word/document.xml", "<w:document><w:p><w:t>The carrier's memo on the tender.</w:t></w:p></w:document>")
    # A file Drive holds under the extract's own name is the case's file: it is never written over.
    _pdf(files / "Complaint.pdf", _typed_page)
    manifest = _manifest(tmp_path)
    manifest["files"].append({"id": "8", "name": "Complaint.pdf.txt", "path": "Complaint.pdf.txt", "local": "Complaint.pdf.txt",
                              "mimeType": "text/plain", "md5": "f", "modified": "t1", "heldBack": False, "action": "download"})
    (tmp_path / "cases" / CASE.key / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (files / "Complaint.pdf.txt").write_text("Counsel's own transcription of the complaint.\n", encoding="utf-8")
    # An extract another tool wrote beside a PDF (".pdf.md") already holds its words.
    _pdf(files / "Order.pdf", _typed_page)
    (files / "Order.pdf.md").write_text("# Order.pdf\n\n" + TYPED, encoding="utf-8")

    report = extract_text(tmp_path, CASE, engines=())
    assert report.extracted == {"the file's own words": 1} and report.has_text == 2 and not report.unreadable
    assert "transcription" in (files / "Complaint.pdf.txt").read_text(encoding="utf-8")
    assert not (files / "Order.pdf.txt").exists()
    entries = {e.path.name: e.context for e in index_sources((CASE,))[0].entries(tmp_path)}
    assert entries == {"Complaint.pdf.txt": "", "Memo.docx.txt": "Memo.docx: the file's own words", "Order.pdf.md": ""}

    # When the PDF's layer is the longer text, the extract is written and the note beside it is not indexed twice.
    (files / "Order.pdf.md").write_text("# Order.pdf\n\n- drive_id: made-up\n", encoding="utf-8")
    assert extract_text(tmp_path, CASE, engines=()).extracted == {"text layer": 1}
    plan = index_sources((CASE,))[0].plan(tmp_path)
    assert sorted(e.path.name for e in plan.entries) == ["Complaint.pdf.txt", "Memo.docx.txt", "Order.pdf.txt"]
    assert plan.left_out == {"a note beside a file whose extract holds its words": 1}


def test_the_vision_model_reads_only_when_asked_and_holds_the_gpu_lock(tmp_path: Path, monkeypatch) -> None:
    from jason import local_ai, locks
    from jason.tasks.case_files import extract_text, vision_reader

    files = _files(tmp_path)
    _pdf(files / "Scan.pdf", _scanned_page)
    _pdf(files / "Typed.pdf", _typed_page)
    local = FakeOcr()
    assert extract_text(tmp_path, CASE, engines=(local,)).extracted == {"OCR: fake-ocr": 1, "text layer": 1}

    class Vision(FakeOcr):
        name, model = "fake-vision", "made-up-model"

        def text_of(self, path: Path) -> str:
            self.held = [h["lock"] for h in locks.holders()]
            return super().text_of(path)

    vision = Vision("The vision model's reading of the scanned notice about the gate camera and its thirty days.")
    report = extract_text(tmp_path, CASE, engines=(local,), vision=vision)
    # The typed file has no scanned page: it is never sent to the model. The scan is read again, under the GPU lock.
    assert report.extracted == {"vision model: made-up-model": 1} and report.unchanged == 1
    assert vision.given == ["page-0.pdf"] and vision.held == ["gpu"]
    (entry,) = [e for e in index_sources((CASE,))[0].entries(tmp_path) if e.path.name == "Scan.pdf.txt"]
    assert entry.context == "Scan.pdf: vision model: made-up-model; may misread"
    # A later run without the flag keeps the model's reading: local OCR never replaces it.
    assert extract_text(tmp_path, CASE, engines=(local,)).unchanged == 2 and len(local.given) == 1

    def refuse(model: str = "", **_kw) -> None:
        raise local_ai.LocalAIUnavailable("Ollama is running without the GPU")

    monkeypatch.setattr(local_ai, "preflight", refuse)
    try:
        vision_reader()
    except local_ai.LocalAIUnavailable as exc:
        assert "without the GPU" in str(exc)
    else:
        raise AssertionError("the vision reader runs the preflight first")


def test_fetch_keeps_the_extracts_rows_and_the_command_prints_the_counts(tmp_path: Path, monkeypatch, capsys) -> None:
    import argparse

    import jason.community
    import jason.config
    from jason.cli import cmd_cases
    from jason.tasks.case_files import extract_text

    _listing(tmp_path)
    _pdf(_files(tmp_path) / "Recordings" / "Minutes.pdf", _typed_page)
    extract_text(tmp_path, CASE, engines=())
    fetch(Drive(), tmp_path, CASE)
    manifest = _manifest(tmp_path)
    assert list(manifest["extracts"]) == ["Recordings/Minutes.pdf"] and len(manifest["files"]) == 7

    class Profile:
        def legal_cases(self):
            return (CASE, NO_FOLDER)

    monkeypatch.setattr(jason.community, "community", lambda: Profile())
    monkeypatch.setattr(jason.config, "data_dir", lambda env_file=None: tmp_path)
    monkeypatch.setattr("jason.community.ocr.local_engines", lambda: ())
    args = argparse.Namespace(fetch_files=False, extract_text=True, vision=False, case="26cv000001", include_held=False,
                              json=False)
    assert cmd_cases(args) == 0
    out = capsys.readouterr().out
    # The fetch's stand-in PDFs are not PDFs: each is listed, none is skipped in silence.
    assert "text: extracted 0, unchanged 1, held back 0, unreadable 3" in out
    assert "unreadable: Complaint.pdf (unreadable PDF" in out and "catalog case-example-26cv000001 (confidential)" in out
