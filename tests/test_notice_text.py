"""A notice's words kept with it (jason.tasks.notice_text) and read back by its record (jason://notice/KEY): a made-up
broadcast and a made-up rule-change draft, each with its text, subject, fill records, and digest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.record_stages import RuleChangeRecord
from jason.community.rule_changes import RuleChange, SectionChange
from jason.tasks import broadcast
from jason.tasks import notice_record as nr
from jason.tasks import notice_text as nt
from jason.tasks import rule_change as rc

ON = date(2099, 2, 20)
BROADCAST_KEY = "board-meeting-2099-01-14"
MESSAGE = ("<p>Dear <span class=\"placeholder\">{first name}</span>,</p><p>Notice of the board meeting of January 14, "
           "2099, at 7 p.m. at 123 Main St.</p><blockquote>Section 4.2(b): the words of the example clause.</blockquote>")
FILL = {"token": "{QUOTE:decl#4.2(b)}", "verb": "QUOTE", "key": "decl", "section": "4.2(b)", "as_of": "",
        "citation": "Declaration Section 4.2(b)", "set_by": "", "set_by_title": "the declaration", "dated": "",
        "digest": "0123456789abcdef", "note": ""}


def _community(rows=()):
    return SimpleNamespace(notice_provisions=lambda: (), hearing_policy=lambda: None, living_documents=lambda: (),
                           citable_documents=lambda: (), rule_change_records=lambda: rows, rule_changes=lambda: ())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _found():
    return broadcast.Recipients(unit_tags=["Building 9"], unit_ids=[901, 902], unit_labels=["123 Main St"],
                                membership_ids=[11, 12, 13], invalid_email=[13])


def test_a_broadcast_saved_for_sending_keeps_its_words_and_its_record_shows_them(tmp_path):
    entry = broadcast.keep_notice(tmp_path, BROADCAST_KEY, message=MESSAGE, subject="Board meeting January 14",
                                  refs=[FILL], found=_found(), state="saved as PayHOA template 7 for a person to send",
                                  by="A Secretary")
    folder = tmp_path / "notices" / BROADCAST_KEY
    assert (folder / "message.html").read_text(encoding="utf-8") == MESSAGE
    assert entry["files"][0] == {"path": "message.html", "role": "text", "sha256": _sha(MESSAGE)}
    plan = json.loads((folder / "recipients.json").read_text(encoding="utf-8"))
    assert plan["notice"] == "board-meeting" and plan["emailMembershipIds"] == [11, 12] and len(plan["mail"]) == 1
    assert "123 Main St" not in json.dumps(plan)                         # ids only: no unit's address
    # the same words kept again add nothing
    broadcast.keep_notice(tmp_path, BROADCAST_KEY, message=MESSAGE, subject="Board meeting January 14", refs=[FILL],
                          found=_found(), state="saved as PayHOA template 7 for a person to send")
    assert len(nt.load(tmp_path, BROADCAST_KEY)["entries"]) == 1

    r = nr.build(BROADCAST_KEY, community=_community(), data_dir=tmp_path, today=ON)
    text = r["text"]
    assert text["words"] == MESSAGE and text["digest"] == _sha(MESSAGE) and text["edited"] is False
    assert text["source"] == f"data/notices/{BROADCAST_KEY}/message.html"
    assert text["subjects"] == ["Board meeting January 14"]
    assert text["fills"][0]["digest"] == "0123456789abcdef" and text["fills"][0]["citation"] == FILL["citation"]
    assert text["kept"][0]["state"].startswith("saved as PayHOA template 7")
    assert r["recipients"]["plan"]["emails"] == 2 and r["recipients"]["plan"]["letters"] == 1
    lines = dict(nr.sections(r))["The notice as sent"]
    assert any(f"sha256 {_sha(MESSAGE)[:16]}: unchanged since it was kept" in ln for ln in lines)
    assert r["proof"]["requirement"] == "board-meeting"

    # an edit after it was kept is detectable, and the edited words are not the text as sent
    (folder / "message.html").write_text(MESSAGE.replace("7 p.m.", "8 p.m."), encoding="utf-8")
    r = nr.build(BROADCAST_KEY, community=_community(), data_dir=tmp_path, today=ON)
    assert r["text"]["edited"] is True and r["text"]["digest"] == _sha(MESSAGE)
    assert any("EDITED since it was kept" in ln for ln in dict(nr.sections(r))["The notice as sent"])


def test_other_words_under_the_same_key_are_kept_beside_never_over(tmp_path):
    nt.keep(tmp_path, BROADCAST_KEY, kind="broadcast", state="saved", body="first", subject="S")
    nt.keep(tmp_path, BROADCAST_KEY, kind="broadcast", state="saved", body="second", subject="S")
    folder = tmp_path / "notices" / BROADCAST_KEY
    assert (folder / "message.html").read_text(encoding="utf-8") == "first"
    assert (folder / "message-2.html").read_text(encoding="utf-8") == "second"
    assert nt.notice_key("owner-info-2099-email-test-20990101-1200") is None
    assert nt.notice_key("owner-info-2099-email-resend-a") == "owner-info-2099-email"
    with pytest.raises(nt.NoticeKeyError):
        nt.folder(tmp_path, "../elsewhere")


def test_a_broadcast_dry_run_keeps_nothing(tmp_path, monkeypatch, capsys):
    from jason.commands import broadcast as command

    monkeypatch.setattr(command, "_data_dir", lambda args: tmp_path)
    args = argparse.Namespace(notice=BROADCAST_KEY, yes=False, by="", file="notice.md", catalog_synced="")
    checked = broadcast.check(MESSAGE, "Board meeting January 14")
    assert command._keep_notice(args, MESSAGE, "Board meeting January 14", [FILL], None, [], checked, "saved") == {}
    assert "would keep" in capsys.readouterr().out and not (tmp_path / "notices").exists()
    args.yes = True
    assert command._keep_notice(args, MESSAGE, "Board meeting January 14", [FILL], None, [], checked, "saved")
    assert (tmp_path / "notices" / BROADCAST_KEY / "message.html").is_file()


def test_a_rule_change_draft_keeps_its_notice_and_its_record_shows_it(tmp_path):
    change = RuleChange("example", "Example rule", "example-rules", "Example Rules", "To be clear.", "Owners know.",
                        (SectionChange("R-2", "Guests", proposed="Guests park in marked spaces only."),))
    when = rc.timeline(None, notice_date=date(2099, 1, 3), decision=date(2099, 2, 11))
    recitals = {"R-2": rc.Recital("R-2", "Guests park anywhere.", "Example Rules R-2", "jason://example-rules/R-2",
                                  "", "adopted 2098-06-01", "shelf")}
    notice = rc.member_notice(change, when, rc.words_of(recitals), "Example Commons Owners Association")
    version = rc.proposed_version(change, when, book="example-rules")
    key = rc.notice_key(change, when)
    assert key == "rule-change-proposed-example-2099-01-03"
    rc.keep_notice(tmp_path, key, notice, change, recitals=recitals, version=version,
                   state="saved as Gmail draft d-1 with no recipients, for a person to address and send")

    record = RuleChangeRecord("example", "Example rule", "example-rules", "Example Rules", decided=date(2099, 2, 11))
    r = nr.build(key, community=_community((record,)), data_dir=tmp_path, today=ON)
    text = r["text"]
    assert text["words"] == notice.text and "THE TEXT OF THE PROPOSED RULE CHANGE" in text["words"]
    assert text["digest"] == _sha(notice.text) and text["edited"] is False
    assert text["subjects"] == [notice.subject]
    recited = next(f for f in text["fills"] if f["section"] == "R-2")
    assert recited["digest"] == nt.words_digest("Guests park anywhere.") and recited["citation"] == "Example Rules R-2"
    assert any(f["citation"] == "jason://example-rules@proposed-2099-01-03" for f in text["fills"])
    assert r["requirement"]["key"] == "rule-change-proposed"
    assert r["stage"]["ruleChange"] == "example" and r["stage"]["stage"] == "proposed"
    assert any("Gmail draft d-1" in ln for ln in dict(nr.sections(r))["The notice as sent"])
