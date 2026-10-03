"""The board meetings' clocks read forward: made-up meetings on a made-up schedule (the second Wednesday)."""

import argparse
import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.base import MeetingSchedule
from jason.community.notices import Anchor, Comparison, NoticeProvision, Timing
from jason.community.schedule import Anchor as ScheduleAnchor, Assignment, Role, Trigger
from jason.tasks import attention
from jason.tasks import meeting_watch as mw
from jason.tasks import schedule as schedule_task
from jason.tasks.attention import Urgency

S = mw.Standing
# The second Wednesday: 2031-01-08, 02-12, 03-12, 04-09, 05-14.
SCHEDULE = MeetingSchedule(weekday=2, nth=2, time="6:30 pm", place="Example Hall")
NOTICE = Assignment("meeting-notice", "Notice of each board meeting", Role.SECRETARY, ("notice:board-meeting",),
                    Trigger.ANCHORED, anchor=ScheduleAnchor.BOARD_MEETING, offset_days=-4)
MINUTES = Assignment("meeting-minutes", "Minutes within 30 days", Role.SECRETARY, ("notice:minutes-available",),
                     Trigger.ANCHORED, anchor=ScheduleAnchor.BOARD_MEETING, offset_days=30)


def _community(provisions=(), rows=(NOTICE, MINUTES)):
    return SimpleNamespace(meeting_schedule=lambda: SCHEDULE, assignments=lambda: rows, hearing_policy=lambda: None,
                           notice_provisions=lambda: provisions, fiscal_year_end=lambda: None)


def _rec(kind, where, name, sent="", ref=""):
    return {"kind": kind, "where": where, "name": name, "ref": ref, "sent": sent, "note": ""}


def _meeting(day, *records, titles=()):
    has = {}
    for r in records:
        has.setdefault(r["kind"], {}).setdefault(r["where"], 0)
        has[r["kind"]][r["where"]] += 1
    return {"date": day, "titles": list(titles), "has": has, "records": list(records)}


def _write(root, meetings, zoom=(), drive=()):
    (root / "meetings").mkdir(parents=True, exist_ok=True)
    (root / "meetings" / "catalog.json").write_text(json.dumps({"builtAt": "2031-03-01T00:00:00+00:00",
                                                                "meetings": meetings}), encoding="utf-8")
    (root / "zoom").mkdir(exist_ok=True)
    (root / "zoom" / "meetings.json").write_text(json.dumps({"meetings": [
        {"date": d, "kind": k, "topic": f"Example {k}"} for d, k in zoom]}), encoding="utf-8")
    if drive:
        (root / "drive").mkdir(exist_ok=True)
        (root / "drive" / "files.json").write_text(json.dumps({"files": [{"id": i, "created": c} for i, c in drive]}),
                                                  encoding="utf-8")


@pytest.fixture
def data(tmp_path):
    _write(tmp_path, [
        # January: the notice two days ahead, the minutes first sent 43 days after.
        _meeting("2031-01-08", _rec("meeting notice", "PayHOA communication", "Board meeting Jan 8",
                                    "2031-01-06T18:00:00Z"),
                 _rec("minutes", "Gmail", "Minutes of 1_8_31.pdf", "2031-02-20T18:00:00Z")),
        # February: noticed five days ahead; no minutes yet.
        _meeting("2031-02-12", _rec("meeting notice", "PayHOA communication", "Board meeting Feb 12",
                                    "2031-02-07T18:00:00Z"), _rec("transcript", "jason", "Example (transcript)")),
        # A meeting solely in executive session, noticed two days ahead.
        _meeting("2031-02-20", _rec("meeting notice", "PayHOA communication", "Executive session Feb 20",
                                    "2031-02-18T18:00:00Z")),
        # The members' annual meeting: not the board's clocks.
        _meeting("2031-02-25", _rec("transcript", "jason", "Annual meeting (transcript)")),
        # March: only jason's draft agenda so far.
        _meeting("2031-03-12", _rec("agenda", "jason draft", "agenda-2031-03-12.md")),
    ], zoom=[("2031-01-08", "board meeting"), ("2031-02-12", "board meeting"), ("2031-02-20", "executive session"),
             ("2031-02-25", "annual meeting of members")])
    return tmp_path


def _by_day(w):
    return {m.day.isoformat(): m for m in w.meetings}


def _clock(m, what):
    return next(c for c in m.clocks if c.what == what)


def test_each_meeting_its_clocks_and_what_is_on_record(data):
    w = mw.watch(_community(), data, on=date(2031, 3, 3))
    found = _by_day(w)
    # the annual meeting of members is left out; May is past the 60 days ahead
    assert sorted(found) == ["2031-01-08", "2031-02-12", "2031-02-20", "2031-03-12", "2031-04-09"]
    jan, feb, exe, mar, apr = (found[d] for d in sorted(found))
    assert _clock(jan, "notice").standing is S.LATE and "2 days before" in _clock(jan, "notice").note
    late = _clock(jan, "minutes")
    assert late.standing is S.LATE and late.deadline == date(2031, 2, 7) and "43 days after" in late.note
    assert _clock(feb, "notice").standing is S.MET and _clock(feb, "notice").on == date(2031, 2, 7)
    running = _clock(feb, "minutes")
    assert running.standing is S.OPEN and running.deadline == date(2031, 3, 14)
    assert running.assignment == "meeting-minutes" and running.due == date(2031, 3, 14)
    # held solely in executive session: two days' notice, and no open minutes owed
    assert exe.kind == "executive session only" and [c.what for c in exe.clocks] == ["notice"]
    assert _clock(exe, "notice").standing is S.MET and _clock(exe, "notice").authority == "CIV 4920(b)(2)"
    ahead = _clock(mar, "notice")
    assert ahead.standing is S.OPEN and ahead.deadline == date(2031, 3, 8) and ahead.authority == "CIV 4920(a)"
    assert ahead.assignment == "meeting-notice" and "set by the meeting schedule" in mar.basis
    assert [c.what for c in mar.clocks] == ["notice"] and _clock(apr, "notice").standing is S.OPEN
    out = w.as_dict()
    assert out["asOf"] == "2031-03-03" and out["caveats"] and any("2031-03-12" in line for line in w.lines())


def test_a_passed_clock_ranks_first_then_what_is_due_soon(data):
    s = attention.meetings_section(_community(), data, date(2031, 3, 3))
    items = s.ordered()
    assert [i.urgency for i in items] == [Urgency.LEGAL, Urgency.SOON, Urgency.SOON]
    assert "minutes were due to members by 2031-02-07" in items[0].text and "43 days after" in items[0].text
    assert items[1].due == date(2031, 3, 8) and "give members notice and the agenda by 2031-03-08" in items[1].text
    assert items[2].due == date(2031, 3, 14) and "[meeting-minutes]" in items[2].text
    assert all(i.command == mw.COMMAND for i in items)
    # January's late notice is older than the 30 days behind: the evidence finder's to read, not the digest's
    assert not any("notice to members on record" in i.text for i in items)
    assert s.summary.startswith("Next: board meeting 2031-03-12, notice by 2031-03-08 (none on record yet).")
    assert any("None on record is not none given" in n for n in s.notes)


def test_the_notice_day_passing_with_none_on_record_is_legal_until_a_person_records_it(data):
    on = date(2031, 3, 10)
    first = [i for i in attention.meetings_section(_community(), data, on).ordered() if "2031-03-12" in i.text]
    assert first[0].urgency is Urgency.LEGAL and "none on record and that day has passed" in first[0].text
    # a posting jason cannot see, recorded by a person against the assignment's due day
    schedule_task.record_done(data, "meeting-notice", date(2031, 3, 8), date(2031, 3, 7), "A Secretary",
                              "posted at the example clubhouse")
    clock = _clock(_by_day(mw.watch(_community(), data, on=on))["2031-03-12"], "notice")
    assert clock.standing is S.MET and "A Secretary" in clock.record and clock.on == date(2031, 3, 7)
    assert not [i for i in attention.meetings_section(_community(), data, on).items if "2031-03-12" in i.text]


def test_a_notice_sent_too_late_for_a_meeting_still_ahead_is_legal(data):
    catalog = json.loads((data / "meetings" / "catalog.json").read_text(encoding="utf-8"))
    catalog["meetings"][-1] = _meeting("2031-03-12", _rec("meeting notice", "PayHOA communication",
                                                          "Board meeting Mar 12", "2031-03-10T18:00:00Z"))
    (data / "meetings" / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    on = date(2031, 3, 11)
    clock = _clock(_by_day(mw.watch(_community(), data, on=on))["2031-03-12"], "notice")
    assert clock.standing is S.LATE and "2 days before" in clock.note and "at least 4" in clock.note
    item = next(i for i in attention.meetings_section(_community(), data, on).items if "2031-03-12" in i.text)
    assert item.urgency is Urgency.LEGAL


def test_minutes_copies_a_draft_counts_jasons_own_does_not_and_a_template_made_ahead_is_undated(tmp_path):
    _write(tmp_path, [
        _meeting("2031-02-12", _rec("transcript", "jason", "x"),
                 _rec("draft minutes", "jason draft", "minutes-draft-2031-02-12.md"),
                 _rec("draft minutes", "Drive", "Draft minutes of 2/12/31", ref="d1")),
        _meeting("2031-01-08", _rec("transcript", "jason", "x"), _rec("minutes", "Drive", "Minutes of 1/8/31", ref="d2")),
    ], zoom=[("2031-02-12", "board meeting"), ("2031-01-08", "board meeting")],
        drive=[("d1", "2031-02-20T18:00:00Z"), ("d2", "2031-01-02T18:00:00Z")])
    found = _by_day(mw.watch(_community(), tmp_path, on=date(2031, 3, 3)))
    feb = _clock(found["2031-02-12"], "minutes")
    assert feb.standing is S.MET and feb.on == date(2031, 2, 20) and "draft" in feb.record
    jan = _clock(found["2031-01-08"], "minutes")
    assert jan.standing is S.UNDATED and "before the meeting" in jan.record
    s = attention.meetings_section(_community(), tmp_path, date(2031, 3, 3))
    assert any(i.urgency is Urgency.OPEN and "with no date" in i.text for i in s.items)


def test_a_document_that_asks_more_moves_the_notice_day(data):
    longer = NoticeProvision("longer-notice", "bylaws", "1.1", "seven days' notice", Comparison.MORE,
                             requirement="board-meeting", timing=(Timing(Anchor.MEETING, least=7),))
    clock = _clock(_by_day(mw.watch(_community((longer,)), data, on=date(2031, 3, 3)))["2031-03-12"], "notice")
    assert clock.deadline == date(2031, 3, 5) and clock.timing == "at least 7 days before the meeting"


def test_no_schedule_and_no_catalog_is_an_empty_watch(tmp_path):
    w = mw.watch(SimpleNamespace(), tmp_path, on=date(2031, 3, 3))
    assert w.meetings == [] and any("No meeting catalog" in n for n in w.notes)
    assert not (tmp_path / "meetings").exists()                      # it reads; it writes nothing
    s = attention.meetings_section(SimpleNamespace(), tmp_path, date(2031, 3, 3))
    assert s.items == [] and s.available


def test_a_scheduled_day_behind_with_nothing_on_record(tmp_path):
    _write(tmp_path, [])
    w = mw.watch(_community(), tmp_path, on=date(2031, 3, 3))
    assert w.gaps == [(date(2031, 1, 8), date(2031, 2, 7)), (date(2031, 2, 12), date(2031, 3, 14))]
    s = attention.meetings_section(_community(), tmp_path, date(2031, 3, 3))
    assert any(i.urgency is Urgency.OPEN and "nothing is on record" in i.text for i in s.items)


def test_the_digest_reads_the_meetings_once_and_the_schedule_leaves_them_to_it(data):
    found = attention.digest(_community(), data, on=date(2031, 3, 3), sections=("meetings", "schedule"))
    by = {s.key: s for s in found.sections}
    assert by["meetings"].available and by["schedule"].available
    assert not any("meeting-notice" in i.text or "meeting-minutes" in i.text for i in by["schedule"].items)
    assert any("read against the meeting records" in n for n in by["schedule"].notes)
    alone = attention.digest(_community(), data, on=date(2031, 3, 3), sections=("schedule",)).sections[0]
    assert any("meeting-notice" in i.text for i in alone.items)          # without the meetings section, listed
    assert mw.owned_keys(_community()) == {"meeting-notice", "meeting-minutes"}


def test_the_watch_flag_is_registered():
    from jason.commands import schedule_evidence as command

    parser = argparse.ArgumentParser()
    command.register(parser.add_subparsers(), lambda p: p.add_argument("--env"), lambda a: None)
    args = parser.parse_args(["schedule-evidence", "--watch", "--as-of", "2031-03-03", "--ahead", "30", "--json"])
    assert args.watch and args.as_of == "2031-03-03" and args.ahead == 30 and args.past == mw.PAST_DAYS
