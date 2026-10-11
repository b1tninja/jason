"""The board family's checks (src/jason/workflows/checks/board.py), each over made-up stores in a temporary data folder.

Every statute, name, address, and date here is made up ("123 Main St", "Ana Example", 2031). A check reads and writes nothing,
so the helper ``run`` pins the whole data folder byte-for-byte before and after each call; an unreadable store fails the check
with the reason and never raises; and nothing reaches the network or a profile (the community is a plain object the test passes).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community.base import MeetingSchedule
from jason.community.law_readings import LawReading, Provision, ReadingState, ReadingStatus, ReadingStanding, Whose
from jason.community.record_stages import Evidence, RuleChangeRecord, Strength, rule_change_history
from jason.community.revisions import Stage
from jason.community.schedule import Anchor as ScheduleAnchor, Assignment, Role as DutyRole, Trigger
from jason.tasks import hearing_decisions, minutes_draft, notice_ledger, record_stages, schedule as schedule_task
from jason.workflows.checks import board as reads, load_all
from jason.workflows.readers import CHECKS, StoreReaders, named_check
from jason.workflows.types import CheckResult, Role, StepDef, StepKind, StepState
from test_workflows_support import data  # noqa: F401 - the `data` fixture

TODAY = date(2031, 3, 3)
SCHEDULE = MeetingSchedule(weekday=2, nth=2, time="6:30 pm", place="Example Hall")      # the second Wednesday
NOTICE = Assignment("meeting-notice", "Notice of each board meeting", DutyRole.SECRETARY, ("notice:board-meeting",),
                    Trigger.ANCHORED, anchor=ScheduleAnchor.BOARD_MEETING, offset_days=-4)
MINUTES = Assignment("meeting-minutes", "Minutes within 30 days", DutyRole.SECRETARY, ("notice:minutes-available",),
                     Trigger.ANCHORED, anchor=ScheduleAnchor.BOARD_MEETING, offset_days=30)


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()} if root.is_dir() else {}


def view(dates=None, subject="", steps=()):
    return SimpleNamespace(id="run-test", definition="x", opened_at="2020-01-01T00:00:00Z", dates=dict(dates or {}),
                           subject=subject, steps=tuple(steps))


def readers_for(data, community=None, today=TODAY):
    data.mkdir(parents=True, exist_ok=True)
    return StoreReaders(data, community=community if community is not None else object(), today=today)


def run(readers, name, v, item=""):
    """One check, with the whole data folder pinned: it must be exactly as it was."""
    before = tree(readers.data_dir)
    existed = readers.data_dir.exists()
    res = CHECKS[name](readers, v, item)
    assert isinstance(res, CheckResult)
    assert tree(readers.data_dir) == before and readers.data_dir.exists() == existed
    return res


def community(rows=(NOTICE, MINUTES)):
    return SimpleNamespace(meeting_schedule=lambda: SCHEDULE, assignments=lambda: rows, hearing_policy=lambda: None,
                           notice_provisions=lambda: (), fiscal_year_end=lambda: None)


# --- registration ----------------------------------------------------------------------------------------------------

NAMES = ("meeting-clocks", "notice-delivery-read", "minutes-checks", "run-complete", "rule-stages", "readings-stale", "shelf-cites",
         "schedule-due", "schedule-coverage", "hearing-dates")


def test_the_ten_reads_are_registered_by_name_and_a_step_finds_them(data):
    load_all()
    assert all(n in CHECKS for n in NAMES) and sorted(reads.__all__) == sorted(n.replace("-", "_") for n in NAMES)
    r = readers_for(data)
    step = StepDef("w.1", "Close", StepKind.CHECK, role=Role.JASON, check=named_check("run-complete"))
    assert r.check(step, view(steps=[SimpleNamespace(id="w.1", state=StepState.READY)])).ok is False        # one step: nothing to close over


# --- meeting-clocks ----------------------------------------------------------------------------------------------------

def rec(kind, where, name, sent=""):
    return {"kind": kind, "where": where, "name": name, "ref": "", "sent": sent, "note": ""}


def meeting(day, *records, titles=()):
    has = {}
    for r in records:
        has.setdefault(r["kind"], {}).setdefault(r["where"], 0)
        has[r["kind"]][r["where"]] += 1
    return {"date": day, "titles": list(titles), "has": has, "records": list(records)}


@pytest.fixture
def meetings(data):
    """January noticed two days ahead (late), February noticed five days ahead with no minutes yet, March only a draft agenda."""
    (data / "meetings").mkdir(parents=True)
    (data / "meetings" / "catalog.json").write_text(json.dumps({"builtAt": "2031-03-01T00:00:00+00:00", "meetings": [
        meeting("2031-01-08", rec("meeting notice", "PayHOA communication", "Board meeting Jan 8", "2031-01-06T18:00:00Z"),
                rec("minutes", "Gmail", "Minutes of 1_8_31.pdf", "2031-02-20T18:00:00Z")),
        meeting("2031-02-12", rec("meeting notice", "PayHOA communication", "Board meeting Feb 12", "2031-02-07T18:00:00Z"),
                rec("transcript", "jason", "Example (transcript)")),
        meeting("2031-03-12", rec("agenda", "jason draft", "agenda-2031-03-12.md"))]}), encoding="utf-8")
    (data / "zoom").mkdir()
    (data / "zoom" / "meetings.json").write_text(json.dumps({"meetings": [
        {"date": "2031-01-08", "kind": "board meeting", "topic": "Example"}, {"date": "2031-02-12", "kind": "board meeting", "topic": "Example"}]}),
        encoding="utf-8")
    return data


def test_the_clocks_name_the_notice_by_day_and_the_minutes_still_owed(meetings):
    r = readers_for(meetings, community())
    res = run(r, "meeting-clocks", view({"meeting_on": "2031-03-12"}))
    assert res.ok is True
    assert "notice of the 2031-03-12 meeting by 2031-03-08 (CIV 4920(a)" in res.message and "none on record yet" in res.message
    assert "minutes still owed from 1 earlier meeting(s): 2031-02-12" in res.message
    assert any(e.startswith("file:meetings/catalog.json@") for e in res.evidence)


def test_a_notice_given_late_or_not_given_by_its_day_fails_and_says_a_later_meeting_is_needed(meetings):
    r = readers_for(meetings, community())
    late = run(r, "meeting-clocks", view({"meeting_on": "2031-01-08"}))
    assert late.ok is False and "on record late" in late.message and "a later meeting day noticed in time" in late.message
    passed = run(readers_for(meetings, community(), today=date(2031, 3, 10)), "meeting-clocks", view({"meeting_on": "2031-03-12"}))
    assert passed.ok is False and "none on record; the deadline passed" in passed.message
    done = run(r, "meeting-clocks", view({"meeting_on": "2031-02-12"}))
    assert done.ok is True and "on record in time" in done.message


def test_a_meeting_the_schedule_does_not_set_is_read_from_the_notice_catalog(meetings):
    r = readers_for(meetings, community())
    special = run(r, "meeting-clocks", view({"meeting_on": "2031-06-12"}))                     # a Thursday: no schedule sets it
    assert special.ok is True and "by 2031-06-08" in special.message and "none on record yet" in special.message
    gone = run(readers_for(meetings, community(), today=date(2031, 3, 10)), "meeting-clocks", view({"meeting_on": "2031-03-13"}))
    assert gone.ok is False and "none on record and the day has passed" in gone.message


def test_the_clocks_cannot_be_read_without_a_day_a_community_or_a_catalog_that_reads(data):
    assert run(readers_for(data), "meeting-clocks", view()).message == "the run has no meeting day (the meeting_on date)"
    def unreadable():
        raise RuntimeError("the profile's schedule cannot be read")

    broken = run(readers_for(data, SimpleNamespace(meeting_schedule=unreadable)), "meeting-clocks", view({"meeting_on": "2031-03-12"}))
    assert broken.ok is False and broken.message == "cannot read: RuntimeError: the profile's schedule cannot be read"
    bare = run(readers_for(data, object()), "meeting-clocks", view({"meeting_on": "2031-03-12"}))
    assert bare.ok is True and "none on record yet" in bare.message                       # a profile that sets no schedule: the catalog's clock
    (data / "meetings").mkdir()
    (data / "meetings" / "catalog.json").write_text("{not json", encoding="utf-8")
    bad = run(readers_for(data, community()), "meeting-clocks", view({"meeting_on": "2031-03-12"}))
    assert bad.ok is False and bad.message.startswith("cannot read:")


# --- notice-delivery-read ----------------------------------------------------------------------------------------------

def attempt(n, status, channel="email", notice="board-meeting-2031-03-12"):
    return notice_ledger.Attempt(notice, n, n, f"{n} Main St", channel, "batch", f"ref-{n}", status=status)


D = notice_ledger.Delivery
MEET = view({"meeting_on": "2031-03-12"})


def test_delivery_waits_for_the_ledger_a_copy_and_an_outcome_for_every_copy(data):
    r = readers_for(data)
    assert "has not been synced" in run(r, "notice-delivery-read", MEET).message
    assert not (data / "notices").exists()                                               # reading made no ledger
    notice_ledger.save(data, [attempt(1, D.DELIVERED, notice="board-meeting-2031-02-12")])
    other = run(r, "notice-delivery-read", MEET)
    assert other.ok is False and "holds no copy of notice board-meeting-2031-03-12" in other.message
    notice_ledger.save(data, [attempt(1, D.PENDING), attempt(2, D.DELIVERED)])
    waiting = run(r, "notice-delivery-read", MEET)
    assert waiting.ok is False and waiting.message.startswith("1 of 2 copies of notice board-meeting-2031-03-12 have no outcome yet")


def test_delivery_passes_when_a_copy_reached_a_member_and_counts_what_is_owed(data):
    r = readers_for(data)
    notice_ledger.save(data, [attempt(1, D.DELIVERED), attempt(2, D.BOUNCED), attempt(3, D.MAILED, "letter")])
    ok = run(r, "notice-delivery-read", MEET)
    assert ok.ok is True and "3 copies of notice board-meeting-2031-03-12 to 3 members" in ok.message
    assert "1 bounced, 1 delivered, 1 mailed; 2 reached, 1 owed a resend" in ok.message
    assert any(e.startswith("file:notices/deliveries.db@") for e in ok.evidence)
    assert "Main St" not in ok.message                                                     # counts, never units
    notice_ledger.save(data, [attempt(1, D.BOUNCED, notice="board-meeting-2031-04-09"),
                              attempt(2, D.SKIPPED, notice="board-meeting-2031-04-09")])
    none = run(r, "notice-delivery-read", view({"meeting_on": "2031-04-09"}))
    assert none.ok is False and "no copy reached a member" in none.message


def test_a_posting_recorded_in_the_ledger_is_a_general_notice_delivered(data):
    r = readers_for(data)
    notice_ledger.set_general(data, "board-meeting-2031-03-12", True, posted="the clubhouse board, 2031-03-07", by="S. Secretary")
    posted = run(r, "notice-delivery-read", MEET)
    assert posted.ok is True and "posted general notice (CIV 4045)" in posted.message and "clubhouse" not in posted.message


def test_a_ledger_that_cannot_be_read_fails_with_the_reason(data):
    (data / "notices").mkdir(parents=True)
    (data / "notices" / "deliveries.db").write_bytes(b"this is not a database" * 40)
    res = run(readers_for(data), "notice-delivery-read", MEET)
    assert res.ok is False and res.message.startswith("cannot read:")
    assert run(readers_for(data), "notice-delivery-read", view()).ok is False


# --- minutes-checks ----------------------------------------------------------------------------------------------------

class Board:
    def quorum(self, in_office):
        return max(in_office // 2 + 1, 2)


DIRECTORS = ["Ana Example", "Ben Sample", "Cy Placeholder", "Dee Testcase"]


def record(attendance):
    return {"directors": DIRECTORS, "attendance": attendance, "unidentified": [], "kind": "", "executiveWords": []}


def draft(data, text, day="2031-03-12"):
    (data / "board").mkdir(parents=True, exist_ok=True)
    (data / "board" / f"minutes-draft-{day}.md").write_text(text, encoding="utf-8")


QUORUM = [("Ana Example", 30), ("Ben Sample", 25), ("Cy Placeholder", 20)]


def test_minutes_checks_pass_a_draft_whose_quorum_the_count_supports_and_count_the_blanks(data, monkeypatch):
    monkeypatch.setattr(minutes_draft, "meeting_record", lambda d, c, day: record(QUORUM))
    draft(data, "# DRAFT\n\n## Attendance and quorum\n\nA quorum was present.\n\n## Business\n\nThe treasurer spoke ___ (not in the "
                "record) and ___ (not in the record).\n\n## jason's checks\n\n- a quorum was present, per the count.\n\n## End\n")
    res = run(readers_for(data, SimpleNamespace(board=lambda: Board())), "minutes-checks", MEET)
    assert res.ok is True and "quorum present (3 of 4 directors on the call, 3 needed); 2 blank(s)" in res.message
    assert any(e.startswith("file:board/minutes-draft-2031-03-12.md@") for e in res.evidence)


def test_a_draft_that_claims_a_quorum_the_count_does_not_support_fails_and_quotes_nothing(data, monkeypatch):
    monkeypatch.setattr(minutes_draft, "meeting_record", lambda d, c, day: record([("Ana Example", 30), ("Ben Sample", 20)]))
    draft(data, "## Attendance and quorum\n\nA quorum was present.\n\n## Business\n\n- **Motion:** Approve a repair.\n\nThe directors "
                "discussed the lawsuit against the association.\n")
    res = run(readers_for(data, SimpleNamespace(board=lambda: Board())), "minutes-checks", MEET)
    assert res.ok is False
    assert "the draft says a quorum was present and the count does not support it" in res.message
    assert "1 motion(s) with no quorum on the record" in res.message and "1 line(s) name a subject" in res.message
    assert "lawsuit" not in res.message and "repair" not in res.message


def test_minutes_checks_need_the_draft_and_a_zoom_record_that_reads(data, monkeypatch):
    r = readers_for(data, SimpleNamespace(board=lambda: Board()))
    missing = run(r, "minutes-checks", MEET)
    assert missing.ok is False and "no minutes draft for 2031-03-12" in missing.message
    draft(data, "## Business\n\nNothing.\n")

    def none(d, c, day):
        raise ValueError(f"no board meeting on {day} in the Zoom record (data/zoom)")

    monkeypatch.setattr(minutes_draft, "meeting_record", none)
    res = run(r, "minutes-checks", MEET)
    assert res.ok is False and res.message.startswith("cannot read: ValueError: no board meeting on 2031-03-12")


# --- run-complete ------------------------------------------------------------------------------------------------------

def steps(*states):
    return [SimpleNamespace(id=f"w.{i + 1}", state=s) for i, s in enumerate(states)]


def test_a_run_closes_over_steps_that_are_done_or_skipped_only(data):
    r = readers_for(data)
    S = StepState
    ok = run(r, "run-complete", view(steps=steps(S.DONE, S.SKIPPED, S.DONE, S.READY)))
    assert ok.ok is True and ok.message == "all 3 steps before w.4 are done or skipped (1 skipped)"
    late = run(r, "run-complete", view(steps=steps(S.DONE, S.NEEDS_PERSON, S.WAITING, S.READY)))
    assert late.ok is False and late.message == "2 of 3 steps are not done or skipped: w.2, w.3"
    assert run(r, "run-complete", view(steps=steps(S.READY))).ok is False
    assert run(r, "run-complete", view()).ok is False


# --- rule-stages -------------------------------------------------------------------------------------------------------

def history(key="example-rule-2031", adopted=True, outcome_adopted=True):
    from jason.community.record_stages import Outcome

    row = RuleChangeRecord(key, "Example rule", "example-rules", "Example Rules", decided=date(2031, 2, 12),
                           outcome=Outcome.ADOPTED if outcome_adopted else Outcome.PENDING)
    found = [Evidence(Stage.DRAFT, "draft", "drive:text", date(2030, 12, 20), Strength.FILE)]
    if adopted:
        found.append(Evidence(Stage.ADOPTED, "the minutes of 2031-02-12", "Minutes of 2/12/31", date(2031, 2, 12), Strength.STATED))
    return rule_change_history(row, found, on=date(2031, 3, 1))


def test_the_stages_pass_when_an_adoption_is_on_record(data, monkeypatch):
    monkeypatch.setattr(record_stages, "rule_change_histories", lambda c, d, on=None, stores=None: [history(), history("other")])
    r = readers_for(data)
    ok = run(r, "rule-stages", view(subject="rule-change:example-rule-2031"))
    assert ok.ok is True and "rule change example-rule-2031 is adopted, decided 2031-02-12" in ok.message
    assert "draft file, proposed none, adopted stated, distributed none" in ok.message
    assert run(r, "rule-stages", view(subject="example-rule-2031")).ok is True                   # the bare key reads too
    monkeypatch.setattr(record_stages, "rule_change_histories", lambda c, d, on=None, stores=None: [history(adopted=False)])
    pending = run(r, "rule-stages", view(subject="rule-change:example-rule-2031"))
    assert pending.ok is False and "no adoption on record" in pending.message
    missing = run(r, "rule-stages", view(subject="rule-change:no-such-change"))
    assert missing.ok is False and "no rule change no-such-change" in missing.message
    assert run(r, "rule-stages", view()).ok is False


def test_the_stages_of_a_change_with_nothing_on_disk_read_as_no_adoption(data):
    row = RuleChangeRecord("example-rule-2031", "Example rule", "example-rules", "Example Rules", decided=date(2031, 2, 12))
    res = run(readers_for(data, SimpleNamespace(rule_change_records=lambda: (row,), rule_changes=lambda: ())), "rule-stages",
              view(subject="rule-change:example-rule-2031"))
    assert res.ok is False and ("no adoption on record" in res.message or res.message.startswith("cannot read:"))
    broken = run(readers_for(data, object()), "rule-stages", view(subject="rule-change:example-rule-2031"))
    assert broken.ok is False


# --- readings-stale ----------------------------------------------------------------------------------------------------

def reading(key):
    return LawReading(key, (Provision("CIV 9901", "a" * 16),), "What does the example notice require?", ReadingStanding.PLAIN,
                      Whose.BOARD, date(2031, 1, 1))


def test_readings_pass_when_each_reads_the_words_on_the_shelf_and_list_the_stale_by_key(data, monkeypatch):
    from jason.community import law_readings

    r = readers_for(data, SimpleNamespace(law_readings=lambda: ()))
    assert run(r, "readings-stale", view()).message == "the profile holds no readings, so none is stale"
    held = SimpleNamespace(law_readings=lambda: (reading("a-reading"), reading("b-reading"), reading("c-reading")))
    states = {"a-reading": ReadingState.CURRENT, "b-reading": ReadingState.STALE, "c-reading": ReadingState.MISSING}
    monkeypatch.setattr(law_readings, "status", lambda rd, d, community=None, as_of=None: ReadingStatus(rd.key, states[rd.key], ()))
    res = run(readers_for(data, held), "readings-stale", view())
    assert res.ok is False and res.message == ("3 readings: 1 current, 1 missing, 1 stale; not applied until redone or confirmed: "
                                               "b-reading, c-reading")
    states.update({"b-reading": ReadingState.CURRENT, "c-reading": ReadingState.CURRENT})
    assert run(readers_for(data, held), "readings-stale", view()).message == "3 readings: 3 current"


def test_a_reading_whose_provision_is_not_on_the_shelf_is_not_current(data):
    res = run(readers_for(data, SimpleNamespace(law_readings=lambda: (reading("a-reading"),))), "readings-stale", view())
    assert res.ok is False and "1 missing" in res.message and "a-reading" in res.message
    assert run(readers_for(data, object()), "readings-stale", view()).ok is True                 # a profile with no readings method holds none


# --- shelf-cites -------------------------------------------------------------------------------------------------------

def survey(data, name, rows):
    (data / "citations").mkdir(parents=True, exist_ok=True)
    (data / "citations" / f"reference-{name}.json").write_text(json.dumps({
        "name": name, "kind": "reference", "made": "2031-01-02", "lawChecked": True,
        "cited": [{"citation": c, "standing": s, "mentions": 1, "sources": [name], "subdivisions": [], "quote": "", "page": ""}
                  for c, s in rows]}), encoding="utf-8")


def test_the_shelf_check_lists_the_cited_sections_it_lacks(data):
    r = readers_for(data)
    assert run(r, "shelf-cites", view()).message.startswith("no citation survey on disk")
    survey(data, "example-guide", [("CIV 9901", "ON_SHELF"), ("CIV 9902", "NOT_EXPORTED"), ("CIV 9903", "NOT_FOUND"), ("GOV 9900", "OTHER_CODE")])
    res = run(r, "shelf-cites", view())
    assert res.ok is False and res.message.startswith("4 sections cited across 1 survey(s); 2 not on the shelf: CIV 9902, CIV 9903")
    assert "to add: CIV 9902" in res.message
    assert any(e.startswith("glob:citations/*.json@") for e in res.evidence)
    survey(data, "example-guide", [("CIV 9901", "ON_SHELF"), ("GOV 9900", "OTHER_CODE")])
    ok = run(r, "shelf-cites", view())
    assert ok.ok is True and "2 sections cited across 1 survey(s); every one is on the shelf" in ok.message


def test_a_survey_that_cannot_be_read_is_left_out_and_one_that_is_malformed_fails(data):
    (data / "citations").mkdir(parents=True)
    (data / "citations" / "reference-bad.json").write_text("{not json", encoding="utf-8")
    assert run(readers_for(data), "shelf-cites", view()).ok is False                           # none readable: no survey
    (data / "citations" / "reference-odd.json").write_text(json.dumps({"cited": [{"citation": "CIV 9901", "standing": "NO_SUCH"}]}),
                                                           encoding="utf-8")
    res = run(readers_for(data), "shelf-cites", view())
    assert res.ok is False and res.message.startswith("cannot read:")


# --- schedule-due ------------------------------------------------------------------------------------------------------

def duty(key, role, **more):
    fields = dict(title="T", role=role, covers=(key,), trigger=Trigger.CADENCE, every_months=1, day=15)
    fields.update(more)
    return Assignment(key, **fields)


def test_the_schedule_counts_what_is_done_overdue_due_soon_and_upcoming(data):
    rows = (duty("treasurer-report", DutyRole.TREASURER), duty("minutes", DutyRole.SECRETARY, day=1))
    schedule_task.record_done(data, "treasurer-report", date(2031, 2, 15), date(2031, 2, 16), "T. Treasurer", "the report, 2031-02-15")
    r = readers_for(data, SimpleNamespace(assignments=lambda: rows))
    res = run(r, "schedule-due", view())
    assert res.ok is True
    assert res.message == "6 occurrence(s) from 2031-02-01 to 2031-04-17: 1 done, 2 overdue, 1 due soon, 2 upcoming"
    assert any(e.startswith("file:schedule/done.jsonl@") for e in res.evidence)
    one = run(r, "schedule-due", view(), "treasurer")
    assert one.message == "3 occurrence(s) for treasurer from 2031-02-01 to 2031-04-17: 1 done, 1 due soon, 1 upcoming"
    assert run(r, "schedule-due", view(), "no-such-role").message.startswith("6 occurrence(s) from")
    assert run(readers_for(data, SimpleNamespace(assignments=lambda: ())), "schedule-due", view()).ok is False


# --- schedule-coverage -------------------------------------------------------------------------------------------------

def test_coverage_fails_for_a_duty_nobody_owns_or_nothing_dates(data, monkeypatch):
    refs = [("bylaws#9.6(a)", "review quarterly", True), ("ccrs#7.8", "owners inspect", True), ("notice:board-meeting", "notice", True),
            ("bylaws#1.2", "purpose", False)]
    monkeypatch.setattr(schedule_task, "_refs", lambda c, d: refs)
    own = (duty("a", DutyRole.TREASURER, covers=("bylaws#9.6", "notice:board-meeting")),
           duty("standing", DutyRole.MANAGER, covers=("ccrs#7",), trigger=Trigger.STANDING))
    res = run(readers_for(data, SimpleNamespace(assignments=lambda: own)), "schedule-coverage", view())
    assert res.ok is False
    assert res.message == "3 duties covered, 1 with no owner, 1 on a clock nothing schedules; no owner: bylaws#1.2; no dates set: ccrs#7.8"
    whole = (duty("a", DutyRole.TREASURER, covers=("bylaws", "notice:board-meeting", "ccrs")),)
    ok = run(readers_for(data, SimpleNamespace(assignments=lambda: whole)), "schedule-coverage", view())
    assert ok.ok is True and ok.message == "4 duties covered, 0 with no owner, 0 on a clock nothing schedules"


def test_coverage_of_a_profile_with_no_assignments_names_every_duty_unowned(data, monkeypatch):
    monkeypatch.setattr(schedule_task, "_refs", lambda c, d: [("bylaws#9.6", "review", True)])
    res = run(readers_for(data, SimpleNamespace(assignments=lambda: ())), "schedule-coverage", view())
    assert res.ok is False and "1 with no owner" in res.message


# --- hearing-dates -----------------------------------------------------------------------------------------------------

HANDLE = "h-abcd1234"


def hearing_row(**more):
    row = {"address": "123 Main St", "violation": "an example violation", "start": "2031-03-12T18:30", "noticeBy": "2031-03-02",
           "executiveNoticeBy": "2031-03-10", "decisionByIfHeld": "2031-03-26", "noticeOn": None, "handle": HANDLE}
    row.update(more)
    return row


def hearings(data, *rows):
    (data / "zoom").mkdir(parents=True, exist_ok=True)
    (data / "zoom" / "hearings.json").write_text(json.dumps({"hearings": list(rows)}), encoding="utf-8")


def test_the_saved_hearing_days_are_checked_against_the_run_and_reveal_no_name_or_address(data):
    hearings(data, hearing_row(), hearing_row(address="9 Elm Ct", handle="h-other000", start="2031-04-09T18:30"))
    r = readers_for(data)
    ok = run(r, "hearing-dates", view({"hearing_on": "2031-03-12"}, f"hearing:{HANDLE}"))
    assert ok.ok is True
    assert ok.message.startswith(f"hearing {HANDLE} on 2031-03-12: notice by 2031-03-02, executive-meeting notice by 2031-03-10, "
                                 "decision notice by 2031-03-26")
    assert "Main St" not in ok.message and "violation" not in ok.message
    assert any(e.startswith("file:zoom/hearings.json@") for e in ok.evidence)
    assert run(r, "hearing-dates", view({}, HANDLE)).ok is True                                      # no slot to compare, the bare handle
    moved = run(r, "hearing-dates", view({"hearing_on": "2031-03-19"}, f"hearing:{HANDLE}"))
    assert moved.ok is False and "is not the saved hearing's day 2031-03-12" in moved.message


def test_a_notice_day_under_ten_days_or_a_decision_day_off_the_count_fails(data):
    hearings(data, hearing_row(noticeBy="2031-03-04"), hearing_row(handle="h-late0000", decisionByIfHeld="2031-03-30"))
    r = readers_for(data)
    short = run(r, "hearing-dates", view({}, f"hearing:{HANDLE}"))
    assert short.ok is False and "under 10 days before the hearing (CIV 5855(a))" in short.message
    off = run(r, "hearing-dates", view({}, "hearing:h-late0000"))
    assert off.ok is False and "is not 14 days after the hearing (CIV 5855(f))" in off.message


def test_a_hearing_that_is_not_saved_or_a_store_that_cannot_be_read_fails_with_the_reason(data):
    r = readers_for(data)
    assert run(r, "hearing-dates", view({}, f"hearing:{HANDLE}")).message == f"no saved hearing has the handle {HANDLE}"
    assert run(r, "hearing-dates", view()).message == "the run's subject names no hearing handle"
    hearings(data, hearing_row(noticeBy=None))
    assert run(r, "hearing-dates", view({}, HANDLE)).message == f"hearing {HANDLE} lacks a saved day: noticeBy"
    (data / "zoom" / "hearings.json").write_text("{not json", encoding="utf-8")
    broken = run(r, "hearing-dates", view({}, HANDLE))
    assert broken.ok is False and broken.message.startswith("cannot read:")
    assert hearing_decisions.HEARINGS.as_posix() == "zoom/hearings.json"


# --- every read, one folder ---------------------------------------------------------------------------------------------

def test_every_read_leaves_a_populated_data_folder_byte_for_byte_and_none_is_ok_by_default(data):
    notice_ledger.save(data, [attempt(1, D.DELIVERED)])
    hearings(data, hearing_row())
    survey(data, "example-guide", [("CIV 9901", "ON_SHELF")])
    draft(data, "## Business\n\nNothing.\n")
    (data / "meetings").mkdir()
    (data / "meetings" / "catalog.json").write_text(json.dumps({"meetings": []}), encoding="utf-8")
    before = tree(data)
    r = readers_for(data, community())
    for name in NAMES:
        res = CHECKS[name](r, view({"meeting_on": "2031-03-12", "hearing_on": "2031-03-12"}, "rule-change:none"), "")
        assert isinstance(res, CheckResult), name
    assert tree(data) == before
    empty = data.parent / "empty"
    bare = StoreReaders(empty, community=object(), today=TODAY)
    for name in NAMES:
        res = CHECKS[name](bare, view(), "")
        assert res.ok is False or name == "readings-stale", (name, res.message)     # nothing to read is never ok (a profile with no readings has none stale)
    assert not empty.exists()
