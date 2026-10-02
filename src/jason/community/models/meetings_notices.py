"""Notices: what the association sends members (and escrow) that is not an agenda, a ballot, or minutes.

The library's notices are a mix: violation and hearing letters, work notices ("no vehicle access"), community
announcements, pending-litigation letters for escrow, and one recorded instrument (the builder's Right to Repair Act
election). The reader says which, and keeps the facts each carries in a record for that sub-type: a violation letter's
fine and hearing, a litigation letter's case, a work notice's hours, a recorded instrument's document number. A hearing
notice is the one the law shapes: the board notifies the member in writing at least 10 days before a meeting to
consider discipline, with the date, time, and place, the nature of the alleged violation, and a statement that the
member may attend and address the board (Civil Code 5855(a), (b)). Owners' names and addresses in a violation letter
are not kept in the record. A letter to escrow on pending litigation is set beside the cases the specification tracks
(``legal_cases``); the case stays confidential, so a finding names only its number.

The pre-ballot notice is read by ``meetings_elections``; annual meeting minutes filed as a notice by ``meetings``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.models.meetings import dollars, normalize
from jason.community.symbols import DocumentKind

HEARING_NOTICE_DAYS = 10  # CIV 5855(a)
_CLOCK = r"(\d{1,2}(?::\d{2})?\s*[AaPp]\.?\s?[Mm]\.?)"


class NoticeType(Enum):
    MEETING = "meeting"
    HEARING = "hearing"                  # a violation and the disciplinary hearing on it
    VIOLATION = "violation"              # a violation letter without a hearing date
    LITIGATION_DISCLOSURE = "litigation_disclosure"
    WORK = "work"                        # maintenance that closes access or needs owners' cooperation
    ANNOUNCEMENT = "announcement"
    RECORDED_INSTRUMENT = "recorded_instrument"


@dataclass(frozen=True)
class Hearing:
    """The hearing a violation letter sets, and what CIV 5855(b) has the notice say."""

    hearing_date: date | None = None
    hearing_time: str = ""
    place: str = ""                       # "Zoom", or the place the letter names
    right_to_attend: bool = False         # the member may attend and address the board
    written_response: bool = False        # the member may answer in writing instead
    continuance: bool = False             # the letter offers a continuance on request


@dataclass(frozen=True)
class Violation:
    fine: int | None = None               # cents, the fine the letter names
    suspension: bool = False              # the letter warns that privileges may be suspended
    hearing: Hearing | None = None


@dataclass(frozen=True)
class Litigation:
    case_number: str = ""
    court: str = ""
    filed_on: date | None = None
    no_litigation: bool = False           # the letter says the association is not a party to pending litigation
    delivery: str = ""                    # "VIA EMAIL / ESCROW PORTAL"


@dataclass(frozen=True)
class Work:
    work_date: date | None = None
    starts: str = ""                      # the hours the work closes access
    ends: str = ""
    contractor: str = ""
    towing: bool = False                  # vehicles left in the work area will be towed


@dataclass(frozen=True)
class Event:
    """A meeting or announced event the notice gives a date for."""

    event_date: date | None = None
    event_time: str = ""
    teleconference: bool = False


@dataclass(frozen=True)
class Recording:
    recording_number: str = ""
    recorded_on: date | None = None
    pages: int | None = None


@dataclass
class Notice:
    notice_type: NoticeType | None = None
    association: str = ""
    title: str = ""
    notice_date: date | None = None       # the letter's own date
    signed_by: str = ""
    provisions: tuple[str, ...] = ()      # the governing-document sections cited ("CC&Rs §4.12")
    statutes: tuple[str, ...] = ()        # the Civil Code sections cited
    violation: Violation | None = None
    litigation: Litigation | None = None
    work: Work | None = None
    event: Event | None = None
    recording: Recording | None = None


def _type(t: str) -> NoticeType:
    head = t[:1500]
    if re.search(r"RECORDING REQUESTED BY|Space Above (?:This )?Line For Recorder", head, re.I):
        return NoticeType.RECORDED_INSTRUMENT
    if re.search(r"Notice of Violation and Hearing|hearing (?:has been|will be) (?:scheduled|held)", t, re.I):
        return NoticeType.HEARING
    if re.search(r"Notice of (?:Second )?Violation|alleged to have been a violation", t, re.I):
        return NoticeType.VIOLATION
    if re.search(r"Pending Litigation", head, re.I):
        return NoticeType.LITIGATION_DISCLOSURE
    if re.search(r"MAINTENANCE SCHEDULED|NO VEHICLE ACCESS|work (?:is )?scheduled|will be towed", t, re.I):
        return NoticeType.WORK
    if re.search(r"Meeting of the (?:Board|Members)|Annual (?:Membership )?Meeting|To be held on", head, re.I):
        return NoticeType.MEETING
    return NoticeType.ANNOUNCEMENT


def _letter_date(t: str, window: int = 400) -> date | None:
    """The date a letter prints at its head (before the salutation), not a date its body mentions."""
    head = re.split(r"\n\s*(?:Dear\b|To Whom|Re:|RE:)", t, maxsplit=1)[0][:window]
    found = dates_in(head)
    return found[0] if found else None


def _violation(t: str, hearing: bool) -> Violation:
    fine = dollars(first(r"(?:would carry|carry|impose) a fine of (\$[\d,.]+)", t)) if re.search(r"fine of \$", t) else None
    h = None
    if hearing:
        m = re.search(r"Date:\s*\n?\s*([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})", t)
        place = "Zoom" if re.search(r"Location:\s*\n?\s*\S*zoom", t, re.I) else first(r"Location:\s*\n?\s*([^\n]+)", t)
        h = Hearing(hearing_date=next(iter(dates_in(m.group(1))), None) if m else None,
                    hearing_time=first(r"Time:\s*\n?\s*(\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?)", t), place=place,
                    right_to_attend=bool(re.search(r"may attend the hearing|right to attend|opportunity to appear", t, re.I)),
                    written_response=bool(re.search(r"(?:submit|provide) a written (?:response|statement)", t, re.I)),
                    continuance=bool(re.search(r"\bcontinuance\b", t, re.I)))
    return Violation(fine=fine, suspension=bool(re.search(r"suspend\s+(?:\w+\s+)?privileges", t, re.I)), hearing=h)


class NoticeModel(DocumentModel):
    # A notice of violation or hearing is its own kind (violation_notice) and reads with the same layouts.
    kinds = (DocumentKind.NOTICE, DocumentKind.VIOLATION_NOTICE)
    name = "notice"
    required = ("notice_type", "title")

    def parse(self, text: str, context: ModelContext) -> Notice | None:
        t = normalize(text)
        if len(squash(t)) < 80:
            return None
        r = Notice(notice_type=_type(t))
        r.association = first(r"^\s*([A-Z][A-Z .]+ASSOCIATION)\s*$", t, flags=re.M).title()
        r.title = (first(r"Re:\s*([^\n]+)", t) or first(r"^\s*((?:NOTICE|DISCLOSURE|PRE-?BALLOT)[^\n]{3,80})$", t, flags=re.M | re.I)
                   or first(r"ASSOCIATION\s*\n\s*([^\n]{4,80})", t))
        r.statutes = tuple(dict.fromkeys(re.findall(r"Civ(?:il|\.)? Code (?:Section |§\s*)?(\d{3,4}(?:\.\d+)?)", t, re.I)))
        r.provisions = tuple(dict.fromkeys(squash(p) for p in re.findall(r"(CC&Rs? ?§ ?[\d.]+(?:\([a-z]\))?)", t)))
        if r.notice_type is NoticeType.RECORDED_INSTRUMENT:
            number = first(r"Doc #\s*([\d ]{8,})", t).replace(" ", "")
            stamped = dates_in(t[:600])
            r.recording = Recording(recording_number=number, recorded_on=stamped[0] if stamped else None,
                                    pages=int(first(r"Pages\s*\n\s*(\d{1,3})\b", t) or 0) or None)
            r.title = first(r"\n\s*(NOTICE OF [A-Z ]+)\n", t, flags=0) or r.title
        elif r.notice_type in (NoticeType.HEARING, NoticeType.VIOLATION):
            r.title = first(r"Re:\s*([^\n]+)", t) or "Notice of Violation"
            r.violation = _violation(t, r.notice_type is NoticeType.HEARING)
            r.notice_date = _letter_date(t.split("NOTICE OF VIOLATION")[0])
            r.signed_by = first(r"(?:Regrettably|Sincerely),?\s*\n(?:\s*[^\n]*ASSOCIATION[^\n]*\n)?\s*(Board of Directors)", t)
        elif r.notice_type is NoticeType.LITIGATION_DISCLOSURE:
            r.notice_date = _letter_date(t)
            filed = first(r"Date Filed:?\s*([^\n]+)", t)
            r.litigation = Litigation(case_number=first(r"Case Number:?\s*([\w-]+)", t).rstrip("."),
                                      court=first(r"Court:?\s*([^\n.]+)", t), filed_on=next(iter(dates_in(filed)), None) if filed else None,
                                      no_litigation=bool(re.search(r"not a party to any pending litigation", t, re.I)),
                                      delivery=first(r"^\s*(VIA [A-Z /]+?)\s*$", t, flags=re.M))
            r.signed_by = first(r"Sincerely,\s*\n\s*([^\n]+)", t)
        elif r.notice_type is NoticeType.WORK:
            found = dates_in(t[:600])
            hours = re.findall(r"\d{4}\s+" + _CLOCK, t[:600])
            r.work = Work(work_date=found[0] if found else None, starts=squash(hours[0]) if hours else "",
                          ends=squash(hours[1]) if len(hours) > 1 else "",
                          contractor=first(r"has hired ([A-Z][\w&.' -]+?) to\b", t, flags=0),
                          towing=bool(re.search(r"\btowed\b", t, re.I)))
            r.signed_by = first(r"\n\s*(BOARD OF DIRECTORS)\s*\n", t).title()
        else:
            r.notice_date = _letter_date(t) if r.notice_type is NoticeType.ANNOUNCEMENT else None
            found = dates_in(t[:800])
            if found or r.notice_type is NoticeType.MEETING:
                r.event = Event(event_date=found[0] if found else None, event_time=first(_CLOCK, t[:800]),
                                teleconference=bool(re.search(r"zoom|teleconference", t, re.I)))
        return r

    def check(self, r: Notice, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.notice_type is NoticeType.RECORDED_INSTRUMENT:
            found.append(Finding("recorded-instrument", "this is a recorded instrument, not a notice to members; its kind may be wrong",
                                 Severity.INFO))
        if r.notice_type is NoticeType.HEARING and r.violation is not None:
            h = r.violation.hearing or Hearing()
            lacks = [label for label, ok in (("the date", h.hearing_date), ("the time", h.hearing_time), ("the place", h.place),
                                              ("the alleged violation", r.provisions), ("the right to attend and address the board", h.right_to_attend))
                     if not ok]
            if lacks:
                found.append(Finding("hearing-notice-content", "the hearing notice does not give " + ", ".join(lacks), Severity.PROBLEM,
                                     "CIV 5855(b)"))
            if r.notice_date and h.hearing_date:
                lead = (h.hearing_date - r.notice_date).days
                if lead < HEARING_NOTICE_DAYS:
                    found.append(Finding("hearing-notice-late", f"dated {lead} days before the hearing; 10 are required", Severity.PROBLEM,
                                         "CIV 5855(a)"))
            else:
                found.append(Finding("hearing-notice-date", "the letter carries no date; confirm it was delivered at least 10 days before "
                                     "the hearing" + (f" ({h.hearing_date})" if h.hearing_date else ""), Severity.CHECK, "CIV 5855(a)"))
        if r.notice_type is NoticeType.LITIGATION_DISCLOSURE and r.litigation is not None:
            found += _against_cases(r, context)
        return found


def _cases(context: ModelContext) -> tuple[Any, ...]:
    cases = getattr(context.community, "legal_cases", None)
    try:
        return tuple(cases()) if callable(cases) else ()
    except Exception:  # a specification without the register: the cross-check stays silent
        return ()


def _filed(case: Any) -> date | None:
    return next((e.day for e in getattr(case, "events", ()) if re.search(r"complaint filed|petition filed|\bfiled\b", e.step, re.I)), None)


def _against_cases(r: Notice, context: ModelContext) -> list[Finding]:
    """The letter to escrow beside the cases the specification tracks: the case it names, or a suit on file on the day it
    says there is none. The case file is confidential, so the finding gives only the number."""
    lit = r.litigation
    found: list[Finding] = []
    if lit.case_number:
        found.append(Finding("litigation", f"pending case {lit.case_number}" + (f", filed {lit.filed_on}" if lit.filed_on else ""),
                             Severity.INFO))
    cases = _cases(context)
    if not cases:
        return found
    if lit.case_number:
        case = next((c for c in cases if (getattr(c, "case_number", "") or "").lower() == lit.case_number.lower()), None)
        if case is None:
            found.append(Finding("case-not-tracked", f"the letter names case {lit.case_number}, which the specification's legal cases do "
                                 "not carry", Severity.CHECK))
        elif lit.filed_on and _filed(case) and _filed(case) != lit.filed_on:
            found.append(Finding("filing-date-differs", f"the letter says case {lit.case_number} was filed {lit.filed_on}; the case "
                                 f"record says {_filed(case)}", Severity.CHECK))
    if lit.no_litigation and r.notice_date:
        for case in cases:
            filed = _filed(case)
            role = getattr(getattr(case, "role", None), "value", "")
            closed = getattr(getattr(case, "status", None), "value", "") in ("settled", "resolved", "closed") and \
                max((e.day for e in case.events), default=filed or r.notice_date) < r.notice_date
            if filed and filed <= r.notice_date and role in ("plaintiff", "defendant", "respondent") and not closed:
                found.append(Finding("no-litigation-contradicted", f"the letter of {r.notice_date} says the association is not a party to "
                                     f"pending litigation; case {getattr(case, 'case_number', '') or getattr(case, 'key', '')} was filed "
                                     f"{filed}", Severity.CHECK))
    return found


register(NoticeModel())

__all__ = ["Notice", "NoticeType", "NoticeModel", "Hearing", "Violation", "Litigation", "Work", "Event", "Recording"]
