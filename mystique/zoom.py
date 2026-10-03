"""How Mystique meets on Zoom: what each meeting's topic says it was, and how a disciplinary hearing is held.

Administrative Resolution 20230130-1 (January 30, 2023) put every meeting on Zoom at 7:00 pm, so the account's history
from that date on is the association's meeting history. The sync reads from ``ZOOM_HISTORY_SINCE``.

The topic rules run in order: a hearing or executive session outranks the words "board meeting" in the same topic. A
meeting no rule names that starts on the schedule's day near its hour is a board meeting by the schedule
(``MEETING_SCHEDULE``, banking.py). A miss stays "other".

A hearing is its own meeting, with a waiting room so the board admits the member and can deliberate apart, and is not
recorded unless the board decides to (the recording and its transcript would be the executive session's record). The
topic Zoom shows invitees names no owner or address.
"""

from __future__ import annotations

from datetime import date

from jason.zoom.models import BoardMeetingPolicy, HearingPolicy, MeetingKind, MeetingRule, Recording

TIMEZONE = "America/Los_Angeles"

ZOOM_HISTORY_SINCE = date(2023, 1, 30)

ZOOM_MEETING_RULES: tuple[MeetingRule, ...] = (
    MeetingRule(MeetingKind.HEARING, ("hearing", "disciplin")),
    MeetingRule(MeetingKind.EXECUTIVE, ("executive session", "executive meeting", "exec session")),
    MeetingRule(MeetingKind.ANNUAL, ("annual meeting", "annual members", "annual homeowners", "election", "ballot count",
                                     "inspector of elections")),
    MeetingRule(MeetingKind.COMMITTEE, ("committee", "architectural review", "landscape review")),
    MeetingRule(MeetingKind.BOARD, ("board meeting", "board of directors", "hoa meeting", "monthly meeting", "mystique")),
)

# The board adjourns the open meeting and stays on the same call in executive session; the members leave. The break is
# the chair's adjournment line, not a mention ("we'll talk about that in executive session"), as the 2025-2026
# transcripts say it: "adjourn to the executive session", "adjourn the regular portion ... the board will meet in the
# executive session", "adjourn the meeting ... board members stick around", "if you're not a board member, I'll kick you
# out". The first line that matches, in order, is the break.
EXECUTIVE_BREAK_PATTERNS: tuple[str, ...] = (
    r"adjourn\w*\b.{0,60}\b(?:executive|closed) session",
    r"adjourn\w*\b.{0,60}\bregular portion",
    r"adjourn\w*\b.{0,120}\bboard members? (?:stick around|stay|remain)",
    r"(?:go|move|going|moving)\s+(?:in)?to (?:the )?(?:executive|closed) session (?:now|part)",
    r"not a board member,? (?:I'?ll|we'?ll) (?:kick|move|put) you",
    r"open forum.{0,80}\bboard\b.{0,20}\bmeet\b.{0,20}\b(?:at the end|after|following)",
)

HEARING_POLICY =HearingPolicy(timezone=TIMEZONE, duration_minutes=30, waiting_room=True, recording=Recording.NONE,
                               topic="Mystique board hearing")

# The board's open meeting: ninety minutes at the schedule's hour, a waiting room, cloud recording on (the open
# session's transcript is the record the sync reads; the host pauses it for the executive session).
BOARD_MEETING_POLICY = BoardMeetingPolicy(timezone=TIMEZONE, duration_minutes=90, waiting_room=True, recording=Recording.CLOUD,
                                          topic="Mystique board meeting")
