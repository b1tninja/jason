"""The legal hold: its scope from disk, the register that survives a rebuild, the Vault plan, labels, and writes gated."""

from __future__ import annotations

import json
from datetime import date

import pytest

from jason.community.holds import LegalHoldSpec
from jason.tasks import legal_hold as task

SPEC = LegalHoldSpec(key="t1", case="case-1", title="Mystique - T1", duty_from=date(2025, 6, 24), relevant_from=date(2025, 4, 1),
                     custodians=("secretary@mystiquecommunity.com",), terms=("dog", "1234 Sample"),
                     drive_folders=("F1",), notice_to=("each director",), suspends=("recording deletion",),
                     outside_vault=("personal email",), counsel="Defense counsel")


class Community:
    def legal_holds(self):
        return (SPEC,)


def _disk(tmp):
    (tmp / "drive").mkdir()
    (tmp / "drive" / "files.json").write_text(json.dumps([
        {"id": "a", "name": "Police report.pdf", "path": "My Drive/Case/Police report.pdf", "folderId": "F1", "md5": "m"},
        {"id": "b", "name": "Notice of Violation - 1234 Sample Walk", "path": "My Drive/Disciplinary/Notice", "folderId": "D"},
        {"id": "c", "name": "Pool schedule.pdf", "path": "My Drive/Pool schedule.pdf", "folderId": "X"},
    ]), encoding="utf-8")
    folder = tmp / "zoom" / "meetings" / "2025-06-17-x"
    folder.mkdir(parents=True)
    (folder / "transcript.txt").write_text("[0:10:00] Chair: the dog got loose again", encoding="utf-8")
    (tmp / "zoom" / "meetings.json").write_text(json.dumps({"meetings": [
        {"uuid": "u1", "date": "2025-06-17", "topic": "Regular Meeting", "folder": "meetings/2025-06-17-x",
         "files": {"transcript": "meetings/2025-06-17-x/transcript.txt"}, "cloud": ["MP4", "TRANSCRIPT"]},
        {"uuid": "u0", "date": "2025-03-18", "topic": "Regular Meeting", "folder": "meetings/old", "files": {}}]}), encoding="utf-8")
    (tmp / "gmail").mkdir()
    (tmp / "gmail" / "correspondence.json").write_text(json.dumps({"messages": [
        {"messageId": "m1", "threadId": "t1", "at": "2025-06-25T10:00:00+00:00", "subject": "Dog bite follow-up"},
        {"messageId": "m2", "threadId": "t2", "at": "2025-06-25T10:00:00+00:00", "subject": "Landscaping"}]}), encoding="utf-8")
    (tmp / "gmail" / "files").mkdir()
    (tmp / "gmail" / "files" / "photo.jpg").write_bytes(b"jpeg")
    (tmp / "gmail" / "files.json").write_text(json.dumps([{"messageId": "m1", "name": "photo.jpg", "path": "gmail/files/photo.jpg",
                                                          "sha256": "s"}]), encoding="utf-8")


def test_scope_reaches_the_folder_the_named_files_the_meetings_and_the_mail(tmp_path) -> None:
    _disk(tmp_path)
    found = task.scope(tmp_path, Community(), SPEC)
    assert set(found["driveIds"]) == {"a", "b"}                       # the pool schedule is not in scope
    assert found["counts"]["Zoom cloud"] == 2 and found["counts"]["jason's copy"] == 1
    gmail = next(i for i in found["items"] if i["where"] == "Gmail")
    assert gmail["name"].startswith("1 messages") and found["counts"]["Gmail attachment"] == 1


def test_the_register_keeps_the_boards_record_across_rebuilds_and_flags_a_changed_copy(tmp_path) -> None:
    _disk(tmp_path)
    reg = task.build_register(tmp_path, Community(), SPEC)
    assert reg["notices"] == [{"to": "each director", "sent": None, "acknowledged": None}]
    reg["notices"][0]["sent"] = "2026-10-01"
    reg["vault"] = {"matterId": "M1", "holds": []}
    task.save_register(tmp_path, reg)
    (tmp_path / "gmail" / "files" / "photo.jpg").write_bytes(b"changed")
    again = task.build_register(tmp_path, Community(), SPEC)
    assert again["notices"][0]["sent"] == "2026-10-01" and again["vault"]["matterId"] == "M1"
    assert again["changedSinceLastScope"] == ["photo.jpg"]


def test_the_vault_plan_holds_drive_whole_and_mail_by_terms_and_writes_need_yes(tmp_path) -> None:
    plan = task.vault_plan(SPEC)
    assert [h["corpus"] for h in plan["holds"]] == ["DRIVE", "MAIL"]
    assert plan["holds"][1]["terms"] == 'dog OR "1234 Sample"' and plan["holds"][1]["start"] == "2025-04-01T00:00:00Z"
    assert task.vault_apply(None, tmp_path, SPEC, yes=False)["dryRun"]
    _disk(tmp_path)
    task.build_register(tmp_path, Community(), SPEC)
    dry = task.label(None, tmp_path, SPEC, yes=False)
    assert dry["dryRun"] and dry["wouldLabel"] == 2 and dry["sample"]["a"]["jason_hold"] == "t1"


def test_vault_apply_creates_the_matter_once_and_only_missing_holds(tmp_path) -> None:
    _disk(tmp_path)
    task.build_register(tmp_path, Community(), SPEC)

    class FakeVault:
        def __init__(self):
            self.made, self.held = [], []

        def matters(self, state=""):
            return iter([])

        def create_matter(self, name, description=""):
            self.made.append(name)
            return {"matterId": "M1", "name": name}

        def holds(self, matter_id):
            return iter(self.held)

        def create_hold(self, matter_id, name, corpus, emails, **kw):
            hold = {"holdId": f"H{len(self.held)}", "name": name, "corpus": corpus.value, "accounts": [{"email": e} for e in emails]}
            self.held.append(hold)
            return hold

    vault = FakeVault()
    out = task.vault_apply(vault, tmp_path, SPEC, yes=True)
    assert out["created"] == ["t1 Drive", "t1 Mail"] and vault.made == ["Mystique - T1"]
    assert task.load_register(tmp_path, "t1")["vault"]["matterId"] == "M1"


def test_notices_are_drafted_never_sent_and_the_custodian_writes_no_letter_to_self(tmp_path) -> None:
    from dataclasses import replace

    spec = replace(SPEC, notice_to=("each director", "the Secretary"), custodian_of_record="Pat Lee, Secretary",
                   counsel_attention="A. Lawyer", counsel_email="a@law.example", board_discussed="executive session")
    _disk(tmp_path)
    task.build_register(tmp_path, Community(), spec)
    planned = task.notices(spec, task.load_register(tmp_path, "t1"))
    assert [n["for"] for n in planned] == ["each director", "defense counsel"]
    director = planned[0]
    assert director["to"] == [] and director["text"].startswith("CONFIDENTIAL - EXECUTIVE SESSION")
    assert "As the board discussed in executive session" in director["text"] and "as a director" in director["text"]
    assert planned[1]["to"] == ["a@law.example"] and "Dear A. Lawyer," in planned[1]["text"]

    class FakeGmail:
        def __init__(self):
            self.saved = []

        def create(self, draft):
            self.saved.append(draft)
            return {"id": f"d{len(self.saved)}"}

    assert task.draft_notices(None, tmp_path, spec, yes=False)["dryRun"]
    gmail = FakeGmail()
    task.draft_notices(gmail, tmp_path, spec, yes=True)
    assert not hasattr(gmail, "send") and len(gmail.saved) == 2
    rows = {r["to"]: r for r in task.load_register(tmp_path, "t1")["notices"]}
    assert rows["each director"]["draftId"] == "d1" and rows["each director"].get("sent") is None
    assert rows["the Secretary"]["drafted"].startswith("no letter")


def test_no_hold_in_the_spec_is_an_error() -> None:
    class Empty:
        def legal_holds(self):
            return ()

    with pytest.raises(ValueError):
        task.hold_spec(Empty())
