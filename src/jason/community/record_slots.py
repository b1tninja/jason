"""The association record checklist as records: slots, the pins and answers people make on them, and the state each slot
is in. Pure: nothing here reads disk, Drive, or a profile (``jason.tasks.record_slots`` assembles the slot list and loads
the records; docs/record-intake.md is the design).

A **slot** is one record an association must be able to put its hands on. It is a row in jason's code, written once for
any association: its key never names one, its ``requires`` is a citation only (the words are recited from the shelf where
a screen shows them), and its ``kinds`` say what a file in the slot is expected to classify as. A profile adds or hides
slots with ``SlotRule`` rows (``Community.record_slots()``, an empty default); a hidden slot is still listed, with the
reason, never absent.

A **pin** is a person's signed act naming a file for a slot; it records an intention and copies nothing. An **answer** is
a person's signed word that a slot has no record to pick: not applicable, none exists, or waiting on someone. Neither is
ever made by jason. The slot's **state** is computed from them and from what the library shows of the picked file; no
control sets it. Missing is an answer, never silent: ``empty`` is only a slot nobody has spoken for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

from jason.community.symbols import DocumentKind


class Cardinality(Enum):
    ONE = "one"
    SEVERAL = "several"      # a set that grows (amendments, annexations, policies): complete only when a person says so
    SERIES = "series"        # one for each year or period (minutes, budgets, statements)


class SlotSource(Enum):
    """Where a slot comes from."""

    RECORD_5200 = "civil code 5200"
    DELIVERY = "developer delivery"
    KEY_DOCUMENT = "key documents"
    ONBOARDING = "onboarding"
    PROGRAM = "program"
    KIND = "document kinds"
    PROFILE = "profile"


class SlotState(Enum):
    """The words a slot's state is told in. The value is what the console carries; ``word`` is what a person reads."""

    EMPTY = "empty"
    PICKED = "picked"
    UPLOADED = "uploaded"
    CLASSIFIED = "classified"
    READ = "read"
    CONFIRMED = "confirmed"
    NOT_APPLICABLE = "notApplicable"
    DOES_NOT_EXIST = "doesNotExist"
    HELD = "held"
    WAITING = "waiting"
    PROBLEM = "problem"

    @property
    def word(self) -> str:
        return STATE_WORDS[self]


STATE_WORDS: dict[SlotState, str] = {
    SlotState.EMPTY: "empty",
    SlotState.PICKED: "picked",
    SlotState.UPLOADED: "uploaded",
    SlotState.CLASSIFIED: "classified",
    SlotState.READ: "read",
    SlotState.CONFIRMED: "confirmed",
    SlotState.NOT_APPLICABLE: "not applicable",
    SlotState.DOES_NOT_EXIST: "does not exist",
    SlotState.HELD: "held",
    SlotState.WAITING: "waiting on someone else",
    SlotState.PROBLEM: "problem",
}

STATE_MEANING: dict[SlotState, str] = {
    SlotState.EMPTY: "nobody has spoken for this slot (not: the record does not exist)",
    SlotState.PICKED: "a person named a file; jason has not read it yet (not: the file is the right one)",
    SlotState.UPLOADED: "a person put a local file in; jason has not read it yet",
    SlotState.CLASSIFIED: "jason has a kind for the file (not: confirmed)",
    SlotState.READ: "jason's readers ran on the file (not: verified against the law)",
    SlotState.CONFIRMED: "a person confirmed the kind (not: adopted, or complete)",
    SlotState.NOT_APPLICABLE: "a person says it does not apply to this association (not: that the law does not require it)",
    SlotState.DOES_NOT_EXIST: "a person says the association holds none (not: that none was ever made)",
    SlotState.HELD: "the file is confidential: held back outside the private view (not: missing)",
    SlotState.WAITING: "a person says who has it (not: that a request was sent)",
    SlotState.PROBLEM: "the file cannot be found, or reads as another kind than the slot's",
}

# How far a picked file has come: a slot with several pins is as far along as its least advanced pin.
_PROGRESS = {SlotState.PICKED: 1, SlotState.UPLOADED: 1, SlotState.CLASSIFIED: 2, SlotState.READ: 3, SlotState.CONFIRMED: 4}


class AnswerKind(Enum):
    NOT_APPLICABLE = "notApplicable"
    NONE = "none"
    WAITING = "waiting"

    @property
    def state(self) -> SlotState:
        return _ANSWER_STATE[self]


_ANSWER_STATE = {AnswerKind.NOT_APPLICABLE: SlotState.NOT_APPLICABLE, AnswerKind.NONE: SlotState.DOES_NOT_EXIST,
                 AnswerKind.WAITING: SlotState.WAITING}


class PinKind(Enum):
    DRIVE = "drive"          # a Drive file, by id
    LIBRARY = "library"      # a file in jason's classified library, by its id
    FILE = "file"            # a file under data/ (a key-documents link or upload)
    FOLDER = "folder"        # a folder the specification pins as the holder (a code pin only)


class Origin(Enum):
    """Whose a pin is: the specification's (a profile's code) or a person's (``records.json``, the key-documents store)."""

    CODE = "specification"
    DATA = "person"


@dataclass(frozen=True)
class Slot:
    """One record on the checklist. ``requires`` names the law or document by citation only."""

    key: str
    title: str
    group: str
    requires: tuple[str, ...] = ()
    cardinality: Cardinality = Cardinality.ONE
    kinds: tuple[DocumentKind, ...] = ()
    confidential: bool = False
    after: tuple[str, ...] = ("classify",)       # the pipeline steps that apply to a file picked here (docs/record-intake.md)
    source: SlotSource = SlotSource.PROFILE
    why: str = ""                                 # a line on why jason's design needs it, where no citation names it
    existence: bool = True                        # whether "none exists" is a possible honest answer
    waits_on: tuple[str, ...] = ()                # slot keys this one is read after (the amendments wait on the declaration)
    gate: str = ""                                # the onboarding stage gate that waits on it, when one does
    key_document: str = ""                        # the key-documents row this slot is the face of; a pick there is its link
    record: str = ""                              # the Civil Code 5200 record it is, by value, when it is one
    delivery: str = ""                            # the 10 CCR 2792.23 delivery it is, by value, when it is one


@dataclass(frozen=True)
class SlotRule:
    """A profile's change to the list: add a slot the association needs, or hide one that cannot apply (with the reason).
    Hiding is shown ("hidden by the profile: reason"), never silent. A slot a statute names is hidden only with a reason."""

    key: str
    slot: Slot | None = None
    hide: bool = False
    reason: str = ""


def apply_rules(slots: Iterable[Slot], rules: Iterable[SlotRule]) -> tuple[tuple[Slot, ...], dict[str, str]]:
    """The slots with the profile's additions, and the reason for each hidden key. An added slot with a key already on the
    list is ignored (a profile cannot replace jason's slot), and a hide with no reason is ignored: it would be silent."""
    found = list(slots)
    keys = {s.key for s in found}
    hidden: dict[str, str] = {}
    for rule in rules or ():
        if rule.slot is not None and rule.slot.key not in keys:
            found.append(replace(rule.slot, source=SlotSource.PROFILE))
            keys.add(rule.slot.key)
        elif rule.hide and rule.key in keys and (rule.reason or "").strip():
            hidden[rule.key] = rule.reason.strip()
    return tuple(found), hidden


# Citations ----------------------------------------------------------------------------------------------------------------

_SECTION = r"\d[\d.]*(?:\([A-Za-z0-9]+\))*"
_CITATION = re.compile(r"\b(?P<code>CIV|BPC|CCP|GOV|CORP|RTC|BUS|10 CCR|CCR)\s+(?P<first>" + _SECTION + r")(?P<more>(?:\s*,\s*" + _SECTION + r")*)")


def citations_in(text: str) -> tuple[str, ...]:
    """The citations a line of existing prose prints, each as code and section ("CIV 4135, 4150" gives CIV 4135 and CIV 4150).
    Used on the onboarding and key-documents lines so a slot's ``requires`` is read from what jason already says."""
    found: list[str] = []
    for m in _CITATION.finditer(str(text or "")):
        found.append(f"{m.group('code')} {m.group('first')}")
        found.extend(f"{m.group('code')} {section}" for section in re.findall(_SECTION, m.group("more") or ""))
    return tuple(dict.fromkeys(found))


# A Drive link -------------------------------------------------------------------------------------------------------------

_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_DRIVE_HOSTS = ("drive.google.com", "docs.google.com", "drive.usercontent.google.com")
_PATH_ID = re.compile(r"/(?:file|document|spreadsheets|presentation|forms)/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,})")
_FOLDER = re.compile(r"/folders/([A-Za-z0-9_-]{10,})")


@dataclass(frozen=True)
class DriveRef:
    id: str
    folder: bool = False
    form: str = "id"          # which shape of link it came from: id, file, document, folder, open


def parse_drive_ref(text: str) -> DriveRef:
    """A Drive file or folder id from a pasted link or a bare id. ValueError, in a sentence, for anything else: a link
    that is not Drive's ("That is not a Drive link"), a link with no id, or text that is not an id. A link to a folder
    says so (a folder is a binding, not a pin)."""
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("give a Drive link or file id")
    if re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.IGNORECASE) or raw.lower().startswith(("www.", "drive.google", "docs.google")):
        url = urlparse(raw if "://" in raw else "https://" + raw)
        host = (url.hostname or "").lower()
        if host not in _DRIVE_HOSTS:
            raise ValueError("That is not a Drive link. Paste a link from drive.google.com or docs.google.com, or the file's id.")
        folder = _FOLDER.search(url.path)
        if folder:
            return DriveRef(folder.group(1), True, "folder")
        hit = _PATH_ID.search(url.path)
        if hit:
            return DriveRef(hit.group(1), False, "file" if "/file/" in url.path else "document")
        ident = (parse_qs(url.query).get("id") or [""])[0]
        if _ID.match(ident):
            return DriveRef(ident, False, "open")
        raise ValueError("That Drive link holds no file id. Open the file in Drive and copy its link (Share, Copy link).")
    if _ID.match(raw):
        return DriveRef(raw)
    raise ValueError("That is neither a Drive link nor a file id (an id is letters, digits, - and _, at least ten).")


# Pins and answers ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Pin:
    """A person's (or the specification's) naming of a file for a slot. ``id`` is stable; ``unpinned_by`` marks a pin
    taken off (who and when) - it is kept, never deleted, and the file stays where it is."""

    id: str
    slot: str
    kind: PinKind
    ref: str
    name: str = ""
    period: str = ""
    by: str = ""
    at: str = ""
    note: str = ""
    origin: Origin = Origin.DATA
    source: str = ""                 # where it comes from: "records.json", "key-documents", "specification"
    unpinned_by: str = ""
    unpinned_at: str = ""
    store_id: str = ""               # the id in the store that holds it, when that is not this pin's id (a key-documents link)
    kept_by: str = ""                # a person kept this pick although jason reads the file as another kind (who, when, why)
    kept_at: str = ""
    kept_reason: str = ""

    @property
    def active(self) -> bool:
        return not self.unpinned_by

    @property
    def kept(self) -> bool:
        return bool(self.kept_by)

    def same_file(self, other: "Pin") -> bool:
        return self.kind == other.kind and self.ref == other.ref


@dataclass(frozen=True)
class Answer:
    id: str
    slot: str
    kind: AnswerKind
    reason: str
    by: str
    at: str
    who: str = ""                    # for waiting: who has it
    source: str = "records.json"
    reopened_by: str = ""            # a person reopened the question; the answer stays in the trail and no longer counts
    reopened_at: str = ""

    @property
    def open(self) -> bool:
        """Whether the answer still stands (a reopened one is history)."""
        return not self.reopened_by


@dataclass(frozen=True)
class Reading:
    """What the library shows of a pinned file: found, its kind (None: jason could not tell), its level, and how far the
    readers got. A miss stays a miss: no kind is no kind."""

    found: bool = False
    name: str = ""
    kind: str | None = None
    confidential: bool = False
    read: bool = False
    confirmed_by: str = ""
    confirmed_at: str = ""
    library_id: str = ""
    method: str = ""


@dataclass(frozen=True)
class PinStatus:
    pin: Pin
    state: SlotState
    reading: Reading = field(default_factory=Reading)
    problem: str = ""
    wrong_slot: bool = False         # the file reads as a kind the slot does not expect
    reads_as: str = ""
    fits: tuple[str, ...] = ()       # slot keys whose kinds include what it reads as (set by the task)

    @property
    def held(self) -> bool:
        return self.reading.confidential


def pin_status(slot: Slot, pin: Pin, reading: Reading | None) -> PinStatus:
    """One pin's state: picked (or uploaded) until the library shows the file; classified with a kind; read once the
    readers ran; confirmed when a person chose the kind. A kind the slot does not expect is a problem, and says so."""
    seen = reading or Reading()
    start = SlotState.UPLOADED if pin.kind is PinKind.FILE and "/files/" in pin.ref else SlotState.PICKED
    if not seen.found or not seen.kind:
        return PinStatus(pin, start, seen)
    expected = {k.value for k in slot.kinds}
    if expected and seen.kind not in expected and not pin.kept:
        return PinStatus(pin, SlotState.PROBLEM, seen,
                         f"jason reads this as {seen.kind.replace('_', ' ')}; the slot expects "
                         + " or ".join(k.value.replace("_", " ") for k in slot.kinds),
                         wrong_slot=True, reads_as=seen.kind)
    state = SlotState.CLASSIFIED
    if seen.read:
        state = SlotState.READ
    if seen.confirmed_by:
        state = SlotState.CONFIRMED
    return PinStatus(pin, state, seen, reads_as=seen.kind)


def merge_holders(slot: Slot, code: Iterable[Pin], data: Iterable[Pin]) -> tuple[list[Pin], list[dict[str, Any]]]:
    """The active holders of a slot and its collisions. The specification's pins and a person's are one list when the slot
    holds several; the same file in both is one holder (the data pin adds who and when). On a ``ONE`` slot, two different
    files are a collision: neither wins, both are shown, and a person says which is current."""
    holders: list[Pin] = []
    for pin in [*code, *data]:
        if not pin.active:
            continue
        twin = next((i for i, held in enumerate(holders) if held.same_file(pin)), None)
        if twin is None:
            holders.append(pin)
        elif pin.origin is Origin.DATA and holders[twin].origin is Origin.CODE:
            holders[twin] = replace(pin, source=f"{pin.source} and the specification")
    collisions: list[dict[str, Any]] = []
    files = [h for h in holders if h.kind is not PinKind.FOLDER]
    # The specification may list several files for one record (a Doc and its PDF export): that is its own list, not a
    # collision. A person's pin collides when it is a different file from every one the specification names, or from
    # another person's pin.
    persons = [h for h in files if h.origin is Origin.DATA]
    agrees = [h for h in persons if "specification" in h.source]          # a pin that is also one the specification names
    coded = [h for h in files if h.origin is Origin.CODE]
    clash = len(persons) > 1 or (len(persons) == 1 and not agrees and bool(coded))
    if slot.cardinality is Cardinality.ONE and len(files) > 1 and clash:
        collisions.append({"slot": slot.key, "holders": [{"pin": h.id, "origin": h.origin.value, "source": h.source,
                                                          "kind": h.kind.value, "by": h.by, "at": h.at} for h in files],
                           "note": "Two holders for a slot that holds one. Neither wins; a person says which is current. "
                                   "A change to the specification is a patch for a person to apply."})
    elif slot.cardinality is Cardinality.SERIES:
        seen: dict[str, Pin] = {}
        for h in files:
            if h.period and h.period in seen and not h.same_file(seen[h.period]):
                collisions.append({"slot": slot.key, "period": h.period,
                                   "holders": [{"pin": p.id, "origin": p.origin.value, "source": p.source, "by": p.by, "at": p.at}
                                               for p in (seen[h.period], h)],
                                   "note": "Two files for one period. Neither wins; a person says which is current."})
            else:
                seen.setdefault(h.period, h)
    return holders, collisions


def latest_answer(answers: Iterable[Answer]) -> Answer | None:
    """The newest answer that still stands (by time, then by order given); a reopened answer is history."""
    out: Answer | None = None
    for a in answers:
        if not a.open:
            continue
        if out is None or a.at >= out.at:
            out = a
    return out


def slot_state(slot: Slot, statuses: Iterable[PinStatus], answer: Answer | None, *, holding: SlotState | None = None) -> SlotState:
    """The slot's state, computed: a problem on any pin first; else the least advanced pin; else (no pins) the newest
    answer; else what the specification's holder shows (``holding``: a folder pinned by a profile, files classified); else
    empty. A pin outranks an older answer: the answer stays in the history."""
    held = list(statuses)
    if any(s.state is SlotState.PROBLEM for s in held):
        return SlotState.PROBLEM
    if held:
        return min((s.state for s in held), key=lambda st: _PROGRESS.get(st, 0))
    if answer is not None:
        return answer.kind.state
    return holding or SlotState.EMPTY


def counts(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Counts over loader rows (dicts with ``state``, ``held``, ``hidden``), keyed as the console's data shape."""
    by_state: dict[str, int] = {s.value: 0 for s in SlotState if s is not SlotState.HELD}
    total = held = hidden = 0
    for row in rows:
        total += 1
        by_state[row["state"]] = by_state.get(row["state"], 0) + 1
        held += 1 if row.get("held") else 0
        hidden += 1 if row.get("hidden") else 0
    return {"total": total, "byState": by_state, "held": held, "hidden": hidden}


__all__ = [
    "Answer", "AnswerKind", "Cardinality", "DriveRef", "Origin", "Pin", "PinKind", "PinStatus", "Reading", "STATE_MEANING",
    "STATE_WORDS", "Slot", "SlotRule", "SlotSource", "SlotState", "apply_rules", "citations_in", "counts", "latest_answer",
    "merge_holders", "parse_drive_ref", "pin_status", "slot_state",
]
