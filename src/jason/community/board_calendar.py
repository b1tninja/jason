"""What the board's calendar carries: the titles of the events jason keeps there, and how long a meeting is held open.

The specification sets one ``CalendarPolicy``. The periods are the statute's (``NOTICE_DAYS``, CIV 4920(a); the
hearing's in ``jason.zoom.models``), not the specification's. An event title names no owner and no address.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

NOTICE_DAYS = 4                        # CIV 4920(a): notice and agenda at least four days before a board meeting


class EventKind(str, Enum):
    """What a planned event is. The value is the first part of the event's stable key."""

    BOARD_MEETING = "board-meeting"
    MEETING_NOTICE = "meeting-notice"
    HEARING = "hearing"
    HEARING_NOTICE = "hearing-notice"
    HEARING_DECISION = "hearing-decision"
    DEADLINE = "deadline"


@dataclass(frozen=True)
class CalendarPolicy:
    """The board's calendar. ``regular_title`` is a meeting in one of the schedule's regular months, ``special_title``
    one in any other month. ``covered_words`` are words in an event jason did not make (a PayHOA or Zoom invitation)
    that show the day's board meeting is already on the calendar; jason then adds no second one."""

    regular_title: str = "Regular Meeting of the Board of Directors"
    special_title: str = "Special Meeting of the Board of Directors"
    meeting_minutes: int = 90
    notice_title: str = "Board meeting notice and agenda due"
    hearing_title: str = "Board hearing"
    hearing_notice_title: str = "Board hearing: notice due"
    hearing_decision_title: str = "Board hearing: written decision due if the board acted"
    deadline_prefix: str = "Deadline: "
    covered_words: tuple[str, ...] = ("board of directors", "board meeting")
    months: int = 3


__all__ = ["NOTICE_DAYS", "CalendarPolicy", "EventKind"]
