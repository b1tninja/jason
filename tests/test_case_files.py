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
