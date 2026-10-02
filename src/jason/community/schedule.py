"""Who does each duty, and when: the association's assignments, so no duty goes unowned.

A duty comes from the law (a statute), the governing documents (``deontic.DocumentDuty``, by section), the notice catalog
(a requirement's key), or a recurring deadline (``obligations.Obligation``). An ``Assignment`` names the duties it
covers, the role that owns them, and when they fall due:

- **CADENCE**: on a calendar: monthly (on a day), every N months, or each year on a month and day;
- **ANCHORED**: a clock from an anchor the association already keeps: each board meeting, the annual meeting, the
  fiscal year's end (``offset_days`` before or after);
- **EVENT**: a clock an event starts (a records request, a hearing request, a payment of a lien): the module that
  handles the event runs it (``handled_by``), so the schedule names who and where, not a date;
- **STANDING**: a continuing rule with no occurrence (never spend reserve funds otherwise), owned all the same.

jason proposes; the board adopts (``Adoption``), naming the minutes or resolution. A role is the office, never a
person: who holds it is the board's record, kept privately. ``coverage`` lists every duty no assignment covers, so a
duty is assigned, handled by an event's module, or marked not applicable with a reason; never silently unowned.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class Role(Enum):
    BOARD = "board"
    PRESIDENT = "president"
    VICE_PRESIDENT = "vice president"
    SECRETARY = "secretary"
    TREASURER = "treasurer"
    MANAGER = "manager"
    INSPECTOR = "inspector of elections"
    COMMITTEE = "committee"
    COUNSEL = "counsel"
    JASON = "jason"                      # a jason command does it (``Assignment.jason``), and a person sees the result
    OWNERS = "owners"                    # a duty the documents put on each owner; the association may remind


class Trigger(Enum):
    CADENCE = "cadence"
    ANCHORED = "anchored"
    EVENT = "event"
    STANDING = "standing"


class Anchor(Enum):
    NONE = "none"
    BOARD_MEETING = "each board meeting"
    ANNUAL_MEETING = "the annual meeting"
    FISCAL_YEAR_END = "the fiscal year's end"


class Adoption(Enum):
    PROPOSED = "proposed"                # jason's proposal; the board has not decided
    ADOPTED = "adopted"                  # the board adopted it (``adopted`` names the minutes or resolution)
    DECLINED = "declined"                # the board chose otherwise (``note`` says how the duty is met)
    NOT_APPLICABLE = "not applicable"    # the duty does not apply (completed, the declarant's era): ``note`` says why


@dataclass(frozen=True)
class Assignment:
    key: str
    title: str
    role: Role
    covers: tuple[str, ...]              # "CIV 5500", "bylaws#9.6", "notice:board-meeting", "obligation:<name>"
    trigger: Trigger
    every_months: int = 0                # CADENCE: 1 monthly, 3 quarterly, 12 yearly
    month: int = 0                       # CADENCE yearly: the month and day it is due
    day: int = 0                         # CADENCE monthly: the day of the month (0: the month's last day)
    anchor: Anchor = Anchor.NONE         # ANCHORED: what the clock runs from
    offset_days: int = 0                 # ANCHORED: days after the anchor (negative: before)
    handled_by: str = ""                 # EVENT: the module or command that runs the clock
    evidence: str = ""                   # what shows it done (the minutes, a payment, a jason store, a notice proof)
    jason: str = ""                      # a jason command that does it or checks it
    backup: Role | None = None
    adoption: Adoption = Adoption.PROPOSED
    adopted: str = ""                    # the minutes or resolution that adopted it
    note: str = ""

    def covers_ref(self, ref: str) -> bool:
        """Whether this assignment covers a duty reference: equal, a section inside one it names ("bylaws#9.6(a)"
        inside "bylaws#9.6"), or any section of a document or article it names ("collection-policy", "bylaws#6")."""
        return any(ref == c or ref.startswith(c + "(") or ref.startswith(c + ".") or ref.startswith(c + ":")
                   or ref.startswith(c + "#") for c in self.covers)

    def cadence(self) -> str:
        if self.trigger is Trigger.CADENCE:
            if self.every_months == 12 and self.month:
                return f"each year by {calendar.month_name[self.month]} {self.day or 'end'}"
            name = {1: "monthly", 3: "quarterly", 6: "semiannually", 12: "yearly"}.get(self.every_months,
                                                                                      f"every {self.every_months} months")
            return name + (f", by day {self.day}" if self.day else "")
        if self.trigger is Trigger.ANCHORED:
            if self.offset_days == 0:
                return f"at {self.anchor.value}"
            side = "after" if self.offset_days > 0 else "before"
            return f"{abs(self.offset_days)} days {side} {self.anchor.value}"
        if self.trigger is Trigger.EVENT:
            return f"on the event ({self.handled_by})" if self.handled_by else "on the event"
        return "standing"


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def occurrences(a: Assignment, start: date, end: date, anchors: dict[Anchor, list[date]] | None = None) -> list[date]:
    """The days ``a`` falls due between ``start`` and ``end`` (inclusive). An event or a standing duty has none."""
    out: list[date] = []
    if a.trigger is Trigger.CADENCE and a.every_months:
        if a.every_months == 12 and a.month:
            for year in range(start.year, end.year + 1):
                due = date(year, a.month, min(a.day or 31, calendar.monthrange(year, a.month)[1]))
                if start <= due <= end:
                    out.append(due)
            return out
        year, month = start.year, start.month
        while date(year, month, 1) <= end:
            if (month - 1) % a.every_months == 0 or a.every_months == 1:
                last = _month_end(year, month)
                due = date(year, month, min(a.day, last.day)) if a.day else last
                if start <= due <= end:
                    out.append(due)
            year, month = (year, month + 1) if month < 12 else (year + 1, 1)
        return out
    if a.trigger is Trigger.ANCHORED and anchors:
        for day in anchors.get(a.anchor, []):
            due = day + timedelta(days=a.offset_days)
            if start <= due <= end:
                out.append(due)
    return sorted(out)


def anchors_for(community: object, start: date, end: date) -> dict[Anchor, list[date]]:
    """The anchor days the specification gives: each regular board meeting (monthly in practice, as the schedule says),
    the annual meeting (the same weekday in its month), and the fiscal year's end."""
    out: dict[Anchor, list[date]] = {a: [] for a in Anchor}
    schedule = getattr(community, "meeting_schedule", lambda: None)()
    if schedule is not None:
        year, month = start.year, start.month
        while date(year, month, 1) <= end:
            day = schedule.day_in(year, month)
            if start <= day <= end:
                out[Anchor.BOARD_MEETING].append(day)
                if schedule.annual_month == month:
                    out[Anchor.ANNUAL_MEETING].append(day)
            year, month = (year, month + 1) if month < 12 else (year + 1, 1)
    fy = getattr(community, "fiscal_year_end", lambda: None)()
    if fy:
        for year in range(start.year, end.year + 1):
            day = date(year, fy[0], fy[1])
            if start <= day <= end:
                out[Anchor.FISCAL_YEAR_END].append(day)
    return out


def assignments(community: object | None = None) -> tuple[Assignment, ...]:
    return tuple(getattr(community, "assignments", lambda: ())()) if community is not None else ()


def covering(ref: str, rows: tuple[Assignment, ...]) -> list[Assignment]:
    return [a for a in rows if a.covers_ref(ref)]


__all__ = ["Adoption", "Anchor", "Assignment", "Role", "Trigger", "anchors_for", "assignments", "covering",
           "occurrences"]
