"""The form library's records: tiers, jurisdictions, form definitions, and what a profile gives them.

A **definition** (``FormDefinition``) extends today's ``FormTemplate`` by composition: the template is the questions and
the words every renderer reads; the definition adds what makes it a form the law reaches (its tier, jurisdiction, version,
as-of day, the content the law requires, the sections it recites, its clocks, its handler). A profile does not write the
forms the law requires. It gives the library what is its own, as records:

- ``Slot``: a value a form's ``{SLOT}`` takes (the association's name, where answers are returned, a contact);
- ``Adjust`` and ``Add``: what a community may change (a stricter clock, a paragraph, a question its documents require);
- ``Bind``: a family form's provisions (the section that creates it, who decides, its clocks, what it must carry, what it
  may not ask);
- ``custom forms``: the community's own, each a ``FormDefinition`` of the ``CUSTOM`` tier.

Words become symbols here: a clock's kind of day, who set it, a channel, a tier are enums, and ``from_dict`` turns JSON's
words into them, so nothing stringly-typed reaches a caller (docs/form-library-design.md).

This module imports no profile and reads no disk.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Iterable, Mapping

from jason.community.forms import FormQuestion, FormTemplate, QuestionKind, ReadAs


class Tier(Enum):
    STATE = "state"        # the law writes the form: built in, fixed once for every community under that law
    FAMILY = "family"      # the documents create the request: a common structure with slots for their provisions
    CUSTOM = "custom"      # the community's own: a handler chosen when it is made


class SetBy(Enum):
    """Who set a clock."""
    STATUTE = "statute"
    DOCUMENTS = "documents"
    PROPOSED_POLICY = "proposed policy"


class DayKind(Enum):
    CALENDAR = "calendar"
    BUSINESS = "business"


class Channel(Enum):
    """The ways a form is made and returned (docs/form-templates.md, "Anatomy of a template")."""
    PAPER = "paper"
    FILLABLE_PDF = "fillable-pdf"
    EMAIL = "email"
    PAYHOA = "payhoa"
    PORTAL = "portal"
    GOOGLE_FORM = "google-form"


class Status(Enum):
    READY = "ready"
    ADJUSTED = "adjusted"
    NOT_OFFERED = "not offered"
    FAILING = "failing"


class Check(Enum):
    """The seven checks of the design, in its order; ``LIBRARY`` is the chain itself (an unknown jurisdiction, two forms
    with one key)."""
    LIBRARY = 0
    REQUIRED = 1
    RECITALS = 2
    SLOTS = 3
    ADJUSTMENTS = 4
    HANDLER = 5
    CODES = 6
    FORBIDDEN = 7

    @property
    def title(self) -> str:
        return {0: "the library", 1: "required content", 2: "recitals", 3: "slots", 4: "adjustments", 5: "handler and procedure",
                6: "marker codes", 7: "what a binding forbids"}[self.value]


class Severity(Enum):
    FAIL = "fail"                  # the form is wrong: ``jason form-library --check`` exits 1
    NOT_OFFERED = "not offered"    # the form is not made until the missing piece is given
    DEFERRED = "deferred"          # a known gap the definition names, to be closed by a later step


# What a required item may point at besides a question's field.
SIGNATURE, PREAMBLE, DESCRIPTION, ATTESTATION = "signature", "preamble", "description", "attestation"
CARRIERS = (SIGNATURE, PREAMBLE, DESCRIPTION, ATTESTATION)

_SLOT = re.compile(r"^[A-Z][A-Z0-9_]*$")
TOKEN = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")


@dataclass(frozen=True)
class Finding:
    """One problem (or note), naming the form and the item."""

    form: str
    check: Check
    severity: Severity
    item: str
    message: str

    def line(self) -> str:
        where = f"{self.form}: " if self.form else ""
        tag = self.check.title
        return f"[{tag}] {where}{self.item}: {self.message}" if self.item else f"[{tag}] {where}{self.message}"

    def as_dict(self) -> dict[str, Any]:
        return {"form": self.form, "check": self.check.title, "checkNumber": self.check.value, "severity": self.severity.value,
                "item": self.item, "message": self.message}


@dataclass(frozen=True)
class Jurisdiction:
    """A body of law with its forms: a key (``CA``) and the module that holds its definitions."""

    key: str
    pack: str
    title: str = ""


JURISDICTIONS: dict[str, Jurisdiction] = {
    "US": Jurisdiction("US", "jason.community.form_library.us", "federal law every state is under"),
    "CA": Jurisdiction("CA", "jason.community.form_library.ca", "the Davis-Stirling Act and the codes around it"),
}


def _enum(kind: type[Enum], word: Any) -> Any:
    if isinstance(word, kind):
        return word
    for member in kind:
        if str(word).strip().casefold() in (member.value.casefold() if isinstance(member.value, str) else "", member.name.casefold(),
                                            member.name.casefold().replace("_", "-")):
            return member
    raise ValueError(f"{word!r} is not a {kind.__name__}: {', '.join(m.value for m in kind)}")


def _tuple(value: Any) -> tuple:
    if value is None or value == "":
        return ()
    return (value,) if isinstance(value, str) or not hasattr(value, "__iter__") else tuple(value)


@dataclass(frozen=True)
class Required:
    """One thing the law says the form or the request must carry, and what carries it: a question's field, or the
    ``signature``, ``preamble``, ``description``, or ``attestation`` of the template. ``deferred`` is a known gap: the
    item is required, the form does not carry it yet, and the text says which step closes it (the check reports it and
    does not fail the form; an item with neither a carrier nor a deferral fails)."""

    item: str
    carried_by: tuple[str, ...] = ()
    authority: str = ""
    deferred: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "carried_by", _tuple(self.carried_by))

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> Required:
        return cls(str(row["item"]), _tuple(row.get("carried_by")), str(row.get("authority") or ""), str(row.get("deferred") or ""))


@dataclass(frozen=True)
class Clock:
    """A day the association runs a request on: counted from an event, a number of calendar or business days, and who set
    it. ``section`` is the statute subdivision or document section it rests on (required for a clock the documents
    set). ``note`` is where the resolver records that this clock replaced a longer one."""

    name: str
    counted_from: str
    number: int
    kind: DayKind
    set_by: SetBy
    section: str = ""
    if_passes: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _enum(DayKind, self.kind))
        object.__setattr__(self, "set_by", _enum(SetBy, self.set_by))

    def words(self) -> str:
        unit = "business days" if self.kind is DayKind.BUSINESS else "calendar days"
        source = self.set_by.value + (f": {self.section}" if self.section else "")
        return f"{self.name}: {self.number} {unit} from {self.counted_from} ({source})"

    def no_longer_than(self, other: Clock) -> bool:
        """Whether this clock can be shown to run no longer than ``other``: counted from the same event, and the same
        kind of day with no larger number, or calendar days in place of business days with no larger number (a calendar
        day is never longer than a business day). Anything else cannot be compared, so it is not accepted."""
        if self.counted_from.casefold() != other.counted_from.casefold():
            return False
        if self.kind is other.kind:
            return self.number <= other.number
        return self.kind is DayKind.CALENDAR and self.number <= other.number

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> Clock:
        return cls(str(row["name"]), str(row["counted_from"]), int(row["number"]), _enum(DayKind, row.get("kind", "calendar")),
                   _enum(SetBy, row.get("set_by", "proposed policy")), str(row.get("section") or ""),
                   str(row.get("if_passes") or ""), str(row.get("note") or ""))

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "countedFrom": self.counted_from, "number": self.number, "kind": self.kind.value,
                "setBy": self.set_by.value, "section": self.section, "ifPasses": self.if_passes, "note": self.note,
                "words": self.words()}


@dataclass(frozen=True)
class Slot:
    """A value for a form's ``{SLOT}``: ``ASSOCIATION``, ``RETURN_BY_MAIL``, ``RETURN_BY_EMAIL``, ``PORTAL``,
    ``BOARD_CONTACT``, ``FEE_SCHEDULE``, and the like. A slot with an empty value is a slot not given."""

    name: str
    value: str

    def __post_init__(self) -> None:
        if not _SLOT.match(self.name):
            raise ValueError(f"a slot's name is capital letters, digits, and underscores: {self.name!r}")

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> Slot:
        return cls(str(row["name"]), str(row.get("value") or ""))


@dataclass(frozen=True)
class Adjust:
    """What a community may change in a form the library gives it.

    May: add paragraphs to the preamble, make a clock stricter (a ``Clock`` of the same name, with its source section),
    add a clock the documents or the board's policy set, set the channels, and give the marker code to a form that has
    none. **Refused** (the resolver leaves the form as the library has it and records the refusal): ``remove`` or
    ``reword`` a question, ``drop_recitals``, lengthen a statutory clock, set a statutory clock, change a marker code."""

    form: str
    preamble: tuple[str, ...] = ()
    clocks: tuple[Clock, ...] = ()
    channels: tuple[Channel, ...] | None = None
    code: str = ""
    remove: tuple[str, ...] = ()                         # question fields: always refused
    reword: tuple[tuple[str, str], ...] = ()             # (field, new title): always refused
    drop_recitals: tuple[str, ...] = ()                  # always refused

    def __post_init__(self) -> None:
        object.__setattr__(self, "preamble", _tuple(self.preamble))
        object.__setattr__(self, "clocks", _tuple(self.clocks))
        object.__setattr__(self, "remove", _tuple(self.remove))
        object.__setattr__(self, "drop_recitals", _tuple(self.drop_recitals))
        object.__setattr__(self, "reword", tuple(dict(self.reword).items()) if isinstance(self.reword, Mapping) else tuple(self.reword))
        if self.channels is not None:
            object.__setattr__(self, "channels", tuple(_enum(Channel, c) for c in _tuple(self.channels)))

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> Adjust:
        channels = row.get("channels")
        return cls(str(row["form"]), _tuple(row.get("preamble")), tuple(Clock.from_dict(c) for c in row.get("clocks") or ()),
                   None if channels is None else tuple(_enum(Channel, c) for c in channels), str(row.get("code") or ""),
                   _tuple(row.get("remove")), tuple((row.get("reword") or {}).items()), _tuple(row.get("drop_recitals")))


@dataclass(frozen=True)
class Add:
    """A question a community's documents require on a library form, put after the question ``after`` (the field), or last.
    Refused when a binding forbids it, or its field is one the form already has."""

    form: str
    question: FormQuestion
    after: str = ""

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> Add:
        return cls(str(row["form"]), question_from_dict(row["question"]), str(row.get("after") or ""))


@dataclass(frozen=True)
class Bind:
    """A family form's provisions: the document ``section`` that creates it, who ``decider`` is, its ``clocks``, what the
    section requires on the form (``required``), and what it forbids asking (``forbidden``, question fields). A family form
    is offered only when its binding is complete: the section, the decider, and a clock for each name the definition lists
    in ``bindable``."""

    form: str
    section: str = ""
    decider: str = ""
    clocks: tuple[Clock, ...] = ()
    required: tuple[Required, ...] = ()
    forbidden: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "clocks", _tuple(self.clocks))
        object.__setattr__(self, "required", _tuple(self.required))
        object.__setattr__(self, "forbidden", _tuple(self.forbidden))

    def missing(self, bindable: Iterable[str]) -> tuple[str, ...]:
        """What a binding still has to give: ``section``, ``decider``, and ``clock NAME`` for each clock not bound."""
        gaps = [part for part, value in (("section", self.section), ("decider", self.decider)) if not value.strip()]
        have = {c.name for c in self.clocks}
        return tuple(gaps + [f"clock {name}" for name in bindable if name not in have])

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> Bind:
        return cls(str(row["form"]), str(row.get("section") or ""), str(row.get("decider") or ""),
                   tuple(Clock.from_dict(c) for c in row.get("clocks") or ()),
                   tuple(Required.from_dict(r) for r in row.get("required") or ()), _tuple(row.get("forbidden")))


def question_from_dict(row: Mapping[str, Any]) -> FormQuestion:
    """A ``FormQuestion`` from JSON: its kind and ``reads`` are words, turned into their symbols."""
    reads = row.get("reads")
    return FormQuestion(str(row["title"]), _enum(QuestionKind, row.get("kind", "short")), bool(row.get("required", True)),
                        tuple(row.get("options") or ()), str(row.get("help") or ""), str(row.get("key") or ""),
                        int(row.get("lines") or 0), str(row.get("prefill") or ""), str(row.get("authority") or ""),
                        str(row.get("section") or ""), None if not reads else _enum(ReadAs, reads), str(row.get("same_as") or ""))


@dataclass(frozen=True)
class FormDefinition:
    """One form the library holds. ``key`` is the library's name for it (``records-request``); the template's own key
    (``FormKey``) is what its returns, markers, and PayHOA records are known by."""

    template: FormTemplate
    tier: Tier = Tier.STATE
    key: str = ""
    jurisdiction: str = ""
    version: str = "1"
    as_of: date | None = None                       # the day of the law it recites
    authority: tuple[str, ...] = ()                 # the citations, canonical ("CIV 5205"): the process key
    required_content: tuple[Required, ...] = ()
    recitals: tuple[str, ...] = ()                  # what it opens by reciting: statutes ("CIV 5205(f)") or document sections ("ccrs#4.15")
    member_clock: str = ""                          # the sentence the member reads
    association_clocks: tuple[Clock, ...] = ()
    acknowledgment: str = ""                        # the receipt text, with {RECEIVED}, {DUE}, {DECIDER}, {REFERENCE}
    procedure: str = ""                             # the SOP key (jason sop)
    handler: str = ""                               # a key of ``handlers.HANDLERS``
    channels: tuple[Channel, ...] = ()
    slots: tuple[str, ...] = ()                     # the {SLOT}s the form uses
    bindable: tuple[str, ...] = ()                  # a family form: the clocks a binding must give, by name

    def __post_init__(self) -> None:
        if not self.key:
            object.__setattr__(self, "key", self.template.key.value)
        for name in ("authority", "required_content", "recitals", "association_clocks", "channels", "slots", "bindable"):
            object.__setattr__(self, name, _tuple(getattr(self, name)))
        for slot in self.slots:
            if not _SLOT.match(slot):
                raise ValueError(f"{self.key}: a slot's name is capital letters, digits, and underscores: {slot!r}")

    @property
    def id(self) -> str:
        return self.key

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "tier": self.tier.value, "jurisdiction": self.jurisdiction, "version": self.version,
                "asOf": self.as_of.isoformat() if self.as_of else "", "title": self.template.title,
                "formKey": self.template.key.value, "authority": list(self.authority), "recitals": list(self.recitals),
                "handler": self.handler, "procedure": self.procedure, "channels": [c.value for c in self.channels],
                "slots": list(self.slots)}


class Library:
    """The registry: each jurisdiction's definitions. ``LIBRARY`` is the library jason ships; a test may make its own."""

    def __init__(self, *, packs: bool = False) -> None:
        self._by: dict[str, dict[str, FormDefinition]] = {}
        self._packs = packs
        self._loaded: set[str] = set()

    def register(self, definition: FormDefinition) -> FormDefinition:
        rows = self._by.setdefault(definition.jurisdiction, {})
        held = rows.get(definition.key)
        if held is not None and held != definition:
            raise ValueError(f"the library already holds {definition.key!r} for {definition.jurisdiction!r}")
        rows[definition.key] = definition
        return definition

    def definitions(self, jurisdiction: str | Jurisdiction) -> tuple[FormDefinition, ...]:
        """The definitions registered for a jurisdiction, in the order its pack registered them. The shipped library
        imports the jurisdiction's pack first; an unknown jurisdiction has none."""
        key = jurisdiction.key if isinstance(jurisdiction, Jurisdiction) else str(jurisdiction)
        self.load(key)
        return tuple(self._by.get(key, {}).values())

    def load(self, key: str) -> bool:
        """Import a jurisdiction's pack (the shipped library only); False when there is no such pack."""
        if not self._packs:
            return key in self._by
        if key in self._loaded:
            return True
        jurisdiction = JURISDICTIONS.get(key)
        if jurisdiction is None:
            return False
        importlib.import_module(jurisdiction.pack)
        self._loaded.add(key)
        return True

    def known(self, key: str) -> bool:
        return key in self._by or (self._packs and key in JURISDICTIONS)


LIBRARY = Library(packs=True)


def register(definition: FormDefinition) -> FormDefinition:
    """Register a definition in the shipped library (a pack's modules call this when imported)."""
    return LIBRARY.register(definition)


def definitions(jurisdiction: str | Jurisdiction) -> tuple[FormDefinition, ...]:
    return LIBRARY.definitions(jurisdiction)


__all__ = ["ATTESTATION", "Add", "Adjust", "Bind", "CARRIERS", "Channel", "Check", "Clock", "DESCRIPTION", "DayKind",
           "Finding", "FormDefinition", "JURISDICTIONS", "Jurisdiction", "LIBRARY", "Library", "PREAMBLE", "Required",
           "SIGNATURE", "SetBy", "Severity", "Slot", "Status", "TOKEN", "Tier", "definitions", "question_from_dict", "register"]
