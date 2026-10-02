"""Kinds from the agenda items that used a file: decided by text or by agreeing uses; else a suggestion or a conflict."""

from __future__ import annotations

import json
from pathlib import Path

from jason.tasks import agenda_kinds


def _items(tmp: Path, meetings: list[dict]) -> None:
    (tmp / "meetings").mkdir(parents=True, exist_ok=True)
    (tmp / "meetings" / "agenda-items.json").write_text(json.dumps({"meetings": meetings}), encoding="utf-8")


def _use(day, item, expects, *related):
    return {"date": day, "agenda": f"Agenda for {day}", "items": [{"item": item, "subitem": "", "expects": expects, "related": list(related)}]}


def _rel(ref, name, name_kind=None, where="PayHOA library"):
    return {"relation": "linked", "where": where, "ref": ref, "name": name, "path": f"x/{name}", "nameKind": name_kind}


def test_text_decides_among_the_items_kinds(tmp_path) -> None:
    _items(tmp_path, [_use("2026-07-07", "Review all open maintenance requests", ["proposal", "invoice", "inspection_report"],
                           _rel("11", "Industrial Door Company.pdf"))])
    (tmp_path / "library" / "text").mkdir(parents=True)
    (tmp_path / "library" / "text" / "11.txt").write_text("INDUSTRIAL DOOR COMPANY\nPROPOSAL\nScope of work: replace the garage door.",
                                                          encoding="utf-8")
    result = agenda_kinds.resolve(tmp_path)
    assert [(d["ref"], d["kind"], d["method"]) for d in result["decided"]] == [("11", "proposal", agenda_kinds.METHOD_TEXT)]
    assert agenda_kinds.decisions(tmp_path, "PayHOA library")["11"]["confidence"] == 0.8


def test_two_agreeing_uses_decide_but_one_use_only_suggests(tmp_path) -> None:
    _items(tmp_path, [
        _use("2025-04-15", "Reports from standing committees", ["committee_report"], _rel("c", "Maintenance Chart", where="Drive")),
        _use("2025-07-15", "Reports from standing committees", ["committee_report"], _rel("c", "Maintenance Chart", where="Drive")),
        _use("2024-09-17", "City of Sacramento - Water Usage Complaint", ["utility_bill"], _rel("w", "Courtesy Notice.pdf", where="Drive")),
    ])
    result = agenda_kinds.resolve(tmp_path)
    assert [d["ref"] for d in result["decided"]] == ["c"] and result["decided"][0]["method"] == agenda_kinds.METHOD_AGREE
    assert [s["ref"] for s in result["suggested"]] == ["w"]


def test_fetch_reads_only_undecided_drive_files_with_no_text_then_their_text_decides(tmp_path) -> None:
    _items(tmp_path, [
        _use("2023-04-18", "Domestic Water Booster Pump", ["proposal", "invoice", "inspection_report"],
             _rel("p1", "Odells - Tank Replacement.pdf", where="Drive"), _rel("d1", "Scope notes", where="Drive"))])
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps([
        {"id": "p1", "name": "Odells - Tank Replacement.pdf", "mimeType": "application/pdf"},
        {"id": "d1", "name": "Scope notes", "mimeType": "application/vnd.google-apps.document"}]), encoding="utf-8")
    agenda_kinds.resolve(tmp_path)

    class FakeDrive:
        def __init__(self):
            self.calls = []

        def download(self, file_id, dest):
            self.calls.append(("download", file_id))
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"%PDF")

        def export_pdf(self, file_id, dest):
            self.calls.append(("export", file_id))
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_bytes(b"%PDF")

    drive = FakeDrive()
    assert agenda_kinds.fetch(drive, tmp_path) == {"wanted": 2, "fetched": 2, "failed": 0}
    assert sorted(drive.calls) == [("download", "p1"), ("export", "d1")]
    assert agenda_kinds.fetch(drive, tmp_path)["fetched"] == 0          # kept on disk: not read again


def test_a_title_outside_the_items_kinds_decides_but_not_body_phrases_or_a_letters_quotes(tmp_path) -> None:
    item = ["treasurer_report", "financial_statement", "bank_statement"]
    _items(tmp_path, [_use("2024-02-06", "Delinquencies", item, _rel("p", "Assessment Collection Policy"),
                           _rel("e", "2016 - Email about Delinquent Taxes"), _rel("f", "Call for Candidates"))])
    text = tmp_path / "library" / "text"
    text.mkdir(parents=True)
    (text / "p.txt").write_text("ASSESSMENT COLLECTION POLICY\nThe board adopts this collection policy.", encoding="utf-8")
    (text / "e.txt").write_text("GRANT DEED\nForwarding the grant deed about the taxes.", encoding="utf-8")
    (text / "f.txt").write_text("Name\nDate:\nPhone\nEmail\nSignature", encoding="utf-8")
    result = agenda_kinds.resolve(tmp_path)
    assert [(d["ref"], d["kind"], d["method"]) for d in result["decided"]] == [("p", "policy", agenda_kinds.METHOD_TEXT_ONLY)]
    assert {s["ref"] for s in result["suggested"]} == {"e", "f"}


def test_a_named_kind_is_never_overridden_only_flagged(tmp_path) -> None:
    _items(tmp_path, [_use("2025-06-17", "Approval of minutes of previous meeting", ["minutes"],
                           _rel("a", "Agenda for 5/20/25", name_kind="agenda", where="Drive"))])
    result = agenda_kinds.resolve(tmp_path)
    assert not result["decided"] and result["conflicts"][0]["nameKind"] == "agenda"
    assert result["conflicts"][0]["agendaExpects"] == ["minutes"]
