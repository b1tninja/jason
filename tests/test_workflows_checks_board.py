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
    assert all(n in CHECKS for n in NAMES) and sorted(reads.__all__) == sorted(n.replace("-", "_") for n in NAMES + NEW)
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


# --- the twelve reads written after the first ten ----------------------------------------------------------------------------

NEW = ("executive-note-open", "rule-in-force", "rule-authority", "notice-text", "election-rules-window", "hearing-delivery-read",
       "hearing-requirements-met", "hearing-minutes-note", "retire-reasons", "manual-headings", "manual-concordance",
       "manual-template-equal")
LATER = date(2031, 4, 1)


def shelf(data, sections):
    """The authorities shelf of the folder: each made-up CIV section (its number and its words)."""
    (data / "authorities" / "CIV").mkdir(parents=True, exist_ok=True)
    pages = []
    for number, words in sections.items():
        file = f"authorities/CIV/CIV-{number}.md"
        (data / file).write_text(f"# CIV {number}: made up\n\n- Source: California Legislature, 2025 session publication, read with "
                                 f"lawlibrary\n\n## CIV {number}\n\n- History: made up\n\n{number}. (Added by Stats. 2012, Ch. 1, "
                                 f"Sec. 1.)\n\n{words}\n", encoding="utf-8")
        pages.append({"file": file, "citation": f"CIV {number}", "title": "Made up", "code": "CIV", "start": number, "end": number,
                      "sections": [number], "basis": "a duty", "why": ["made up"], "session": "2025"})
    (data / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2031-01-01", "session": "2025", "pages": pages}),
                                                        encoding="utf-8")


def test_the_twelve_new_reads_are_registered_and_none_is_left_wanted():
    from jason.workflows.defs import board as defs

    load_all()
    assert set(NEW) <= set(CHECKS) and all(CHECKS[n].__module__ == reads.__name__ for n in NEW)
    assert sorted(reads.__all__) == sorted(n.replace("-", "_") for n in NAMES + NEW)
    assert not [w for w in defs.WANTED if w.startswith("check:")]


@pytest.mark.parametrize("name", NEW)
def test_a_new_read_with_no_subject_no_stores_and_no_profile_fails_with_a_reason_and_creates_nothing(name, tmp_path):
    missing = tmp_path / "no-data-folder"
    res = CHECKS[name](StoreReaders(missing, community=object(), today=TODAY), view(), "")
    assert (res.ok is False or name == "retire-reasons") and res.message and not missing.exists()     # no rule row: none to check


# --- executive-note-open / hearing-minutes-note --------------------------------------------------------------------------------

NOTE = "The board met in executive session to discuss member discipline (Civil Code 4935(b))."


def test_the_executive_session_is_noted_generally_in_the_statutes_words(data):
    r = readers_for(data)
    draft(data, f"# DRAFT\n\n## Executive session\n\n{NOTE}\n\n## jason's checks\n\n- one line speaks of the executive session.\n\n## End\n")
    before = tree(data)
    res = run(r, "executive-note-open", MEET)
    assert res.ok is True and res.message == "1 line(s) of the 2031-03-12 draft speak of an executive session, 1 in the statute's general words"
    assert any(e.startswith("file:board/minutes-draft-2031-03-12.md@") for e in res.evidence)
    assert tree(data) == before


def test_no_note_or_a_note_that_names_no_allowed_subject_fails_and_quotes_nothing(data):
    r = readers_for(data)
    assert "no minutes draft for 2031-03-12" in run(r, "executive-note-open", MEET).message
    draft(data, "## Business\n\nNothing was said about it.\n")
    none = run(r, "executive-note-open", MEET)
    assert none.ok is False and "if none was held, skip this step with the reason" in none.message
    draft(data, "## Executive session\n\nThe board met in executive session about the Example lawsuit on 123 Main St.\n")
    particular = run(r, "executive-note-open", MEET)
    assert particular.ok is False and "1 name no subject 4935 allows" in particular.message
    assert "Example" not in particular.message and "Main St" not in particular.message
    assert run(r, "executive-note-open", view()).message == "the run has no meeting day (the meeting_on date)"


def test_the_hearings_matter_is_noted_in_the_next_open_minutes_by_its_subject_only(data):
    hearings(data, hearing_row())
    r = readers_for(data)
    draft(data, "## Executive session\n\nThe board met in executive session about a matter.\n", day="2031-02-12")        # before: ignored
    assert "no minutes draft on or after the hearing day 2031-03-12" in run(r, "hearing-minutes-note", view({}, f"hearing:{HANDLE}")).message
    draft(data, f"## Executive session\n\n{NOTE}\n", day="2031-04-09")
    before = tree(data)
    ok = run(r, "hearing-minutes-note", view({}, f"hearing:{HANDLE}"))
    assert ok.ok is True and "the 2031-04-09 draft has 1 executive-session line(s), 1 noting member discipline" in ok.message
    assert tree(data) == before
    draft(data, f"## Executive session\n\n{NOTE} Concerning 123 Main St.\n", day="2031-03-12")                         # the hearing day's own
    leaked = run(r, "hearing-minutes-note", view({}, f"hearing:{HANDLE}"))
    assert leaked.ok is False and "carries the hearing's address" in leaked.message and "Main St" not in leaked.message
    draft(data, "## Executive session\n\nThe board met in executive session to discuss personnel matters.\n", day="2031-03-12")
    off = run(r, "hearing-minutes-note", view({}, f"hearing:{HANDLE}"))
    assert off.ok is False and "member discipline" in off.message
    assert run(r, "hearing-minutes-note", view({}, "h-none0000")).message == "no saved hearing has the handle h-none0000"
    assert run(r, "hearing-minutes-note", view()).ok is False


# --- the rule-change reads -----------------------------------------------------------------------------------------------------

def change(*sections, key="example-rule-2031", authorities=("CIV 9901", "CIV 9902")):
    from jason.community.rule_changes import RuleChange

    return RuleChange(key, "Example rule", "example-rules", "Example Rules", "To make the hours plain.", "Owners keep the hours.",
                      sections, authorities=authorities)


def section(number="1", **more):
    from jason.community.rule_changes import SectionChange

    return SectionChange(number, "Quiet hours", more.pop("proposed", "Quiet hours begin at ten at night."), **more)


def book(data, *records, document="example-rules"):
    from jason.community.rules_document import RuleBook
    from jason.tasks.rules_documents import records_path, save_book

    save_book(RuleBook(list(records), document=document), records_path(data, document))


def rule(number, *versions, subjects=(), title="", id_=None):
    from jason.community.rules_document import RuleRecord

    return RuleRecord(id_ or f"example-rules#{number}", number=number, title=title, versions=tuple(versions), subjects=subjects)


def version(adopted=date(2030, 6, 1), **more):
    from jason.community.rules_document import RuleVersion

    return RuleVersion("Quiet hours begin at nine.", adopted=adopted, **more)


def changes_community(*rows, **more):
    return SimpleNamespace(**{"rule_changes": lambda: tuple(rows), "conflicts": lambda: (), "applicability_facts": lambda: (),
                              "region": "", "name": "The Example Association", **more})


RC = view({"decision_on": "2031-05-13"}, "rule-change:example-rule-2031")


def test_the_version_in_force_of_each_amended_rule_is_read_from_the_stored_records(data):
    book(data, rule("1", version()), rule("2", version(None)))
    r = readers_for(data, changes_community(change(section("1"), section("2"), section("3", new=True))))
    before = tree(data)
    res = run(r, "rule-in-force", RC)
    assert res.ok is True
    assert res.message == ("2 section(s) amended: 1 with a version in force and an adoption day on record (latest 2030-06-01), 1 with a "
                           "version in force and no adoption day (2: a person reads whether a change since has an adoption on record)")
    assert any(e.startswith("file:rule-records/example-rules.json@") for e in res.evidence)
    assert tree(data) == before


def test_a_rule_with_no_record_or_no_version_in_force_fails_and_a_new_rule_has_nothing_to_read(data):
    book(data, rule("1", version(date(2032, 1, 1))), rule("2", version(proposed=True)))
    r = readers_for(data, changes_community(change(section("1"), section("2"), section("4"))))
    res = run(r, "rule-in-force", RC)
    assert res.ok is False and "no record for 4" in res.message and "no version in force for 1, 2" in res.message
    only_new = run(readers_for(data, changes_community(change(section("5", new=True)))), "rule-in-force", RC)
    assert only_new.ok is True and "adds 1 new section(s)" in only_new.message


def test_the_rule_reads_need_the_change_the_community_and_the_stored_records(data):
    r = readers_for(data, changes_community(change(section("1"))))
    assert "no stored rule records for example-rules" in run(r, "rule-in-force", RC).message
    assert "no proposed rule change 'other'" in run(r, "rule-in-force", view({}, "rule-change:other")).message
    assert run(r, "rule-in-force", view()).message == "the run's subject names no rule change"
    assert run(readers_for(data, object()), "rule-in-force", RC).ok is False


def test_the_authority_read_passes_when_it_reads_and_names_each_flag_without_fetching(data):
    r = readers_for(data, changes_community(change(section("1"))))
    before = tree(data)
    res = run(r, "rule-authority", RC)
    assert res.ok is True and not (data / "authorities").exists()                   # a citation off the shelf is a flag, never a fetch
    assert "0 of 2 named citations are on the shelf; 0 stored grant(s); 0 open conflict row(s)" in res.message
    assert "flags for a person: 2 of 2 citations not on the shelf: CIV 9901, CIV 9902; no stored grant of rule-making power" in res.message
    assert tree(data) == before
    shelf(data, {"9901": "A made-up rule.", "9902": "Another made-up rule."})
    res = run(r, "rule-authority", RC)
    assert "2 of 2 named citations are on the shelf" in res.message and "not on the shelf" not in res.message
    assert run(r, "rule-authority", view({}, "rule-change:other")).ok is False


def test_the_member_notice_is_rendered_for_the_decision_day_and_its_elements_checked_without_saving_it(data):
    r = readers_for(data, changes_community(change(section("1"))))
    before = tree(data)
    res = run(r, "notice-text", RC)
    assert res.ok is True and res.message.startswith("the notice for example-rule-2031 (given 2031-04-15, decision 2031-05-13): ")
    assert "2 of 2 catalog elements shown, 0 missing" in res.message and "6 of 6 of the Act's elements on the page shown" in res.message
    assert tree(data) == before
    later = run(r, "notice-text", view({"decision_on": "2031-05-13", "notice_on": "2031-04-01"}, "rule-change:example-rule-2031"))
    assert "given 2031-04-01" in later.message
    assert run(r, "notice-text", view({}, "rule-change:example-rule-2031")).message == "the run has no decision day (the decision_on date)"


# --- election-rules-window ---------------------------------------------------------------------------------------------------------

def change_record(key="election-rules-2031", **more):
    from jason.community.record_stages import RuleChangeRecord

    return RuleChangeRecord(key, more.pop("title", "Election rules"), more.pop("document", "election-rules"),
                            more.pop("document_title", "Election Rules"), **more)


ELECTION = view({"count_on": "2031-05-04"})


def window_community(*rows):
    return SimpleNamespace(rule_change_records=lambda: tuple(rows))


def test_an_election_rule_changed_inside_the_ninety_days_fails_and_one_outside_passes(data):
    r = readers_for(data, window_community(change_record(decided=date(2031, 3, 1)), change_record("other-2031", title="Parking rules", document="parking-rules", document_title="Parking Rules", decided=date(2031, 3, 1))))
    before = tree(data)
    inside = run(r, "election-rules-window", ELECTION)
    assert inside.ok is False and "1 election-rule change inside it: election-rules-2031 (2031-03-01)" in inside.message
    assert "from 2031-02-03 (exclusive) to the election on 2031-05-04" in inside.message and "Parking" not in inside.message
    outside = run(readers_for(data, window_community(change_record(decided=date(2031, 2, 3)), change_record("later-2031", effective=date(2031, 5, 5)))),
                  "election-rules-window", ELECTION)
    assert outside.ok is True and "none on record inside it" in outside.message
    assert tree(data) == before


def test_the_stored_rule_records_are_read_too_and_an_unreadable_source_is_not_ok(data):
    book(data, rule("3", version(date(2031, 4, 1)), subjects=("elections",)), rule("4", version(date(2031, 4, 1)), title="Parking"),
         rule("5", version(date(2031, 4, 2), proposed=True), title="Election day"), document="example-rules")
    res = run(readers_for(data, object()), "election-rules-window", ELECTION)
    assert res.ok is False and "example-rules#3 (2031-04-01)" in res.message and "#4" not in res.message and "#5" not in res.message
    assert run(readers_for(data, object()), "election-rules-window", view()).message == "the run has no election day (the count_on date)"
    empty = readers_for(data.parent / "empty", object())
    assert run(empty, "election-rules-window", ELECTION).ok is False


# --- the hearing's delivery and requirements ---------------------------------------------------------------------------------------

def save_attempts(data, notice, *statuses, sent="2031-03-01T10:00:00Z"):
    notice_ledger.save(data, [notice_ledger.Attempt(notice, n, n, f"{n} Main St", "email", "batch", f"ref-{n}-{notice}", sent_at=sent, status=s)
                              for n, s in enumerate(statuses, 1)])


def test_the_hearings_notice_must_have_reached_the_member_by_its_notice_by_day(data):
    hearings(data, hearing_row(noticeOn="2031-03-01"))
    r = readers_for(data)
    handle = view({}, f"hearing:{HANDLE}")
    assert "has not been synced" in run(r, "hearing-delivery-read", handle).message
    save_attempts(data, "discipline-hearing-2031-03-12", D.DELIVERED, D.BOUNCED)
    before = tree(data)
    ok = run(r, "hearing-delivery-read", handle)
    assert ok.ok is True and ok.message.startswith(f"notice of hearing {HANDLE}: 2 copy/copies, 1 reached; delivery day 2031-03-01, "
                                                   "notice-by day 2031-03-02")
    assert "Main St" not in ok.message and tree(data) == before
    hearings(data, hearing_row(noticeOn="2031-03-05"))
    late = run(r, "hearing-delivery-read", handle)
    assert late.ok is False and "delivered after the notice-by day, so the hearing moves" in late.message
    hearings(data, hearing_row())                                                           # no day recorded: the ledger's first send
    assert "delivery day 2031-03-01" in run(r, "hearing-delivery-read", handle).message


def test_a_notice_with_no_copy_a_pending_outcome_or_no_one_reached_fails(data):
    hearings(data, hearing_row())
    r = readers_for(data)
    handle = view({}, f"hearing:{HANDLE}")
    save_attempts(data, "discipline-hearing-2031-02-01", D.DELIVERED)
    assert "holds no copy of the notice of hearing" in run(r, "hearing-delivery-read", handle).message
    save_attempts(data, "discipline-hearing-2031-03-12", D.PENDING, D.DELIVERED)
    assert "1 of 2 copies of the notice of hearing" in run(r, "hearing-delivery-read", handle).message
    save_attempts(data, "discipline-hearing-2031-03-12", D.BOUNCED, D.BOUNCED)
    assert "no copy of the notice of hearing" in run(r, "hearing-delivery-read", handle).message
    assert run(r, "hearing-delivery-read", view({}, "h-none0000")).ok is False and run(r, "hearing-delivery-read", view()).ok is False
    hearings(data, hearing_row(noticeBy=None))
    assert run(r, "hearing-delivery-read", handle).message == f"hearing {HANDLE} lacks a saved day: noticeBy"


def test_every_requirement_the_days_can_show_is_stated_met_or_not_on_record(data):
    decision = {"findings": "the board's own words", "decidedOn": "2031-03-12", "noticeDueBy": "2031-03-26", "by": "S. Secretary"}
    hearings(data, hearing_row(noticeOn="2031-02-20", decision=decision))
    r = readers_for(data, today=LATER)
    handle = view({}, f"hearing:{HANDLE}")
    save_attempts(data, "discipline-hearing-2031-03-12", D.DELIVERED, sent="2031-02-20T10:00:00Z")
    save_attempts(data, "discipline-decision-2031-03-12", D.DELIVERED, sent="2031-03-20T10:00:00Z")
    before = tree(data)
    ok = run(r, "hearing-requirements-met", handle)
    assert ok.ok is True and ok.message.startswith(f"hearing {HANDLE} (held 2031-03-12): 5 of 5 requirements shown met on record")
    assert "findings" not in ok.message and "Main St" not in ok.message and tree(data) == before
    late = readers_for(data, today=LATER)
    hearings(data, hearing_row(noticeOn="2031-03-05", decision=decision))
    short = run(late, "hearing-requirements-met", handle)
    assert short.ok is False and "not met: notice at least 10 days before the hearing (5855(a))" in short.message
    hearings(data, hearing_row(noticeOn="2031-02-20"))
    missing = run(late, "hearing-requirements-met", handle)
    assert missing.ok is False and "not on record: board's findings recorded; decision delivered within 14 days" in missing.message
    assert run(r, "hearing-requirements-met", view({}, "h-none0000")).ok is False


# --- retire-reasons ------------------------------------------------------------------------------------------------------------------

def retire_community(*rows):
    return SimpleNamespace(people_task_rules=lambda: tuple(rows))


def retire_rule(key, **more):
    from jason.community.people_tasks import PeopleTaskRule

    return PeopleTaskRule(key, key, "A kind of task", retire=more.pop("retire", "The filing is no longer required."), **more)


def test_each_reason_that_retires_a_duty_must_cite_a_source_the_shelf_can_show(data):
    shelf(data, {"9901": "A made-up rule."})
    r = readers_for(data, retire_community(retire_rule("a-filing", source="CIV 9901"), retire_rule("a-clause", source="decl#4.1"),
                                          retire_rule("kept", retire="")))
    before = tree(data)
    ok = run(r, "retire-reasons", view())
    assert ok.ok is True and ok.message == "2 retire reasons: 1 cite a section on the shelf, 1 a clause for a person to read, 0 cite no source, 0 cite a section off the shelf"
    assert tree(data) == before
    bad = readers_for(data, retire_community(retire_rule("off", source="CIV 9902"), retire_rule("none", source=""), retire_rule("fine", source="CIV 9901")))
    res = run(bad, "retire-reasons", view())
    assert res.ok is False and "no source: none" in res.message and "off the shelf: off" in res.message and not (data / "authorities" / "CIV" / "CIV-9902.md").exists()
    assert run(readers_for(data, retire_community()), "retire-reasons", view()).message == "the profile sets no retire reason, so none is to be checked"
    assert run(readers_for(data, retire_community(retire_rule("kept", retire=""))), "retire-reasons", view()).ok is True


# --- the owner's manual's three checks --------------------------------------------------------------------------------------------------

def manual_community():
    return SimpleNamespace(owners_manual=lambda: SimpleNamespace(document="manual"))


def manual_outline(data, text, starts, revision="r1"):
    from jason.community.outlines import DocumentOutline, Section

    sections = [Section(str(i + 1), "A section", 1, s, len(text)) for i, s in enumerate(starts)]
    (data / "outlines").mkdir(parents=True, exist_ok=True)
    (data / "outlines" / "manual.json").write_text(json.dumps(DocumentOutline("manual", "The Manual", text=text, sections=sections,
                                                                             revision=revision).to_dict()), encoding="utf-8")


def test_every_numbered_capital_line_of_the_stored_outline_opens_a_section(data):
    r = readers_for(data, manual_community())
    text = "1. QUIET HOURS\nBody text here.\n2. PETS ON THE COMMON AREA\nMore body.\n3. LOST HEADING\nStill more.\nnot a heading\n"
    manual_outline(data, text, [0, text.index("2. PETS")])
    before = tree(data)
    res = run(r, "manual-headings", view())
    assert res.ok is False and res.message.startswith("3 numbered capital line(s) in the outline of manual, 2 open a section; not a heading: 3.")
    assert tree(data) == before
    manual_outline(data, text, [0, text.index("2. PETS"), text.index("3. LOST")])
    assert run(r, "manual-headings", view()).ok is True
    manual_outline(data, "just some words\n", [0])
    assert "no numbered capital line" in run(r, "manual-headings", view()).message
    (data / "outlines" / "manual.json").unlink()
    assert "no outline of manual on disk" in run(r, "manual-headings", view()).message
    assert "no owner's manual" in run(readers_for(data, SimpleNamespace(owners_manual=lambda: None)), "manual-headings", view()).message


def concordance(data, refs, revision="r1", rows=3):
    folder = data / "manual" / "manual"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "concordance.json").write_text(json.dumps({"rows": [{}] * rows, "references": refs}), encoding="utf-8")
    (folder / "classification.json").write_text(json.dumps({"revision": revision}), encoding="utf-8")


def test_the_concordance_resolves_every_existing_citation_and_is_not_older_than_the_outline(data):
    r = readers_for(data, manual_community())
    assert "no concordance for manual" in run(r, "manual-concordance", view()).message
    manual_outline(data, "1. A HEADING\n", [0])
    concordance(data, [{"where": "assignment x", "ref": "1", "new": "A-1"}, {"where": "duties store", "ref": "2", "new": "A-2"}])
    before = tree(data)
    ok = run(r, "manual-concordance", view())
    assert ok.ok is True and ok.message == "3 addresses mapped; 2 of 2 existing citations resolved"
    assert tree(data) == before
    concordance(data, [{"where": "assignment x", "ref": "1", "new": ""}, {"where": "duties store", "ref": "2", "new": "A-2"}])
    bad = run(r, "manual-concordance", view())
    assert bad.ok is False and "1 unresolved: assignment x cites 1" in bad.message
    concordance(data, [], revision="r0")
    old = run(r, "manual-concordance", view())
    assert old.ok is False and "built from revision r0 and the outline is now r1" in old.message


def render_files(data, manual="# Manual\n\nOne.\n", document="# Manual\n\nOne.\n", unlabeled=()):
    import os

    (data / "drafts").mkdir(parents=True, exist_ok=True)
    (data / "drafts" / "owners-manual.md").write_text(manual, encoding="utf-8", newline="")
    (data / "drafts" / "owners-manual.document.md").write_text(document, encoding="utf-8", newline="")
    os.utime(data / "drafts" / "owners-manual.md", (1_900_000_000, 1_900_000_000))
    os.utime(data / "drafts" / "owners-manual.document.md", (1_900_000_100, 1_900_000_100))
    (data / "manual" / "manual").mkdir(parents=True, exist_ok=True)
    (data / "manual" / "manual" / "render.json").write_text(json.dumps({"unlabeled": list(unlabeled)}), encoding="utf-8")


def test_the_definitions_rendering_equals_the_manual_with_no_unlabeled_piece_and_is_not_older(data):
    r = readers_for(data, manual_community())
    assert "jason manual --render writes it" in run(r, "manual-template-equal", view()).message
    render_files(data, manual="# Manual\r\n\r\nOne.  \r\n")                                    # line endings and trailing spaces aside
    before = tree(data)
    ok = run(r, "manual-template-equal", view())
    assert ok.ok is True and ok.message == "identical: yes; 0 unlabeled piece(s)"
    assert tree(data) == before
    render_files(data, document="# Manual\n\nTwo.\n")
    assert "identical: NO" in run(r, "manual-template-equal", view()).message
    render_files(data, unlabeled=[{"segment": "x"}])
    assert "1 unlabeled piece(s) (a difference no label explains is a finding)" in run(r, "manual-template-equal", view()).message
    render_files(data)
    import os

    os.utime(data / "drafts" / "owners-manual.md", (1_900_000_500, 1_900_000_500))
    assert "older than the manual's" in run(r, "manual-template-equal", view()).message
    (data / "manual" / "manual" / "render.json").unlink()
    assert "no render check for manual" in run(r, "manual-template-equal", view()).message


# --- the twelve, one populated folder ------------------------------------------------------------------------------------------------------

def test_the_new_reads_change_no_byte_of_a_populated_folder(data):
    hearings(data, hearing_row(noticeOn="2031-02-20"))
    save_attempts(data, "discipline-hearing-2031-03-12", D.DELIVERED, sent="2031-02-20T10:00:00Z")
    draft(data, f"## Executive session\n\n{NOTE}\n")
    book(data, rule("1", version()))
    shelf(data, {"9901": "A made-up rule."})
    manual_outline(data, "1. A HEADING\n", [0])
    concordance(data, [])
    render_files(data)
    community_ = changes_community(change(section("1")), rule_change_records=lambda: (), people_task_rules=lambda: (),
                                   owners_manual=lambda: SimpleNamespace(document="manual"))
    before = tree(data)
    r = readers_for(data, community_, today=LATER)
    for name in NEW:
        res = CHECKS[name](r, view({"meeting_on": "2031-03-12", "decision_on": "2031-05-13", "count_on": "2031-05-04"},
                                   f"hearing:{HANDLE}" if name.startswith("hearing") else "rule-change:example-rule-2031"), "")
        assert isinstance(res, CheckResult) and res.message, name
    assert tree(data) == before
