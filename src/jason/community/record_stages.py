"""The revision histories of two series jason tracks: operating rule changes (Civil Code 4360) and board minutes (4950).

Each history is a list of ``revisions.RecordVersion`` (the shared model; nothing here redefines it), the evidence on
disk for each stage, and the clocks the law runs between stages.

**A rule change** (Civil Code 4355-4365) moves through:

- ``Stage.DRAFT``: its text as written, before any notice;
- ``Stage.PROPOSED``: the general notice of the proposed change, with "the text of the proposed rule change and a
  description of the purpose and effect" (4360(a)), at least 28 days before the board decides. The version cites the
  source that holds its words (a Drive file, a library file, the specification's row);
- ``Stage.ADOPTED``: the decision at a board meeting, after considering members' comments (4360(b));
- ``Stage.DISTRIBUTED``: the general notice of the change, "not more than 15 days after making the rule change"
  (4360(c)). Members owning 5 percent of the separate interests may call a vote to reverse it by a written request
  delivered within 30 days after that notice (4365(b)); 4365 does not apply to an emergency change (4365(h)).

**Minutes** (4950) move through:

- ``Stage.DRAFT``: the minutes, or "minutes proposed for adoption that are marked to indicate draft status", available
  to members within 30 days of the meeting (4950(a)); not executive-session minutes;
- ``Stage.APPROVED``: the minutes of a later meeting record their approval;
- ``Stage.CORRECTED``: a later meeting approves them as corrected, or a corrected copy is filed.

A version not in force (a draft, a proposal) is cited as itself (``RecordVersion.label()``), never merged into the text
in force. Executive-session minutes are restricted (4935): a shared row gives only that they exist and their date.

Pure records and parsers. ``jason.tasks.record_stages`` reads the disk and builds the histories. A profile names the
association's own past rule changes as ``RuleChangeRecord`` rows (``Community.rule_change_records()``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any

from jason.community.revisions import RecordVersion, Stage

MINUTES_BOOK = "min"
PROPOSED_NOTICE = "rule-change-proposed"      # the notice catalog's rows (jason.community.notice_catalog)
ADOPTED_NOTICE = "rule-change-adopted"
MINUTES_AVAILABLE = "minutes-available"
REVERSAL_REQUEST_DAYS = 30                    # Civil Code 4365(b): the request, within 30 days after the notice


class Strength(Enum):
    """How strongly a record shows a stage happened."""

    DELIVERED = "delivered"        # a send on record: a mailing, the delivery ledger, PayHOA's log
    STATED = "stated"              # the minutes say it was done ("approved the minutes", "adopted")
    LISTED = "listed"              # named on an item the minutes carry; the outcome is not written
    EMAILED = "emailed"            # a copy emailed; to whom is not read here
    FILE = "file"                  # a file written that day; when it reached members is not on record
    PLANNED = "planned"            # a task to do it, not that it was done


class Standing(Enum):
    MET = "on record in time"
    LATE = "on record late"
    FILE_ONLY = "a file in time; its delivery is not on record"
    FILE_LATE = "a file, written after the deadline; its delivery is not on record"
    UNDATED = "on record, undated"
    OPEN = "none on record yet"
    PASSED = "none on record; the deadline passed"
    NOT_DUE = "not running: no decision on record"
    NOT_APPLICABLE = "does not apply"


class Outcome(Enum):
    ADOPTED = "adopted"
    PENDING = "proposed; no decision on record"
    WITHDRAWN = "withdrawn"
    REVERSED = "reversed by the members (4365)"


@dataclass(frozen=True)
class RuleChangeRecord:
    """One rule change the association made or proposed, as the profile names it.

    ``files`` is a pattern (case-insensitive, searched in a file's name) for the change's own files: its notices and
    its text. ``words`` are what the minutes call it. ``decided`` is the board meeting that decided it (None while no
    decision is on record). ``tasks`` is a pattern for a Google Task that plans one of its steps. ``emergency`` marks a
    4360(d) change (no 28-day notice; 4365 does not apply). ``notices`` names the files among ``files`` that are the
    notice of the proposed change although their names do not say so."""

    key: str
    title: str
    document: str                 # the rule's key (the book of its versions)
    document_title: str
    files: str = ""
    words: tuple[str, ...] = ()
    decided: date | None = None
    notices: str = ""             # files that are the notice of the proposed change although their names do not say so
    effective: date | None = None
    outcome: Outcome = Outcome.ADOPTED
    tasks: str = ""
    emergency: bool = False
    note: str = ""


@dataclass(frozen=True)
class Evidence:
    """One record of one stage: what it is, where its words are, its day, and how strongly it shows the stage."""

    stage: Stage
    what: str
    source: str                   # drive:<id>, library:<id>, a data/ path, or the minutes' label
    on: date | None
    strength: Strength
    passage: str = ""
    note: str = ""

    def row(self) -> dict[str, Any]:
        return {"stage": self.stage.value, "what": self.what, "source": self.source,
                "on": self.on.isoformat() if self.on else None, "strength": self.strength.value,
                "passage": self.passage, "note": self.note}


@dataclass(frozen=True)
class StageClock:
    requirement: str              # the notice catalog's key
    authority: str
    timing: str
    anchor: date | None           # the event the clock runs from (the decision, the meeting)
    deadline: date | None         # the last day it is met
    standing: Standing
    evidence: Evidence | None = None
    note: str = ""

    def row(self) -> dict[str, Any]:
        return {"requirement": self.requirement, "authority": self.authority, "timing": self.timing,
                "anchor": self.anchor.isoformat() if self.anchor else None,
                "deadline": self.deadline.isoformat() if self.deadline else None, "standing": self.standing.value,
                "evidence": self.evidence.row() if self.evidence else None, "note": self.note}


def version_row(v: RecordVersion) -> dict[str, Any]:
    return {"book": v.book, "item": v.item, "stage": v.stage.value, "on": v.on.isoformat() if v.on else None,
            "effective": v.effective.isoformat() if v.effective else None, "label": v.label(), "source": v.source,
            "event": v.event, "note": v.note}


# ---------------------------------------------------------------------------------------------------------------
# The clocks.


def _timing(key: str):
    from jason.community.notice_catalog import requirement

    row = requirement(key)
    return row, row.timing[0]


def notice_clock(key: str, authority: str, anchor: date | None, found: list[Evidence], on: date, *,
                 applies: bool = True, note: str = "") -> StageClock:
    """A notice's clock from ``anchor`` (the decision), with the best record found: a delivery first, then a file or an
    emailed copy, which shows the notice was written, not that it reached the members."""
    _, timing = _timing(key)
    if not applies:
        return StageClock(key, authority, timing.describe(), anchor, None, Standing.NOT_APPLICABLE, note=note)
    if anchor is None:
        first = min((e for e in found if e.on), key=lambda e: e.on, default=None)
        return StageClock(key, authority, timing.describe(), None, None, Standing.NOT_DUE, first, note)
    deadline = timing.window(anchor)[1]
    delivered = sorted((e for e in found if e.strength is Strength.DELIVERED and e.on), key=lambda e: e.on)
    if delivered:
        first = delivered[0]
        return StageClock(key, authority, timing.describe(), anchor, deadline,
                          Standing.MET if first.on <= deadline else Standing.LATE, first, note)
    files = sorted((e for e in found if e.strength in (Strength.FILE, Strength.EMAILED) and e.on), key=lambda e: e.on)
    if files:
        first = files[0]
        return StageClock(key, authority, timing.describe(), anchor, deadline,
                          Standing.FILE_ONLY if first.on <= deadline else Standing.FILE_LATE, first, note)
    undated = [e for e in found if e.strength in (Strength.FILE, Strength.DELIVERED, Strength.EMAILED)]
    if undated:
        return StageClock(key, authority, timing.describe(), anchor, deadline, Standing.UNDATED, undated[0], note)
    return StageClock(key, authority, timing.describe(), anchor, deadline,
                      Standing.PASSED if on > deadline else Standing.OPEN, None, note)


# ---------------------------------------------------------------------------------------------------------------
# Rule changes.


_ADOPTED_FILE = re.compile(r"notice of (?:the )?adopted|adopted rule", re.I)
_PROPOSED_FILE = re.compile(r"notice of (?:the )?proposed|proposed (?:rule )?changes?\b", re.I)
RULE_CHANGE_FILE = re.compile(r"^notice of (?:the )?(?:proposed|adopted) (?:rule )?changes?\b", re.I)


def file_stage(name: str) -> Stage:
    """What a rule change's file is by its name: the notice of the adopted change, the notice of the proposed change,
    or (any other) the rule's text."""
    if _ADOPTED_FILE.search(name):
        return Stage.DISTRIBUTED
    if _PROPOSED_FILE.search(name):
        return Stage.PROPOSED
    return Stage.DRAFT


@dataclass
class RuleChangeHistory:
    key: str
    title: str
    document: str
    document_title: str
    origin: str                                   # "record" (the profile's row) or "specification" (a draft change)
    outcome: Outcome
    decided: date | None
    versions: list[RecordVersion] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    clocks: list[StageClock] = field(default_factory=list)
    reversal: str = ""
    actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def stages_with_evidence(self) -> dict[str, str]:
        """Each stage and the strongest record of it, or "none"."""
        order = list(Strength)
        out = {}
        for stage in (Stage.DRAFT, Stage.PROPOSED, Stage.ADOPTED, Stage.DISTRIBUTED):
            found = [e.strength for e in self.evidence if e.stage is stage and e.strength is not Strength.PLANNED]
            out[stage.value] = min(found, key=order.index).value if found else "none"
        return out

    def row(self) -> dict[str, Any]:
        return {"key": self.key, "title": self.title, "document": self.document, "documentTitle": self.document_title,
                "origin": self.origin, "outcome": self.outcome.value,
                "decided": self.decided.isoformat() if self.decided else None,
                "stages": self.stages_with_evidence(), "versions": [version_row(v) for v in self.versions],
                "clocks": [c.row() for c in self.clocks], "evidence": [e.row() for e in self.evidence],
                "reversal": self.reversal, "actions": self.actions, "notes": self.notes}

    def lines(self) -> list[str]:
        head = f"{self.key}: {self.title} ({self.document_title}; {self.outcome.value}"
        out = [head + (f", decided {self.decided})" if self.decided else ")")]
        for v in self.versions:
            out.append(f"    {self.document}{v.label():28} {v.event}" + (f" [{v.source}]" if v.source else ""))
            if v.note:
                out.append(f"        {v.note}")
        for c in self.clocks:
            tail = f": {c.evidence.what}, {c.evidence.on}" if c.evidence and c.evidence.on else (
                f": {c.evidence.what}" if c.evidence else "")
            out.append(f"    clock {c.authority} ({c.timing}"
                       + (f", by {c.deadline}" if c.deadline else "") + f"): {c.standing.value}{tail}")
            if c.note:
                out.append(f"        {c.note}")
        if self.reversal:
            out.append(f"    4365: {self.reversal}")
        for e in self.evidence:
            if e.strength is Strength.PLANNED:
                out.append(f"    planned: {e.what}")
        out += [f"    * {n}" for n in self.notes]
        out += [f"    ACTION: {a}" for a in self.actions]
        return out


def rule_change_history(record: RuleChangeRecord, evidence: list[Evidence], *, on: date,
                        origin: str = "record") -> RuleChangeHistory:
    """The versions, clocks, and reversal window of one rule change, from the evidence found for it."""
    h = RuleChangeHistory(record.key, record.title, record.document, record.document_title, origin, record.outcome,
                          record.decided, evidence=sorted(evidence, key=lambda e: (e.on or date.max, e.what)))
    decided = record.decided
    texts = [e for e in h.evidence if e.stage is Stage.DRAFT and e.source]
    proposed = [e for e in h.evidence if e.stage is Stage.PROPOSED and e.strength is not Strength.PLANNED]
    adoption = [e for e in h.evidence if e.stage is Stage.ADOPTED]
    distributed = [e for e in h.evidence if e.stage is Stage.DISTRIBUTED and e.strength is not Strength.PLANNED]

    before = [e for e in texts if decided is None or (e.on is not None and e.on < decided)]
    if before:
        first = before[0]
        h.versions.append(RecordVersion(record.document, "", Stage.DRAFT, first.on, None, first.source,
                                        "the text as drafted", first.what))
    sources = [e for e in proposed if e.source]
    if sources:
        # The day: the first delivery, else the first file or copy. The words: a file kept (Drive, the library, the
        # specification), else whatever holds them.
        best = next((e for e in sources if e.strength is Strength.DELIVERED), sources[0])
        kept = next((e for e in sources if e.source.startswith(("drive:", "library:", "specification:", "data/"))),
                    best)
        how = {Strength.DELIVERED: "the notice of the proposed change, delivered",
               Strength.EMAILED: "the notice of the proposed change, a copy emailed",
               Strength.FILE: "the notice of the proposed change, as written (its delivery is not on record)"}
        note = kept.what if kept is best else f"Its words: {kept.what}. Delivered: {best.what}."
        h.versions.append(RecordVersion(record.document, "", Stage.PROPOSED, best.on, None, kept.source,
                                        how.get(best.strength, "the notice of the proposed change"), note))
    elif proposed:
        h.notes.append("A notice of the proposed change is on record with no source for its words: the proposed "
                       "version is not cited until its text is found.")
    if decided is not None:
        after = [e for e in texts if e.on is not None and e.on >= decided]
        held = after[0] if after else next((e for e in distributed if e.source), None)
        source = held.source if held else (adoption[0].source if adoption else "")
        note = (f"Its words: {held.what}." if held else
                "No copy of the adopted text dated on or after the decision is on record; the minutes are cited.")
        if record.effective is None:
            note += " In force from the decision unless the adopted text sets a later day (not read here)."
        h.versions.append(RecordVersion(record.document, "", Stage.ADOPTED, decided, record.effective or decided,
                                        source, f"board meeting {decided}", note))
    if distributed:
        best = next((e for e in distributed if e.strength is Strength.DELIVERED), distributed[0])
        h.versions.append(RecordVersion(record.document, "", Stage.DISTRIBUTED, best.on, None, best.source,
                                        "the notice of the adopted change (4360(c))", best.what))

    emergency = record.emergency
    h.clocks.append(notice_clock(PROPOSED_NOTICE, "CIV 4360(a)", decided, proposed, on, applies=not emergency,
                                 note="An emergency change needs no notice before it (4360(d))." if emergency else ""))
    h.clocks.append(notice_clock(ADOPTED_NOTICE, "CIV 4360(c)", decided, distributed, on))
    if decided is not None and not adoption:
        h.notes.append(f"No passage of the minutes of {decided} is on record for the decision: the profile's date "
                       "is the evidence (4360(b): a decision at a board meeting).")

    # 4365: the members' request for a reversal vote, within 30 days after the general notice of the change.
    if emergency:
        h.reversal = "does not apply to an emergency rule change (4365(h))"
    elif decided is None:
        h.reversal = "not running: the change is not made"
    else:
        sent = h.clocks[1].evidence if h.clocks[1].standing in (Standing.MET, Standing.LATE) else None
        if sent and sent.on:
            last = sent.on + timedelta(days=REVERSAL_REQUEST_DAYS)
            h.reversal = (f"members owning 5 percent may deliver a written request for a reversal vote until {last} "
                          f"(30 days after the notice delivered {sent.on}, 4365(b))"
                          + ("; that day has passed" if on > last else "") + ". No request is on record: jason reads "
                          "no members' petitions.")
        else:
            h.reversal = ("the 30 days for a reversal request run from the general notice of the change (4365(b)); "
                          "no delivery of that notice is on record, so when they end is not shown.")

    # What a person or the board should act on.
    a, c = h.clocks
    if record.outcome is Outcome.ADOPTED and c.standing in (Standing.PASSED, Standing.FILE_LATE):
        h.actions.append(f"No notice of the adopted change is on record within 15 days of {decided} (4360(c)). A "
                         "person checks the mail, PayHOA's log, and any posting; if none went out, the board gives "
                         "general notice of the rule now and records it.")
    elif record.outcome is Outcome.ADOPTED and c.standing in (Standing.FILE_ONLY, Standing.UNDATED):
        h.actions.append("The notice of the adopted change is on file but its delivery is not on record: a person "
                         "confirms how and when it was given and records it.")
    if record.outcome is Outcome.ADOPTED and not emergency and a.standing in (Standing.PASSED, Standing.LATE,
                                                                             Standing.FILE_LATE):
        h.actions.append(f"No notice of the proposed change is on record 28 days before {decided} (4360(a)). A "
                         "person checks the record; if none was given, counsel says whether the rule needs to be "
                         "noticed and adopted again.")
    if record.outcome is Outcome.PENDING and proposed:
        first = min((e.on for e in proposed if e.on), default=None)
        if first and (on - first).days > 90:
            h.actions.append(f"Proposed by {first} with no decision on record: the board decides it at a meeting or "
                             "withdraws it. A decision long after the notice, or on changed text, may need a new "
                             "28-day notice (counsel).")
    for e in h.evidence:
        if e.strength is Strength.PLANNED and "needsAction" in e.note and e.on and e.on < on:
            h.actions.append(f"A task to send a notice is still open past its due day: {e.what}.")
    if record.note:
        h.notes.append(record.note)
    return h


# ---------------------------------------------------------------------------------------------------------------
# Minutes: the approval items a later meeting's minutes carry.


_MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                       "dec"), 1)}
_HEADING = re.compile(r"(?:(?<=\s)|^)(?:[IVX]{1,6}|\d{1,2})\.\s+(?=[A-Z])")
_ITEM = re.compile(r"approv\w*\s+(?:of\s+)?(?:the\s+)?(?:previous\s+)?(?:meeting\s+)?minutes"
                   r"|minutes\s+of\s+(?:the\s+)?previous\s+meetings?", re.I)
_STATED = re.compile(r"\bapproved\b|\bM/S/P\b|\bMSC\b(?!\s*-\s*Motion)|\bmotion\b[^.]{0,80}\bcarried\b|\bunanimously\b",
                     re.I)
_STATED_ANYWHERE = re.compile(r"\bapprov(?:ed|ing)\b[^.]{0,60}\bminutes\b|\bminutes\b[^.]{0,40}\b(?:were|was)\s+"
                              r"approved\b", re.I)
_CORRECTED = re.compile(r"\b(?:as\s+)?(?:corrected|amended)\b|\bcorrections?\b|\brevis(?:ed|ions?)\b", re.I)
_BOILERPLATE = re.compile(r"true and correct", re.I)
CORRECTED_NAME = re.compile(r"\b(?:corrected|amended|revised)\b", re.I)
DRAFT_NAME = re.compile(r"\bdraft\b", re.I)


def _year(text: str) -> int:
    n = int(text)
    return n + 2000 if n < 100 else n


def named_dates(text: str) -> list[date]:
    """The dates a passage names, in order, once each: 5/19/26, 5_19_26, May 19, 2026, October 17th, 2023."""
    found: list[tuple[int, date]] = []
    for m in re.finditer(r"(?<![\d/_])(\d{1,2})[/_](\d{1,2})[/_](\d{4}|\d{2})(?![\d/_])", text):
        try:
            found.append((m.start(), date(_year(m.group(3)), int(m.group(1)), int(m.group(2)))))
        except ValueError:
            pass
    for m in re.finditer(_MONTH + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", text, re.I):
        try:
            found.append((m.start(), date(int(m.group(3)), _MONTHS[m.group(1).lower()[:3]], int(m.group(2)))))
        except ValueError:
            pass
    out: list[date] = []
    for _, d in sorted(found, key=lambda f: f[0]):
        if d not in out:
            out.append(d)
    return out


@dataclass(frozen=True)
class ApprovalItem:
    """An approval of minutes as a later meeting's minutes carry it: the meetings it names, whether the minutes state
    the approval (or only list the item), whether it was approved as corrected, and the passage."""

    dates: tuple[date, ...]
    previous: bool                 # names "the previous meeting" with no date
    stated: bool
    corrected: bool
    passage: str


def _clean(text: str) -> str:
    return " ".join(text.replace("​", " ").replace(" ", " ").split())


def approval_items(text: str) -> list[ApprovalItem]:
    """Each approval-of-minutes item in a meeting's minutes. The item runs from its heading to the next heading (or
    300 characters). An approval written anywhere in the text ("they approved the minutes") marks every item stated."""
    text = text.replace("​", " ")
    heads = [m.start() for m in _HEADING.finditer(text)]
    anywhere = bool(_STATED_ANYWHERE.search(text))
    out: list[ApprovalItem] = []
    seen: set[tuple[tuple[date, ...], bool]] = set()
    for m in _ITEM.finditer(text):
        start = max([h for h in heads if h <= m.start() and m.start() - h <= 200] or [m.start()])
        end = min([h for h in heads if h > m.end()] + [m.end() + 300])
        section = text[start:end]
        dates = tuple(named_dates(section))
        previous = not dates and bool(re.search(r"previous", section, re.I))
        if not dates and not previous:
            continue
        key = (dates, previous)
        if key in seen:
            continue
        seen.add(key)
        stated = bool(_STATED.search(section)) or anywhere
        corrected = bool(_CORRECTED.search(_BOILERPLATE.sub("", section)))
        out.append(ApprovalItem(dates, previous, stated, corrected, _clean(section)[:240]))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Minutes histories.


class MeetingKind(Enum):
    BOARD = "board meeting"
    EXECUTIVE = "executive session only"
    MEMBERS = "members' meeting"
    UNKNOWN = "meeting (kind not on record)"


@dataclass(frozen=True)
class MinutesCopy:
    """One copy of the minutes on file. A confidential copy (an executive session's) shows only that it exists and its
    date in a shared row."""

    name: str
    where: str
    source: str                    # drive:<id>, library:<id>, or where it is kept
    on: date | None                # sent, or created on Drive
    draft: bool = False
    confidential: bool = False
    count: int = 1                 # copies of one name in one place (a file attached to many emails)

    def row(self) -> dict[str, Any]:
        if self.confidential:
            return {"kind": "executive session minutes", "date": self.on.isoformat() if self.on else None}
        return {"name": self.name, "where": self.where, "source": self.source,
                "on": self.on.isoformat() if self.on else None, "draft": self.draft, "count": self.count}

    def label(self) -> str:
        if self.confidential:
            return "executive session minutes" + (f", {self.on}" if self.on else "")
        many = f" x{self.count}" if self.count > 1 else ""
        return f"{self.name} ({self.where}{', draft' if self.draft else ''}{many})" + (f", {self.on}" if self.on else "")


@dataclass(frozen=True)
class Approval:
    meeting: date                  # the later meeting whose minutes record it
    source: str                    # that meeting's minutes
    stated: bool
    corrected: bool
    passage: str

    def row(self) -> dict[str, Any]:
        return {"meeting": self.meeting.isoformat(), "source": self.source, "stated": self.stated,
                "corrected": self.corrected, "passage": self.passage}


@dataclass
class MinutesHistory:
    day: date
    kind: MeetingKind
    basis: str
    copies: list[MinutesCopy] = field(default_factory=list)
    approvals: list[Approval] = field(default_factory=list)
    clock: StageClock | None = None
    versions: list[RecordVersion] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    @property
    def draft_on_time(self) -> bool | None:
        """Whether a copy is on record within 30 days; None when 4950(a) does not apply or the clock still runs."""
        if self.clock is None or self.clock.standing in (Standing.NOT_APPLICABLE, Standing.OPEN):
            return None
        return self.clock.standing is Standing.MET

    @property
    def approval(self) -> str:
        """"stated", "listed" (named on a later meeting's approval item, the outcome not written), or "none"."""
        if any(a.stated for a in self.approvals):
            return "stated"
        return "listed" if self.approvals else "none"

    def row(self) -> dict[str, Any]:
        return {"date": self.day.isoformat(), "kind": self.kind.value, "basis": self.basis,
                "draftOnTime": self.draft_on_time, "approval": self.approval,
                "copies": [c.row() for c in self.copies], "approvals": [a.row() for a in self.approvals],
                "clock": self.clock.row() if self.clock else None,
                "versions": [version_row(v) for v in self.versions], "notes": self.notes, "actions": self.actions}

    def lines(self) -> list[str]:
        out = [f"{self.day}  {self.kind.value}; {self.basis}"]
        for v in self.versions:
            out.append(f"    {v.book}/{v.item}{v.label():28} {v.event}" + (f" [{v.source}]" if v.source else ""))
            if v.note:
                out.append(f"        {v.note}")
        if self.clock is not None:
            c = self.clock
            rec = f": {c.evidence.what}" + (f", {c.evidence.on}" if c.evidence.on else "") if c.evidence else ""
            out.append(f"    clock {c.authority} ({c.timing}" + (f", by {c.deadline}" if c.deadline else "")
                       + f"): {c.standing.value}{rec}")
        for copy in self.copies:
            out.append(f"    copy: {copy.label()}")
        out += [f"    * {n}" for n in self.notes]
        out += [f"    ACTION: {a}" for a in self.actions]
        return out


def minutes_versions(h: MinutesHistory) -> list[RecordVersion]:
    """The minutes' versions: the draft (the first copy on record), each approval, and each correction."""
    item = h.day.isoformat()
    out: list[RecordVersion] = []
    public = [c for c in h.copies if not c.confidential]
    dated = sorted((c for c in public if c.on and c.on >= h.day), key=lambda c: c.on)   # one made ahead is a template
    first_approval = min((a.meeting for a in h.approvals), default=None)
    drafts = [c for c in dated if first_approval is None or c.on < first_approval]
    if drafts:
        first = next((c for c in drafts if c.draft), drafts[0])
        out.append(RecordVersion(MINUTES_BOOK, item, Stage.DRAFT, first.on, None, first.source,
                                 "the first copy on record" + (", marked draft" if first.draft else ""),
                                 first.label()))
    elif any(c.draft for c in public):
        c = next(c for c in public if c.draft)
        out.append(RecordVersion(MINUTES_BOOK, item, Stage.DRAFT, c.on, None, c.source, "a copy marked draft",
                                 c.label()))
    kept = [c for c in public if not c.draft and c.where != "Gmail"]     # a file kept, not an email's attachment
    for a in sorted(h.approvals, key=lambda a: a.meeting):
        later = [c for c in dated if c in kept and c.on >= a.meeting]
        undated = [c for c in kept if c.on is None]
        earlier = [c for c in dated if c in kept]
        held = (later or undated or earlier or [c for c in public if not c.draft] or [None])[0]
        how = "approval stated" if a.stated else "named on the approval item; the outcome is not written"
        note = f"Its words: {held.label()}." if held else "No copy of the approved text is on file."
        if held is not None and held.on is not None and held.on < a.meeting:
            note += " The copy is dated before the approval: the approved words are that copy as it now stands."
        stage = Stage.CORRECTED if a.corrected else Stage.APPROVED
        out.append(RecordVersion(MINUTES_BOOK, item, stage, a.meeting, a.meeting, held.source if held else a.source,
                                 f"minutes of the meeting of {a.meeting}: {how}"
                                 + ("; approved as corrected" if a.corrected else ""), note))
    for c in public:
        if CORRECTED_NAME.search(c.name):
            out.append(RecordVersion(MINUTES_BOOK, item, Stage.CORRECTED, c.on, None, c.source,
                                     "a copy named as corrected", c.label()))
    return out


__all__ = ["ADOPTED_NOTICE", "Approval", "ApprovalItem", "CORRECTED_NAME", "DRAFT_NAME", "Evidence", "MINUTES_AVAILABLE",
           "MINUTES_BOOK", "MeetingKind", "MinutesCopy", "MinutesHistory", "Outcome", "PROPOSED_NOTICE",
           "REVERSAL_REQUEST_DAYS", "RULE_CHANGE_FILE", "RuleChangeHistory", "RuleChangeRecord", "StageClock",
           "Standing", "Strength", "approval_items", "file_stage", "minutes_versions", "named_dates", "notice_clock",
           "rule_change_history", "version_row"]
