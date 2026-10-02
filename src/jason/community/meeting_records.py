"""Meeting records: every agenda, notice, minutes, transcript, summary, chat, and recording, placed on its meeting's date.

A ``MeetingRecord`` is one copy of one record in one place: Zoom's cloud, jason's copy of it (``data/zoom``), Drive, the
PayHOA library, or jason's own drafts. ``record_kind`` names what a file is by the specification's ``RecordRule`` rows,
in order; a rule that needs meeting context matches only when the name or path says meeting, minutes, recording, or
Zoom (a phone video in a violation folder is evidence, not a meeting recording). ``meeting_date`` reads the date a
name carries ("Minutes of 6_17_25", "Agenda for 9/15/26", Zoom's "GMT20250521-015946" in UTC, "Apr 14, 2026",
"230130", "2024 Annual Membership Meeting"). A file whose date cannot be read stays unplaced: a miss stays a miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo


class RecordKind(Enum):
    NOTICE = "meeting notice"
    AGENDA = "agenda"
    EXECUTIVE_AGENDA = "executive session agenda"
    DRAFT_MINUTES = "draft minutes"
    MINUTES = "minutes"
    TRANSCRIPT = "transcript"
    AI_SUMMARY = "AI summary"
    CHAT = "chat"
    ATTENDANCE = "attendance"
    AUDIO = "audio recording"
    VIDEO = "video recording"
    RECORDING_NOTICE = "recording notice"          # Zoom's email that a cloud recording or its assets are ready
    CORRESPONDENCE = "correspondence"              # replies and threads about the meeting's agenda or notice


RECORDINGS = frozenset({RecordKind.AUDIO, RecordKind.VIDEO})


class Where(Enum):
    ZOOM_CLOUD = "Zoom cloud"
    JASON = "jason's copy"
    DRIVE = "Drive"
    PAYHOA = "PayHOA library"
    PAYHOA_SENT = "PayHOA communication"
    GMAIL = "Gmail"
    DRAFT = "jason draft"


@dataclass(frozen=True)
class EmailRule:
    """An email about a meeting, by its subject and (optionally) the sender's domain."""

    kind: RecordKind
    subject: str
    domains: tuple[str, ...] = ()
    note: str = ""

    def matches(self, subject: str, domains: list[str]) -> bool:
        if self.domains and not any(d in domains for d in self.domains):
            return False
        return bool(re.search(self.subject, subject, re.I))


@dataclass(frozen=True)
class RecordRule:
    """A name pattern (case-insensitive) that says what a meeting file is."""

    kind: RecordKind
    pattern: str
    needs_context: bool = False

    def matches(self, name: str, context: str) -> bool:
        if not re.search(self.pattern, name, re.I):
            return False
        return not self.needs_context or bool(re.search(r"meeting|minutes|recording|zoom|gmt\d{8}", context, re.I))


def record_kind(name: str, path: str, rules: tuple[RecordRule, ...]) -> RecordKind | None:
    for rule in rules:
        if rule.matches(name, f"{path} {name}"):
            return rule.kind
    return None


_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def _year(y: str) -> int:
    n = int(y)
    return n + 2000 if n < 100 else n


def meeting_date(name: str, path: str = "", *, tz: str = "America/Los_Angeles", schedule: Any = None,
                 reference: date | None = None) -> date | None:
    """The meeting date a file's name (or its folder) carries, or None. ``reference`` (when the file or message was
    made) supplies the year for a date without one ("Sep 15th at 7:00 pm"): the nearest such date to it."""
    text = f"{name}"
    if reference is not None:
        m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2})(?:st|nd|rd|th)?\b(?!,? \d{4})", text, re.I)
        if m:
            month, day = _MONTHS[m.group(1).lower()], int(m.group(2))
            options = []
            for year in (reference.year - 1, reference.year, reference.year + 1):
                try:
                    options.append(date(year, month, day))
                except ValueError:
                    pass
            if options:
                return min(options, key=lambda d: abs((d - reference).days))
    m = re.search(r"GMT(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})", text)
    if m:
        y, mo, d, h, mi, s = (int(g) for g in m.groups())
        return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc).astimezone(ZoneInfo(tz)).date()
    m = re.search(r"(?<!\d)(20\d\d)[._-](\d{1,2})[._-](\d{1,2})(?!\d)", text)        # 2022.05.11, 2021-03-10
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"(?<!\d)(\d{1,2})[/_.-](\d{1,2})[/_.-](\d{2}|\d{4})(?!\d)", text)
    if m:
        try:
            return date(_year(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            try:                                                                    # 26-02-17: year first
                return date(_year(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2}),? (\d{4})", text, re.I)
    if m:
        return date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    m = re.search(r"(?<!\d)(2\d)(0[1-9]|1[0-2])([0-3]\d)(?!\d)", text)       # 230130
    if m:
        try:
            return date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"(?<!\d)(0?[1-9]|1[0-2])([0-3]\d)(2\d)(?!\d)", text)       # 083022, 72922: month, day, year
    if m:
        try:
            return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    m = re.search(r"(20\d\d) annual", text, re.I) or re.search(r"annual[^/]*?(20\d\d)", text, re.I)
    if m and schedule is not None and schedule.annual_month:
        return schedule.day_in(int(m.group(1)), schedule.annual_month)
    m = re.search(r"Meetings/(20\d\d)/(\d{2})(\d{2})/", path)                # PayHOA "Meetings/2024/0206/"
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


@dataclass
class MeetingRecord:
    kind: RecordKind
    where: Where
    name: str
    location: str                     # a Drive path, a PayHOA library path, a data/ path, or "zoom:<uuid>"
    ref: str = ""                     # the Drive id, PayHOA id, or Zoom meeting UUID
    day: date | None = None
    confidential: bool = False
    note: str = ""
    sent: str = ""                    # when a notice or email went out (ISO, UTC)
    md5: str = ""                     # content digests, to join copies of one file across places
    sha256: str = ""

    def row(self) -> dict[str, Any]:
        out = {"kind": self.kind.value, "where": self.where.value, "name": self.name, "location": self.location,
               "ref": self.ref, "date": self.day.isoformat() if self.day else None, "confidential": self.confidential,
               "note": self.note}
        for key in ("sent", "md5", "sha256"):
            if getattr(self, key):
                out[key] = getattr(self, key)
        return out


@dataclass
class Meeting:
    day: date
    titles: set[str] = field(default_factory=set)
    records: list[MeetingRecord] = field(default_factory=list)

    def has(self, *kinds: RecordKind) -> bool:
        return any(r.kind in kinds for r in self.records)


__all__ = ["EmailRule", "Meeting", "MeetingRecord", "RECORDINGS", "RecordKind", "RecordRule", "Where", "meeting_date", "record_kind"]
