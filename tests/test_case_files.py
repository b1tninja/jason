"""A legal case's file as its own AnythingLLM catalog: fetched from the Drive listing, medical records held back, never in
the shared workspace, synced only when named, and never moved into or out of the association's records."""

from __future__ import annotations

import json
from pathlib import Path

from jason.community.anythingllm import AnythingLLM
from jason.community.legal_cases import CaseRole, CaseStatus, Forum, LegalCase
from jason.tasks.anythingllm_sync import ask, chosen_catalogs, sync_catalogs
from jason.tasks.case_files import case_catalogs, fetch, plan

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


def test_the_plan_takes_what_anythingllm_reads_and_lists_the_rest(tmp_path: Path) -> None:
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


def test_a_case_catalog_is_its_own_and_is_synced_only_when_named() -> None:
    (catalog,) = case_catalogs((CASE, NO_FOLDER))
    assert (catalog.name, catalog.workspace) == ("case-example-26cv000001", "Case 26CV000001")
    assert catalog.confidential and catalog.explicit and not catalog.shared
    assert catalog not in chosen_catalogs((), (catalog,))
    assert chosen_catalogs(("case-example-26cv000001",), (catalog,)) == (catalog,)
    assert chosen_catalogs(("cases",), (catalog,)) == (catalog,)


def test_the_sync_keeps_a_case_out_of_the_shared_workspace_and_moves_nothing(tmp_path: Path) -> None:
    _listing(tmp_path)
    fetch(Drive(), tmp_path, CASE)
    catalogs = case_catalogs((CASE,))
    calls = []

    def portal(method, url, payload):
        calls.append((method, url, payload))
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "mystique", "name": "Mystique"}]}
        if url.endswith("/workspace/new"):
            return {"workspace": {"slug": payload["name"].lower().replace(" ", "-")}}
        if url.endswith("/documents"):
            # The same title already in the association's records must not be moved into the case.
            return {"localFiles": {"items": [{"type": "folder", "name": "association-records", "items": [
                {"type": "file", "name": "c.json", "title": "26CV000001: Complaint.pdf"}]}]}}
        return {"success": True}

    report = sync_catalogs(AnythingLLM(api_key="k", fetch=portal), tmp_path, None, names=("cases",), extra=catalogs)
    assert report.moved == [] and report.errors == []
    assert sorted(report.uploaded) == ["26CV000001: Complaint.pdf", "26CV000001: Defense Request.pdf", "26CV000001: Q_ what_.pdf",
                                       "26CV000001: Recordings/Meeting.transcript.vtt.txt"]
    uploads = [c for c in calls if "/document/upload/" in c[1]]
    assert {c[1].rsplit("/", 1)[-1] for c in uploads} == {"case-example-26cv000001"}
    assert {c[2]["addToWorkspaces"] for c in uploads} == {"case-26cv000001"}
    assert not any(c[1].endswith("/document/move-files") for c in calls)

    # Everything else never takes the case: a sync of all catalogs leaves it out.
    everything = sync_catalogs(AnythingLLM(api_key="k", fetch=portal), tmp_path, None, extra=catalogs)
    assert "case-example-26cv000001" not in everything.workspaces


def test_asking_a_case_labels_its_sources_confidential() -> None:
    def portal(method, url, payload):
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "case-26cv000001", "name": "Case 26CV000001"}]}
        if url.endswith("/chat"):
            return {"textResponse": "June 24.", "sources": [{"title": "26CV000001: Letter.pdf", "text": "preserve"}]}
        if url.endswith("/documents"):
            return {"localFiles": {"items": [{"type": "folder", "name": "case-example-26cv000001", "items": [
                {"type": "file", "name": "l.json", "title": "26CV000001: Letter.pdf"}]}]}}
        return {}

    result = ask(AnythingLLM(api_key="k", fetch=portal), "when?", catalog="case-example-26cv000001", extra=case_catalogs((CASE,)))
    assert result["sources"][0]["shelf"].startswith("case file") and "confidential" in result["note"]


def test_a_failed_chat_model_still_gives_the_retrieved_passages() -> None:
    searched = []

    def portal(method, url, payload):
        if url.endswith("/workspaces"):
            return {"workspaces": [{"slug": "case-26cv000001", "name": "Case 26CV000001"}]}
        if url.endswith("/chat"):
            return {"type": "abort", "textResponse": None, "sources": [],
                    "error": "AnythingLLM::getChatCompletion failed to communicate with AnythingLLM internal ollama. cudaMalloc failed"}
        if url.endswith("/vector-search"):
            searched.append(payload["query"])
            return {"results": [{"text": "preserve all video", "score": 0.59, "metadata": {"title": "26CV000001: Letter.pdf"}}]}
        if url.endswith("/documents"):
            return {"localFiles": {"items": [{"type": "folder", "name": "case-example-26cv000001", "items": [
                {"type": "file", "name": "l.json", "title": "26CV000001: Letter.pdf"}]}]}}
        return {}

    result = ask(AnythingLLM(api_key="k", fetch=portal), "what to preserve?", catalog="case-example-26cv000001",
                 extra=case_catalogs((CASE,)))
    assert searched == ["what to preserve?"] and result["answer"] == "" and "cudaMalloc" in result["modelError"]
    assert result["sources"][0]["title"] == "26CV000001: Letter.pdf" and result["sources"][0]["shelf"].startswith("case file")
    assert result["note"].startswith("AnythingLLM's chat model failed")
