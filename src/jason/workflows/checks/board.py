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
- ``hearing-dates`` (the saved hearings): a hearing's saved notice and decision days against the run's hearing day. This read
  reveals no name, address, or matter: a handle and days only.
- ``executive-note-open`` (the minutes draft): the executive session is generally noted, in the statute's words (CIV 4935(e)).
- ``rule-in-force``, ``rule-authority``, ``notice-text`` (the stored rule records, the shelf on disk, the notice as rendered):
  a rule change's version in force, its named authorities and conflict rows, and the member notice's required elements.
- ``election-rules-window`` (the rule-change records and stored rule records): no election rule amended inside the 90 days.
- ``hearing-delivery-read``, ``hearing-requirements-met``, ``hearing-minutes-note`` (the saved hearing, the notice ledger,
  the minutes draft): counts and days only; a held run's matter, member, and address are never read out.
- ``retire-reasons`` (the profile's people-task rules): each reason that retires a duty cites a source on the shelf.
- ``manual-headings``, ``manual-concordance``, ``manual-template-equal`` (the stored outline, ``data/manual/KEY``, and
  ``data/drafts``): the owner's manual's stored artifacts, read and never rendered.

A statute is looked up on the authorities shelf on disk and never fetched (an on-demand export writes a page). A check that
cannot read returns ``ok=False`` with the reason, never ``ok``, and never raises. "None on record" is not "none
given": a miss stays a miss, and a person records what was done where jason does not look.
"""

from __future__ import annotations

import functools
import json
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

ELECTION_RULES_DAYS = 90
"""CIV 5105(h)(4)(B)(iii): the election operating rules are not amended less than 90 days before the election."""


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


def _hearing_handle(view: RunView) -> tuple[str, str]:
    """(the run's subject as a hearing handle, why not). A subject that is not the shape of a handle (``h-`` and eight hex
    digits) is never echoed: a person can start a run with any text as its subject, an address among it, and a message
    reaches the results and the history."""
    from jason.tasks.hearing_decisions import is_handle

    key = _key(view)
    if not key:
        return "", "the run's subject names no hearing handle"
    if not is_handle(key):
        return "", "the run's subject names no hearing handle (not a handle)"
    return key, ""


def _meeting_day(view: RunView) -> date | None:
    return day_of(view.dates.get("meeting_on", "")) or day_of(_key(view))


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


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

    handle, why = _hearing_handle(view)
    if why:
        return _fail(why)
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


# --- the executive session's general note (CIV 4935(e)) ------------------------------------------------------------------

EXECUTIVE_LINE = re.compile(r"executive session", re.I)
_CHECKS_HEADING = "jason's checks"


def _draft_text(root: Path, day: date) -> tuple[str, str]:
    """(the minutes draft's words without jason's checks block, why not). The draft is read where ``jason board --minutes``
    writes it and is never changed."""
    path = root / "board" / f"minutes-draft-{day.isoformat()}.md"
    if not path.is_file():
        return "", (f"no minutes draft for {day.isoformat()} (data/board/minutes-draft-{day.isoformat()}.md): jason board --minutes "
                    f"{day.isoformat()}, or the secretary writes them by hand")
    return re.sub(r"\n## jason's checks\n.*?(?=\n## |\Z)", "\n", path.read_text(encoding="utf-8"), flags=re.S), ""


def _executive_lines(text: str) -> list[str]:
    """The lines of the draft that speak of an executive session, outside jason's own checks block."""
    out, heading = [], ""
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip().casefold()
            continue
        if heading == _CHECKS_HEADING or line.startswith("_"):
            continue
        if EXECUTIVE_LINE.search(line):
            out.append(line.strip())
    return out


def _general_terms() -> dict[str, str]:
    """{the statute's general words: the subject's name} for each subject CIV 4935 allows in executive session."""
    from jason.community.models.meetings import EXECUTIVE_GENERAL_TERMS

    return {words.casefold(): subject.value for subject, (words, _) in EXECUTIVE_GENERAL_TERMS.items()}


@check("executive-note-open")
@_safe
def executive_note_open(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The open minutes' draft notes the executive session generally (CIV 4935(e): "generally noted in the minutes of the
    immediately following meeting that is open to the entire membership"): at least one line speaks of the session, and
    each such line names its matter only in the statute's general words (a subject 4935 allows: litigation, member discipline,
    and the like). Lines are counted, never quoted. The agenda's own wording is compared by ``minutes-checks``. None on record
    is not none held: with no line, the step is skipped with the reason if no session was held."""
    day = _meeting_day(view)
    if day is None:
        return _fail("the run has no meeting day (the meeting_on date)")
    text, why = _draft_text(readers.data_dir, day)
    if why:
        return _fail(why)
    lines = _executive_lines(text)
    evidence = readers.evidence_entries((f"file:board/minutes-draft-{day.isoformat()}.md",))
    if not lines:
        return CheckResult(False, evidence, f"no line of the {day.isoformat()} draft speaks of an executive session: if one was held "
                                            "it is generally noted here (CIV 4935(e)); if none was held, skip this step with the "
                                            "reason (none on record is not none held)")
    terms = _general_terms()
    general = [ln for ln in lines if any(t in ln.casefold() for t in terms)]
    said = f"{len(lines)} line(s) of the {day.isoformat()} draft speak of an executive session, {len(general)} in the statute's general words"
    if len(general) < len(lines):
        return CheckResult(False, evidence, said + f"; {len(lines) - len(general)} name no subject 4935 allows, so the open minutes "
                                                   "do not note the matter generally")
    return CheckResult(True, evidence, said)


@check("hearing-minutes-note")
@_safe
def hearing_minutes_note(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The next open minutes' draft (the first draft on or after the hearing day) notes the hearing's matter only by its 4935
    subject, member discipline, in the statute's general words, and no line carries the hearing's address. The hearing is found by
    its opaque handle (the run's subject); nothing but the handle and days is read out."""
    from jason.tasks import hearing_decisions

    handle, why = _hearing_handle(view)
    if why:
        return _fail(why)
    row = next((r for r in hearing_decisions.load(readers.data_dir) if r.get("handle") == handle), None)
    if row is None:
        return _fail(f"no saved hearing has the handle {handle}")
    held = day_of(str(row.get("start") or "")[:10])
    if held is None:
        return _fail(f"hearing {handle} lacks a saved day: start")
    folder = readers.data_dir / "board"
    days = sorted(d for p in (folder.glob("minutes-draft-*.md") if folder.is_dir() else ())
                  if (d := day_of(p.stem.removeprefix("minutes-draft-"))) is not None and d >= held)
    if not days:
        return _fail(f"no minutes draft on or after the hearing day {held.isoformat()} (jason board --minutes DATE)")
    day = days[0]
    text, why = _draft_text(readers.data_dir, day)
    if why:
        return _fail(why)
    lines = _executive_lines(text)
    evidence = readers.evidence_entries((f"file:board/minutes-draft-{day.isoformat()}.md", "file:zoom/hearings.json"))
    discipline = [ln for ln in lines if "member discipline" in ln.casefold()]
    address = re.sub(r"\s+", " ", str(row.get("address") or "")).strip().casefold()
    names = bool(address) and address in re.sub(r"\s+", " ", text).casefold()
    said = (f"hearing {handle} (held {held.isoformat()}): the {day.isoformat()} draft has {len(lines)} executive-session line(s), "
            f"{len(discipline)} noting member discipline")
    if names:
        return CheckResult(False, evidence, said + "; a line of the draft carries the hearing's address (4935(e) allows the subject "
                                                   "only)")
    if not discipline:
        return CheckResult(False, evidence, said + f"; none notes the matter in the statute's words: member discipline (CIV 4935(e))")
    return CheckResult(True, evidence, said)


# --- rule-change -----------------------------------------------------------------------------------------------------

def _change(readers: StoreReaders, view: RunView) -> tuple[Any, Any, CheckResult | None]:
    """(the rule change the run's subject names, the community, or the failing result)."""
    key = _key(view)
    if not key:
        return None, None, _fail("the run's subject names no rule change")
    community, why = _community(readers)
    if community is None:
        return None, None, _fail(why)
    from jason.tasks import rule_change

    try:
        return rule_change.find_change(tuple(community.rule_changes()), key), community, None
    except LookupError as exc:
        return None, None, _fail(str(exc))


@check("rule-in-force")
@_safe
def rule_in_force(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each rule the change amends or repeals can be read as a record: the stored rule records (``data/rule-records``) hold a
    version in force today for its section, with the day the board adopted it where that is on record. A section the change adds
    has nothing to read. A section with no record, or no version in force, fails; a version whose adoption day is not on record is
    named for a person (its words are the source document's, and a change since may have no adoption)."""
    change, community, failed = _change(readers, view)
    if failed is not None:
        return failed
    from jason.tasks.rules_documents import load_book, records_path

    existing = [s for s in change.sections if not s.new]
    if not existing:
        return CheckResult(True, (), f"the change adds {len(change.sections)} new section(s) and amends none: there is no version in "
                                     "force to read")
    path = records_path(readers.data_dir, change.document)
    book = load_book(path)
    if book is None:
        return _fail(f"no stored rule records for {change.document} (data/rule-records/{change.document}.json): jason "
                     "document-template rules-and-regulations --export-records keeps them")
    evidence = readers.evidence_entries((f"file:rule-records/{change.document}.json",))
    absent, no_version, unadopted, adopted = [], [], [], []
    for s in existing:
        numbers = {s.number, re.sub(r"^(\d+)\(\1\)", r"\1", s.number)}
        record = next((r for r in book.records if r.number in numbers), None)
        if record is None:
            absent.append(s.number)
            continue
        version = record.version_on(readers.today)
        if version is None:
            no_version.append(s.number)
        elif version.adopted is None:
            unadopted.append(s.number)
        else:
            adopted.append(version.adopted)
    said = (f"{len(existing)} section(s) amended: {len(adopted)} with a version in force and an adoption day on record"
            + (f" (latest {max(adopted).isoformat()})" if adopted else "") + f", {len(unadopted)} with a version in force and no adoption day")
    if absent or no_version:
        bad = [f"no record for {_some(absent)}"] if absent else []
        bad += [f"no version in force for {_some(no_version)}"] if no_version else []
        return CheckResult(False, evidence, said + "; " + "; ".join(bad))
    if unadopted:
        said += f" ({_some(unadopted)}: a person reads whether a change since has an adoption on record)"
    return CheckResult(True, evidence, said)


@check("rule-authority")
@_safe
def rule_authority(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The change's authority and conflicts can be read: each citation the change names is looked up on the authorities shelf
    **on disk** (never fetched), the stored grants of rule-making power are counted, and the profile's open conflict rows are
    counted. It passes when it reads; a citation off the shelf, no stored grant, or an open conflict is named as a flag for a
    person to acknowledge, and blocks nothing."""
    change, community, failed = _change(readers, view)
    if failed is not None:
        return failed
    from jason.community import authority_order
    from jason.tasks.export_authorities import authority_text

    shelf = [(c, bool(authority_text(readers.data_dir, c, fetch=False).get("found"))) for c in change.authorities]
    missing = [c for c, ok in shelf if not ok]
    flags = []
    if missing:
        flags.append(f"{len(missing)} of {len(shelf)} citations not on the shelf: {_some(missing)}")
    grants = None
    if (readers.data_dir / "rules" / "authority.json").is_file():
        from jason.community import rule_authority as ra

        grants = sum(1 for a in ra.stored(readers.data_dir) if a.answer is ra.Answer.GRANT and a.review is not ra.Review.REJECTED)
    if not grants:
        flags.append("no stored grant of rule-making power (jason rules --find reads them)")
    conflicts = len(authority_order.conflicts(community, open_only=True))
    if conflicts:
        flags.append(f"{conflicts} open conflict row(s) in the profile (jason conflicts)")
    said = (f"rule change {change.key}: {len(shelf) - len(missing)} of {len(shelf)} named citations are on the shelf; "
            f"{grants or 0} stored grant(s); {conflicts} open conflict row(s)")
    evidence = readers.evidence_entries(("file:authorities/manifest.json", "file:rules/authority.json"))
    return CheckResult(True, evidence, said + ("; flags for a person: " + "; ".join(flags) if flags else ""))


@check("notice-text")
@_safe
def notice_text(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The member notice of the proposed change, as ``jason rule-change`` would render it for the run's decision day, carries
    what CIV 4360(a) asks of it: the text of the proposed change and a description of its purpose and effect (the catalog's
    ``rule-change-proposed`` row, read with the change's scope and kind as facts: a listed subject, noticed). The notice is
    rendered here and nothing is saved, kept, or sent. It needs the run's decision_on day (the notice day is 28 days before)."""
    change, community, failed = _change(readers, view)
    if failed is not None:
        return failed
    decision = day_of(view.dates.get("decision_on", ""))
    if decision is None:
        return _fail("the run has no decision day (the decision_on date)")
    from jason.community.notice_catalog import requirement
    from jason.community.notice_elements import Status, check as elements, event_facts
    from jason.tasks import rule_change as rc
    from jason.tasks.applicability_asks import association_facts

    given = day_of(view.dates.get("notice_on", "")) or decision - timedelta(days=rc.NOTICE_DAYS)
    when = rc.Timeline(notice_date=given, decision=decision, comment_deadline=decision - timedelta(days=1),
                       agenda_notice_by=decision - timedelta(days=rc.AGENDA_NOTICE_DAYS),
                       adoption_notice_by=decision + timedelta(days=rc.ADOPTION_NOTICE_DAYS),
                       reversal_request_by=decision + timedelta(days=rc.ADOPTION_NOTICE_DAYS + rc.REVERSAL_REQUEST_DAYS),
                       notice_by=decision - timedelta(days=rc.NOTICE_DAYS))
    current = rc.current_sections(readers.data_dir, change.document)
    notice = rc.member_notice(change, when, current, str(getattr(community, "name", "") or "the association"))
    facts = association_facts(community, readers.data_dir).merge(
        event_facts(["rule_scope=listed_subject", "rule_change=noticed"], where="rule-change notice-text"))
    found = elements(requirement("rule-change-proposed"), notice.text, facts)
    missing = [f for f in found if f.status is Status.MISSING]
    own = [name for name, _, ok in rc.required_elements(notice, change, when) if not ok]
    unread = sum(1 for f in found if f.status is Status.UNCHECKED)
    said = (f"the notice for {change.key} (given {given.isoformat()}, decision {decision.isoformat()}): "
            f"{sum(1 for f in found if f.ok)} of {len(found)} catalog elements shown, {len(missing)} missing, {unread} for a person to read; "
            f"{len(rc.REQUIRED_ELEMENTS) - len(own)} of {len(rc.REQUIRED_ELEMENTS)} of the Act's elements on the page shown")
    evidence = readers.evidence_entries((f"file:outlines/{change.document}.json",))
    if missing or own or not found:
        bad = [f"{f.element} ({f.cite})" for f in missing] + own
        return CheckResult(False, evidence, said + (": missing " + "; ".join(bad[:SHOWN]) if bad else ": the catalog lists no element"))
    return CheckResult(True, evidence, said)


# --- election --------------------------------------------------------------------------------------------------------

@check("election-rules-window")
@_safe
def election_rules_window(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """No election operating rule was adopted or took effect inside the 90 days before the election (CIV 5105(h)(4)(B)(iii): "not
    amended less than 90 days prior to the election"), counted from the run's count_on day. Read from the rule changes the
    profile records and from the stored rule records' versions, taking as election rules those whose subject or heading is
    elections. It passes only when at least one of the two sources was read and none falls in the window; a change inside the
    window is named by its key, and the dates move. A plain day-count, no holiday or weekend rule."""
    election = day_of(view.dates.get("count_on", ""))
    if election is None:
        return _fail("the run has no election day (the count_on date)")
    start = election - timedelta(days=ELECTION_RULES_DAYS)
    inside = lambda d: d is not None and start < d <= election                    # noqa: E731 - "less than 90 days prior"
    community, why = _community(readers)
    found: list[str] = []
    read = 0
    records = getattr(community, "rule_change_records", None) if community is not None else None
    if records is not None:
        rows = [r for r in records() if re.search(r"election", f"{r.title} {r.document_title} {r.document}", re.I)]
        read += 1
        found += [f"{r.key} ({d.isoformat()})" for r in rows for d in (r.decided, r.effective) if inside(d)]
    from jason.tasks.rules_documents import load_book

    folder = readers.data_dir / "rule-records"
    books = sorted(folder.glob("*.json")) if folder.is_dir() else []
    for path in books:
        book = load_book(path)
        if book is None:
            continue
        read += 1
        for record in book.records:
            if "elections" not in record.subjects and not re.search(r"election", record.title or "", re.I):
                continue
            for v in record.versions:
                found += [f"{record.id} ({d.isoformat()})" for d in (v.adopted, v.effective) if not v.proposed and inside(d)]
    if not read:
        return _fail("neither the profile's rule-change records nor any stored rule records can be read" + (f" ({why})" if why else ""))
    said = f"the window runs from {start.isoformat()} (exclusive) to the election on {election.isoformat()}; {read} source(s) read"
    evidence = readers.evidence_entries(("glob:rule-records/*.json",))
    if found:
        return CheckResult(False, evidence, said + f"; {_plural(len(found), 'election-rule change')} inside it: {_some(sorted(found))} "
                                                   "(the dates move; no clock is shortened)")
    return CheckResult(True, evidence, said + "; none on record inside it (none on record is not none made)")


# --- hearing ---------------------------------------------------------------------------------------------------------

def _hearing(readers: StoreReaders, view: RunView) -> tuple[dict[str, Any] | None, str]:
    """(the saved hearing the run's handle names, why not)."""
    from jason.tasks import hearing_decisions

    handle, why = _hearing_handle(view)
    if why:
        return None, why
    row = next((r for r in hearing_decisions.load(readers.data_dir) if r.get("handle") == handle), None)
    if row is None:
        return None, f"no saved hearing has the handle {handle}"
    return row, ""


def _delivery(root: Path, keys: list[str]) -> dict[str, Any]:
    """What the notice ledger holds under the first of ``keys`` it has anything for: attempts, members reached, outcomes still
    unknown, the first send's day, and whether a posting is recorded. Counts and days only."""
    from jason.tasks import notice_ledger

    for key in keys:
        attempts, posted, why = _ledger(root, key)
        if why:
            return {"why": why}
        if not attempts and not posted:
            continue
        people = notice_ledger.standing(attempts, general=posted)
        days = sorted(a.sent_at[:10] for a in attempts if a.sent_at)
        return {"key": key, "attempts": len(attempts), "reached": sum(1 for s in people if s.reached), "posted": posted,
                "pending": sum(1 for a in attempts if a.status is notice_ledger.Delivery.PENDING), "first": days[0] if days else ""}
    return {"none": True}


@check("hearing-delivery-read")
@_safe
def hearing_delivery_read(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The hearing's notice was delivered, and in time: the notice ledger (key ``discipline-hearing-DAY``, the hearing day or the
    day the notice was delivered) shows a copy that reached the member, with no outcome still unknown, and the delivery day (the
    person's recorded day, else the first send in the ledger) is no later than the notice-by day (CIV 5855(a)). A hearing notified
    late moves: a new day and a new notice. The hearing is found by its opaque handle; units, names, and the matter are never
    read out, only counts and days."""
    row, why = _hearing(readers, view)
    if row is None:
        return _fail(why)
    held = day_of(str(row.get("start") or "")[:10])
    notice_by = day_of(row.get("noticeBy"))
    recorded = day_of(row.get("noticeOn"))
    handle = row.get("handle")
    if held is None or notice_by is None:
        return _fail(f"hearing {handle} lacks a saved day: {'start' if held is None else 'noticeBy'}")
    keys = [f"discipline-hearing-{held.isoformat()}"] + ([f"discipline-hearing-{recorded.isoformat()}"] if recorded else [])
    found = _delivery(readers.data_dir, keys)
    if found.get("why"):
        return _fail(found["why"])
    evidence = readers.evidence_entries(("file:notices/deliveries.db", "file:zoom/hearings.json"))
    if found.get("none"):
        return CheckResult(False, evidence, f"the ledger holds no copy of the notice of hearing {handle} and no posting "
                                            f"({keys[0]}): none on record is not none given")
    if found["pending"]:
        return CheckResult(False, evidence, f"{found['pending']} of {found['attempts']} copies of the notice of hearing {handle} have "
                                            f"no outcome yet (jason notices {found['key']} --sync)")
    if not found["reached"] and not found["posted"]:
        return CheckResult(False, evidence, f"no copy of the notice of hearing {handle} reached the member ({found['attempts']} "
                                            "sent): a new notice and, if it is late, a new day")
    delivered = recorded or day_of(found["first"])
    said = (f"notice of hearing {handle}: {found['attempts']} copy/copies, {found['reached']} reached; delivery day "
            f"{delivered.isoformat() if delivered else 'not on record'}, notice-by day {notice_by.isoformat()}")
    if delivered is None:
        return CheckResult(False, evidence, said + ": no delivery day is on record")
    if delivered > notice_by:
        return CheckResult(False, evidence, said + ": delivered after the notice-by day, so the hearing moves (a new day and a new "
                                                   "notice; whether a resend cures is for the board or counsel)")
    return CheckResult(True, evidence, said + " (CIV 5855(a); the delivery day beyond a recorded one is the ledger's first send)")


@check("hearing-requirements-met")
@_safe
def hearing_requirements_met(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each requirement of CIV 5855 that stored days can show is shown met or not met, from the saved hearing and the notice
    ledger: the notice given at least 10 days before (5855(a)), delivered (4040), the hearing held, the board's findings recorded,
    and the decision's notice delivered within 14 days of the action (5855(f)). It states what is on record; whether the
    requirements were fulfilled is the board's and counsel's to say (5855(g)). Counts and days only, never the matter."""
    row, why = _hearing(readers, view)
    if row is None:
        return _fail(why)
    handle = row.get("handle")
    held = day_of(str(row.get("start") or "")[:10])
    if held is None:
        return _fail(f"hearing {handle} lacks a saved day: start")
    notified = day_of(row.get("noticeOn"))
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    decided = day_of(decision.get("decidedOn"))
    due = day_of(decision.get("noticeDueBy"))
    notice = _delivery(readers.data_dir, [f"discipline-hearing-{held.isoformat()}"]
                       + ([f"discipline-hearing-{notified.isoformat()}"] if notified else []))
    if notice.get("why"):
        return _fail(notice["why"])
    sent = _delivery(readers.data_dir, [f"discipline-decision-{decided.isoformat()}"] if decided else [])
    rows: list[tuple[str, bool | None]] = [
        ("notice at least 10 days before the hearing (5855(a))", None if notified is None else notified <= held - timedelta(days=10)),
        ("notice delivered (5855(a), 4040)", None if notice.get("none") else bool(notice.get("reached") or notice.get("posted"))),
        ("hearing held", held <= readers.today),
        ("board's findings recorded", True if decided else None),
        ("decision delivered within 14 days of the action (5855(f))",
         None if (sent.get("none") or not decided or due is None or not sent.get("first"))
         else bool(sent.get("reached") and day_of(sent["first"]) <= due)),
    ]
    met = [name for name, ok in rows if ok]
    unmet = [name for name, ok in rows if ok is False]
    unknown = [name for name, ok in rows if ok is None]
    said = (f"hearing {handle} (held {held.isoformat()}): {len(met)} of {len(rows)} requirements shown met on record"
            + (f"; not met: {'; '.join(unmet)}" if unmet else "") + (f"; not on record: {'; '.join(unknown)}" if unknown else ""))
    evidence = readers.evidence_entries(("file:zoom/hearings.json", "file:notices/deliveries.db"))
    if unmet or unknown:
        return CheckResult(False, evidence, said + " (jason states what is on record; the board and counsel decide, CIV 5855(g))")
    return CheckResult(True, evidence, said + " (the board and counsel decide whether 5855 was fulfilled, CIV 5855(g))")


# --- law-review ------------------------------------------------------------------------------------------------------

_STATUTE = re.compile(r"\b(?P<code>[A-Z]{2,5})\s+(?P<number>\d+(?:\.\d+)?[a-z]?)")
_CLAUSE = re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+)*#[A-Za-z0-9][A-Za-z0-9.()\-]*")


@check("retire-reasons")
@_safe
def retire_reasons(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Each people-task rule that retires a duty (``Community.people_task_rules()``, a row with a ``retire`` reason) cites a source
    the shelf can show: a statute section on the authorities shelf **on disk**, or a governing document's clause (read by a
    person). A repealed filing or an exemption retires a duty only on its source, so a reason with no source, or a statute off the
    shelf, fails and is named by the rule's key. It passes with none to check."""
    community, why = _community(readers)
    if community is None:
        return _fail(why)
    from jason.community import law_text

    rules = [r for r in getattr(community, "people_task_rules", lambda: ())() if getattr(r, "retire", "")]
    if not rules:
        return CheckResult(True, (), "the profile sets no retire reason, so none is to be checked")
    unsourced, off, shelf, clauses = [], [], 0, 0
    for rule in rules:
        statutes = list(dict.fromkeys(f"{m['code']} {m['number']}" for m in _STATUTE.finditer(rule.source or "")))
        clause = bool(_CLAUSE.search(rule.source or ""))
        if not statutes and not clause:
            unsourced.append(rule.key)
            continue
        held = [law_text.versions(f"{s}", readers.data_dir) for s in statutes]
        if statutes and not all(held):
            off.append(rule.key)
        elif statutes:
            shelf += 1
        else:
            clauses += 1
    said = (f"{_plural(len(rules), 'retire reason')}: {shelf} cite a section on the shelf, {clauses} a clause for a person to read, "
            f"{len(unsourced)} cite no source, {len(off)} cite a section off the shelf")
    evidence = readers.evidence_entries(("file:authorities/manifest.json",))
    if unsourced or off:
        return CheckResult(False, evidence, said + ": " + "; ".join(
            ([f"no source: {_some(unsourced)}"] if unsourced else []) + ([f"off the shelf: {_some(off)}"] if off else [])))
    return CheckResult(True, evidence, said)


# --- owners-manual ---------------------------------------------------------------------------------------------------

NUMBERED_CAPITAL = re.compile(r"^[ \t]*(?:[A-Z]-)?\d+(?:\.\d+)*[.)]?[ \t]+(?P<words>[A-Z][A-Z0-9 ,;:&'()/\-]*[A-Z])[ \t]*$", re.M)
"""A line that opens with a number and is then in capitals: the shape of a section heading in a printed document."""


def _manual_key(readers: StoreReaders) -> tuple[str, str]:
    """(the owner's manual's outline key, why not): the profile's ``owners_manual()`` row names it."""
    community, why = _community(readers)
    if community is None:
        return "", why
    spec = getattr(community, "owners_manual", lambda: None)()
    if spec is None or not getattr(spec, "document", ""):
        return "", "the profile has no owner's manual (Community.owners_manual())"
    return str(spec.document), ""


def _outline(readers: StoreReaders, key: str) -> Any:
    from jason.community.outlines import DocumentOutline

    path = readers.data_dir / "outlines" / f"{key}.json"
    if not path.is_file():
        return None
    return DocumentOutline.from_dict(json.loads(path.read_text(encoding="utf-8")))


@check("manual-headings")
@_safe
def manual_headings(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """Every numbered capital line of the owner's manual, as its stored outline (``data/outlines``) holds the text, opens a
    section the outline reads: a heading the outline missed is named by its number. This reads the stored outline's own text;
    comparing it with the PDF is the benchmark script's (``scripts/structure_fuzz.py``), which needs the PDF. It fails when
    the text has no numbered capital line, since nothing was then compared."""
    key, why = _manual_key(readers)
    if not key:
        return _fail(why)
    outline = _outline(readers, key)
    if outline is None:
        return _fail(f"no outline of {key} on disk: jason outlines --fetch (read-only) reads it")
    starts = sorted(s.start for s in outline.sections)
    lines = list(NUMBERED_CAPITAL.finditer(outline.text))
    missed = [m.group(0).strip().split()[0] for m in lines if not any(m.start() <= s <= m.end() for s in starts)]
    evidence = readers.evidence_entries((f"file:outlines/{key}.json",))
    if not lines:
        return CheckResult(False, evidence, f"the stored outline of {key} has no numbered capital line, so no heading was compared")
    said = f"{len(lines)} numbered capital line(s) in the outline of {key}, {len(lines) - len(missed)} open a section"
    if missed:
        return CheckResult(False, evidence, said + f"; not a heading: {_some(missed)} (a person says each is not one, or the Doc's style "
                                                   "is corrected)")
    return CheckResult(True, evidence, said)


@check("manual-concordance")
@_safe
def manual_concordance(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The manual's concordance (``data/manual/KEY/concordance.json``, written by ``jason manual --concordance``) resolves every
    existing citation of the manual to a new address: none is unresolved. It also fails when the concordance was built from an
    older revision of the outline than the one on disk."""
    key, why = _manual_key(readers)
    if not key:
        return _fail(why)
    folder = readers.data_dir / "manual" / key
    path = folder / "concordance.json"
    if not path.is_file():
        return _fail(f"no concordance for {key} (data/manual/{key}/concordance.json): jason manual --concordance writes it")
    raw = json.loads(path.read_text(encoding="utf-8"))
    refs = raw.get("references") or []
    unresolved = [f"{r.get('where')} cites {r.get('ref')}" for r in refs if not r.get("new")]
    evidence = readers.evidence_entries((f"file:manual/{key}/concordance.json", f"file:manual/{key}/classification.json"))
    built = ""
    try:
        built = str(json.loads((folder / "classification.json").read_text(encoding="utf-8")).get("revision") or "")
    except (OSError, ValueError):
        pass
    outline = _outline(readers, key)
    now = str(outline.revision) if outline is not None and outline.revision else ""
    said = f"{len(raw.get('rows') or [])} addresses mapped; {len(refs) - len(unresolved)} of {len(refs)} existing citations resolved"
    if built and now and built != now:
        return CheckResult(False, evidence, said + f"; built from revision {built} and the outline is now {now} (jason manual --concordance "
                                                   "again)")
    if unresolved:
        return CheckResult(False, evidence, said + f"; {len(unresolved)} unresolved: {_some(unresolved)} (an unresolved citation blocks the "
                                                   "render)")
    return CheckResult(True, evidence, said)


def _plain(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


@check("manual-template-equal")
@_safe
def manual_template_equal(readers: StoreReaders, view: RunView, item: str = "") -> CheckResult:
    """The manual rendered from its definition (``data/drafts/owners-manual.document.md``, from ``jason document-template
    owners-manual``) is the manual ``jason manual --render`` wrote (``owners-manual.md``), line endings and trailing spaces aside,
    and the render's own check (``data/manual/KEY/render.json``) leaves no unlabeled difference. It also fails when the
    definition's rendering is older than the manual's. Neither rendering is made here."""
    key, why = _manual_key(readers)
    if not key:
        return _fail(why)
    drafts = readers.data_dir / "drafts"
    manual, document = drafts / "owners-manual.md", drafts / "owners-manual.document.md"
    for path in (manual, document):
        if not path.is_file():
            return _fail(f"no data/drafts/{path.name}: " + ("jason manual --render writes it" if path is manual
                                                              else "jason document-template owners-manual writes it"))
    check_path = readers.data_dir / "manual" / key / "render.json"
    if not check_path.is_file():
        return _fail(f"no render check for {key} (data/manual/{key}/render.json): jason manual --render writes it")
    render = json.loads(check_path.read_text(encoding="utf-8"))
    unlabeled = len(render.get("unlabeled") or [])
    same = _plain(manual.read_text(encoding="utf-8")) == _plain(document.read_text(encoding="utf-8"))
    evidence = readers.evidence_entries(("file:drafts/owners-manual.md", "file:drafts/owners-manual.document.md",
                                         f"file:manual/{key}/render.json"))
    said = f"identical: {'yes' if same else 'NO'}; {unlabeled} unlabeled piece(s)"
    if not same:
        return CheckResult(False, evidence, said + " (the definition's rendering differs from the manual's)")
    if document.stat().st_mtime + 1 < manual.stat().st_mtime:
        return CheckResult(False, evidence, said + "; the definition's rendering is older than the manual's: render it again")
    if unlabeled:
        return CheckResult(False, evidence, said + " (a difference no label explains is a finding)")
    return CheckResult(True, evidence, said)


__all__ = ["election_rules_window", "executive_note_open", "hearing_dates", "hearing_delivery_read", "hearing_minutes_note",
           "hearing_requirements_met", "manual_concordance", "manual_headings", "manual_template_equal", "meeting_clocks",
           "minutes_checks", "notice_delivery_read", "notice_text", "readings_stale", "retire_reasons", "rule_authority",
           "rule_in_force", "rule_stages", "run_complete", "schedule_coverage", "schedule_due", "shelf_cites"]
