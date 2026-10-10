"""Rule records, read: a rule on any day, its history, its comparison with the working Doc, and where it was applied
(docs/rule-records.md, phase 1).

This extends the records of ``jason.community.rules_document`` (``RuleBook``, ``RuleRecord``, ``RuleVersion``); it adds no
second record. Pure: no disk, no clock, no profile. The tasks (``jason.tasks.rule_records``) read the stores and hand them
in; the command, the MCP tools, and the web loaders all shape their answers with the functions here, so the three agree.

What it decides, and what it does not.

- **Status is derived, never typed.** A record's status on a day is a fold of its versions, its acts (a suspension or a
  repeal a person recorded), and the adoption events: ``proposed``, ``noticed``, ``adopted``, ``suspended``,
  ``repealed``, ``expired``. A version whose adoption day is not on record (a derived record's first version) is shown as
  **in force, adoption not on record**, with ``adoption_on_record`` false. It is never promoted to "adopted".
- **The words come first.** A version's words are the stored words with the version's citation, source and day; every
  reading (the status, the grounds, the comparison with the Doc) follows and is labeled jason's.
- **The Doc is a working source, never the rule.** ``compare`` sets the working Doc's words beside the version in force
  and names the relation with one of four words; it merges nothing and the adopted words stay the rule.
- **A miss stays a miss.** No grant found is a question for the board and counsel, never "no authority"; no use linked is
  not "never applied"; a Doc not read is not "same".
- A use is a list, never a finding that a rule was or was not applied consistently.

jason proposes; the board adopts. Nothing here adopts, approves, or recommends.
"""

from __future__ import annotations

import difflib
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Iterable, Sequence

from jason.community import rule_authority as ra
from jason.community.manual import AdoptionAction, AdoptionEvent
from jason.community.rules_document import RuleBook, RuleRecord, RuleVersion, event_covers

CAVEAT = "jason's text of an adopted rule. The minutes and the recorded instrument govern."
NO_ADOPTION_CAVEAT = "No adoption found is a finding for a person, not proof that none happened."
SUGGESTION_NOTE = "A pending suggestion is not accepted and is not a rule."
USE_NOTE = "A list of the association's uses of the rule, not a finding. 'No use linked' is shown as that."
NO_USE = "no use linked: not a finding that the rule was not applied"
ADDRESS = "jason://rules/"


class Status(Enum):
    PROPOSED = "proposed"
    NOTICED = "noticed"
    ADOPTED = "adopted"
    SUSPENDED = "suspended"
    REPEALED = "repealed"
    EXPIRED = "expired"


NOT_ON_RECORD = "in force, adoption not on record"
STATUS_WORDS = tuple(s.value for s in Status) + (NOT_ON_RECORD,)


class CompareWord(Enum):
    SAME = "same"
    RECORD_BEHIND = "the record is behind"
    DOC_AHEAD = "the Doc ran ahead"
    NO_ADOPTION = "changed with no adoption found"


COMPARE_WORDS = tuple(c.value for c in CompareWord)

# What a version's words are (docs/rule-records.md, section 3.2). A working draft is never one of them.
SOURCE_ADOPTED = "the adopted text"
SOURCE_NOTICED = "the noticed text"
SOURCE_AS_READ = "the document's words as read, adoption on record"
SOURCE_IMPORTED = "imported, adoption not on record"
SOURCE_PROPOSED = "proposed words, not adopted"
SOURCES = (SOURCE_ADOPTED, SOURCE_NOTICED, SOURCE_AS_READ, SOURCE_IMPORTED, SOURCE_PROPOSED)


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _digest(text: str) -> str:
    return hashlib.sha256(" ".join((text or "").split()).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------------------------------------------------
# Versions, by day


def numbers_of(record: RuleRecord) -> tuple[str, ...]:
    """The numbers an adoption event may name the rule by."""
    tail = record.id.split("#", 1)[-1].split("/", 1)[0]
    return tuple(dict.fromkeys(n for n in (record.number, tail) if n))


def version_id(record: RuleRecord, index: int) -> str:
    return record.versions[index].version or f"v{index + 1}"


def version_index_on(record: RuleRecord, day: date | None) -> int | None:
    """The index of the newest adopted version on or before ``day``; a proposed version is in force on no day. A version
    whose adoption day is not on record is in force on every day (the words as the source document has them)."""
    live = [((v.adopted or date.min), i) for i, v in enumerate(record.versions) if v.in_force(day)]
    return max(live)[1] if live else None


def version_on(record: RuleRecord, day: date | None) -> RuleVersion | None:
    i = version_index_on(record, day)
    return record.versions[i] if i is not None else None


def events_for(record: RuleRecord, events: Iterable[AdoptionEvent]) -> list[AdoptionEvent]:
    """The adoption events that name the rule, oldest first (an event with no day last)."""
    nums = numbers_of(record)
    mine = [e for e in events if nums and event_covers(e, *nums)]
    return sorted(mine, key=lambda e: (e.on is None, e.on or date.min))


def _latest_adopted(record: RuleRecord) -> date | None:
    days = [v.adopted for v in record.versions if v.adopted and not v.proposed]
    return max(days) if days else None


def is_noticed(record: RuleRecord, events: Iterable[AdoptionEvent], index: int | None = None) -> bool:
    """Whether a proposed version has a notice on record: ledger keys on the version, or a noticed or delivered event
    for the rule dated after the newest adopted version."""
    if index is not None and record.versions[index].notice:
        return True
    floor = _latest_adopted(record)
    return any(e.action in (AdoptionAction.NOTICED, AdoptionAction.DELIVERED) and (e.on is None or floor is None or e.on > floor)
               for e in events_for(record, events))


@dataclass(frozen=True)
class StatusOn:
    """A rule's status on a day. ``adoption_on_record`` is false for a version whose adoption day is not on record."""

    status: Status | None
    adoption_on_record: bool = True
    since: date | None = None
    until: date | None = None
    version: str = ""
    note: str = ""

    @property
    def word(self) -> str:
        if self.status is None:
            return "no version in force"
        if self.status is Status.ADOPTED and not self.adoption_on_record:
            return NOT_ON_RECORD
        return self.status.value

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status.value if self.status else None, "statusWord": self.word,
                "adoptionOnRecord": self.adoption_on_record, "since": _day(self.since), "until": _day(self.until),
                "version": self.version, "note": self.note}


def status_on(record: RuleRecord, day: date | None, events: Iterable[AdoptionEvent] = ()) -> StatusOn:
    """The status on ``day`` (None: the newest). The acts first (a repeal, a suspension), then the version in force; with
    none in force, a proposed version is ``noticed`` when a notice is on record, else ``proposed``."""
    events = list(events)
    repeal = [a for a in record.acts if a.kind == "repeal" and (day is None or a.on <= day)]
    if repeal:
        act = max(repeal, key=lambda a: a.on)
        return StatusOn(Status.REPEALED, True, act.on, note="repealed by a person's record" + (f" ({act.evidence})" if act.evidence else ""))
    held = [a for a in record.acts if a.kind == "suspension" and (day is None or (a.on <= day and (a.until is None or day <= a.until)))]
    i = version_index_on(record, day)
    if held:
        act = max(held, key=lambda a: a.on)
        return StatusOn(Status.SUSPENDED, True, act.on, act.until, version_id(record, i) if i is not None else "",
                        "the version is not edited; the rule is suspended for a time")
    if i is not None:
        v = record.versions[i]
        if v.expires and day is not None and day > v.expires:
            return StatusOn(Status.EXPIRED, v.adopted is not None, v.expires, None, version_id(record, i),
                            "an emergency version whose end day has passed")
        return StatusOn(Status.ADOPTED, v.adopted is not None, v.adopted, None, version_id(record, i),
                        "" if v.adopted else "the adoption day is not on record; a person records it from the minutes")
    proposed = [k for k, v in enumerate(record.versions) if v.proposed]
    if proposed:
        k = proposed[-1]
        noticed = is_noticed(record, events, k)
        return StatusOn(Status.NOTICED if noticed else Status.PROPOSED, True, None, None, version_id(record, k),
                        "in force on no day until the board adopts it")
    return StatusOn(None, True, note="the record does not show which words were in force on this day")


def open_proposals(record: RuleRecord) -> list[str]:
    return [version_id(record, i) for i, v in enumerate(record.versions) if v.proposed]


# ---------------------------------------------------------------------------------------------------------------------
# Where a version's words come from


@dataclass(frozen=True)
class Source:
    kind: str
    file: str = ""
    caveat: str = CAVEAT

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {"kind": self.kind, "caveat": self.caveat}
        if self.file:
            raw["file"] = self.file
        return raw


def source_of(record: RuleRecord, index: int, events: Iterable[AdoptionEvent] = ()) -> Source:
    """Which of the sources of docs/rule-records.md section 3.2 a version's words are from. A stored ``source`` is used as
    it is; otherwise it is read from the version: proposed words with a notice on record are the noticed text; an adopted
    day on record means the document's words as read; no adoption day means imported, adoption not on record. A working
    Doc's words are never a source."""
    v = record.versions[index]
    if v.source:
        return Source(v.source, v.source_file)
    if v.proposed:
        return Source(SOURCE_NOTICED if is_noticed(record, events, index) else SOURCE_PROPOSED, v.source_file)
    return Source(SOURCE_AS_READ if v.adopted else SOURCE_IMPORTED, v.source_file)


# ---------------------------------------------------------------------------------------------------------------------
# History


def diff_words(before: str, after: str) -> list[dict[str, str]]:
    """The change between two sets of words, run by run, each ``{"op": "same"|"removed"|"added", "text"}``: a list the
    screen prints with text markers, never a merged text."""
    a, b = (before or "").split(), (after or "").split()
    out: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append({"op": "same", "text": " ".join(a[i1:i2])})
        else:
            if i2 > i1:
                out.append({"op": "removed", "text": " ".join(a[i1:i2])})
            if j2 > j1:
                out.append({"op": "added", "text": " ".join(b[j1:j2])})
    return out


def version_stage(record: RuleRecord, index: int, events: Iterable[AdoptionEvent] = ()) -> str:
    v = record.versions[index]
    if v.proposed:
        return "noticed" if is_noticed(record, events, index) else "proposed"
    return "adopted"


def history(record: RuleRecord, events: Iterable[AdoptionEvent] = (), day: date | None = None) -> dict[str, Any]:
    """Every version, newest first: its words and the change from the one before, its adoption (day, board item, decision),
    its notice, who proposed it and who recorded the adoption (empty where no one did: a miss), what it superseded, and
    the version in force on ``day`` marked. Then the adoption events that name the rule, and the gaps."""
    events = list(events)
    in_force = version_index_on(record, day) if day is not None else None
    rows: list[dict[str, Any]] = []
    previous: int | None = None
    gaps: list[dict[str, str]] = []
    for i, v in enumerate(record.versions):
        src = source_of(record, i, events)
        prior = record.versions[previous] if previous is not None else None
        replaced = v.supersedes or (version_id(record, previous) if previous is not None and not v.proposed else "")
        rows.append({
            "id": version_id(record, i), "stage": version_stage(record, i, events), "words": v.words or v.text,
            "digest": _digest(v.words or v.text), "diffTo": version_id(record, previous) if previous is not None else "",
            "diff": diff_words(prior.words or prior.text, v.words or v.text) if prior is not None else [],
            "adopted": _day(v.adopted), "adoptionOnRecord": (v.adopted is not None) if not v.proposed else None,
            "effective": _day(v.effective), "expires": _day(v.expires), "boardItem": v.board_item, "decision": v.decision,
            "recordedBy": v.recorded_by, "recordedAt": v.recorded_at, "proposedBy": v.proposed_by,
            "notice": list(v.notice), "supersedes": replaced, "source": src.to_dict(), "note": v.note,
            "inForce": in_force == i,
            "confidentiality": (record.confidentiality or "board") if v.proposed else (record.confidentiality or "open")})
        if not v.proposed:
            previous = i
    first = next((v for v in record.versions if not v.proposed), None)
    if first is not None and first.adopted is not None:
        gaps.append({"before": first.version or "v1",
                     "note": f"the record does not show which words were in force before {first.adopted.isoformat()}"})
    for r in rows:
        if r["stage"] != "proposed" and not r["proposedBy"] and not r["recordedBy"] and r["adoptionOnRecord"] is not False:
            r["whoNote"] = "who proposed it and who recorded the adoption are not on record"
    rows.reverse()
    return {"versions": rows, "ended": [], "gaps": gaps,
            "events": [{"on": _day(e.on), "action": e.action.value, "evidence": e.evidence, "source": e.source,
                        "record": e.record, "note": e.note} for e in events_for(record, events)],
            "acts": [a.to_dict() for a in record.acts]}


# ---------------------------------------------------------------------------------------------------------------------
# Grounds: the grant a rule rests on


@dataclass(frozen=True)
class Grounds:
    """The authority a rule rests on, as ``jason rules`` found it, set beside the rule. ``standing`` is a word from
    ``rule_authority.Standing`` (or ``not read`` / ``no subject read``). No grant found is a question, never "no authority"."""

    subjects: tuple[str, ...]
    subject_source: str
    standing: str
    grants: tuple[dict[str, Any], ...] = ()
    general: tuple[str, ...] = ()
    in_guidance: tuple[str, ...] = ()
    stated: tuple[str, ...] = ()
    reach: tuple[dict[str, Any], ...] = ()
    no_grant_found: bool = False
    read: bool = True
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"subjects": list(self.subjects), "subjectSource": self.subject_source, "standing": self.standing,
                "grants": list(self.grants), "general": list(self.general), "inGuidance": list(self.in_guidance),
                "stated": list(self.stated), "reach": list(self.reach), "noGrantFound": self.no_grant_found,
                "read": self.read, "note": self.note}


_STANDING_ORDER = (ra.Standing.AUTHORITY_AND_RULES, ra.Standing.AUTHORITY_ONLY, ra.Standing.GENERAL_AND_RULES,
                   ra.Standing.GENERAL_ONLY, ra.Standing.RULES_ONLY, ra.Standing.NEITHER)


def subjects_of(record: RuleRecord, version: RuleVersion | None = None) -> tuple[tuple[str, ...], str]:
    """The record's subjects and where they came from: the words a person stored, else the rule reader's reading of the
    heading and the first words (``rule_authority.subjects_of``), which is jason's reading, to be confirmed."""
    if record.subjects:
        return tuple(record.subjects), "stored (a person confirmed)"
    v = version or (record.versions[-1] if record.versions else None)
    text = f"{record.title} {(v.words or v.text)[:600] if v else ''}"
    return tuple(s.value for s in ra.subjects_of(text)), "read by jason's rule reader from the heading and the words"


def grant_dict(a: ra.RuleAuthority) -> dict[str, Any]:
    """A grant as the record shows it: the words recited whole with the citation, then the reading (tier, readers,
    holder, subjects, conditions, review)."""
    return {"id": a.id, "citation": f"{a.source} {a.section}".strip(), "title": a.title, "tier": a.tier.value,
            "readers": list(a.readers), "holder": a.holder.value, "subjects": [s.value for s in a.subjects],
            "conditions": [{"kind": c.kind.value, "quote": c.quote} for c in a.conditions], "procedure": a.procedure,
            "review": a.review.value, "reviewNote": a.note,
            "recital": {"words": a.words or a.sentence, "citation": f"{a.source} {a.section}".strip()}}


def grounds_for(record: RuleRecord, version: RuleVersion | None = None, rows: Sequence[ra.SubjectRow] | None = None,
                authorities: Sequence[ra.RuleAuthority] = ()) -> Grounds:
    """The record's grounds. ``rows`` are ``jason rules --subjects``' subject rows (None: not read); ``authorities`` the
    stored grants. A grant a person tied to the record (``record.authority``) is shown as stated; otherwise the grants that
    name the record's subjects. The 4355 reach of each subject is jason's reading, labeled."""
    subjects, how = subjects_of(record, version)
    reach = []
    for word in subjects:
        try:
            r = ra.reach(ra.Subject(word))
        except ValueError:
            continue
        reach.append({"subject": word, "reach": r.reach.value, "cites": list(r.cites), "note": r.note,
                      "label": "jason's reading of Civil Code 4355"})
    by_id = {a.id: a for a in authorities}
    stated = tuple(i for i in record.authority)
    if rows is None:
        return Grounds(subjects, how, "not read", tuple(grant_dict(by_id[i]) for i in stated if i in by_id), stated=stated,
                       reach=tuple(reach), read=False, note="the grants have not been read: jason rules --find, then jason rules --subjects")
    if not subjects and not stated:
        return Grounds((), how, "no subject read", reach=(), note="say which subject the rule is about; it is a question, not a finding")
    mine = [r for r in rows if r.subject.value in subjects]
    named = list(dict.fromkeys([*stated, *(g for r in mine for g in r.grants)]))
    general = tuple(dict.fromkeys(g for r in mine for g in r.general if g not in named))
    guide = tuple(dict.fromkeys(g for r in mine for g in r.in_guidance))
    best = next((s for s in _STANDING_ORDER for r in mine if r.standing is s), None)
    standing = best.value if best else (ra.Standing.AUTHORITY_ONLY.value if named else "not read")
    grants = tuple(grant_dict(by_id[i]) for i in named if i in by_id)
    none = not named and not general
    return Grounds(subjects, how, standing, grants, general, guide, stated, tuple(reach), none, True,
                   "no grant found: a question for the board and counsel, never an accusation (jason rules --find)" if none else "")


# ---------------------------------------------------------------------------------------------------------------------
# The Doc beside the record


@dataclass(frozen=True)
class DocReading:
    """What the task read of the working Doc for one rule. ``words`` is the Doc's words; ``later_adoption`` describes an
    adoption on record that covers them (a later one than the version stored); ``suggested`` says the Doc's words include a
    pending suggestion; ``in_doc`` is false when the Doc has no such section."""

    words: str = ""
    revision: str = ""
    later_adoption: str = ""
    suggested: bool = False
    pending: int = 0
    in_doc: bool = True
    changed_between: tuple[str, str] = ("", "")


def _plain(text: str) -> list[str]:
    text = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return [w.lower() for w in re.sub(r"[#*_`>|]", " ", text).split()]


def same_words(a: str, b: str) -> bool:
    return _plain(a) == _plain(b)


@dataclass(frozen=True)
class Compare:
    word: CompareWord | None
    standing: str                              # "compared", "the Doc was not read", "not in the Doc", "no version in force"
    adopted_version: str = ""
    adopted_words: str = ""
    adopted_on: date | None = None
    doc: DocReading | None = None
    acts: tuple[str, ...] = ()
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        doc = self.doc
        return {"word": self.word.value if self.word else None, "standing": self.standing,
                "adopted": {"version": self.adopted_version, "words": self.adopted_words, "adopted": _day(self.adopted_on)},
                "doc": ({"revision": doc.revision, "words": doc.words, "changedBetween": [d for d in doc.changed_between if d],
                         "pendingSuggestions": doc.pending, "suggestionNote": SUGGESTION_NOTE,
                         "laterAdoption": doc.later_adoption} if doc else None),
                "acts": list(self.acts), "actsBuilt": False, "note": self.note,
                "caveat": NO_ADOPTION_CAVEAT}


def compare(record: RuleRecord, day: date | None, doc: DocReading | None) -> Compare:
    """The working Doc's words against the version in force, with one of four words (docs/rule-records.md, section 4.1):
    **same**; **the record is behind** (an adoption on record covers the Doc's words); **the Doc ran ahead** (a proposed
    version on file has the Doc's words); **changed with no adoption found**. The adopted version is the rule in each; no
    act here makes the Doc's words the rule, and nothing merges the two."""
    i = version_index_on(record, day)
    ver = record.versions[i] if i is not None else None
    base = dict(adopted_version=version_id(record, i) if i is not None else "", adopted_words=(ver.words or ver.text) if ver else "",
                adopted_on=ver.adopted if ver else None, doc=doc)
    if doc is None:
        return Compare(None, "the Doc was not read", note="jason manual --classify and jason revisions read the Doc", **base)
    if not doc.in_doc:
        return Compare(None, "not in the Doc", note="the record has no section in the Doc's outline (a stored record, or a Doc section removed)", **base)
    proposal = next((v for v in record.versions if v.proposed and same_words(v.words or v.text, doc.words)), None)
    if ver is None:
        word = CompareWord.DOC_AHEAD if proposal else CompareWord.NO_ADOPTION
        return Compare(word, "no version in force", acts=_acts(word), note="no version of the rule is in force on this day", **base)
    if same_words(ver.words or ver.text, doc.words):
        return Compare(CompareWord.SAME, "compared", **base)
    if doc.later_adoption:
        word = CompareWord.RECORD_BEHIND
    elif proposal is not None:
        word = CompareWord.DOC_AHEAD
    else:
        word = CompareWord.NO_ADOPTION
    note = ("a pending suggestion is among the Doc's words; it is not accepted and is not a rule" if doc.suggested else "")
    return Compare(word, "compared", acts=_acts(word), note=note, **base)


def _acts(word: CompareWord) -> tuple[str, ...]:
    return {CompareWord.RECORD_BEHIND: ("record-adoption",), CompareWord.DOC_AHEAD: ("link-proposal",),
            CompareWord.NO_ADOPTION: ("take-as-proposal", "board-note")}.get(word, ())


# ---------------------------------------------------------------------------------------------------------------------
# Uses


@dataclass(frozen=True)
class Use:
    """Something the association did that rests on a rule, recorded where it lives; the record keeps this link only."""

    kind: str
    on: date | None
    outcome: str = ""
    ref: dict[str, Any] = field(default_factory=dict)
    by: str = ""


def uses_view(record: RuleRecord, uses: Iterable[Use], day: date | None = None) -> dict[str, Any]:
    """Each linked use with the version in force that day (never rewritten to the current one), counts by outcome, and
    whether the version of its day is the one in force now. A list, not a finding."""
    now = version_index_on(record, day)
    rows = []
    for u in sorted(uses, key=lambda u: (u.on is None, u.on or date.min)):
        i = version_index_on(record, u.on) if u.on else None
        rows.append({"kind": u.kind, "on": _day(u.on), "version": version_id(record, i) if i is not None else "",
                     "versionNote": ("" if i is not None else "no version of the rule is in force on that day"),
                     "isCurrent": (i == now) if i is not None else None, "outcome": u.outcome, "ref": u.ref, "by": u.by})
    counts = Counter(r["outcome"] or "no outcome recorded" for r in rows)
    return {"found": True, "id": record.id, "address": ADDRESS + record.id, "count": len(rows),
            "byOutcome": [{"outcome": k, "n": n} for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))],
            "uses": rows, "note": USE_NOTE if rows else NO_USE}


# ---------------------------------------------------------------------------------------------------------------------
# The views


def version_dict(record: RuleRecord, index: int | None, events: Iterable[AdoptionEvent] = ()) -> dict[str, Any] | None:
    if index is None:
        return None
    v = record.versions[index]
    return {"id": version_id(record, index), "words": v.words or v.text, "digest": _digest(v.words or v.text),
            "stage": version_stage(record, index, events), "adopted": _day(v.adopted), "adoptionOnRecord": v.adopted is not None,
            "effective": _day(v.effective), "expires": _day(v.expires), "boardItem": v.board_item, "decision": v.decision,
            "recordedBy": v.recorded_by, "recordedAt": v.recorded_at, "notice": list(v.notice), "supersedes": v.supersedes,
            "source": source_of(record, index, events).to_dict(), "note": v.note}


def citation(record: RuleRecord) -> str:
    return f"{ADDRESS}{record.id}"


def record_row(record: RuleRecord, day: date | None, events: Iterable[AdoptionEvent] = (), *,
               rows: Sequence[ra.SubjectRow] | None = None, authorities: Sequence[ra.RuleAuthority] = (),
               comparison: Compare | None = None, uses: int | None = None) -> dict[str, Any]:
    """One record, summary: for the list."""
    events = list(events)
    i = version_index_on(record, day)
    st = status_on(record, day, events)
    g = grounds_for(record, record.versions[i] if i is not None else None, rows, authorities)
    return {"id": record.id, "number": record.number, "title": record.title, "kind": record.kind, "subjects": list(g.subjects),
            "status": st.status.value if st.status else None, "statusWord": st.word, "adoptionOnRecord": st.adoption_on_record,
            "inForce": ({"version": version_id(record, i), "adopted": _day(record.versions[i].adopted),
                         "boardItem": record.versions[i].board_item} if i is not None else None),
            "grounds": {"standing": g.standing, "grants": [x["id"] for x in g.grants], "noGrantFound": g.no_grant_found},
            "openProposals": open_proposals(record), "uses": uses,
            "compare": comparison.word.value if comparison and comparison.word else (comparison.standing if comparison else None)}


def matches(row: dict[str, Any], status: str = "", subject: str = "") -> bool:
    if status:
        token = "adoption-not-on-record" if row["status"] == "adopted" and not row["adoptionOnRecord"] else None
        if status not in (row["status"], row["statusWord"], token):
            return False
    return not subject or subject in row["subjects"]


def record_view(record: RuleRecord, day: date | None, events: Iterable[AdoptionEvent] = (), *,
                rows: Sequence[ra.SubjectRow] | None = None, authorities: Sequence[ra.RuleAuthority] = (),
                comparison: Compare | None = None, uses: int | None = None) -> dict[str, Any]:
    """One rule on a day, as the console loader serves it: the version in force with its source, the status, the grounds,
    the comparison with the Doc, and the gaps. The words are the version's; every reading is labeled."""
    events = list(events)
    i = version_index_on(record, day)
    st = status_on(record, day, events)
    g = grounds_for(record, record.versions[i] if i is not None else None, rows, authorities)
    gaps = []
    if i is None:
        gaps.append(st.note or "no version of the rule is in force on this day")
    if st.status is Status.ADOPTED and not st.adoption_on_record:
        gaps.append("the adoption day is not on record: a person records it from the minutes")
    if g.no_grant_found:
        gaps.append(g.note)
    return {"found": True, "id": record.id, "address": citation(record), "asOf": _day(day), "number": record.number,
            "numberThen": record.number, "renumbered": False, "title": record.title, "kind": record.kind,
            "subjects": list(g.subjects), "subjectSource": g.subject_source,
            "confidentiality": record.confidentiality or "open", "status": st.to_dict(),
            "version": version_dict(record, i, events), "grounds": g.to_dict(), "reach": list(g.reach),
            "copies": list(record.copies), "notes": list(record.notes), "openProposals": open_proposals(record),
            "compare": comparison.to_dict() if comparison else None, "uses": {"count": uses}, "gaps": gaps,
            "reading": "The status, the subjects, the grounds and the comparison are jason's readings; the words are the stored words.",
            "caveats": [CAVEAT]}


def book_view(book: RuleBook, day: date | None, events: Iterable[AdoptionEvent] = (), *,
              rows: Sequence[ra.SubjectRow] | None = None, authorities: Sequence[ra.RuleAuthority] = (),
              comparisons: dict[str, Compare] | None = None, uses: dict[str, int] | None = None,
              status: str = "", subject: str = "") -> dict[str, Any]:
    """The records, filtered, with counts by status taken over the whole book (not the filter)."""
    events = list(events)
    comparisons = comparisons or {}
    out = [record_row(r, day, events, rows=rows, authorities=authorities, comparison=comparisons.get(r.id),
                      uses=(uses or {}).get(r.id) if uses is not None else None) for r in book.records]
    counts: Counter[str] = Counter()
    for r in out:
        counts[r["status"] or "no version in force"] += 1
    cmp_counts = Counter(c.word.value if c.word else c.standing for c in comparisons.values())
    summary = {"records": len(out), **{k: counts.get(k, 0) for k in (s.value for s in Status)},
               "noVersionInForce": counts.get("no version in force", 0),
               "adoptionNotOnRecord": sum(1 for r in out if r["status"] == "adopted" and not r["adoptionOnRecord"]),
               "noGrantFound": sum(1 for r in out if r["grounds"]["noGrantFound"]),
               "compare": dict(cmp_counts)}
    shown = [r for r in out if matches(r, status, subject)]
    return {"found": bool(book.records), "asOf": _day(day), "document": book.document, "source": book.source,
            "stored": book.source.startswith("stored"), "counts": summary, "records": shown,
            "grantsRead": rows is not None, "caveats": [CAVEAT]}


def recite(record: RuleRecord, day: date | None, events: Iterable[AdoptionEvent] = ()) -> list[str]:
    """The words first, with the version's citation, source and day; nothing of jason's reading in these lines."""
    events = list(events)
    i = version_index_on(record, day)
    head = f"{record.number or record.id}  {record.title}".strip()
    if i is None:
        return [head, f"  no version of the rule is in force on {day.isoformat() if day else 'this day'} "
                      "(the record does not show which words were in force)"]
    v = record.versions[i]
    src = source_of(record, i, events)
    when = f"adopted {v.adopted.isoformat()}" if v.adopted else "adoption day not on record"
    return [head, f"  {citation(record)} {version_id(record, i)}, {when}; words from: {src.kind}", "", f"  {(v.words or v.text).strip()}"]
