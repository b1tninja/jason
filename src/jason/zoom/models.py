"""A Zoom meeting as a record, the rules that say what kind of meeting it was, and a disciplinary hearing's plan.

``ZoomMeeting`` keeps one ended occurrence: its UUID, meeting id, topic, local start, duration, participant count, and
which files the association holds (transcript, chat, AI Companion summary). ``classify_meeting`` reads the topic against
the specification's ``MeetingRule`` rows in order; the first match names the kind. A meeting no rule names that started
on the schedule's day at the schedule's hour is a board meeting "by the schedule". A miss stays "other".

An executive session or a hearing is confidential (Civil Code 4935): its transcript and summary are held back unless
asked for. A board meeting's recording can run on into the executive session that follows it; the transcript is the
whole call.

``parse_vtt`` turns Zoom's transcript (WebVTT, "Speaker: words" cues) into speaker turns. ``summary_record`` reads the
AI Companion summary, preferring the host's edited version. The summary is Zoom's, not the minutes: it records no roll
call, motion, or vote.

``HearingPlan`` is a hearing under Civil Code 5855: the member is notified in writing at least 10 days before the
meeting (5855(a)), by personal delivery or individual delivery (4040; a mailed notice is delivered on deposit, 4050(b));
the notice carries the date, time, and place, the nature of the alleged violation, and that the member may attend and
address the board, and may ask for executive session (5855(b), 4935(b)); the member may cure before the meeting (5855(c));
the decision is delivered in writing within 14 days (5855(f)); and discipline is not effective otherwise (5855(g)).
A meeting held solely in executive session is noticed to the members two days before (4920(b)(2)).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo


class MeetingKind(Enum):
    BOARD = "board meeting"
    ANNUAL = "annual meeting of members"
    EXECUTIVE = "executive session"
    HEARING = "disciplinary hearing"
    COMMITTEE = "committee meeting"
    OTHER = "other"


CONFIDENTIAL_KINDS = frozenset({MeetingKind.EXECUTIVE, MeetingKind.HEARING})


class Recording(Enum):
    """Zoom's ``auto_recording`` setting."""

    NONE = "none"
    CLOUD = "cloud"
    LOCAL = "local"


@dataclass(frozen=True)
class MeetingRule:
    """Topic words (any, case-folded) that name a meeting's kind."""

    kind: MeetingKind
    words: tuple[str, ...]

    def matches(self, topic: str) -> list[str]:
        t = topic.casefold()
        return [w for w in self.words if w.casefold() in t]


@dataclass(frozen=True)
class HearingPolicy:
    """How the association holds a hearing on Zoom: its time zone, the meeting's length, the waiting room (the board
    admits the member, and can deliberate apart), and whether Zoom records it. The statute's periods are not here."""

    timezone: str
    duration_minutes: int = 30
    waiting_room: bool = True
    recording: Recording = Recording.NONE
    topic: str = "Board hearing"


NOTICE_DAYS = 10               # CIV 5855(a)
SUSPENSION_NOTICE_DAYS = 15    # Corp 7341(c)(2): suspending a member of a mutual benefit corporation
DECISION_DAYS = 14             # CIV 5855(f)
EXECUTIVE_NOTICE_DAYS = 2      # CIV 4920(b)(2), a meeting held solely in executive session


def local_time(stamp: str, tz: str) -> datetime | None:
    """Zoom's UTC time (``2026-09-16T02:00:04Z``) in the association's zone."""
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(tz))


def classify_meeting(topic: str, start: datetime | None, rules: tuple[MeetingRule, ...], schedule: Any = None) -> tuple[MeetingKind, list[str]]:
    """The first rule whose words the topic holds; else a board meeting when it started on the schedule's day within
    two hours of its time; else other."""
    for rule in rules:
        hits = rule.matches(topic or "")
        if hits:
            return rule.kind, hits
    if schedule is not None and start is not None:
        day = schedule.day_in(start.year, start.month)
        hour = schedule_time(schedule.time)
        if start.date() == day and hour is not None:
            gap = abs((start.hour * 60 + start.minute) - (hour.hour * 60 + hour.minute))
            if gap <= 120:
                return MeetingKind.BOARD, [f"started on the schedule's day ({day.isoformat()}, {schedule.time})"]
    return MeetingKind.OTHER, []


def schedule_time(text: str) -> time | None:
    m = re.match(r"\s*(\d{1,2})(?::(\d\d))?\s*([ap])\.?m", text or "", re.I)
    if not m:
        return None
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return time(hour, int(m.group(2) or 0))


@dataclass
class ZoomMeeting:
    uuid: str
    meeting_id: str
    topic: str
    start: datetime | None
    duration: int | None = None              # minutes
    participants: int | None = None
    kind: MeetingKind = MeetingKind.OTHER
    evidence: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)   # "transcript", "chat", "summary" -> path under data/zoom

    @classmethod
    def from_api(cls, row: dict[str, Any], tz: str) -> ZoomMeeting:
        """From a past meeting, a recording, or a summary row: each names the UUID, id, topic, and start its own way."""
        uuid = str(row.get("uuid") or row.get("meeting_uuid") or "")
        topic = str(row.get("topic") or row.get("meeting_topic") or "")
        start = local_time(str(row.get("start_time") or row.get("meeting_start_time") or ""), tz)
        duration = row.get("duration") if isinstance(row.get("duration"), int) else None
        count = row.get("participants_count")
        return cls(uuid=uuid, meeting_id=str(row.get("id") or row.get("meeting_id") or ""), topic=topic, start=start,
                   duration=duration, participants=count if isinstance(count, int) else None)

    @property
    def confidential(self) -> bool:
        return self.kind in CONFIDENTIAL_KINDS

    def record(self) -> dict[str, Any]:
        return {
            "uuid": self.uuid, "meetingId": self.meeting_id, "topic": self.topic,
            "start": self.start.isoformat(timespec="minutes") if self.start else None,
            "date": self.start.date().isoformat() if self.start else None,
            "duration": self.duration, "participants": self.participants,
            "kind": self.kind.value, "evidence": self.evidence, "confidential": self.confidential, "files": self.files,
        }


# --- the transcript -----------------------------------------------------------------------------------------------

_CUE_TIME = re.compile(r"(\d{1,2}):(\d\d):(\d\d)[.,](\d{3})\s*-->")


@dataclass(frozen=True)
class Turn:
    """One speaker's words, from the first cue's start (seconds into the recording)."""

    at: float
    speaker: str
    text: str

    def line(self) -> str:
        h, rest = divmod(int(self.at), 3600)
        m, s = divmod(rest, 60)
        return f"[{h:d}:{m:02d}:{s:02d}] {self.speaker or 'unknown'}: {self.text}"


def parse_vtt(text: str) -> list[Turn]:
    """Zoom's WebVTT transcript as speaker turns; a speaker's consecutive cues join into one turn."""
    turns: list[Turn] = []
    at: float | None = None
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        words: list[str] = []
        for ln in lines:
            m = _CUE_TIME.match(ln)
            if m:
                h, mi, s, ms = (int(g) for g in m.groups())
                at = h * 3600 + mi * 60 + s + ms / 1000
            elif ln == "WEBVTT" or ln.isdigit() or ln.startswith("NOTE"):
                continue
            elif at is not None:
                words.append(ln)
        if not words or at is None:
            continue
        spoken = " ".join(words)
        speaker, sep, said = spoken.partition(": ")
        if not sep or len(speaker) > 60:
            speaker, said = "", spoken
        if turns and turns[-1].speaker == speaker:
            turns[-1] = Turn(turns[-1].at, speaker, f"{turns[-1].text} {said}")
        else:
            turns.append(Turn(at, speaker, said))
    return turns


def speakers(turns: list[Turn]) -> dict[str, int]:
    """Each speaker's number of words, most first."""
    counts: dict[str, int] = {}
    for turn in turns:
        counts[turn.speaker or "unknown"] = counts.get(turn.speaker or "unknown", 0) + len(turn.text.split())
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


@dataclass(frozen=True)
class ExecutiveBreak:
    """Where the open meeting ends and the executive session begins on the same call."""

    at: float                  # seconds into the transcript
    turn: int                  # index of the first executive-session turn (the one after the adjournment line)
    cue: str                   # the adjournment line, trimmed
    method: str                # "adjournment" or "departures"
    departed: int = 0          # people whose last leave falls from a minute before to ten minutes after the break
    remained: int = 0          # people still on the call ten minutes after

    def record(self) -> dict[str, Any]:
        return {"minute": round(self.at / 60, 1), "turn": self.turn, "cue": self.cue, "method": self.method,
                "departed": self.departed, "remained": self.remained}


def find_executive_break(turns: list[Turn], patterns: tuple[str, ...], departures: list[float] | None = None) -> ExecutiveBreak | None:
    """The first turn that says the chair adjourns to executive session, corroborated by who left (``departures``: each
    participant's last leave, in seconds from the start). With no such line, the break is where people left while at
    least two stayed on and talked for three more minutes. None when neither shows one."""
    leaves = sorted(departures or [])

    def counts(at: float) -> tuple[int, int]:
        return (sum(1 for t in leaves if at - 60 <= t <= at + 600), sum(1 for t in leaves if t > at + 600))

    for k, turn in enumerate(turns):
        if any(re.search(p, turn.text, re.I) for p in patterns):
            departed, remained = counts(turn.at)
            return ExecutiveBreak(turn.at, k + 1, turn.text[:160], "adjournment", departed, remained)
    if len(leaves) >= 3 and turns:
        end = turns[-1].at
        for t in leaves:
            departed, remained = counts(t)
            later = [x for x in turns if x.at > t]
            if departed >= 1 and remained >= 2 and later and end - t >= 180 and t < end - 180:
                return ExecutiveBreak(t, turns.index(later[0]), "", "departures", departed, remained)
    return None


# --- the AI Companion summary -------------------------------------------------------------------------------------

def summary_record(body: dict[str, Any]) -> dict[str, Any]:
    """The summary's title, overview, details by topic, and next steps; the host's edits win over Zoom's draft."""
    edited = body.get("edited_summary") or {}
    details = edited.get("summary_details") or body.get("summary_details") or []
    steps = edited.get("next_steps") or body.get("next_steps") or []
    return {
        "title": body.get("summary_title") or "",
        "overview": edited.get("summary_overview") or body.get("summary_overview") or "",
        "details": [{"label": d.get("label") or "", "summary": d.get("summary") or ""} for d in details if isinstance(d, dict)],
        "nextSteps": [str(s) for s in steps],
        "content": body.get("summary_content") or "",      # the newer Markdown form, when Zoom gives it
        "edited": bool(edited),
        "created": body.get("summary_created_time") or "",
    }


def summary_text(summary: dict[str, Any]) -> str:
    lines = [f"# {summary.get('title') or 'Meeting summary'}", ""]
    if summary.get("overview"):
        lines += [summary["overview"], ""]
    for d in summary.get("details") or []:
        lines += [f"## {d['label']}", "", d["summary"], ""]
    if summary.get("nextSteps"):
        lines += ["## Next steps", ""] + [f"- {s}" for s in summary["nextSteps"]] + [""]
    if summary.get("content") and not summary.get("details"):
        lines += [summary["content"], ""]
    return "\n".join(lines)


# --- a disciplinary hearing ---------------------------------------------------------------------------------------

@dataclass
class HearingPlan:
    """A hearing's dates and what its notice must say. ``violation`` is the board's words, never jason's."""

    address: str
    building: str
    violation: str
    start: datetime
    policy: HearingPolicy
    notice_by: date = field(init=False)
    executive_notice_by: date = field(init=False)
    decision_by_if_held: date = field(init=False)
    notice_on: date | None = None
    suspension: bool = False           # the board may suspend membership rights: 15 days' notice (Corp 7341(c))
    zoom: dict[str, Any] = field(default_factory=dict)   # id, join_url, password, dial-in, once created
    problems: list[str] = field(default_factory=list)

    @property
    def notice_days(self) -> int:
        return SUSPENSION_NOTICE_DAYS if self.suspension else NOTICE_DAYS

    @property
    def notice_authority(self) -> str:
        return "Corp 7341(c)" if self.suspension else "CIV 5855(a)"

    def __post_init__(self) -> None:
        held = self.start.date()
        self.notice_by = held - timedelta(days=self.notice_days)
        self.executive_notice_by = held - timedelta(days=EXECUTIVE_NOTICE_DAYS)
        self.decision_by_if_held = held + timedelta(days=DECISION_DAYS)
        if not self.violation.strip():
            self.problems.append("no violation stated: the notice must give the nature of the alleged violation (CIV 5855(b))")
        if self.notice_on and self.notice_on > self.notice_by:
            self.problems.append(f"a notice delivered {self.notice_on.isoformat()} is fewer than {self.notice_days} days before "
                                 f"{held.isoformat()} ({self.notice_authority}); move the hearing to "
                                 f"{self.notice_on + timedelta(days=self.notice_days)} or later")

    def meeting_body(self) -> dict[str, Any]:
        """The ``POST /users/me/meetings`` body: the topic names no owner or address; the member is admitted from the
        waiting room."""
        return {
            "topic": f"{self.policy.topic} {self.start.date().isoformat()}",
            "type": 2,
            "start_time": self.start.strftime("%Y-%m-%dT%H:%M:%S"),
            "timezone": self.policy.timezone,
            "duration": self.policy.duration_minutes,
            "agenda": "Hearing under Civil Code 5855",
            "settings": {
                "waiting_room": self.policy.waiting_room,
                "join_before_host": False,
                "mute_upon_entry": True,
                "approval_type": 2,
                "auto_recording": self.policy.recording.value,
            },
        }

    def record(self) -> dict[str, Any]:
        return {
            "address": self.address, "building": self.building, "violation": self.violation,
            "start": self.start.isoformat(timespec="minutes"), "timezone": self.policy.timezone,
            "noticeBy": self.notice_by.isoformat(), "noticeOn": self.notice_on.isoformat() if self.notice_on else None,
            "executiveNoticeBy": self.executive_notice_by.isoformat(), "decisionByIfHeld": self.decision_by_if_held.isoformat(),
            "zoom": self.zoom, "problems": self.problems,
        }


def zoom_details(created: dict[str, Any]) -> dict[str, Any]:
    """What a hearing notice may carry from ``create_meeting``'s answer: never the host's start link."""
    numbers = (created.get("settings") or {}).get("global_dial_in_numbers") or []
    dial = [f"{n.get('number')} ({n.get('city') or n.get('country_name') or n.get('country')})" for n in numbers
            if str(n.get("country") or "").upper() == "US"][:2]
    return {"id": created.get("id"), "joinUrl": created.get("join_url"), "passcode": created.get("password"),
            "dialIn": dial, "created": created.get("created_at")}


def notice_text(plan: HearingPlan, association: str) -> str:
    """A draft of the hearing notice with the elements 5855(b) requires. The owner's name is left for the secretary."""
    when = plan.start.strftime("%A, %B %d, %Y at %I:%M %p").replace(" 0", " ")
    z = plan.zoom
    place = ["By Zoom video conference."]
    if z.get("joinUrl"):
        place.append(f"Join: {z['joinUrl']}")
        place.append(f"Meeting ID: {z.get('id')}; passcode: {z.get('passcode')}")
        for number in z.get("dialIn") or []:
            place.append(f"By telephone: {number}")
    else:
        place.append("[Zoom link, meeting ID, and passcode: not yet scheduled]")
    lines = [
        f"# Notice of hearing before the Board of Directors, {association}",
        "",
        "To: [owner of record], " + plan.address,
        f"Delivered by: [personal delivery or individual delivery (Civil Code 4040)] on [date, no later than {plan.notice_by:%B %d, %Y}]",
        "",
        f"The Board of Directors will meet on {when} to consider imposing discipline for the matter below.",
        "",
        "## Place",
        "",
        *place,
        "",
        "## The alleged violation",
        "",
        plan.violation.strip() or "[the nature of the alleged violation, as the board states it]",
        "",
        "## Your rights",
        "",
        "- You have the right to attend the hearing and to address the Board.",
        "- The Board will meet in executive session if you ask it to. You may attend that session (Civil Code 4935(b)).",
        "- You may cure the violation before the hearing. The Board will not impose discipline if you cure it before the"
        " hearing, or, if a cure would take longer than the time before the hearing, if you give a financial commitment"
        " to cure it (Civil Code 5855(c)).",
        "- If you and the Board do not agree after the hearing, you may ask for internal dispute resolution (Civil Code 5910).",
        f"- The Board will deliver its decision to you in writing within {DECISION_DAYS} days after it acts (Civil Code 5855(f)).",
        "",
        "[Signature, title, and the association's contact for questions]",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "CONFIDENTIAL_KINDS", "DECISION_DAYS", "EXECUTIVE_NOTICE_DAYS", "ExecutiveBreak", "find_executive_break", "HearingPlan", "HearingPolicy", "MeetingKind", "MeetingRule",
    "NOTICE_DAYS", "Recording", "SUSPENSION_NOTICE_DAYS", "Turn", "ZoomMeeting", "classify_meeting", "local_time", "notice_text", "parse_vtt", "speakers",
    "summary_record", "summary_text", "zoom_details",
]
