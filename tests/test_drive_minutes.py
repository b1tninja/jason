"""Minutes the library lacks, read from Drive: the Doc before its PDF export, one per meeting, never one already read."""

from __future__ import annotations

import json

from jason.tasks.drive_minutes import DOC_MIME, wanted


def test_one_copy_per_unread_meeting_the_google_doc_first(tmp_path) -> None:
    (tmp_path / "meetings").mkdir()
    (tmp_path / "meetings" / "catalog.json").write_text(json.dumps({"meetings": [
        {"date": "2024-12-17", "records": [{"kind": "minutes", "where": "Drive", "ref": "pdf1", "name": "Minutes of 12_17_24.pdf"},
                                           {"kind": "minutes", "where": "Drive", "ref": "doc1", "name": "Minutes of 12/17/24"}]},
        {"date": "2025-01-21", "records": [{"kind": "minutes", "where": "Drive", "ref": "pdf2", "name": "Minutes of 1_21_25.pdf"}]},
        {"date": "2025-02-18", "records": [{"kind": "agenda", "where": "Drive", "ref": "a3", "name": "Agenda"}]},
    ]}), encoding="utf-8")
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps([
        {"id": "pdf1", "mimeType": "application/pdf"}, {"id": "doc1", "mimeType": DOC_MIME}, {"id": "pdf2", "mimeType": "application/pdf"}]),
        encoding="utf-8")
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "readings.json").write_text(json.dumps({"readings": [
        {"id": "9", "kind": "minutes", "name": "Minutes of 1_21_25.pdf"}]}), encoding="utf-8")
    assert [(w["date"], w["ref"]) for w in wanted(tmp_path)] == [("2024-12-17", "doc1")]
