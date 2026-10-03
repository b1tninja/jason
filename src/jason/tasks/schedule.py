"""The association's schedule: what falls due, who owns it, what shows it done, and which duties nobody owns.

``agenda`` lists each assignment's occurrences in a window (``schedule.occurrences``), with its standing: done (a
completion recorded for that day), overdue, due soon, or upcoming. A completion is recorded by a person
(``record_done``) in ``data/schedule/done.jsonl``: the assignment, the day it was due, the day it was done, who did it,
and the evidence (the minutes' date and item, a payment, a notice proof). ``coverage`` checks every duty jason knows of
against the assignments:

- the association's own duties the governing documents state (``deontic`` readings: duties whose bearer is the
  association, the board, an officer, a committee, the inspector, the manager, or unstated; a rejected reading is left
  out), by ``source#section``;
- every requirement of the notice catalog, by ``notice:<key>``;
- every recurring deadline, by ``obligation:<name>``.

A duty no assignment covers is listed: assign it, or mark why it needs none. Owners' and occupants' duties are the
owners'; ``owner-maintenance`` and similar rows cover the ones the association chooses to remind.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.schedule import Assignment, Trigger, anchors_for, assignments, covering, occurrences

SOON_DAYS = 14
ASSOCIATION_BEARERS = ("association", "board", "officer", "committee", "inspector", "manager", "unstated")


def done_path(data_dir: Path) -> Path:
    return Path(data_dir) / "schedule" / "done.jsonl"


def completions(data_dir: Path) -> list[dict[str, Any]]:
    path = done_path(data_dir)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_done(data_dir: Path, key: str, due: date, done_on: date, by: str, evidence: str) -> dict[str, Any]:
    """A person's record that an occurrence was done: who, when, and the evidence. Never without a name and evidence."""
    if not by or not evidence:
        raise ValueError("a completion names who did it and the evidence")
    row = {"key": key, "due": due.isoformat(), "done": done_on.isoformat(), "by": by, "evidence": evidence,
           "recorded": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path = done_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return row


@dataclass(frozen=True)
class Occurrence:
    assignment: Assignment
    due: date
    standing: str                      # done, overdue, due soon, upcoming
    done: dict[str, Any] | None = None


def agenda(community: Any, data_dir: Path, *, start: date, end: date, today: date | None = None) -> list[Occurrence]:
    """Every occurrence of every assignment (not declined or not applicable) from ``start`` to ``end``."""
    from jason.community.schedule import Adoption

    today = today or date.today()
    anchors = anchors_for(community, start, end)
    done = {(r["key"], r["due"]): r for r in completions(data_dir)}
    out = []
    for a in assignments(community):
        if a.adoption in (Adoption.DECLINED, Adoption.NOT_APPLICABLE):
            continue
        for due in occurrences(a, start, end, anchors):
            record = done.get((a.key, due.isoformat()))
            if record:
                standing = "done"
            elif due < today:
                standing = "overdue"
            elif due <= today + timedelta(days=SOON_DAYS):
                standing = "due soon"
            else:
                standing = "upcoming"
            out.append(Occurrence(a, due, standing, record))
    return sorted(out, key=lambda o: (o.due, o.assignment.role.value, o.assignment.key))


def duty_refs(community: Any, data_dir: Path) -> list[tuple[str, str]]:
    """Every duty jason knows of, as (reference, what it says): the association's document duties, the notice
    catalog, the recurring deadlines. A reference whose duty has a deadline or a recurrence is in ``timed_refs``."""
    return [(ref, text) for ref, text, _ in _refs(community, data_dir)]


def timed_refs(community: Any, data_dir: Path) -> set[str]:
    """The references whose duty runs on a clock: a document duty with a deadline or recurrence, every notice
    requirement, every recurring deadline."""
    return {ref for ref, _, timed in _refs(community, data_dir) if timed}


def _refs(community: Any, data_dir: Path) -> list[tuple[str, str, bool]]:
    from jason.community.deontic import DutyKind, ReviewStatus
    from jason.tasks.document_duties import stored

    refs: list[tuple[str, str, bool]] = []
    seen: dict[str, int] = {}
    folder = Path(data_dir) / "duties"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        for d in stored(data_dir, path.stem):
            if d.kind is not DutyKind.DUTY or d.review is ReviewStatus.REJECTED:
                continue
            if d.bearer.value not in ASSOCIATION_BEARERS:
                continue
            ref = f"{d.source}#{d.section}"
            if ref not in seen:
                seen[ref] = len(refs)
                refs.append((ref, " ".join(d.quote.split())[:160], d.timed))
            elif d.timed:
                ref_, text, _ = refs[seen[ref]]
                refs[seen[ref]] = (ref_, " ".join(d.quote.split())[:160], True)
    try:
        from jason.community.notice_catalog import REQUIREMENTS

        refs += [(f"notice:{r.key}", r.title, True) for r in REQUIREMENTS]
    except ImportError:
        pass
    refs += [(f"obligation:{o.name}", o.authority, True) for o in getattr(community, "obligations", lambda: ())()]
    return refs


def coverage(community: Any, data_dir: Path) -> tuple[list[tuple[str, str, list[str]]], list[tuple[str, str]]]:
    """(covered, uncovered): each duty with the assignments that cover it, and the duties none covers."""
    rows = assignments(community)
    covered, uncovered = [], []
    for ref, text in duty_refs(community, data_dir):
        who = [a.key for a in covering(ref, rows)]
        (covered if who else uncovered).append((ref, text, who) if who else (ref, text))
    return covered, uncovered


def unscheduled(community: Any, data_dir: Path) -> list[tuple[str, str, list[str]]]:
    """Duties on a clock that are owned only by standing assignments: assigned, but nothing sets their dates. Each
    needs a cadence, an anchored clock, or an event's module."""
    rows = assignments(community)
    out = []
    for ref, text, timed in _refs(community, data_dir):
        if not timed:
            continue
        who = covering(ref, rows)
        if who and all(a.trigger is Trigger.STANDING for a in who):
            out.append((ref, text, [a.key for a in who]))
    return out


def lines(found: list[Occurrence]) -> list[str]:
    out = []
    for o in found:
        a = o.assignment
        mark = {"done": "done", "overdue": "OVERDUE", "due soon": "due soon", "upcoming": "upcoming"}[o.standing]
        tail = f" (done {o.done['done']} by {o.done['by']}: {o.done['evidence']})" if o.done else ""
        cond = f" (only if {a.applies_if})" if a.applies_if else ""
        out.append(f"{o.due}  {mark:9} {a.role.value:22} {a.title}{cond} [{a.key}; {a.adoption.value}]{tail}")
    return out


def assignment_lines(rows: tuple[Assignment, ...]) -> list[str]:
    out = []
    for a in rows:
        extra = f"; backup {a.backup.value}" if a.backup else ""
        cond = f" Only if {a.applies_if}." if a.applies_if else ""
        out.append(f"- **{a.key}** ({a.adoption.value}): {a.title}. {a.role.value}{extra}; {a.cadence()}.{cond}"
                   + (f" Evidence: {a.evidence}." if a.evidence else "") + (f" jason: `{a.jason}`." if a.jason else "")
                   + (f" {a.note}" if a.note else ""))
    return out


__all__ = ["Occurrence", "agenda", "assignment_lines", "completions", "coverage", "duty_refs", "lines", "record_done",
           "timed_refs", "unscheduled"]
