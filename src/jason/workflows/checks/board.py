"""The board family's read-only checks (docs/workflows/board-governance.md; the definitions are ``defs/board.py``).

Each is a ``check`` step's read: it takes the readers, the run's view, and an item, and returns a ``CheckResult``. All of
them read stores on disk through the read functions that already exist, write nothing, call no outside system, and name no
association (the community is asked through the readers' lazy ``community``, so a test passes its own).

- ``meeting-clocks`` (``jason.tasks.meeting_watch``): the last day to notice the meeting and the minutes still owed.
- ``notice-delivery-read`` (the notice ledger): every emailed or mailed copy of the meeting's notice has an outcome.
- ``minutes-checks`` (``jason.tasks.minutes_draft.checks``): the draft's quorum, confidential lines, and the executive
  session's wording, counted and never quoted.
- ``run-complete``: every other step of the run is done or skipped.
- ``rule-stages`` (``jason.tasks.record_stages``): the rule change's stages and the strongest record of each.
- ``readings-stale`` (``jason.community.law_readings``): each reading still reads the words on the shelf.
- ``shelf-cites`` (``jason.tasks.citation_coverage``): what the surveyed documents cite that the shelf lacks.
- ``schedule-due`` (``jason.tasks.schedule``): the occurrences that fall due, by standing.
- ``schedule-coverage`` (``jason.tasks.schedule``): the duties nobody owns and those on a clock nothing sets.
- ``hearing-dates`` (the saved hearings): a hearing's saved notice and decision days against the run's hearing day. The
  hearing definition is not registered, and this read reveals no name, address, or matter: a handle and days only.

A check that cannot read returns ``ok=False`` with the reason, never ``ok``, and never raises. "None on record" is not "none
given": a miss stays a miss, and a person records what was done where jason does not look.
"""

from __future__ import annotations

import functools
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from jason.workflows.checks import check
from jason.workflows.readers import StoreReaders, day_of
from jason.workflows.types import CheckResult, RunView, StepState

CITATION_GAPS = ("NOT_FOUND", "NOT_EXPORTED", "RENUMBERED")
"""The standings of a cited section that a person looks at (``jason.mcp.citations``): not on the shelf, not in the law as
published, or cited by an old number."""

DUE_PAST_DAYS = 30
DUE_AHEAD_DAYS = 45
"""The window ``jason schedule`` reads: 30 days back for what is overdue, and the page's 45 days ahead."""

SHOWN = 5
"""How many keys a message names; the rest are counted."""


# --- helpers ---------------------------------------------------------------------------------------------------------

def _fail(message: str) -> CheckResult:
    return CheckResult(False, (), message)


def _cause(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _safe(fn: Callable[..., CheckResult]) -> Callable[..., CheckResult]:
    """A read that raises is a read that failed, with the reason."""

    @functools.wraps(fn)
    def run(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
        try:
            return fn(readers, view, item)
        except Exception as exc:  # noqa: BLE001 - an unreadable store fails the check with the reason, never ok
            return _fail(f"cannot read: {_cause(exc)}")

    return run


def _community(readers: StoreReaders) -> tuple[Any, str]:
    """(the profile, "") or (None, why not). The readers load the active one only when a check asks."""
    try:
        found = readers.community
    except Exception as exc:  # noqa: BLE001 - no community chosen
        return None, f"no community can be loaded ({_cause(exc)})"
    return (found, "") if found is not None else (None, "no community is chosen")


def _key(view: RunView) -> str:
    """The run's subject without its kind prefix: ``rule-change:KEY`` and ``KEY`` both read KEY."""
    return str(view.subject).rpartition(":")[2].strip()


def _meeting_day(view: RunView) -> date | None:
    return day_of(view.dates.get("meeting_on", "")) or day_of(_key(view))


def _some(keys: list[str]) -> str:
    shown = ", ".join(keys[:SHOWN])
    return shown + (f" and {len(keys) - SHOWN} more" if len(keys) > SHOWN else "")


# --- board-meeting ---------------------------------------------------------------------------------------------------

@check("meeting-clocks")
@_safe
def meeting_clocks(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The last day to give notice of the meeting (CIV 4920(a), or the longer period the governing documents state), what
    the record shows for it, and the minutes still owed from earlier meetings (4950(a)). It fails when the notice-by day has
    passed with no notice on record in time: a later meeting day, noticed in time, is then needed. It never marks 4920 met;
    none on record is not none given."""
    day = _meeting_day(view)
    if day is None:
        return _fail("the run has no meeting day (the meeting_on date)")
    community, why = _community(readers)
    if community is None:
        return _fail(why)
    from jason.tasks import meeting_watch as watch_task

    today = readers.today
    found = watch_task.watch(community, readers.data_dir, on=today, past=max(watch_task.PAST_DAYS, (today - day).days + 1),
                             ahead=max(watch_task.AHEAD_DAYS, (day - today).days + 1))
    owed = sorted(m.day.isoformat() for m in found.meetings if m.day < today and m.day != day for c in m.clocks
                  if c.what == "minutes" and c.standing in (watch_task.Standing.OPEN, watch_task.Standing.PASSED))
    minutes = (f"; minutes still owed from {len(owed)} earlier meeting(s): {_some(owed)}" if owed
               else "; no minutes owed from an earlier meeting on record")
    evidence = readers.evidence_entries(("file:meetings/catalog.json", "file:schedule/done.jsonl", "file:zoom/meetings.json"))
    meeting = next((m for m in found.meetings if m.day == day), None)
    clock = next((c for c in meeting.clocks if c.what == "notice"), None) if meeting is not None else None
    if clock is None:
        from jason.community.notice_catalog import effective
        from jason.community.notices import Anchor

        row, clocks, _, _ = effective(watch_task.NOTICE, community)
        timing = next(t for t in clocks if t.anchor is Anchor.MEETING)
        deadline = timing.window(day)[1]
        said = f"notice of the {day.isoformat()} meeting by {deadline.isoformat()} ({watch_task.SUBDIVISION[watch_task.NOTICE]}, " \
               f"{timing.describe()}): none on record yet"
        if today > deadline:
            return _fail(said.replace("none on record yet", "none on record and the day has passed")
                         + f"; a later meeting day noticed in time is needed (none on record is not none given){minutes}")
        return CheckResult(True, evidence, said + minutes)
    said = (f"notice of the {day.isoformat()} meeting by {clock.deadline.isoformat()} ({clock.authority}, {clock.timing}): "
            f"{clock.standing.value}")
    late = clock.standing in (watch_task.Standing.PASSED, watch_task.Standing.LATE, watch_task.Standing.FILE_LATE)
    if late:
        return CheckResult(False, evidence, said + "; a later meeting day noticed in time is needed (none on record is not none "
                                            "given: a posting is recorded with jason schedule --done)" + minutes)
    return CheckResult(True, evidence, said + minutes)


def _ledger(root: Path, notice: str) -> tuple[list[Any], bool, str]:
    """(the notice's attempts, whether a posting is recorded, why not). Opened read-only: the ledger's own ``load`` would
    make the file."""
    from jason.tasks import notice_ledger

    path = root / "notices" / "deliveries.db"
    if not path.is_file():
        return [], False, "the notice ledger has not been synced yet (jason notices KEY --sync)"
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute("select * from attempts where notice = ? order by unit, membership_id, sent_at", (notice,)).fetchall()
        try:
            kind = con.execute("select general from notice_kinds where notice = ?", (notice,)).fetchone()
        except sqlite3.OperationalError:
            kind = None
    finally:
        con.close()
    attempts = [notice_ledger.Attempt(r["notice"], r["membership_id"], r["unit_id"], r["unit"], r["channel"], r["batch"], r["key"],
                                      r["sent_at"], notice_ledger.Delivery(r["status"]), r["status_at"], r["reason"]) for r in rows]
    return attempts, bool(kind and kind[0]), ""


@check("notice-delivery-read")
@_safe
def notice_delivery_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every copy of the meeting's notice (``board-meeting-DAY``) has an outcome in the notice ledger, and some copy reached a
    member; or the ledger records the notice posted as a general notice (CIV 4045). A file never meets the notice clock, so the
    ledger is the only record read. Follow-ups still owed are counted, not acted on."""
    day = _meeting_day(view)
    if day is None:
        return _fail("the run has no meeting day (the meeting_on date)")
    from jason.tasks import notice_ledger

    notice = f"board-meeting-{day.isoformat()}"
    attempts, posted, why = _ledger(readers.data_dir, notice)
    if why:
        return _fail(why)
    evidence = readers.evidence_entries(("file:notices/deliveries.db",))
    if not attempts and not posted:
        return _fail(f"the ledger holds no copy of notice {notice} and no posting (jason notices {notice} --sync, or "
                     f"--mark-general --posted): none on record is not none given")
    if not attempts:
        return CheckResult(True, evidence, f"notice {notice} is recorded as posted general notice (CIV 4045); the ledger holds no copy")
    waiting = sum(1 for a in attempts if a.status is notice_ledger.Delivery.PENDING)
    if waiting:
        return _fail(f"{waiting} of {len(attempts)} copies of notice {notice} have no outcome yet (jason notices {notice} --sync)")
    people = notice_ledger.standing(attempts, general=posted)
    reached = sum(1 for s in people if s.reached)
    resend = sum(1 for s in people if any(f.resend for f, _ in s.follow_ups))
    tally: dict[str, int] = {}
    for a in attempts:
        tally[a.status.value] = tally.get(a.status.value, 0) + 1
    said = (f"{len(attempts)} copies of notice {notice} to {len(people)} members: "
            + ", ".join(f"{n} {w}" for w, n in sorted(tally.items())) + f"; {reached} reached, {resend} owed a resend")
    if posted:
        return CheckResult(True, evidence, said + "; recorded as posted general notice (CIV 4045)")
    if not reached:
        return CheckResult(False, evidence, said + ": no copy reached a member")
    return CheckResult(True, evidence, said)


@check("minutes-checks")
@_safe
def minutes_checks(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """jason's checks on the minutes draft (``data/board/minutes-draft-DAY.md``), counted without writing the draft: a quorum
    claimed that the count does not support, motions with no quorum on record, a line naming a confidential subject, a line
    about the executive session that uses the agenda's own words (CIV 4935(e)), and a meeting type the title does not
    support. Blanks and pronouns are counted for the secretary and do not fail it. Lines are counted, never quoted."""
    day = _meeting_day(view)
    if day is None:
        return _fail("the run has no meeting day (the meeting_on date)")
    community, why = _community(readers)
    if community is None:
        return _fail(why)
    from jason.community.minutes_template import UNKNOWN
    from jason.tasks import minutes_draft

    path = readers.data_dir / "board" / f"minutes-draft-{day.isoformat()}.md"
    if not path.is_file():
        return _fail(f"no minutes draft for {day.isoformat()} (data/board/minutes-draft-{day.isoformat()}.md): jason board --minutes "
                     f"{day.isoformat()}, or the secretary writes them by hand")
    text = re.sub(r"\n## jason's checks\n.*?(?=\n## )", "\n", path.read_text(encoding="utf-8"), flags=re.S)
    found = minutes_draft.checks(minutes_draft.meeting_record(readers.data_dir, community, day), text, community)
    quorum = found["quorum"]
    problems: list[str] = []
    if quorum["standing"] == "not on the record":
        if found["claimsQuorum"]:
            problems.append("the draft says a quorum was present and the count does not support it")
        if found["motions"]:
            problems.append(f"{found['motions']} motion(s) with no quorum on the record")
    if found["confidential"]:
        problems.append(f"{len(found['confidential'])} line(s) name a subject the open minutes give only generally")
    if found["executiveParticulars"]:
        problems.append(f"{len(found['executiveParticulars'])} executive-session line(s) use the agenda's own words")
    if found["kindDiffers"]:
        problems.append("the meeting type in the draft differs from the meeting's title")
    count = (f"quorum {quorum['standing']} ({len(quorum['present'])} of {quorum['inOffice']} directors on the call, "
             f"{quorum['needed'] if quorum['needed'] is not None else 'no'} needed); {text.count(UNKNOWN)} blank(s) for the "
             f"secretary; {len(found['pronouns'])} line(s) call a person he or she")
    evidence = readers.evidence_entries((f"file:board/minutes-draft-{day.isoformat()}.md",))
    if problems:
        return CheckResult(False, evidence, "; ".join(problems) + f". {count}")
    return CheckResult(True, evidence, count)


@check("run-complete")
@_safe
def run_complete(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every step of the run but the closing one (the last) is done or skipped. A late-found fact that reopens a step makes
    this fail again, so the run does not close over it."""
    steps = list(view.steps)
    if len(steps) < 2:
        return _fail("the run has no steps before its last to close over")
    closing, rest = steps[-1], steps[:-1]
    open_ = [s.id for s in rest if s.state not in (StepState.DONE, StepState.SKIPPED)]
    if open_:
        return _fail(f"{len(open_)} of {len(rest)} steps are not done or skipped: {_some(open_)}")
    skipped = sum(1 for s in rest if s.state is StepState.SKIPPED)
    return CheckResult(True, (), f"all {len(rest)} steps before {closing.id} are done or skipped ({skipped} skipped)")


# --- rule-change -----------------------------------------------------------------------------------------------------

@check("rule-stages")
@_safe
def rule_stages(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The rule change's stages as the record shows them (``jason record-stages --change KEY``): its draft, the proposed
    notice (CIV 4360(a)), the adoption, and the adopted notice (4360(c)), each with the strongest record found. It passes when
    an adoption is on record (the minutes or a decision); a file's date is when it was written, not when members read it."""
    key = _key(view)
    if not key:
        return _fail("the run's subject names no rule change")
    community, why = _community(readers)
    if community is None:
        return _fail(why)
    from jason.tasks import record_stages

    found = record_stages.rule_change_histories(community, readers.data_dir, on=readers.today)
    history = next((h for h in found if h.key == key), None)
    if history is None:
        return _fail(f"no rule change {key} in the profile's rows or drafts ({len(found)} read)")
    stages = history.stages_with_evidence()
    said = (f"rule change {key} is {history.outcome.value}"
            + (f", decided {history.decided.isoformat()}" if history.decided else "") + "; strongest record by stage: "
            + ", ".join(f"{k} {v}" for k, v in stages.items()))
    evidence = readers.evidence_entries(("file:drive/files.json", "file:gmail/correspondence.json", "file:meetings/catalog.json",
                                         "file:schedule/google-read.json", "file:notices/deliveries.db"))
    if stages.get("adopted", "none") == "none":
        return CheckResult(False, evidence, said + ": no adoption on record (the adopted words are entered from the minutes, "
                                                  "not typed)")
    return CheckResult(True, evidence, said)


# --- law-review ------------------------------------------------------------------------------------------------------

@check("readings-stale")
@_safe
def readings_stale(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each reading the profile holds still reads the words on the shelf (``jason readings --stale``). A reading whose words
    changed, whose provision is off the shelf, or whose quote is not in what it reads is listed by key and is not applied
    until a person redoes or confirms it. It passes when none is."""
    community, why = _community(readers)
    if community is None:
        return _fail(why)
    from jason.community import law_readings

    held = law_readings.readings(community)
    if not held:
        return CheckResult(True, (), "the profile holds no readings, so none is stale")
    tally: dict[str, list[str]] = {}
    for reading in held:
        state = law_readings.status(reading, readers.data_dir, community=community).state
        tally.setdefault(state.value, []).append(reading.key)
    counts = ", ".join(f"{len(v)} {k}" for k, v in sorted(tally.items()))
    said = f"{len(held)} readings: {counts}"
    bad = sorted(k for state, keys in tally.items() if state != law_readings.ReadingState.CURRENT.value for k in keys)
    if bad:
        return _fail(said + f"; not applied until redone or confirmed: {_some(bad)}")
    return CheckResult(True, (), said)


@check("shelf-cites")
@_safe
def shelf_cites(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The sections the surveyed documents cite (the saved reference-work surveys and the last ingest) are on the authorities
    shelf. A section off the shelf, not in the law as published, or cited by an old number is a gap for a person to add as a row
    (``citation_gaps``); jason adds nothing. A section exported since a survey was made is placed against the shelf as it is now."""
    import json

    from jason.tasks.citation_coverage import from_dict, merge, saved

    root = readers.data_dir
    raws = list(saved(root))
    try:
        from jason.tasks.ingest import last_report

        report = last_report(root)
        cited = json.loads(report.read_text(encoding="utf-8")).get("citations") if report is not None else None
    except (OSError, ValueError, ImportError):
        cited = None
    if cited:
        raws.append({"name": "ingest", "kind": "ingest", **cited})
    if not raws:
        return _fail("no citation survey on disk (jason reference --cites WORK, or jason ingest SOURCE)")
    combined = merge([from_dict(r, root) for r in raws])
    gaps = [r for r in combined.rows if r.standing.name in CITATION_GAPS]
    said = f"{len(combined.rows)} sections cited across {len(raws)} survey(s)"
    evidence = readers.evidence_entries(("glob:citations/*.json", "file:authorities/manifest.json"))
    if gaps:
        return CheckResult(False, evidence, said + f"; {len(gaps)} not on the shelf: " + _some([r.citation for r in gaps])
                           + ("; to add: " + combined.proposal() if combined.proposal() else ""))
    return CheckResult(True, evidence, said + "; every one is on the shelf, a regulation, or another code")


# --- duty-schedule ---------------------------------------------------------------------------------------------------

@check("schedule-due")
@_safe
def schedule_due(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """What falls due, read the way ``jason schedule --days 45`` reads it: 30 days back for what is overdue, 45 ahead, each
    occurrence done, overdue, due soon, or upcoming. A given ``item`` that names a role narrows it to that role. It passes when
    the schedule can be read and the profile sets assignments; the counts are information for a person, never a verdict."""
    community, why = _community(readers)
    if community is None:
        return _fail(why)
    from jason.community.schedule import assignments
    from jason.tasks import schedule

    if not assignments(community):
        return _fail("the profile sets no duty assignments, so nothing falls due on the schedule")
    today = readers.today
    start, end = today - timedelta(days=DUE_PAST_DAYS), today + timedelta(days=DUE_AHEAD_DAYS)
    found = schedule.agenda(community, readers.data_dir, start=start, end=end, today=today)
    roles = {o.assignment.role.value for o in found}
    if item and item in roles:
        found = [o for o in found if o.assignment.role.value == item]
    tally: dict[str, int] = {}
    for o in found:
        tally[o.standing] = tally.get(o.standing, 0) + 1
    order = ("done", "overdue", "due soon", "upcoming")
    counts = ", ".join(f"{tally[k]} {k}" for k in order if tally.get(k)) or "none"
    scope = f" for {item}" if item and item in roles else ""
    return CheckResult(True, readers.evidence_entries(("file:schedule/done.jsonl",)),
                       f"{len(found)} occurrence(s){scope} from {start.isoformat()} to {end.isoformat()}: {counts}")


@check("schedule-coverage")
@_safe
def schedule_coverage(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every duty jason knows of has an assignment, and every duty on a clock has something that sets its dates (``jason
    schedule --coverage``). A duty with no owner, or owned only by a standing assignment, is listed; the list blocks the
    board's adoption of the assignments."""
    community, why = _community(readers)
    if community is None:
        return _fail(why)
    from jason.tasks import schedule

    covered, uncovered = schedule.coverage(community, readers.data_dir)
    loose = schedule.unscheduled(community, readers.data_dir)
    said = f"{len(covered)} duties covered, {len(uncovered)} with no owner, {len(loose)} on a clock nothing schedules"
    problems = []
    if uncovered:
        problems.append("no owner: " + _some([ref for ref, *_ in uncovered]))
    if loose:
        problems.append("no dates set: " + _some([ref for ref, *_ in loose]))
    evidence = readers.evidence_entries(("glob:duties/*.json",))
    if problems:
        return CheckResult(False, evidence, said + "; " + "; ".join(problems))
    return CheckResult(True, evidence, said)


# --- hearing ---------------------------------------------------------------------------------------------------------

@check("hearing-dates")
@_safe
def hearing_dates(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The saved hearing's notice and decision days, against the run's hearing day: the notice is given at least 10 days
    before the meeting (CIV 5855(a)) and the decision notice is due within 14 days of the board's action (5855(f)). The hearing
    is found by its opaque handle (the run's subject). Nothing but the handle and the days is read out: never a name, an
    address, or the matter. The 15-day suspension notice (Corporations Code 7341) is not on the shelf and is not checked."""
    from jason.tasks import hearing_decisions
    from jason.tasks.zoom import NOTICE_DAYS

    handle = _key(view)
    if not handle:
        return _fail("the run's subject names no hearing handle")
    row = next((r for r in hearing_decisions.load(readers.data_dir) if r.get("handle") == handle), None)
    if row is None:
        return _fail(f"no saved hearing has the handle {handle}")
    held = day_of(str(row.get("start") or "")[:10])
    notice_by = day_of(row.get("noticeBy"))
    executive_by = day_of(row.get("executiveNoticeBy"))
    decision_by = day_of(row.get("decisionByIfHeld"))
    missing = [name for name, value in (("start", held), ("noticeBy", notice_by), ("executiveNoticeBy", executive_by),
                                        ("decisionByIfHeld", decision_by)) if value is None]
    if missing:
        return _fail(f"hearing {handle} lacks a saved day: {', '.join(missing)}")
    problems = []
    on = day_of(view.dates.get("hearing_on", ""))
    if on is not None and on != held:
        problems.append(f"the run's hearing day {on.isoformat()} is not the saved hearing's day {held.isoformat()}")
    if notice_by > held - timedelta(days=NOTICE_DAYS):
        problems.append(f"the notice-by day {notice_by.isoformat()} is under {NOTICE_DAYS} days before the hearing (CIV 5855(a))")
    if decision_by != held + timedelta(days=hearing_decisions.DECISION_DAYS):
        problems.append(f"the decision-by day {decision_by.isoformat()} is not {hearing_decisions.DECISION_DAYS} days after the "
                        "hearing (CIV 5855(f))")
    said = (f"hearing {handle} on {held.isoformat()}: notice by {notice_by.isoformat()}, executive-meeting notice by "
            f"{executive_by.isoformat()}, decision notice by {decision_by.isoformat()} if the board acts that day")
    evidence = readers.evidence_entries(("file:zoom/hearings.json",))
    if problems:
        return CheckResult(False, evidence, "; ".join(problems) + ". " + said)
    return CheckResult(True, evidence, said + " (plain day-count, no holiday or weekend rule applied)")


__all__ = ["hearing_dates", "meeting_clocks", "minutes_checks", "notice_delivery_read", "readings_stale", "rule_stages",
           "run_complete", "schedule_coverage", "schedule_due", "shelf_cites"]
