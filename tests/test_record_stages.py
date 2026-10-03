"""Revision histories of rule changes (Civil Code 4360) and minutes (4950), from made-up meetings and rule changes."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.base import MeetingSchedule
from jason.community.record_stages import (Approval, Evidence, MeetingKind, MinutesCopy, MinutesHistory, Outcome,
                                           RuleChangeRecord, Standing, Strength, approval_items, file_stage,
                                           minutes_versions, named_dates, notice_clock, rule_change_history)
from jason.community.revisions import Stage
from jason.community.rule_changes import RuleChange, SectionChange
from jason.tasks import record_stages as rs

SCHEDULE = MeetingSchedule(weekday=2, nth=2, time="6:30 pm", place="Example Hall")


# ---------------------------------------------------------------------------------------------------------------
# Pure: dates, approval items, clocks, versions.


def test_named_dates_reads_the_forms_minutes_use():
    text = "See: Minutes of 1/8/31 and Minutes of 2_12_31; Minutes of Previous Meeting dated October 17th, 2030"
    assert named_dates(text) == [date(2031, 1, 8), date(2031, 2, 12), date(2030, 10, 17)]


def test_an_approval_item_is_stated_listed_corrected_or_previous():
    listed = approval_items("I. Call to Order II. Approval of minutes of previous meeting See: Minutes of 1/8/31 "
                            "III. Treasurer's Report")
    assert [(i.dates, i.stated) for i in listed] == [((date(2031, 1, 8),), False)]
    stated = approval_items("III. Approval of minutes of Previous Meeting The board approved the minutes of the "
                            "previous meeting. See: Minutes 12/10/30 IV. Meeting Schedule")
    assert stated[0].stated and stated[0].dates == (date(2030, 12, 10),)
    corrected = approval_items("II. Approval of minutes Minutes of 1/8/31 approved as corrected. III. Reports")
    assert corrected[0].corrected and corrected[0].stated
    previous = approval_items("2. Approval of the minutes of the previous meeting. M/S/P 3. Reports")
    assert previous[0].previous and previous[0].stated and not previous[0].dates
    # A legend for the abbreviation is not a motion; a certificate's "true and correct" is not a correction.
    legend = approval_items("MSC - Motion seconded carried II. Approval of minutes See: Minutes of 1/8/31 III. Other. "
                            "The undersigned certifies this is a true and correct copy.")
    assert not legend[0].stated and not legend[0].corrected
    # An approval written anywhere ("they approved the minutes") marks the item stated.
    summary = approval_items("II. Approval of minutes See: Minutes of 1/8/31 III. Reports. Quick recap: the board "
                             "approved the January meeting minutes.")
    assert summary[0].stated


def test_file_stage_reads_a_rule_change_file_by_its_name():
    assert file_stage("Notice of Proposed Rule Change - Example") is Stage.PROPOSED
    assert file_stage("Notice of Adopted Rule Change 010131.pdf") is Stage.DISTRIBUTED
    assert file_stage("Example Rules 1.2.31.docx") is Stage.DRAFT


def _e(stage, on, strength=Strength.FILE, source="drive:example"):
    return Evidence(stage, f"example {stage.value}", source, on, strength)


def test_a_notice_clock_prefers_a_delivery_then_a_file():
    decided = date(2031, 2, 12)
    on = date(2031, 6, 1)
    met = notice_clock("rule-change-proposed", "CIV 4360(a)", decided,
                       [_e(Stage.PROPOSED, date(2031, 1, 2), Strength.DELIVERED)], on)
    assert met.standing is Standing.MET and met.deadline == date(2031, 1, 15)
    late = notice_clock("rule-change-proposed", "CIV 4360(a)", decided,
                        [_e(Stage.PROPOSED, date(2031, 1, 20), Strength.DELIVERED)], on)
    assert late.standing is Standing.LATE
    file_only = notice_clock("rule-change-adopted", "CIV 4360(c)", decided, [_e(Stage.DISTRIBUTED, date(2031, 2, 20))], on)
    assert file_only.standing is Standing.FILE_ONLY and file_only.deadline == date(2031, 2, 27)
    assert notice_clock("rule-change-adopted", "CIV 4360(c)", decided, [], on).standing is Standing.PASSED
    assert notice_clock("rule-change-adopted", "CIV 4360(c)", decided, [], date(2031, 2, 20)).standing is Standing.OPEN
    assert notice_clock("rule-change-proposed", "CIV 4360(a)", None, [], on).standing is Standing.NOT_DUE


def test_an_adopted_rule_change_has_its_versions_clocks_and_reversal_window():
    record = RuleChangeRecord("example-2031", "Example rule", "example-rules", "Example Rules",
                              decided=date(2031, 2, 12))
    h = rule_change_history(record, [
        _e(Stage.DRAFT, date(2030, 12, 20), source="drive:text"),
        _e(Stage.PROPOSED, date(2031, 1, 5), source="drive:notice"),
        _e(Stage.PROPOSED, date(2031, 1, 6), Strength.DELIVERED, source="PayHOA communications: notice"),
        Evidence(Stage.ADOPTED, "the minutes of 2031-02-12", "Minutes of 2/12/31", date(2031, 2, 12), Strength.STATED),
        _e(Stage.DISTRIBUTED, date(2031, 2, 20), Strength.DELIVERED, source="PayHOA communications: adopted"),
    ], on=date(2031, 6, 1))
    labels = [f"{v.book}{v.label()}" for v in h.versions]
    assert labels == ["example-rules@draft-2030-12-20", "example-rules@proposed-2031-01-06", "example-rules@2031-02-12",
                      "example-rules@distributed-2031-02-20"]
    proposed = h.versions[1]
    assert proposed.source == "drive:notice" and not proposed.in_force_on(date(2031, 6, 1))   # never in force
    assert h.versions[2].in_force_on(date(2031, 6, 1))
    assert [c.standing for c in h.clocks] == [Standing.MET, Standing.MET]
    assert "2031-03-22" in h.reversal and not h.actions
    assert h.stages_with_evidence() == {"draft": "file", "proposed": "delivered", "adopted": "stated",
                                        "distributed": "delivered"}


def test_a_rule_change_with_no_notices_on_record_asks_a_person():
    record = RuleChangeRecord("example-2030", "Example rule", "example-rules", "Example Rules", decided=date(2030, 5, 14))
    h = rule_change_history(record, [], on=date(2031, 6, 1))
    assert [c.standing for c in h.clocks] == [Standing.PASSED, Standing.PASSED]
    assert len(h.actions) == 2 and "not shown" in h.reversal
    emergency = rule_change_history(RuleChangeRecord("e", "Emergency", "example-rules", "Example Rules",
                                                     decided=date(2030, 5, 14), emergency=True), [], on=date(2031, 6, 1))
    assert emergency.clocks[0].standing is Standing.NOT_APPLICABLE and "4365(h)" in emergency.reversal


def test_a_pending_proposal_long_without_a_decision_is_an_action():
    record = RuleChangeRecord("pending", "Pending", "example-rules", "Example Rules", outcome=Outcome.PENDING)
    h = rule_change_history(record, [_e(Stage.PROPOSED, date(2030, 1, 5), source="drive:notice")], on=date(2031, 6, 1))
    assert h.versions[0].label() == "@proposed-2030-01-05"
    assert h.clocks[0].standing is Standing.NOT_DUE and any("no decision" in a for a in h.actions)


def test_executive_session_minutes_show_only_existence_and_date():
    copy = MinutesCopy("Executive minutes about a member", "Drive", "drive:secret", date(2031, 2, 1), confidential=True)
    assert copy.row() == {"kind": "executive session minutes", "date": "2031-02-01"}
    assert "member" not in copy.label()


def test_minutes_versions_draft_approved_corrected():
    h = MinutesHistory(date(2031, 1, 8), MeetingKind.BOARD, "on record", [
        MinutesCopy("Minutes of 1/8/31", "Drive", "drive:doc", date(2031, 1, 10)),
        MinutesCopy("Minutes of 1_8_31.pdf", "PayHOA library", "library:1", None),
    ], [Approval(date(2031, 2, 12), "Minutes of 2/12/31", True, False, ""),
        Approval(date(2031, 3, 12), "Minutes of 3/12/31", True, True, "")])
    versions = minutes_versions(h)
    assert [v.label() for v in versions] == ["@draft-2031-01-10", "@2031-02-12", "@2031-03-12"]
    assert [v.stage for v in versions] == [Stage.DRAFT, Stage.APPROVED, Stage.CORRECTED]
    assert versions[1].source == "library:1" and versions[0].book == "min" and versions[0].item == "2031-01-08"


# ---------------------------------------------------------------------------------------------------------------
# From disk: a made-up association.


def _rec(kind, where, name, sent="", ref="", confidential=False):
    return {"kind": kind, "where": where, "name": name, "ref": ref, "sent": sent, "note": "",
            "confidential": confidential}


def _meeting(day, *records):
    has = {}
    for r in records:
        has.setdefault(r["kind"], {}).setdefault(r["where"], 0)
        has[r["kind"]][r["where"]] += 1
    return {"date": day, "titles": [], "has": has, "records": list(records)}


MINUTES_TEXT = {
    "jan": "Minutes of 1/8/31\nI. Call to Order II. Approval of minutes of previous meeting See: Minutes of 12/10/30 "
           "III. Treasurer's Report",
    "feb": "Minutes of 2/12/31\nI. Call to Order II. Approval of minutes of previous meeting​ See: Minutes of 1/8/31 "
           "III. Example Rules: after considering members' comments the board adopted the proposed rule change. "
           "IV. Open Forum",
    "mar": "Minutes of 3/12/31\nI. Call to Order II. Approval of minutes The board approved the minutes of "
           "2/12/31 as corrected. III. Parking: the board discussed a fine schedule for later.",
}


@pytest.fixture
def data(tmp_path):
    root = tmp_path
    (root / "meetings" / "minutes-files").mkdir(parents=True)
    (root / "meetings" / "catalog.json").write_text(json.dumps({"builtAt": "2031-05-01T00:00:00+00:00", "meetings": [
        _meeting("2031-01-08", _rec("meeting notice", "PayHOA communication", "Board meeting", "2031-01-02T18:00:00Z"),
                 _rec("minutes", "Drive", "Minutes of 1/8/31", ref="jan")),
        _meeting("2031-02-12", _rec("meeting notice", "PayHOA communication", "Board meeting", "2031-02-06T18:00:00Z"),
                 _rec("minutes", "Drive", "Minutes of 2/12/31", ref="feb"),
                 _rec("minutes", "Drive", "Executive Session Minutes 2/12/31 Example Owner", ref="exec",
                      confidential=True)),
        _meeting("2031-02-20", _rec("meeting notice", "PayHOA communication", "Executive session",
                                    "2031-02-18T18:00:00Z"),
                 _rec("minutes", "Drive", "Executive Minutes 2/20/31 Example Owner", ref="exec2", confidential=True)),
        _meeting("2031-03-12", _rec("meeting notice", "PayHOA communication", "Board meeting", "2031-03-06T18:00:00Z"),
                 _rec("minutes", "Drive", "Minutes of 3/12/31", ref="mar")),
        _meeting("2031-04-09", _rec("meeting notice", "PayHOA communication", "Board meeting", "2031-04-03T18:00:00Z"),
                 _rec("transcript", "jason", "Example (transcript)")),
    ]}), encoding="utf-8")
    readings = []
    for key, day in (("jan", "2031-01-08"), ("feb", "2031-02-12"), ("mar", "2031-03-12")):
        (root / "meetings" / "minutes-files" / f"{key}.txt").write_text(MINUTES_TEXT[key], encoding="utf-8")
        readings.append({"id": f"drive-{key}", "kind": "minutes", "hasText": True, "period": day,
                         "name": f"Minutes of {day}"})
    (root / "meetings" / "minutes-files" / "exec.txt").write_text("Example Owner's hearing", encoding="utf-8")
    readings.append({"id": "drive-exec", "kind": "minutes", "hasText": True, "period": "2031-02-12",
                     "name": "Executive Session Minutes 2/12/31 Example Owner", "confidential": True})
    (root / "documents").mkdir()
    (root / "documents" / "readings.json").write_text(json.dumps({"readings": readings}), encoding="utf-8")
    (root / "zoom").mkdir()
    (root / "zoom" / "meetings.json").write_text(json.dumps({"meetings": [
        {"date": "2031-01-08", "kind": "board meeting"}, {"date": "2031-02-12", "kind": "board meeting"},
        {"date": "2031-02-20", "kind": "executive session"}, {"date": "2031-03-12", "kind": "board meeting"},
        {"date": "2031-04-09", "kind": "board meeting"}]}), encoding="utf-8")
    (root / "drive").mkdir()
    (root / "drive" / "files.json").write_text(json.dumps({"files": [
        {"id": "jan", "name": "Minutes of 1/8/31", "created": "2031-01-12T18:00:00Z"},
        {"id": "feb", "name": "Minutes of 2/12/31", "created": "2031-03-20T18:00:00Z"},
        {"id": "mar", "name": "Minutes of 3/12/31", "created": "2031-03-13T18:00:00Z"},
        {"id": "exec", "name": "Executive Session Minutes 2/12/31 Example Owner", "created": "2031-02-13T18:00:00Z"},
        {"id": "exec2", "name": "Executive Minutes 2/20/31 Example Owner", "created": "2031-02-21T18:00:00Z"},
        {"id": "text", "name": "Example Rules 12.20.30.docx", "path": "My Drive/Rules/Example Rules 12.20.30.docx",
         "created": "2030-12-20T00:00:00Z", "modified": "2030-12-21T18:00:00Z"},
        {"id": "pn", "name": "Notice of Proposed Rule Change - Example Rules", "path": "My Drive/Notices/x",
         "created": "2031-01-05T18:00:00Z", "modified": "2031-01-05T18:00:00Z"},
        {"id": "other", "name": "Notice of Proposed Rule Change - Something Else", "path": "My Drive/Notices/y",
         "created": "2031-03-01T18:00:00Z"},
        {"id": "audio", "name": "Notice of Proposed Rule Change.mp3", "mimeType": "audio/mpeg"},
    ]}), encoding="utf-8")
    (root / "payhoa").mkdir()
    (root / "payhoa" / "communications.json").write_text(json.dumps({"notices": [
        {"sent": "2031-01-06T18:00:00Z", "subject": "Notice of Proposed Rule Change - Example Rules"},
        {"sent": "2031-02-20T18:00:00Z", "subject": "Notice of Adopted Rule Change - Example Rules"},
    ]}), encoding="utf-8")
    (root / "schedule").mkdir()
    (root / "schedule" / "google-read.json").write_text(json.dumps({"tasklists": [{"title": "Tasks", "tasks": [
        {"id": "t1", "title": "Send Notice of Proposed Rule Change", "notes": "Pending Rules", "due": "2031-03-01",
         "status": "needsAction"}]}]}), encoding="utf-8")
    return root


def _community():
    records = (
        RuleChangeRecord("example-2031", "Example Rules revised", "example-rules", "Example Rules",
                         files=r"Example Rules", words=("adopted the proposed rule change",),
                         decided=date(2031, 2, 12)),
        RuleChangeRecord("pending-2031", "Pending rules", "pending-rules", "Pending Rules", outcome=Outcome.PENDING,
                         tasks=r"pending rules"),
    )
    draft = RuleChange("draft-change", "A draft change", "draft-rules", "Draft Rules", "purpose", "effect",
                       (SectionChange("1", "One", "New words."),))
    return SimpleNamespace(rule_change_records=lambda: records, rule_changes=lambda: (draft,),
                           meeting_schedule=lambda: SCHEDULE, notice_provisions=lambda: (), hearing_policy=lambda: None)


ON = date(2031, 6, 1)


def test_rule_change_histories_from_disk(data):
    found = {h.key: h for h in rs.rule_change_histories(_community(), data, on=ON)}
    assert set(found) == {"example-2031", "pending-2031", "draft-change"}
    h = found["example-2031"]
    assert [v.label() for v in h.versions] == ["@draft-2030-12-20", "@proposed-2031-01-06", "@2031-02-12",
                                               "@distributed-2031-02-20"]
    assert h.versions[0].source == "drive:text"
    assert h.versions[1].source == "drive:pn"               # a proposed version cites the file that holds its words
    assert [c.standing for c in h.clocks] == [Standing.MET, Standing.MET]
    assert h.stages_with_evidence()["adopted"] == "stated"
    assert "2031-03-22" in h.reversal
    pending = found["pending-2031"]
    assert any("Google Task" in a for a in pending.actions)
    draft = found["draft-change"]
    assert draft.origin == "specification" and draft.versions[0].stage is Stage.DRAFT
    assert draft.versions[0].source == "specification:rule_changes/draft-change"


def test_leads_name_files_no_row_claims(data):
    found = rs.leads(_community(), data)
    assert [f["source"] for f in found["files"]] == ["drive:other"]      # the audio file is not a notice
    assert [p["date"] for p in found["minutes"]] == ["2031-03-12"]


def test_minutes_histories_from_disk(data):
    found = {h.day.isoformat(): h for h in rs.minutes_histories(_community(), data, on=ON)}
    jan = found["2031-01-08"]
    assert jan.clock.standing is Standing.MET and jan.approval == "listed"
    assert [v.label() for v in jan.versions] == ["@draft-2031-01-12", "@2031-02-12"]
    feb = found["2031-02-12"]
    assert feb.clock.standing is Standing.LATE and feb.approval == "stated"
    assert [v.stage for v in feb.versions] == [Stage.CORRECTED]          # its only copy is dated after the approval
    # The executive session's minutes on a board day, and a meeting held solely in executive session.
    assert {"kind": "executive session minutes", "date": "2031-02-13"} in [c.row() for c in feb.copies]
    executive = found["2031-02-20"]
    assert executive.kind is MeetingKind.EXECUTIVE and executive.clock is None and not executive.approvals
    assert [c.row() for c in executive.copies] == [{"kind": "executive session minutes", "date": "2031-02-21"}]
    april = found["2031-04-09"]
    assert april.clock.standing is Standing.PASSED and april.actions
    summary = rs.minutes_summary(list(found.values()))
    assert summary["boardMeetings"] == 4 and summary["draftOnTime"] == 2 and summary["executiveOnly"] == 1
    assert summary["approval"] == {"stated": 1, "listed": 1, "none": 2} and summary["neither"] == 1


def test_a_shared_output_never_carries_executive_session_names(data):
    result = rs.histories(_community(), data, on=ON)
    text = json.dumps(result)
    assert "Example Owner" not in text and "exec" not in text.replace("executive", "")
    lines = "\n".join(rs.lines(result, rs.rule_change_histories(_community(), data, on=ON),
                               rs.minutes_histories(_community(), data, on=ON)))
    assert "Example Owner" not in lines


def test_the_command_reads_and_prints(data, monkeypatch, capsys):
    import argparse

    from jason.commands import record_stages as command

    monkeypatch.setattr(command, "_data_dir", lambda args: data)
    monkeypatch.setattr("jason.community.community", _community)
    args = argparse.Namespace(env=None, as_of="2031-06-01", since="2031-01-01", meeting="2031-02-12", change=None,
                              rules=False, minutes=False, json=False)
    assert command.cmd_record_stages(args) == 0
    out = capsys.readouterr().out
    assert "min/2031-02-12@2031-03-12" in out and "Example Owner" not in out
