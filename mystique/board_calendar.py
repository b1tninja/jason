"""Mystique's board calendar: the titles of the events jason keeps on it.

A meeting in January, April, July, or October is a regular meeting under Administrative Resolution 20230130-1. The board
meets every month in practice; whether the other months' meetings are regular or special is before the board (board item
meeting-schedule-resolution), so their events are titled without deciding it. The board's Zoom invitations already say
"Regular Meeting of the Board of Directors", so an event with those words on the day stands for the meeting.
"""

from __future__ import annotations

from jason.community.board_calendar import CalendarPolicy

CALENDAR_POLICY = CalendarPolicy(
    regular_title="Regular Meeting of the Board of Directors",
    special_title="Meeting of the Board of Directors",
    meeting_minutes=90,
    covered_words=("board of directors", "board meeting"),
    months=3,
)

__all__ = ["CALENDAR_POLICY"]
