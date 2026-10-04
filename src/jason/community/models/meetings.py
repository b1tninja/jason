"""Meetings: agendas, minutes, executive session agendas, and committee reports.

The Open Meeting Act (Civil Code 4900-4955) shapes these. The association gives notice of a board meeting's time and
place at least four days before it, two days for a meeting held solely in executive session, none for an emergency
meeting (4920(a), (b)); the notice contains the agenda (4920(d)). The board may not discuss or act on an item that was
not on that agenda, except as 4930(b)-(d) allow. A teleconference meeting's notice names a physical location unless it
is held solely in executive session or under 4926, whose notice gives technical instructions, the telephone number and
email of a person who can help, and a reminder that a member may ask for individual delivery; under 4926 every
director's vote is by roll call, and a meeting at which ballots are counted cannot use it (4090(b), 4926(a), (b)). The
board may meet in executive session only on litigation, formation of contracts, member discipline, personnel, a
member's assessment payment or payment plan, and a foreclosure decision (4935(a)-(d)), and generally notes those
matters in the minutes of the next open meeting (4935(e)). Minutes, draft minutes marked as drafts, or a summary are
available to members within 30 days (4950(a)) and open to inspection permanently (5210(a)(2)); agendas and minutes
are association records (5200(a)(8)). A temporary transfer from reserves is noticed on the agenda with its reasons,
repayment options, and whether a special assessment may be considered, and its written finding goes in the minutes
(5515(b), (c)). A rule change is noticed 28 days before the board decides it (4360(a)).

The association's own agendas and minutes are one Google Docs template exported to PDF: a centered header (the
association, the meeting, "To be held on" or "Held on", the date, Zoom details), roman-numeral items with lettered or
lower-roman sub-items and attachment links, and a running footer. Minutes are the same document annotated under each
item (2024-early 2025) or followed by a Zoom AI "Quick recap / Next steps / Summary" (mid 2025 on). A manager's
agenda numbers its items 1-7 with consent, review, action, and discussion sections; it is known by the manager's name
in its header, a sender of kind ``MANAGER`` in the specification (``sources.manager_in``).

An agenda's text does not say when it went out; PayHOA's communications log (``data/payhoa/communications.json``) gives
the day its notice email did, which the agenda check sets beside the four days 4920(a) requires, or the governing
documents' longer period where the specification records one (4920(b)(3), ``notice_need``). A Zoom AI summary retells
the call: it is never expected to hold a roll call or an attendance list, so it gets one finding for what it lacks.

A reading is evidence. A finding is a lead for a person: the agenda in the library may not be the version posted, and a
Zoom summary is not a roll call.
"""

from __future__ import annotations

import difflib
import functools
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    ModelReading,
    Severity,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.base import name_regex
from jason.community.reviews import AS_OF
from jason.community.sources import fold, manager_in
from jason.community.symbols import DocumentKind

MINUTES_DAYS = 30          # CIV 4950(a)
NOTICE_DAYS = 4            # CIV 4920(a)
EXECUTIVE_NOTICE_DAYS = 2  # CIV 4920(b)(2)
RULE_NOTICE_DAYS = 28      # CIV 4360(a)
MEMBERS_NOTICE_DAYS = 10   # Corp. Code 7511(a)


class MeetingType(Enum):
    REGULAR = "regular"
    SPECIAL = "special"
    ANNUAL = "annual"
    EXECUTIVE = "executive"
    EMERGENCY = "emergency"


class MeetingBody(Enum):
    BOARD = "board"
    MEMBERS = "members"


class MinutesLayout(Enum):
    ANNOTATED_AGENDA = "annotated_agenda"  # the agenda with the secretary's notes under each item
    AI_SUMMARY = "ai_summary"              # the agenda followed by a Zoom AI recap, next steps, and summary
    NO_QUORUM = "no_quorum"                # a one-page record that the meeting lacked a quorum
    NARRATIVE = "narrative"                # prose minutes: present, motions, adjournment
    WRITTEN_CONSENT = "written_consent"    # an emergency meeting by email: the items and the directors' signed consents (CIV 4910(b))


class Outcome(Enum):
    APPROVED = "approved"
    DENIED = "denied"
    TABLED = "tabled"


class ExecutiveSubject(Enum):
    """The subjects Civil Code 4935(a)-(d) allows in executive session."""

    LITIGATION = "litigation"
    CONTRACTS = "formation_of_contracts"
    DISCIPLINE = "member_discipline"
    PERSONNEL = "personnel"
    ASSESSMENTS = "assessment_payment"  # a member's payment of assessments or a payment plan (5665)
    FORECLOSURE = "foreclosure"          # a decision to foreclose on a lien (5705(b))


# Each subject in the statute's own words, and the subdivisions of Civil Code 4935 that name it. 4935(e): "Any matter
# discussed in executive session shall be generally noted in the minutes of the immediately following meeting that is
# open to the entire membership." The open record notes a matter by these words and never by its item's title, which
# can name the member, the party, or the matter.
EXECUTIVE_GENERAL_TERMS: dict[ExecutiveSubject, tuple[str, tuple[str, ...]]] = {
    ExecutiveSubject.LITIGATION: ("litigation", ("a",)),
    ExecutiveSubject.CONTRACTS: ("matters relating to the formation of contracts with third parties", ("a",)),
    ExecutiveSubject.DISCIPLINE: ("member discipline", ("a", "b")),
    ExecutiveSubject.PERSONNEL: ("personnel matters", ("a",)),
    ExecutiveSubject.ASSESSMENTS: ("a member's payment of assessments", ("a", "c")),
    ExecutiveSubject.FORECLOSURE: ("whether to foreclose on a lien", ("d",)),
}


def executive_subject(value: Any) -> ExecutiveSubject | None:
    """The ``ExecutiveSubject`` a stored word names, or None for an empty or unknown word (a miss stays a miss)."""
    if isinstance(value, ExecutiveSubject):
        return value
    try:
        return ExecutiveSubject(str(value or "").strip())
    except ValueError:
        return None


def executive_general_note(subjects: Any) -> str:
    """The general words for ``subjects`` with their citation, as the open minutes note them (Civil Code 4935(e)):
    "litigation and member discipline (Civil Code 4935(a), (b))". Empty when no subject is named."""
    named = [s for s in (executive_subject(v) for v in subjects or ()) if s is not None]
    named = list(dict.fromkeys(named))
    if not named:
        return ""
    words = [EXECUTIVE_GENERAL_TERMS[s][0] for s in named]
    letters = sorted({x for s in named for x in EXECUTIVE_GENERAL_TERMS[s][1]})
    said = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return f"{said} (Civil Code 4935({'), ('.join(letters)}))"


@dataclass(frozen=True)
class AgendaItem:
    number: str
    title: str
    subitems: tuple["AgendaItem", ...] = ()
    notes: str = ""                        # the text under the item (minutes' annotations, an item's description)
    attachments: tuple[str, ...] = ()      # the files the item links


@dataclass(frozen=True)
class MeetingHeader:
    association: str = ""
    meeting_type: MeetingType | None = None
    body: MeetingBody | None = None
    meeting_date: date | None = None
    meeting_time: str = ""
    teleconference: bool = False
    dial_in: bool = False
    meeting_id: str = ""
    physical_location: str = ""
    draft: bool = False


@dataclass(frozen=True)
class Action:
    """One thing the minutes say the board decided."""

    text: str
    outcome: Outcome
    amount: int | None = None      # cents, the first dollar amount in the sentence
    mover: str = ""
    seconder: str = ""
    yes: int | None = None
    no: int | None = None
    abstain: int | None = None
    unanimous: bool | None = None
    roll_call: bool = False


@dataclass
class Agenda:
    layout: str = ""                                  # "association" (the board's template) or "manager"
    preparer: str = ""
    association: str = ""
    meeting_type: MeetingType | None = None
    body: MeetingBody | None = None
    meeting_date: date | None = None
    meeting_time: str = ""
    teleconference: bool = False
    dial_in: bool = False
    meeting_id: str = ""
    physical_location: str = ""
    tech_assistance: bool = False                     # a person to call or email for help with the teleconference
    individual_delivery_reminder: bool = False
    posted_on: date | None = None
    notice_sent: date | None = None                   # PayHOA's notice email for this meeting (its communications log, not the text)
    notice_subject: str = ""
    items: tuple[AgendaItem, ...] = ()
    executive_topics: tuple[str, ...] = ()
    member_comment: bool = False                      # an open forum / member comment item
    next_meeting: date | None = None
    prior_minutes: tuple[date, ...] = ()              # minutes listed for approval
    borrowing_notice: str = ""                        # a "Notice of Intent to Borrow" item and its text
    rule_change_items: tuple[str, ...] = ()
    acclamation_item: str = ""


@dataclass
class Minutes:
    layout: MinutesLayout | None = None
    association: str = ""
    meeting_type: MeetingType | None = None
    body: MeetingBody | None = None
    meeting_date: date | None = None
    meeting_time: str = ""
    teleconference: bool = False
    physical_location: str = ""
    draft: bool = False
    approved_on: date | None = None
    called_to_order: str = ""
    adjourned: str = ""
    quorum: bool | None = None
    quorum_note: str = ""                             # the sentence that speaks of the quorum
    directors_count: int | None = None                # "reached quorum with four directors attending" (a summary names no one)
    directors_present: tuple[str, ...] = ()
    directors_absent: tuple[str, ...] = ()
    others_present: tuple[str, ...] = ()
    items: tuple[AgendaItem, ...] = ()
    actions: tuple[Action, ...] = ()
    prior_minutes: tuple[date, ...] = ()
    prior_minutes_approved: bool | None = None
    executive_session: bool = False
    executive_topics: tuple[str, ...] = ()
    executive_summary: str = ""
    executive_detail: bool = False                    # the AI summary recounts what the executive session discussed
    reserve_transfer: str = ""                        # the sentence recording a transfer from reserves
    ai_summary: bool = False
    next_steps: tuple[str, ...] = ()
    next_meeting: date | None = None
    has_proceedings: bool = False                     # the text records something beyond the agenda
    consents: tuple[tuple[str, date | None], ...] = ()  # an emergency meeting by email: each director's signature and its date


@dataclass
class ExecutiveSession:
    association: str = ""
    meeting_date: date | None = None
    meeting_time: str = ""
    teleconference: bool = False
    draft: bool = False
    parent_meeting: MeetingType | None = None
    topics: tuple[AgendaItem, ...] = ()
    subjects: tuple[ExecutiveSubject, ...] = ()
    unlisted_topics: tuple[str, ...] = ()             # topics that match none of 4935's subjects


@dataclass(frozen=True)
class Proposal:
    title: str
    amounts: tuple[int, ...] = ()                     # cents


@dataclass
class CommitteeReport:
    association: str = ""
    committee: str = ""
    year: int | None = None
    report_date: date | None = None
    proposals: tuple[Proposal, ...] = ()
    recommendation: str = ""


# ---------------------------------------------------------------------------------------------------------------
# Shared text handling


def normalize(text: str) -> str:
    """Zero-width and non-breaking spaces out; "January 23rd, 2024" as "January 23, 2024"."""
    t = (text or "").replace("​", "").replace("﻿", "").replace("\xa0", " ").replace("\r", "")
    return re.sub(r"\b(\d{1,2})(?:st|nd|rd|th),", r"\1,", t)


_ASSOCIATION = re.compile(r"^\s*([A-Z][A-Z0-9 .,&'-]*ASSOCIATION)\s*$", re.M)
_FOOTER = re.compile(r"^[^\n]*ASSOCIATION[ \t]*\n[ \t]*-[ \t]*\n[^\n]*\n[^\n]*(?:Meeting|Session)[^\n]*\n[^\n]*\d{4}[^\n]*$", re.M)
_FOOTER_EXEC = re.compile(r"^[^\n]*ASSOCIATION[ \t]*\n[^\n]*-[ \t]*\n[ \t]*\(Zoom\)[ \t]*\n[^\n]*\d{4}[^\n]*$", re.M)
_PAGE_HEAD = re.compile(r"^[^\n]*ASSOCIATION[ \t]*\n[^\n]*-[ \t]*(?:Agenda|Minutes)[ \t]*$", re.M)
_TITLE = re.compile(r"(Regular|Special|Emergency|Annual|Organizational)\s+Meeting\s+of\s+the\s+(Board\s+of\s+Directors|Members(?:hip)?)|"
                    r"Annual\s+(?:Membership|Members'?)\s+Meeting|Executive\s+Session\s+of\s+the\s+Board|"
                    # The former manager's and hand-typed minutes: "Regular Board of Director's meeting", "Board of Directors
                    # Open Meeting", "Board Meeting Minutes" (Drive minutes, September 30, 2026).
                    r"(?:(?:Regular|Special|Emergency|Annual|Organizational)\s+)?Board\s+of\s+Director[’']?s'?\s+(?:Open\s+)?Meeting|"
                    r"Board\s+Meeting\s+(?:Agenda|Minutes)", re.I)
_TIME = re.compile(r"\b(\d{1,2}(?::\d{2})?\s*[AaPp]\.?\s?[Mm]\.?)")
_PHONE = re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}|\b1?-?\d{3}-\d{3}-\d{4}\b|\bDial\b|\+1 \d{3}")
_ZOOM = re.compile(r"\bvia Zoom\b|\bon Zoom\b|Join via Zoom|Zoom Meeting|\(Zoom\)|teleconference|video ?conference|zoom\.us|take place online", re.I)
_ADDRESS = re.compile(r"\b\d{2,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+(?:Dr|Drive|Ln|Lane|St|Street|Ave|Avenue|Blvd|Way|Circle|Walk|Ct|Court|Rd|Road)\b\.?")

EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
_ATTACHMENT = re.compile(r"\.(?:pdf|mov|mp4|jpe?g|png|docx?|xlsx?|csv)\s*$|…\s*$", re.I)


def strip_furniture(text: str) -> str:
    """The text without the running page headers and footers the template prints."""
    t = _FOOTER.sub("", text)
    t = _FOOTER_EXEC.sub("", t)
    return _PAGE_HEAD.sub("", t)


def meeting_title(text: str) -> tuple[MeetingType | None, MeetingBody | None, str]:
    """The meeting's kind from the first title line the text prints."""
    head = "\n".join(text.splitlines()[:40])
    m = _TITLE.search(head)
    if not m:
        return None, None, ""
    title = squash(m.group(0))
    low = title.lower()
    body = MeetingBody.MEMBERS if "member" in low else MeetingBody.BOARD
    if low.startswith("annual"):
        kind = MeetingType.ANNUAL
    elif low.startswith("executive"):
        kind = MeetingType.EXECUTIVE
    else:
        kind = {"regular": MeetingType.REGULAR, "special": MeetingType.SPECIAL, "emergency": MeetingType.EMERGENCY,
                "annual": MeetingType.ANNUAL}.get(low.split()[0])
    return kind, body, title


def _first_item_at(text: str) -> int:
    m = re.search(r"^\s*(?:[IVX]{1,4}|1)\.\s*(?:\n|\S)", text, re.M)
    return m.start() if m else min(len(text), 1500)


def _manager_letterhead(head: str, community: object) -> bool:
    """The header carries a manager's name or its office address (the specification's senders of kind ``MANAGER`` and
    its former managers' mail addresses): an address there is the manager's office, not where the meeting is held."""
    if manager_in(head, getattr(community, "senders", tuple)()) is not None:
        return True
    folded = fold(head)
    return any(getattr(a.kind, "name", "") == "FORMER_MANAGER" and any(fold(word) in folded for word in a.words)
               for a in getattr(community, "mail_addresses", tuple)())


def meeting_header(text: str, community: object = None) -> MeetingHeader:
    """The facts the template's header and footer give: the meeting, its date and time, and where it is held."""
    kind, body, _title = meeting_title(text)
    head = text[:_first_item_at(text)]
    when = None
    for label in (r"To be held on:?", r"\bHeld on:?", r"\bHeld\b", r"Meeting\s*\n"):
        # Not the closing certification's "Minutes of ... Meeting held on <date>": a template's date, sometimes left stale.
        m = next((x for x in re.finditer(label, text, re.I) if not re.search(r"hereby certify", text[max(0, x.start() - 250): x.start()], re.I)), None)
        if m:
            found = dates_in(text[m.end(): m.end() + 90])
            if found:
                when = found[0]
                break
    if when is None:
        found = dates_in(head)
        when = found[0] if found else None
    if when is None:
        footer = re.search(r"\((?:Zoom)\)[ \t]*\n[^\n]*\n([^\n]*\d{4}[^\n]*)", text)
        found = dates_in(footer.group(1)) if footer else []
        when = found[0] if found else None
    time_m = _TIME.search(head) or _TIME.search(text[:2500])
    zoom = bool(_ZOOM.search(text))
    place = ""
    m = re.search(r"(?:gather at|held at|Location:|meet in person at)\s*([^\n]+)", text, re.I)
    if m and _ADDRESS.search(m.group(1)):
        place = squash(m.group(1)).rstrip(" .")
    elif _ADDRESS.search(head) and not _manager_letterhead(head, community):
        place = _ADDRESS.search(head).group(0)
    assoc = _ASSOCIATION.search(text)
    return MeetingHeader(
        association=squash(assoc.group(1)).title() if assoc else "",
        meeting_type=kind, body=body, meeting_date=when,
        meeting_time=re.sub(r"\s+", "", time_m.group(1)).lower() if time_m else "",
        teleconference=zoom, dial_in=bool(_PHONE.search(text[:4000])),
        meeting_id=first(r"Meeting ID:?\s*([\d ]{9,13}\d)", text),
        physical_location=place,
        draft=bool(re.match(r"\s*DRAFT\b", text)) or bool(re.search(r"^\s*DRAFT\s*$", text[:400], re.M))
        or bool(re.search(r"^\s*DRAFT Minutes\b", text[:400], re.M | re.I)),
    )


_ROMAN = re.compile(r"^\s*([IVXL]{1,5})\.\s*(.*)$")
_NUMBER = re.compile(r"^\s*(\d{1,2})\.\s*(.*)$")
_LOWER_ROMAN = re.compile(r"^\s*([ivx]{1,4})\.\s*(.*)$")
_LETTER = re.compile(r"^\s*([a-hA-H])\.\s*(.*)$")
_BULLET = re.compile(r"^\s*[●○•◦▪■]\s*(.*)$")
_END = re.compile(r"^\s*(Quick recap|Meeting summary|Summary|Next steps|Decorum Rules|Appendix|Bylaws\b.*|Meeting assets for\b.*|"
                  r"Mystique Community Association - \d{4} Meeting Calendar)\s*$", re.I)


def _clean_title(title: str) -> str:
    t = squash(EMOJI.sub("", title)).strip(" -–:")
    if len(t) > 60 and " (" in t:
        t = t.split(" (")[0]
    return t


@dataclass
class _Node:
    number: str
    title: str = ""
    notes: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    children: list["_Node"] = field(default_factory=list)

    def freeze(self) -> AgendaItem:
        notes = squash(" ".join(n for n in self.notes if n))
        return AgendaItem(self.number, self.title, tuple(c.freeze() for c in self.children), notes, tuple(self.attachments))


def parse_items(text: str) -> tuple[AgendaItem, ...]:
    """The agenda's items, with sub-items, the notes under each, and linked files, from the template's numbering.

    The board's template numbers items I., II., ... with i./ii. or A./B. sub-items; the manager's numbers them 1., 2., ...
    with a./b. sub-items. Bulleted lines stay in the notes. Parsing stops at the Zoom summary, the decorum rules, or an
    appendix."""
    lines = strip_furniture(text).splitlines()
    roman_top = any(_ROMAN.match(l) and _ROMAN.match(l).group(1) in ("I", "II") for l in lines)
    top_re = _ROMAN if roman_top else _NUMBER
    subs = (_LOWER_ROMAN, _LETTER, _NUMBER) if roman_top else (_LETTER, _LOWER_ROMAN)
    items: list[_Node] = []
    current: _Node | None = None
    sub: _Node | None = None
    pending: _Node | None = None  # a marker whose title is on the next line
    started = False
    for raw in lines:
        line = raw.strip()
        if not line or line == "DRAFT":
            continue
        if pending is not None:
            if _ATTACHMENT.search(line):
                # An item whose only content is a linked file: the file names it.
                pending.attachments.append(squash(line))
                pending.title = _clean_title(re.sub(r"\.\w{2,4}\s*$|…\s*$", "", line))
                pending = None
                continue
            if top_re.match(line) or any(s.match(line) for s in subs):
                pending = None  # an empty item; fall through
            else:
                pending.title = _clean_title(line)
                pending = None
                continue
        if started and _END.match(line):
            break
        m = top_re.match(line)
        if m and not roman_top and not started and m.group(1) != "1":
            m = None  # a wrapped line that begins "6. Director ..." is not the first item
        if m and (not roman_top or not started or _roman_next(items, m.group(1))):
            started = True
            current = _Node(m.group(1))
            sub = None
            items.append(current)
            if m.group(2).strip():
                current.title = _clean_title(m.group(2))
            else:
                pending = current
            continue
        if not started or current is None:
            continue
        if _ATTACHMENT.search(line):
            (sub or current).attachments.append(squash(line))
            continue
        for s in subs:
            m = s.match(line)
            if m:
                sub = _Node(m.group(1))
                current.children.append(sub)
                if m.group(2).strip():
                    sub.title = _clean_title(m.group(2))
                else:
                    pending = sub
                break
        else:
            target = sub or current
            if re.fullmatch(r"(?:See:?|,|and|, and|📷|📸|Review any|Review)", EMOJI.sub("", line).strip() or "📷", re.I):
                continue
            else:
                b = _BULLET.match(line)
                target.notes.append(EMOJI.sub("", b.group(1) if b else line).strip())
    return tuple(i.freeze() for i in items)


_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50}


def roman(s: str) -> int:
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = _ROMAN_VALUES.get(a, 0)
        total += -v if _ROMAN_VALUES.get(b, 0) > v else v
    return total


def _roman_next(items: list[_Node], numeral: str) -> bool:
    """A top-level numeral continues the sequence (so a lettered sub-item "I." or a stray "V." is not taken for one)."""
    return not items or roman(numeral) == roman(items[-1].number) + 1


def walk(items: tuple[AgendaItem, ...]):
    for item in items:
        yield item
        yield from walk(item.subitems)


def item_titles(items: tuple[AgendaItem, ...]) -> list[str]:
    return [i.title for i in walk(items) if i.title]


def _find_item(items: tuple[AgendaItem, ...], pattern: str) -> AgendaItem | None:
    for item in walk(items):
        if re.search(pattern, item.title, re.I):
            return item
    return None


def minutes_dates(item: AgendaItem | None, text: str = "") -> tuple[date, ...]:
    """The dates of the minutes an "Approval of minutes" item lists ("Minutes of 7/15/25", "Minutes 4/15/25")."""
    source = " ".join([item.title, item.notes, *item.attachments, *(s.title for s in item.subitems)]) if item else ""
    source += " " + " ".join(re.findall(r"Minutes (?:of )?(?:Regular Meeting Held |Special Meeting |Previous Meeting dated )?([^\n]{6,22})", text))
    seen: list[date] = []
    for d in dates_in(source):
        if d not in seen:
            seen.append(d)
    return tuple(seen)


def dollars(sentence: str) -> int | None:
    m = re.search(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d\d))?", sentence)
    return int(m.group(1).replace(",", "")) * 100 + int(m.group(2) or 0) if m else None


def classify_executive(topic: str) -> ExecutiveSubject | None:
    t = topic.lower()
    rules = ((ExecutiveSubject.FORECLOSURE, r"foreclos"),
             (ExecutiveSubject.ASSESSMENTS, r"delinquen|payment plan|assessment|collection|late fee|waive"),
             (ExecutiveSubject.DISCIPLINE, r"disciplin|violation|hearing|fine\b|animal|trash|pet|noise|parking"),
             (ExecutiveSubject.LITIGATION, r"legal|litigation|lawsuit|attorney|counsel|claim|\d{2}CV\d+|court"),
             (ExecutiveSubject.PERSONNEL, r"personnel|employee|staff"),
             (ExecutiveSubject.CONTRACTS, r"contract|agreement|proposal|bid|vendor|consultant|handyman|electrician|landscap|"
                                          r"pagerduty|management|seed funds|design"))
    for subject, pattern in rules:
        if re.search(pattern, t):
            return subject
    return None


# ---------------------------------------------------------------------------------------------------------------
# The library, for cross-checks (disk only; each call reads the stored index once)


@functools.lru_cache(maxsize=4)
def _library(data_dir: str) -> tuple[dict[str, Any], ...]:
    try:
        from jason.tasks.library import distinct, load
        return tuple({k: r.get(k) for k in ("id", "name", "period", "kind")} for r in distinct(load(Path(data_dir))))
    except Exception:  # no index on disk: the cross-checks stay silent
        return ()


@functools.lru_cache(maxsize=256)
def _library_text(data_dir: str, doc_id: str) -> str:
    try:
        from jason.tasks.library import text_for
        return normalize(text_for(Path(data_dir), doc_id))
    except Exception:
        return ""


def library_rows(context: ModelContext, kinds: tuple[DocumentKind, ...], day: date | None = None) -> list[dict[str, Any]]:
    if context.data_dir is None:
        return []
    values = {k.value for k in kinds}
    rows = [r for r in _library(str(context.data_dir)) if r.get("kind") in values]
    if day is not None:
        rows = [r for r in rows if str(r.get("period") or "") == day.isoformat()]
    return rows


def library_text(context: ModelContext, row: dict[str, Any]) -> str:
    return _library_text(str(context.data_dir), str(row["id"])) if context.data_dir else ""


def meeting_files(context: ModelContext, kind: DocumentKind, day: date | None, meeting_type: MeetingType | None = None) -> list[dict[str, Any]]:
    """The library's files of ``kind`` for the meeting on ``day``: by period, or, for an annual meeting filed by year, by
    year and name (annual minutes may be filed as a notice)."""
    if day is None or context.data_dir is None:
        return []
    rows = [r for r in library_rows(context, (kind,), day) if r.get("name") != context.name]
    if rows or meeting_type is not MeetingType.ANNUAL:
        return rows
    kinds = (kind, DocumentKind.NOTICE) if kind is DocumentKind.MINUTES else (kind,)
    out = []
    for r in library_rows(context, kinds):
        if str(r.get("period") or "") == str(day.year) and "annual" in str(r.get("name") or "").lower() and r.get("name") != context.name:
            text = library_text(context, r)
            if kind is DocumentKind.MINUTES and not re.search(r"-\s*Minutes|\bHeld on", text):
                continue
            if kind is DocumentKind.AGENDA and not re.search(r"To be held on|Agenda", text):
                continue
            out.append(r)
    return out


COMMUNICATIONS = Path("payhoa") / "communications.json"   # `jason meetings` saves PayHOA's meeting-notice mailings here


@functools.lru_cache(maxsize=4)
def _mailings(data_dir: str) -> tuple[dict[str, Any], ...]:
    try:
        return tuple(json.loads((Path(data_dir) / COMMUNICATIONS).read_text(encoding="utf-8")).get("notices") or ())
    except (OSError, ValueError):
        return ()


def _timezone(context: ModelContext) -> str:
    policy = getattr(context.community, "hearing_policy", None)
    try:
        tz = getattr(policy(), "timezone", "") if callable(policy) else ""
    except Exception:  # a specification without the policy: the association's own zone
        tz = ""
    return tz or "America/Los_Angeles"


def _local_day(stamp: str, tz: str) -> date | None:
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    from zoneinfo import ZoneInfo

    return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).astimezone(ZoneInfo(tz)).date()


def notice_mailings(context: ModelContext, day: date | None) -> tuple[list[tuple[date, str]], date | None]:
    """PayHOA's email notices for the meeting on ``day`` (the local day each went out, and its subject), earliest first,
    and the day PayHOA's log starts (before it, a missing mailing says nothing). Disk only."""
    if day is None or context.data_dir is None:
        return [], None
    from jason.community.meeting_records import meeting_date

    tz = _timezone(context)
    found, start = [], None
    for n in _mailings(str(context.data_dir)):
        sent = _local_day(str(n.get("sent") or ""), tz)
        subject = str(n.get("subject") or "")
        if sent is None or subject.startswith("(Preview)"):
            continue
        start = min(start, sent) if start else sent
        if meeting_date(subject, tz=tz, reference=sent) == day:
            found.append((sent, squash(subject)))
    return sorted(found), start


def _same(a: str, b: str) -> bool:
    """Two item titles name the same item: one contains the other, they nearly match, or they agree before " - "
    (minutes write "President - <name>" where the agenda wrote "President (Chief Executive Officer)")."""
    for x, y in ((_key(a), _key(b)), (_key(a.split(" - ")[0]), _key(b.split(" - ")[0].split(" (")[0]))):
        if x and y and (x in y or y in x or difflib.SequenceMatcher(None, x, y).ratio() >= 0.8):
            return True
    return False


def _key(title: str) -> str:
    t = re.sub(r"\b(see|the|of|a|an|and|to|for|review|approve|approval)\b", " ", title.lower())
    return re.sub(r"[^a-z0-9]+", "", t)


# ---------------------------------------------------------------------------------------------------------------
# Agenda


def notice_need(executive_only: bool, context: ModelContext) -> tuple[int, str]:
    """Days of notice a board meeting needs, and their source: the governing documents' longer period where the
    context's specification records one (CIV 4920(b)(3); ``jason.tasks.board_items.notice_period``), else the statute's
    four days, two for a meeting held solely in executive session. With no specification in the context, the statute's
    period: a model reads no profile of its own."""
    if context.community is None:
        return (EXECUTIVE_NOTICE_DAYS, "CIV 4920(b)(2)") if executive_only else (NOTICE_DAYS, "CIV 4920(a)")
    from jason.tasks.board_items import notice_period

    return notice_period(executive_only=executive_only, community=context.community)


class AgendaModel(DocumentModel):
    kind = DocumentKind.AGENDA
    name = "meeting-agenda"
    required = ("meeting_type", "meeting_date", "meeting_time", "items")
    enriched = ("notice_sent", "notice_subject")

    def parse(self, text: str, context: ModelContext) -> Agenda | None:
        t = normalize(text)
        kind, body, title = meeting_title(t)
        if not title and not re.search(r"\bAgenda\b", t[:3000], re.I):
            return None
        items = parse_items(t)
        if not title and not items:
            return None
        h = meeting_header(t, context.community)
        a = Agenda(association=h.association, meeting_type=kind, body=body, meeting_date=h.meeting_date,
                   meeting_time=h.meeting_time, teleconference=h.teleconference, dial_in=h.dial_in,
                   meeting_id=h.meeting_id, physical_location=h.physical_location, items=items)
        manager = manager_in(t[:300], getattr(context.community, "senders", tuple)())
        if manager is not None:
            a.layout = "manager"
            a.preparer = first(rf"^\s*({name_regex(manager.name)}[^\n]*?)\s*$", t, flags=re.I | re.M) or manager.name
        else:
            a.layout = "association"
        flat = squash(t)
        a.tech_assistance = bool(re.search(r"technical (?:assistance|support|help)|trouble (?:joining|connecting)|help with (?:the )?(?:zoom|teleconference)", flat, re.I))
        a.individual_delivery_reminder = bool(re.search(r"individual (?:delivery|notice)", flat, re.I))
        a.posted_on = next(iter(dates_in(first(r"^\s*(?:Date Posted|Posted(?: on)?|Notice Date|Notice given(?: on)?|Mailed(?: on)?)\s*:\s*([^\n]{6,30})", t, flags=re.M))), None)
        exec_item = _find_item(items, r"Executive Session")
        if exec_item:
            a.executive_topics = tuple(s.title for s in exec_item.subitems if s.title)
        a.member_comment = bool(_find_item(items, r"Open Forum|Member Comment|Homeowner (?:Forum|Comment)|Owner Comment"))
        nxt = _find_item(items, r"Time and Place of Next|Next (?:Regular )?Meeting")
        if nxt:
            found = dates_in(" ".join([nxt.notes] + [s.notes + " " + s.title for s in nxt.subitems]))
            a.next_meeting = found[0] if found else None
        if a.next_meeting is None:
            m = re.search(r"Time and Place of next[^\n]*\n(?:[^\n]*\n){0,3}?[^\n]*?(\w{3,9}\.? \d{1,2}, \d{4})", t, re.I)
            a.next_meeting = next(iter(dates_in(m.group(1))), None) if m else None
        a.prior_minutes = minutes_dates(_find_item(items, r"minutes"), "")
        borrow = _find_item(items, r"Intent to Borrow|Borrow")
        if borrow:
            a.borrowing_notice = squash(" ".join([borrow.title, borrow.notes, *borrow.attachments]))
        a.rule_change_items = tuple(i.title for i in walk(items) if re.search(r"\b(?:rules?|polic(?:y|ies))\b", i.title, re.I)
                                    and not re.search(r"insurance|umbrella|flood", i.title, re.I))
        acc = _find_item(items, r"acclamation")
        if acc:
            a.acclamation_item = squash(" ".join([acc.title, acc.notes]))
        return a

    def enrich(self, a: Agenda, context: ModelContext) -> None:
        """From the communications log, not the agenda's text: when the earliest notice email for this meeting went out,
        and its subject."""
        sent, _start = notice_mailings(context, a.meeting_date)
        if sent:
            a.notice_sent, a.notice_subject = sent[0]

    def check(self, a: Agenda, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        need, basis = notice_need(a.meeting_type is MeetingType.EXECUTIVE, context)
        board = a.body is not MeetingBody.MEMBERS and a.meeting_type is not MeetingType.EMERGENCY
        if a.posted_on and a.meeting_date:
            lead = (a.meeting_date - a.posted_on).days
            if board and lead < need:
                found.append(Finding("notice-late", f"posted {a.posted_on}, {lead} days before the meeting; the notice is due {need} days "
                                     "before", Severity.PROBLEM, basis))
        if a.notice_sent and a.meeting_date:
            lead = (a.meeting_date - a.notice_sent).days
            if board and lead < need:
                found.append(Finding("notice-sent-late", f"PayHOA's notice email ('{a.notice_subject}') went out {a.notice_sent}, {lead} "
                                     f"day{'s' if lead != 1 else ''} before the meeting; board meeting notice is due {need} days before "
                                     "(a posting the annual policy statement designates may have come sooner)", Severity.CHECK,
                                     f"{basis}; CIV 4045"))
            elif a.body is MeetingBody.MEMBERS and lead < MEMBERS_NOTICE_DAYS:
                found.append(Finding("members-notice", f"PayHOA's notice email went out {a.notice_sent}, {lead} days before this members' "
                                     f"meeting; written notice of a members' meeting is due {MEMBERS_NOTICE_DAYS} to 90 days before (the "
                                     "inspector's pre-ballot notice, which names the counting meeting, may have served)", Severity.CHECK,
                                     "Corp. Code 7511(a)"))
        if not a.posted_on and not a.notice_sent and a.body is not MeetingBody.MEMBERS:
            _sent, start = notice_mailings(context, a.meeting_date)
            logged = bool(start and a.meeting_date and start <= a.meeting_date <= context.today)
            found.append(Finding("posting-date-not-shown", "the agenda does not show when it was posted" +
                                 (", and PayHOA's communications log has no notice email for this meeting" if logged else "") +
                                 f"; notice with the agenda is due at least {need} days before the meeting",
                                 Severity.CHECK if logged else Severity.INFO, f"{basis}; CIV 4920(d)"))
        if a.teleconference and not a.physical_location:
            missing = []
            if not a.tech_assistance:
                missing.append("the phone number and email of a person who can help with the teleconference")
            if not a.individual_delivery_reminder:
                missing.append("a reminder that a member may ask for individual delivery of notices")
            if not a.dial_in:
                missing.append("a way to join by telephone")
            if missing:
                found.append(Finding("teleconference-notice", "the meeting is by teleconference with no physical location, and the agenda "
                                     "does not give " + "; ".join(missing) + " (the notice that carried it may)", Severity.CHECK,
                                     "CIV 4090(b), 4926(a)(1), (4)"))
            if a.meeting_type is MeetingType.ANNUAL and _find_item(a.items, r"Election"):
                found.append(Finding("ballot-count-online", "ballots are counted at this meeting, which has no physical location; a "
                                     "meeting that counts ballots cannot be held under the teleconference-only rule", Severity.CHECK,
                                     "CIV 4926(b), 5120(a)"))
        if a.borrowing_notice:
            lacks = [label for label, pattern in (("the reasons", r"cash ?flow|because|due to|reason|to (?:meet|fund|pay)"),
                                                   ("options for repayment", r"repa(?:y|id)|restor"),
                                                   ("whether a special assessment may be considered", r"special assessment"))
                     if not re.search(pattern, a.borrowing_notice, re.I)]
            if lacks:
                found.append(Finding("borrowing-notice", "the Notice of Intent to Borrow item does not state " + ", ".join(lacks) +
                                     " (a linked resolution may)", Severity.CHECK, "CIV 5515(a), (b)"))
        for title in a.rule_change_items:
            found.append(Finding("rule-change", f"'{title}': if this adopts or changes an operating rule on a covered subject (common area, "
                                 "separate interests, discipline, payment plans, disputes, architecture, elections), the text and purpose "
                                 f"need general notice {RULE_NOTICE_DAYS} days before the board decides it", Severity.CHECK,
                                 "CIV 4355(a), 4360(a), (b)"))
        if a.acclamation_item and not re.search(r"[A-Z][a-z]+ [A-Z][a-z]+,? (?:and )?[A-Z][a-z]+ [A-Z][a-z]+", a.acclamation_item.split("(")[0][40:] or ""):
            found.append(Finding("acclamation-names", "the item to seat candidates by acclamation does not name the candidates in its text "
                                 "(a linked results file may)", Severity.CHECK, "CIV 5103(e)"))
        unlisted = [t for t in a.executive_topics if classify_executive(t) is None]
        if unlisted:
            found.append(Finding("executive-topic", "executive session topics outside the subjects the law allows: " + "; ".join(unlisted),
                                 Severity.CHECK, "CIV 4935(a)"))
        if not a.member_comment and a.body is MeetingBody.BOARD and a.meeting_type is not MeetingType.EXECUTIVE:
            found.append(Finding("no-member-comment", "the agenda has no open forum or member comment item; members may speak at any "
                                 "open meeting", Severity.INFO, "CIV 4925(b)"))
        if a.meeting_date and context.data_dir is not None:
            minutes = meeting_files(context, DocumentKind.MINUTES, a.meeting_date, a.meeting_type)
            due = a.meeting_date + timedelta(days=MINUTES_DAYS)
            if not minutes and due < context.today:
                found.append(Finding("no-minutes-on-file", f"the library has no minutes for this {a.meeting_date} meeting; minutes or a "
                                     f"summary were due to members by {due}", Severity.CHECK, "CIV 4950(a), 5210(a)(2)"))
            for day in a.prior_minutes:
                if not library_rows(context, (DocumentKind.MINUTES,), day):
                    found.append(Finding("prior-minutes-not-on-file", f"the agenda lists minutes of {day} for approval; the library "
                                         "has no minutes for that date", Severity.CHECK, "CIV 5200(a)(8), 5210(a)(2)"))
        return found


# ---------------------------------------------------------------------------------------------------------------
# Minutes

_ACTION = re.compile(
    r"\b(?:board|group|team|they|directors?|members|all present members|the committee)\b[^.]{0,80}?"
    r"\b(approved|approves|accepted|agreed to|agreed that|voted|passed|adopted|resolved|granted|appointed|elected|imposed|ratified|"
    r"decided to|decided that|decided against|denied|rejected|tabled)\b|"
    r"\bwhich was approved\b|\bwas approved by\b|\bapproved by all\b|^\s*-?\s*(?:Approved|Granted|TABLED)\b|\bMotion (?:carried|passed|failed)\b|"
    r"\bMotion (?:was )?(?:made )?by\b|(?-i:\b[A-Z][a-z]+ [A-Z][a-z]+ moved\b)|"
    # The manager's shorthand: "Motion to approve the 2024 Budget - M/S/P" (moved, seconded, passed or carried).
    # The board secretary's "MSC" is not read: those minutes prefix it to items with no motion ("MSC - Meeting called to order").
    r"\bM/S/[PC]\b",
    re.I)
_TABLE = re.compile(r"\btabled?\b|\bpostpone|\bdefer|\brevisit\b|decided to table|\bTABLED\b|decided to wait|at a later date", re.I)
_HEADING = re.compile(r"(?m)^([A-Z][^.\n,;:]{2,58}?)[ \t]*$")
_DENY = re.compile(r"\bdenied\b|\brejected\b|decided against|\bfailed\b|not approved", re.I)
_MOTION = re.compile(r"(?:Motion|Moved)\s+(?:was\s+)?(?:made\s+)?by\s+([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)?)[,;]?\s*(?:and\s+)?seconded\s+by\s+"
                     r"([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)?)|([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)?) moved\b[^.;]*[.;]\s*([A-Z][\w.'-]+(?: [A-Z][\w.'-]+)?) seconded")
_TALLY = re.compile(r"\b(\d)\s*[-–]\s*(\d)(?:\s*[-–]\s*(\d))?\b|\b(\d) (?:yes|ayes?|in favor)\b[^.]*?\b(\d) (?:no|nays?|opposed)\b(?:[^.]*?\b(\d) abstain)?", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"(-])")
_NAMES = re.compile(r"[,;]| and ")
_QUORUM_NO = re.compile(r"quorum (?:requirements )?(?:was |were )?not (?:met|reached|present)|without a quorum|\bno quorum|lacked a quorum|"
                        r"did not (?:have|reach) (?:a )?quorum|\bonly one (?:board member|director) (?:was )?present", re.I)
_QUORUM_YES = re.compile(r"(?:reached|confirm(?:ing|ed)?|established|achieved|had) (?:a )?quorum|quorum (?:was |is )?(?:present|established|"
                         r"confirmed|reached)|quorum confirmation|all (?:board members|directors) were present|"
                         r"(?:one more|another) (?:board )?member (?:to (?:start|begin|open) the meeting)?[^.]{0,40}?\bjoined", re.I)
_QUORUM_TALK = re.compile(r"\bquorum\b|(?:one more|another) (?:board )?member (?:to|was needed|needed)", re.I)
_QUORUM_DOUBT = re.compile(r"lack of|without|despite|need(?:ed|s)?\b|waiting|one more|not (?:met|reached)", re.I)
_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}
_COUNT = re.compile(r"\b(two|three|four|five|six|seven|\d) (?:directors|board members) (?:attending|present|were present|in attendance)\b", re.I)


def _names(text: str) -> tuple[str, ...]:
    out = []
    for part in _NAMES.split(text):
        n = squash(re.sub(r"\((?:[^)]*)\)", "", part)).strip(" .")
        if n and re.match(r"[A-Z]", n) and len(n.split()) <= 4 and not re.search(r"\d", n) and n.lower() not in ("none", "n/a"):
            out.append(n)
    return tuple(out)


def actions_in(text: str) -> tuple[Action, ...]:
    """The decisions a text records. A motion sentence and the vote sentence right after it are one action."""
    out: list[Action] = []
    last = -2
    for n, sentence in enumerate(_SENTENCE.split(squash(text))):
        if len(sentence) < 8 or not _ACTION.search(sentence):
            continue
        if _is_heading(sentence):
            continue
        if re.search(r"no action may be taken|will be (?:discussed|considered)|could be funded|hereby certify", sentence, re.I):
            continue
        outcome = Outcome.TABLED if _TABLE.search(sentence) and not re.search(r"\bapproved\b", sentence, re.I) else \
            Outcome.DENIED if _DENY.search(sentence) else Outcome.APPROVED
        m = _MOTION.search(sentence)
        mover, seconder = ((m.group(1) or m.group(3) or ""), (m.group(2) or m.group(4) or "")) if m else ("", "")
        tally = _TALLY.search(sentence)
        yes = no = abstain = None
        if tally:
            nums = [g for g in tally.groups() if g is not None]
            yes, no = int(nums[0]), int(nums[1])
            abstain = int(nums[2]) if len(nums) > 2 else None
        unanimous = True if re.search(r"unanimous|all (?:present )?(?:board )?members|all present|all board members|all directors", sentence, re.I) else None
        action = Action(sentence.strip(), outcome, dollars(sentence), mover, seconder, yes, no, abstain, unanimous,
                        bool(re.search(r"roll[- ]call", sentence, re.I)))
        prev = out[-1] if out and last == n - 1 else None
        if prev and prev.mover and not mover and prev.yes is None and not prev.unanimous:
            out[-1] = Action(prev.text + " " + action.text, action.outcome if re.search(r"carried|passed|approved|failed|denied", sentence, re.I)
                             else prev.outcome, prev.amount if prev.amount is not None else action.amount, prev.mover, prev.seconder,
                             yes, no, abstain, unanimous, prev.roll_call or action.roll_call)
        else:
            out.append(action)
        last = n
    return _distinct([a for a in out if not _ASSIGNMENT.search(a.text) or _FIRM.search(a.text)])


# "They agreed to walk the property", "agreed to contact the agency": a task someone takes on, not a decision of the board
# (the minutes questions found the rules counting these; September 30, 2026). A sentence that also approves, votes, or
# moves is still a decision.
_ASSIGNMENT = re.compile(r"\bagreed (?:to|that)\b[^.]{0,20}?\b(?:walk|contact|look into|reach out|follow up|check|research|"
                         r"investigate|address|prioritize|consider|reconvene|delegate|involve|discuss|revisit|explore|ask|"
                         r"send|schedule|get (?:more )?(?:quotes|bids|proposals)|gather|review)\b", re.I)
_FIRM = re.compile(r"\b(?:approved|approves|voted|passed|adopted|resolved|appointed|elected|imposed|ratified|motion|moved|"
                   r"seconded|authorized|denied|rejected|tabled)\b", re.I)


def _distinct(actions: list[Action]) -> tuple[Action, ...]:
    """One action per decision: an AI summary tells a decision in its overview and again in its detail. Two actions with
    the same dollar amount, or most of the same words, are one; the telling that names a mover or a vote is kept."""
    from jason.community.questions import _related, _signature

    kept: list[tuple[Action, Any]] = []
    for a in actions:
        sig = _signature(a.text)
        match = next((i for i, (_, s) in enumerate(kept) if _related(sig, s)), None)
        if match is None:
            kept.append((a, sig))
        elif (a.mover or a.yes is not None or a.unanimous) and not (kept[match][0].mover or kept[match][0].yes is not None):
            kept[match] = (a, sig)
    return tuple(a for a, _ in kept)


def _is_heading(sentence: str) -> bool:
    """A summary's topic heading ("Board Elects Officers and Approves Investments"), not a sentence."""
    words = sentence.rstrip(".").split()
    return len(words) <= 8 and sum(w[:1].isupper() for w in words) >= len(words) - 1


def _prose(text: str, short: int = 60) -> list[str]:
    """The text's sentences, with each short line that ends without punctuation before a capitalized line (a heading, a
    header line) ended first, so it does not open the next sentence. Hand-typed prose wraps near 60 characters, so its
    reader passes a smaller ``short``."""
    lines = strip_furniture(text).splitlines()
    out = []
    for n, line in enumerate(lines):
        s = line.strip()
        nxt = next((x.strip() for x in lines[n + 1:] if x.strip()), "")
        if s and len(s) <= short and not re.search(r"[.!?:;,]$", s) and nxt[:1].isupper():
            s += "."
        out.append(s)
    return [s.strip() for s in _SENTENCE.split(squash(" ".join(out))) if s.strip()]


def _list_after(label: str, text: str) -> tuple[str, ...]:
    m = re.search(r"(?:^|\n)\s*(?:" + label + r")\s*:\s*([^\n]+)", text, re.I)
    return _names(m.group(1)) if m else ()


# An item whose title carries its outcome: "Proposal - The Sign Factory - Approved - $30,848.13", "... - Tabled", or the
# manager's "Motion to approve the 2024 Budget - M/S/P" (the minutes read from Drive, September 30, 2026).
_MARKED = re.compile(r"[-–]\s*(Approved|Tabled|Denied)\b|\bM/S/([PCF])\b", re.I)


def _marked_actions(items: tuple[AgendaItem, ...], have: tuple[Action, ...]) -> tuple[Action, ...]:
    from jason.community.questions import _related, _signature

    out = []
    for i in walk(items):
        m = _MARKED.search(i.title)
        if not m or re.search(r"\badjourn", i.title, re.I):
            continue
        word = (m.group(1) or "").lower()
        failed = (m.group(2) or "").upper() == "F"
        outcome = Outcome.TABLED if word == "tabled" else Outcome.DENIED if word == "denied" or failed else Outcome.APPROVED
        if any(a.outcome is outcome and i.title[:20] in a.text for a in have):
            continue
        # The amount is in the title, or alone on the line under it.
        amount = dollars(i.title)
        if amount is None and re.match(r"\s*\$", i.notes):
            amount = dollars(i.notes)
        # The notes already tell this decision ("the board approved the contract for ..."): one action, not two.
        sig = _signature(i.title)
        if not any(a.outcome is outcome and _related(sig, _signature(a.text)) for a in have):
            out.append(Action(i.title, outcome, amount))
    return tuple(out)


_ROSTER = re.compile(r"^\s*(?:Board Members|Directors)\s*:?\s*$", re.I | re.M)
_ROSTER_END = re.compile(r"^[^\n]*:[ \t]*$|^[ \t]*(?:\d{1,2}|[IVX]{1,4})\.\s", re.M)


def _roster(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The directors present and absent from a roster block: "Board Members:" then one "Name, Office" per line, an absent
    director marked "(Absent)"; the block ends at the next label ("Management Representative:") or the first item."""
    m = _ROSTER.search(text)
    if not m:
        return (), ()
    rest = text[m.end():]
    end = _ROSTER_END.search(rest)
    present, absent = [], []
    for line in rest[: end.start() if end else 600].splitlines():
        line = line.strip()
        if not line:
            continue
        name = squash(re.split(r",", re.sub(r"\((?:[^)]*)\)", "", line))[0])
        if not re.fullmatch(r"[A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,3}", name):
            continue
        (absent if re.search(r"\(Absent\)", line, re.I) else present).append(name)
    return tuple(present), tuple(absent)


# An emergency meeting by email: the directors' consents, each an e-signature stamped "(Aug 24, 2022 20:01 PDT)".
_CONSENT = re.compile(r"Consent\s+to\s+(?:an?\s+)?(?:Emergency\s+)?(?:Board\s+)?Meeting|unanimous\s+written\s+consent|"
                      r"action\s+(?:taken\s+)?without\s+(?:a\s+)?meeting", re.I)
_SIGNATURE = re.compile(r"^\s*([A-Z][\w.'-]+(?: [A-Za-z][\w.'-]+){1,3})\s*\(((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* "
                        r"\d{1,2},? \d{4})[^)]*\)\s*$", re.M)


def _consents(text: str) -> tuple[tuple[str, date | None], ...]:
    seen: dict[str, date | None] = {}
    for m in _SIGNATURE.finditer(text):
        name = squash(m.group(1)).title()
        if name not in seen:
            seen[name] = next(iter(dates_in(m.group(2))), None)
    return tuple(seen.items())


@AS_OF.check("minutes-as-of", Minutes, fields=("draft", "next_meeting", "meeting_date"))
def minutes_as_of(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: a draft the next meeting should have replaced, and minutes still within their thirty days."""
    found: list[Finding] = []
    if r.draft:
        if r.next_meeting and r.next_meeting < as_of:
            found.append(Finding("draft-after-next-meeting", f"this copy is still marked DRAFT; the next meeting ({r.next_meeting}) has "
                                 "passed, so the approved minutes should replace it", Severity.CHECK, "CIV 4950(a)"))
        else:
            found.append(Finding("minutes-draft", "marked DRAFT: proposed minutes, to be replaced once the board approves them",
                                 Severity.INFO, "CIV 4950(a)"))
    if r.meeting_date:
        due = r.meeting_date + timedelta(days=MINUTES_DAYS)
        if as_of <= due:
            found.append(Finding("minutes-due", f"minutes, draft minutes, or a summary must be available to members by {due}",
                                 Severity.INFO, "CIV 4950(a)"))
    return found


class MinutesModel(DocumentModel):
    kind = DocumentKind.MINUTES
    name = "meeting-minutes"
    required = ("meeting_type", "meeting_date", "items")
    lens_checks = (minutes_as_of,)

    def recognizes(self, t: str) -> bool:
        return bool(meeting_title(t)[2]) and bool(re.search(r"\bHeld\b|Minutes|called to order|Quick recap|Summary|quorum|adjourn", t, re.I)
                                                    or _CONSENT.search(t))

    def parse(self, text: str, context: ModelContext) -> Minutes | None:
        t = normalize(text)
        if not self.recognizes(t):
            return None
        h = meeting_header(t, context.community)
        r = Minutes(association=h.association, meeting_type=h.meeting_type, body=h.body, meeting_date=h.meeting_date,
                    meeting_time=h.meeting_time, teleconference=h.teleconference, physical_location=h.physical_location,
                    draft=h.draft or bool(re.search(r"^\s*DRAFT\s*$", t, re.M)))
        r.items = parse_items(t)
        flat = squash(t)
        r.approved_on = next(iter(dates_in(first(r"^\s*(?:Minutes )?Approved(?: by the Board)?(?: on)?:?\s*([^\n]{6,24})", t, flags=re.M))), None)
        # "at 6:14pm", or a hand-typed "adjourned at 8:15" with no am or pm.
        clock = r"(\d{1,2}(?::\d{2})?\s*[ap]\.?\s?m\b|\d{1,2}:\d{2}\b)"
        r.called_to_order = first(r"called to order at\s*" + clock, flat) or first(r"Call to Order\s*:?\s*(?:at\s*)?" + clock, flat)
        r.adjourned = first(r"adjourned(?: at)?\s*" + clock, flat) or first(r"Adjournment\s*:?\s*" + clock, flat)
        if _QUORUM_NO.search(flat):
            r.quorum = False
        elif _QUORUM_YES.search(flat):
            r.quorum = True
        counts = [m for m in _COUNT.finditer(flat) if not re.search(r"need\w*\s*$", flat[max(0, m.start() - 12): m.start()], re.I)]
        if counts:
            r.directors_count = _WORDS.get(counts[-1].group(1).lower()) or int(counts[-1].group(1))
        r.directors_present = _list_after(r"(?:Directors|Board Members?) Present", t) or _list_after(r"Present", t)
        m = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+(?:,? (?:and )?[A-Z][a-z]+ [A-Z][a-z]+)+) were present", flat)
        if not r.directors_present and m:
            r.directors_present = _names(m.group(1))
        r.directors_absent = _list_after(r"(?:Directors |Board Members? )?Absent", t)
        if not r.directors_present:
            present, absent = _roster(t)
            r.directors_present, r.directors_absent = present, r.directors_absent or absent
        r.others_present = _list_after(r"(?:Also|Others) Present|Guests", t)
        recap = re.search(r"^\s*(?:Quick recap|Meeting summary|Summary)\s*$", t, re.M)
        # The summary's topic headings carry no period; end them so a heading does not open the next sentence.
        summary_text = strip_furniture(t[recap.start():]) if recap else ""
        summary_text = re.sub(r"^\s*Next steps\s*$.*?(?=^\s*Summary\s*$|\Z)", " ", summary_text, flags=re.M | re.S)
        summary_text = _HEADING.sub(r"\1.", summary_text)
        r.ai_summary = recap is not None or bool(re.search(r"AI can make mistakes|Meeting assets for", t))
        steps = re.search(r"^\s*Next steps\s*$(.*?)(?:^\s*Summary\s*$|\Z)", t, re.M | re.S)
        if steps:
            r.next_steps = tuple(squash(s) for s in re.split(r"\n\s*[●•]\s*", "\n" + steps.group(1)) if squash(s))
        # Each item's notes end a sentence, so one item's trailing words do not open the next item's first sentence.
        notes = " ".join(f"{n.rstrip(' .')}." for i in r.items if not re.search(r"Open Forum|Executive Session|Time and Place", i.title, re.I)
                         for n in [i.notes, *(s.notes for s in walk(i.subitems))] if n)
        r.actions = actions_in(notes + " " + summary_text) if (r.items or summary_text) else actions_in(" ".join(_prose(t, 40)))
        # An item the secretary marked TABLED is a decision, even where the notes say no more.
        r.actions += tuple(Action(i.title, Outcome.TABLED) for i in walk(r.items) if re.search(r"\bTABLED\b", i.title + " " + i.notes)
                           and not any(a.outcome is Outcome.TABLED and i.title[:20] in a.text for a in r.actions))
        r.actions += _marked_actions(r.items, r.actions)
        motions = [mm for mm in _MOTION.finditer(flat)]
        if motions and not any(a.mover for a in r.actions):
            r.actions += tuple(Action(squash(mm.group(0)), Outcome.APPROVED, None, mm.group(1) or mm.group(3) or "", mm.group(2) or mm.group(4) or "")
                               for mm in motions)
        minutes_item = _find_item(r.items, r"minutes")
        r.prior_minutes = minutes_dates(minutes_item)
        if re.search(r"approved (?:the )?(?:\w+ )?(?:meeting )?minutes|minutes (?:were|was) approved|"
                     r"minutes (?:for|of) the \w+ \d{4} meeting (?:were |was )?(?:presented and )?approved", flat, re.I):
            r.prior_minutes_approved = True
        exec_item = _find_item(r.items, r"Executive Session")
        r.executive_session = bool(exec_item) or bool(re.search(r"executive session", summary_text, re.I))
        if exec_item:
            r.executive_topics = tuple(s.title for s in exec_item.subitems if s.title)
            note = squash(re.sub(r"Only directors, managers.*?executive session meetings\.?", " ", exec_item.notes, flags=re.I | re.S))
            if len(note) > 20:
                r.executive_summary = note
        if not r.executive_summary:
            m = re.search(r"[^.]*(?:met in Executive Session|During the executive session|in executive session,)[^.]*\.", flat, re.I)
            r.executive_summary = squash(m.group(0)) if m else ""
        if not r.executive_summary and summary_text:
            # A summary that names the session's subject ("reconvene ... for an executive session to address a disciplinary
            # hearing") notes it generally; one that puts the session off ("the need for future executive sessions") held none.
            said = [s for s in _prose(summary_text) if re.search(r"executive session", s, re.I)]
            if any(re.search(r"future executive session|executive session (?:was|is|will be) (?:postponed|deferred|rescheduled)|"
                             r"did not (?:hold|meet in) (?:an? )?executive session|\bno executive session", s, re.I) for s in said):
                r.executive_session = False
            r.executive_summary = next((s for s in said if classify_executive(re.sub(r"executive session", "", s, flags=re.I))
                                        and not re.search(r"future executive session|next (?:regular )?meeting|scheduled for|"
                                                          r"will (?:meet|hold|discuss)|may attend executive session", s, re.I)), "")
        r.executive_detail = bool(re.search(r"\b(?:During|In) the executive session\b|\bexecutive session,? the board (?:discussed|decided)",
                                            summary_text, re.I))
        sentences = _SENTENCE.split(squash(notes + " " + summary_text))
        for n, sentence in enumerate(sentences):
            if re.search(r"\b(?:borrow|transfer)\w*\b", sentence, re.I) and re.search(r"\breserve", sentence, re.I) and \
                    re.search(r"resolved|approved|authoriz|agreed|voted|adopted", sentence, re.I):
                r.reserve_transfer = squash(" ".join(sentences[n:n + 2]))
                break
        # The sentence that speaks of the quorum, with the summary's topic headings and the page furniture ended first.
        r.quorum_note = next((s for s in _prose(t) if (_QUORUM_TALK.search(s) or _QUORUM_YES.search(s) or _QUORUM_NO.search(s))
                              and not re.search(r"§|\bshall\b|^\s*\d+ - Quorum", s) and not _is_heading(s)), "")
        nxt = _find_item(r.items, r"Time and Place of Next|Next (?:Regular )?Meeting")
        if nxt:
            found = dates_in(" ".join([nxt.title, nxt.notes] + [s.title + " " + s.notes for s in nxt.subitems]))
            r.next_meeting = found[0] if found else None
        if r.next_meeting is None:
            m = re.search(r"Time and Place of next[^\n]*\n(?:[^\n]*\n){0,3}?[^\n]*?(\w{3,9}\.? \d{1,2}, \d{4})", t, re.I)
            r.next_meeting = next(iter(dates_in(m.group(1))), None) if m else None
        consent = _CONSENT.search(t)
        if consent:
            r.consents = _consents(t)
        if consent and r.consents:
            # The meeting by email is its items and the consents: each item after the consent is the board's action once
            # every director has signed (CIV 4910(b)(2)); the attached file names what was adopted.
            r.layout = MinutesLayout.WRITTEN_CONSENT
            r.directors_present = tuple(n for n, _ in r.consents)
            r.actions += tuple(Action(squash(" ".join([i.title, *i.attachments])), Outcome.APPROVED, dollars(" ".join([i.title, *i.attachments])))
                               for i in r.items if not _CONSENT.search(i.title) and (i.title or i.attachments)
                               and not any(i.title and i.title[:20] in a.text for a in r.actions))
        elif r.quorum is False and not r.items:
            r.layout = MinutesLayout.NO_QUORUM
        elif r.ai_summary:
            r.layout = MinutesLayout.AI_SUMMARY
        elif r.items:
            r.layout = MinutesLayout.ANNOTATED_AGENDA
        else:
            r.layout = MinutesLayout.NARRATIVE
        boiler = r"Open Forum is devoted|Only directors, managers|No audio or video recording"
        item_notes = [n for i in walk(r.items) for n in [i.notes] if n and not re.search(boiler, n)
                      and not re.fullmatch(r"(?:Review all open maintenance requests|on Zoom|at 7:00 pm on Zoom)", n, re.I)]
        r.has_proceedings = bool(r.actions or summary_text or r.quorum is False or r.called_to_order or
                                 any(len(n) > 40 for n in item_notes))
        return r

    def check(self, r: Minutes, context: ModelContext) -> list[Finding]:
        found: list[Finding] = [minutes_as_of]   # the as-of lens's place: a stale draft, and minutes still due
        if r.layout is MinutesLayout.WRITTEN_CONSENT:
            return found + self._consent_findings(r, context)
        summary = r.layout is MinutesLayout.AI_SUMMARY
        members = r.body is MeetingBody.MEMBERS
        attended = bool(r.directors_present or r.directors_count)
        if r.layout is MinutesLayout.NO_QUORUM:
            found.append(Finding("no-quorum", "the meeting lacked a quorum and was adjourned; no business was transacted", Severity.INFO))
        elif r.actions and r.quorum is not True and _QUORUM_DOUBT.search(r.quorum_note):
            found.append(Finding("quorum-question", f"the minutes record actions and say: \"{r.quorum_note[:200]}\"", Severity.CHECK,
                                 "Bylaws 7.10"))
        elif r.actions and members and r.quorum is None:
            found.append(Finding("membership-not-shown", "the minutes of this members' meeting record business but not the number of "
                                 "memberships present or represented (the inspector's results may give the ballots received)",
                                 Severity.CHECK, "Bylaws 10.10"))
        elif r.actions and r.quorum is None and not attended and not summary:
            found.append(Finding("quorum-not-shown", "the minutes record actions but not who attended or that a quorum was present",
                                 Severity.CHECK, "Bylaws 10.10"))
        board = context.community.board() if context.community is not None and hasattr(context.community, "board") else None
        if board is not None and attended and r.actions and not members:
            present = len(r.directors_present) or r.directors_count or 0
            full = board.quorum()
            least = board.quorum(board.minimum)
            if present < least:
                found.append(Finding("below-quorum", f"{present} directors present, fewer than the {least} a quorum needs even with "
                                     f"only {board.minimum} in office", Severity.PROBLEM, "Bylaws 7.10"))
            elif present < full:
                found.append(Finding("quorum-depends-on-seats", f"{present} directors present: a quorum only if no more than "
                                     f"{2 * present - 1} of the {board.seats} seats were filled that day", Severity.CHECK, "Bylaws 7.10"))
        if not r.has_proceedings:
            found.append(Finding("no-proceedings", "the minutes repeat the agenda and record no discussion, action, or adjournment",
                                 Severity.CHECK, "Bylaws 10.10"))
        acted = [a for a in r.actions if a.outcome is Outcome.APPROVED]
        remote = r.teleconference and not r.physical_location
        roll_call = any(a.roll_call for a in r.actions)
        # A Zoom AI summary retells the call; it never records a roll call, and the members vote by ballot, not by roll call.
        no_roll_call = bool(acted and remote and not roll_call and not summary and not members)
        if no_roll_call:
            found.append(Finding("no-roll-call", f"{len(acted)} board actions at a teleconference meeting with no physical location, and the "
                                 "minutes record no roll-call vote", Severity.CHECK, "CIV 4926(a)(3)"))
        if acted and not any(a.yes is not None or a.unanimous for a in acted) and not no_roll_call \
                and not summary and not members:
            found.append(Finding("votes-not-recorded", f"{len(acted)} actions recorded without a vote count or the directors' votes",
                                 Severity.CHECK))
        if summary and acted:
            lacks = [label for label, shown in (("who attended", attended), ("that a quorum was present", r.quorum is not None),
                                                ("each director's vote" + (" by roll call" if remote else ""), roll_call)) if not shown]
            if lacks:
                found.append(Finding("ai-summary", f"the proceedings are Zoom's AI summary of the call: it tells of {len(acted)} decisions "
                                     f"but not {', '.join(lacks)}; the minutes the board approves should record them", Severity.CHECK,
                                     "Bylaws 10.10" + (", CIV 4926(a)(3)" if remote and not roll_call else "")))
            else:
                found.append(Finding("ai-summary", f"the proceedings are Zoom's AI summary of the call ({len(acted)} decisions); it is the "
                                     "minutes only once the board reviews and adopts it", Severity.INFO))
        elif r.ai_summary:
            found.append(Finding("ai-summary", "the proceedings are an automated meeting summary (Zoom AI), not a record of each motion "
                                 "and vote; it is the minutes only once the board reviews and adopts it", Severity.INFO))
        if r.executive_session and not r.executive_summary and not self._noted_next(r, context):
            found.append(Finding("executive-session-not-noted", "the agenda adjourned to executive session; if the board met, its matters "
                                 "must be generally noted in the minutes of the next open meeting", Severity.CHECK, "CIV 4935(e)"))
        if r.executive_detail:
            found.append(Finding("executive-detail", "the AI summary in these open minutes recounts what the board discussed in executive "
                                 "session; the open minutes note those matters only generally, and a member's discipline or payment "
                                 "stays private", Severity.CHECK, "CIV 4935(a), (e)"))
        if r.reserve_transfer:
            repaid = re.search(r"repa(?:y|id)|restor", r.reserve_transfer, re.I)
            if repaid:
                found.append(Finding("reserve-transfer", "the minutes record a transfer from reserves with when or how it will be repaid; "
                                     + (f"restore it by {r.meeting_date + timedelta(days=365)}" if r.meeting_date else "restore it within a year"),
                                     Severity.INFO, "CIV 5515(c), (d)"))
            else:
                found.append(Finding("reserve-transfer-finding", "the minutes mention a transfer from reserves without saying when and how "
                                     "it will be repaid", Severity.CHECK, "CIV 5515(c)"))
        found += self._against_agenda(r, context)
        return found

    def _consent_findings(self, r: Minutes, context: ModelContext) -> list[Finding]:
        """An emergency meeting by email holds only with every director's written consent, filed with the minutes."""
        board = context.community.board() if context.community is not None and hasattr(context.community, "board") else None
        signed = [d for _, d in r.consents if d]
        when = f" (signed {min(signed)} to {max(signed)})" if signed else ""
        late = f"; the consents were signed after the meeting date ({r.meeting_date})" if signed and r.meeting_date and \
            max(signed) > r.meeting_date else ""
        short = board is not None and len(r.consents) < board.seats
        text = (f"an emergency meeting by email: {len(r.consents)} directors' written consents on file{when}{late}; the law allows "
                "it only if every director consents in writing and the consents are filed with the minutes")
        if short:
            text += f" ({board.seats} seats; a director who did not sign, or a vacant seat, should be confirmed)"
        return [Finding("written-consent", text, Severity.CHECK if short or late else Severity.INFO, "CIV 4910(b)(2)")]

    def _noted_next(self, r: Minutes, context: ModelContext) -> bool:
        """The next open meeting's minutes in the library note an executive session (beyond the adjournment item)."""
        if r.meeting_date is None or context.data_dir is None:
            return False
        later = sorted((str(x.get("period") or ""), x) for x in library_rows(context, (DocumentKind.MINUTES,))
                       if str(x.get("period") or "") > r.meeting_date.isoformat() and len(str(x.get("period") or "")) == 10)
        if not later:
            return False
        text = strip_furniture(library_text(context, later[0][1]))
        text = re.sub(r"Adjourn to Executive Session|Only directors, managers[^\n]*(?:\n[^\n]*){0,3}executive session meetings\.?|"
                      r"except for meetings of the board held in executive session", " ", text, flags=re.I)
        return bool(re.search(r"executive session", text, re.I))

    def _against_agenda(self, r: Minutes, context: ModelContext) -> list[Finding]:
        if context.data_dir is None or r.meeting_date is None:
            return []
        agendas = meeting_files(context, DocumentKind.AGENDA, r.meeting_date, r.meeting_type)
        if not agendas:
            return [Finding("no-agenda-on-file", f"the library has no agenda for the {r.meeting_date} meeting", Severity.CHECK,
                            "CIV 4920(d), 5200(a)(8)")] if r.layout is not MinutesLayout.NO_QUORUM else []
        agenda = AgendaModel().parse(library_text(context, agendas[0]), context)
        if agenda is None or not agenda.items:
            return []
        posted = item_titles(agenda.items)
        extra = [t for t in _marked_titles(r.items) if not any(_same(t, p) for p in posted)]
        if extra:
            return [Finding("not-on-agenda", "the minutes list items the agenda on file does not: " + "; ".join(extra) +
                            " (the posted agenda may differ from the library's copy)", Severity.CHECK, "CIV 4930(a)")]
        return [Finding("agenda-on-file", f"the agenda for this meeting is in the library ({agendas[0]['name']})", Severity.INFO)]

    def read(self, text: str, context: ModelContext, kind: DocumentKind | None = None) -> ModelReading | None:
        reading = super().read(text, context, kind)
        if reading is not None and reading.record.layout is MinutesLayout.NO_QUORUM and "items" in reading.missing:
            # A meeting adjourned for want of a quorum has no items to record.
            reading.missing = tuple(m for m in reading.missing if m != "items")
            reading.findings = tuple(f for f in reading.findings if f.code != "missing-items")
        if reading is not None and kind is not None and kind is not DocumentKind.MINUTES:
            reading.findings = reading.findings + (Finding("filed-as-" + kind.value.replace("_", "-"), f"the library files this as a "
                                                   f"{kind.value.replace('_', ' ')}; the text is minutes", Severity.INFO),)
        return reading


def _marked_titles(items: tuple[AgendaItem, ...]) -> list[str]:
    return [i.title for i in walk(items) if i.title and not re.fullmatch(r"[ivx]+|[a-h]|\d+|[A-H]", i.title)]


class MisfiledMinutesModel(MinutesModel):
    """Annual meeting minutes filed as a notice: the text says "- Minutes" or "Held on", not "To be held on"."""

    kind = DocumentKind.NOTICE
    name = "meeting-minutes"

    def recognizes(self, t: str) -> bool:
        return bool(meeting_title(t)[2]) and bool(re.search(r"-\s*Minutes\b|^\s*Held on", t, re.I | re.M)) and \
            not re.search(r"To be held on", t, re.I)


# ---------------------------------------------------------------------------------------------------------------
# Executive session agenda


class ExecutiveSessionModel(DocumentModel):
    kind = DocumentKind.EXECUTIVE_SESSION
    name = "executive-session"
    required = ("meeting_date", "topics")

    def parse(self, text: str, context: ModelContext) -> ExecutiveSession | None:
        t = normalize(text)
        if not re.search(r"Executive Session", t[:1500], re.I):
            return None
        h = meeting_header(t, context.community)
        items = parse_items(t)
        r = ExecutiveSession(association=h.association, meeting_date=h.meeting_date, meeting_time=h.meeting_time,
                             teleconference=h.teleconference, draft=h.draft, topics=items)
        m = re.search(r"(Regular|Special|Annual) Meeting of the Board", t, re.I)
        r.parent_meeting = MeetingType(m.group(1).lower()) if m else None
        subjects, unlisted = [], []
        for item in items:
            s = classify_executive(" ".join([item.title, item.notes, *(c.title for c in item.subitems)]))
            if s is None:
                unlisted.append(item.title)
            elif s not in subjects:
                subjects.append(s)
        r.subjects, r.unlisted_topics = tuple(subjects), tuple(unlisted)
        return r

    def check(self, r: ExecutiveSession, context: ModelContext) -> list[Finding]:
        found = []
        if r.unlisted_topics:
            found.append(Finding("executive-topic", "topics outside the subjects the law allows in executive session: " +
                                 "; ".join(r.unlisted_topics), Severity.CHECK, "CIV 4935(a)"))
        if r.parent_meeting is None:
            found.append(Finding("executive-only-notice", "a meeting held solely in executive session needs notice of its time and place "
                                 "at least two days before", Severity.INFO, "CIV 4920(b)(2)"))
        found.append(Finding("note-in-open-minutes", "the matters discussed must be generally noted in the minutes of the next open "
                             "meeting; executive session minutes are not member-inspectable records", Severity.INFO, "CIV 4935(e), 5200(a)(8)"))
        return found


# ---------------------------------------------------------------------------------------------------------------
# Committee report


class CommitteeReportModel(DocumentModel):
    kind = DocumentKind.COMMITTEE_REPORT
    name = "committee-report"
    required = ("committee", "proposals")

    def parse(self, text: str, context: ModelContext) -> CommitteeReport | None:
        t = normalize(text)
        m = re.search(r"^\s*([A-Z][\w &/-]*Committee)\b[^\n]*(?:Report|Recommendation)", t[:1500], re.M | re.I)
        if not m:
            return None
        r = CommitteeReport(committee=squash(m.group(1)))
        assoc = _ASSOCIATION.search(t)
        r.association = squash(assoc.group(1)).title() if assoc else ""
        year = first(r"Committee\s*-\s*(\d{4})\s*Report", t) or first(r"\b(20\d\d) Report\b", t)
        r.year = int(year) if year else None
        found = dates_in(t[:600])
        r.report_date = found[0] if found else None
        block = re.search(r"proposes the following[^\n]*\n(.*?)(?:\n\s*If the board|\n[^\n]*ASSOCIATION\s*\n)", t, re.S | re.I)
        titles: list[str] = []
        if block:
            parts = re.split(r"^\s*\d{1,2}\.\s*", block.group(1), flags=re.M)
            titles = [squash(p) for p in parts[1:] if squash(p)]
        # Each proposal has its own page: "Committee Report" then its heading, then the detail and prices.
        sections = re.findall(r"Committee Report\s*\n\s*([^\n]+)\n(.*?)(?=\n[^\n]*ASSOCIATION\s*\n|\Z)", t, re.S)
        proposals = []
        for title in titles:
            words = set(re.findall(r"[a-z]{4,}", title.lower()))
            section = next((body for heading, body in sections
                            if _same(heading, title) or len(words & set(re.findall(r"[a-z]{4,}", heading.lower()))) >= 2), "")
            amounts = [dollars(x) for x in re.findall(r"\$\s?[\d,]+(?:\.\d\d)?", section)]
            proposals.append(Proposal(title, tuple(a for a in amounts if a is not None)))
        r.proposals = tuple(proposals)
        r.recommendation = first(r"(If the board[^.]*\.)", squash(t))
        return r


register(AgendaModel())
register(MinutesModel())
register(MisfiledMinutesModel())
register(ExecutiveSessionModel())
register(CommitteeReportModel())

__all__ = ["MeetingType", "MeetingBody", "MinutesLayout", "Outcome", "ExecutiveSubject", "EXECUTIVE_GENERAL_TERMS",
           "executive_subject", "executive_general_note", "AgendaItem", "MeetingHeader", "Action",
           "Agenda", "Minutes", "ExecutiveSession", "CommitteeReport", "Proposal", "AgendaModel", "MinutesModel",
           "MisfiledMinutesModel", "ExecutiveSessionModel", "CommitteeReportModel", "normalize", "parse_items", "meeting_header",
           "meeting_title", "actions_in", "classify_executive", "library_rows", "library_text", "meeting_files", "notice_mailings",
           "notice_need"]
