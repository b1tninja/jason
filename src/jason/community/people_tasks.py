"""People's own tasks and events: what the board keeps in Google Tasks and on its calendar, read beside what jason tracks.

jason writes keyed items to Google (``schedule_sync``'s ``schedule:`` events and tasks, the board calendar's events, the
action register's tasks), and people keep their own beside them: a reminder to renew a policy, a seasonal chore, a call
to make. Those are read here, never written. Each is matched to what jason already tracks:

- an **assignment** in the schedule (``Community.assignments()``), by a rule row or the assignment's own title;
- a **recurring deadline** (``obligation:<name>``);
- an item on the board's **action register** (``data/board/items.json``), by its title;
- a member's **request** of a kind the response handler answers;
- the **board meetings** the board calendar plans (the calendar policy's words);
- an **insurance policy** in the insurance store, whose renewal the deadlines carry.

What matches nothing is classified: **recurring** (a series on the calendar, a title that comes back, or a rule that says
the duty recurs) is a clock jason should have, and is proposed; the rest is a **one-off**. Either is **stale** when it is
an open task whose due day has passed. A rule may say a task's duty no longer exists (``retire``): the item is then a
proposal to close it, in Google, by a person.

The profile's rule rows (``Community.people_task_rules()``) are tried in order before the general matches, and the
first that fits wins. A match is a lead for a person, not a mark: jason never completes, edits, or deletes a person's
task or event. A title can name an owner or a unit, so it stays in the private store and the private outputs; a rule's
``label`` is what a shared output prints instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# Google Calendar shows a task with a due day as an event whose description begins with this; it is the task's mirror,
# not a second item.
TASK_MIRROR = "Changes made to the title, description, or attachments will not be saved"


class Tracker(Enum):
    """What jason already keeps that a person's task or event can stand for."""

    ASSIGNMENT = "assignment"            # ``ref``: an assignment's key
    OBLIGATION = "obligation"            # ``ref``: a recurring deadline's name
    BOARD_ITEM = "board item"            # ``ref``: an action register item's id ("" for the register as a whole)
    REQUEST = "request"                  # ``ref``: a request kind the response handler answers
    BOARD_MEETING = "board meeting"      # the meetings the board calendar plans
    INSURANCE = "insurance policy"       # ``ref``: a policy kind's value ("flood", "master"); "" for any


class Kind(Enum):
    COVERED = "covered"                  # jason tracks it
    RECURRING = "untracked recurring"    # a duty that comes back and has no clock in jason: a proposal
    ONE_OFF = "one-off"


class Source(Enum):
    TASK = "task"
    EVENT = "event"


@dataclass(frozen=True)
class PeopleTaskRule:
    """One rule row: a person's task or event whose title matches ``pattern`` (a regular expression, any case).

    ``tracker`` and ``ref`` name what jason tracks it by; with no tracker the rule only classifies. ``recurring`` says
    the duty comes back (a seasonal chore seen once is still recurring). ``label`` is what a shared output prints in
    place of the title: a kind of task, never a person or a unit. ``retire`` is why the task's duty no longer exists
    (a rule withdrawn, a filing no longer required): the item becomes a proposal to close it. ``source`` cites the
    authority behind ``retire`` or the clock."""

    key: str
    pattern: str
    label: str
    tracker: Tracker | None = None
    ref: str = ""
    recurring: bool = False
    retire: str = ""
    source: str = ""
    note: str = ""

    def matches(self, title: str) -> bool:
        return bool(re.search(self.pattern, title or "", re.IGNORECASE))


@dataclass(frozen=True)
class Match:
    tracker: Tracker
    ref: str
    how: str                             # "rule <key>", "board item title", "assignment title", "calendar words"
    valid: bool = True                   # False: a rule names something jason does not keep (a miss, said so)


def normal_title(title: str) -> str:
    """A title folded for comparing: case, punctuation, and spacing removed."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", (title or "").casefold()).split())


__all__ = ["Kind", "Match", "PeopleTaskRule", "Source", "TASK_MIRROR", "Tracker", "normal_title"]
