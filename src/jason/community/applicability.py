"""What a rule-like row applies to: facets as closed sets, a condition language, and a three-valued answer.

A provision applies only to some things: a standard to some systems, a contract term to one party and one kind of
work, a notice to some transactions, a version of a statute between two dates (docs/applicability.md, sections 1-4).
A row (an obligation, a deliverable rule, a statutory notice, a filing rule, a term's scope) carries an ``applies``
condition built here, and ``evaluate(condition, facts)`` answers it with one of three answers:

- ``Answer.APPLIES``;
- ``Answer.DOES_NOT_APPLY``, with the fact that decided it;
- ``Answer.UNDETERMINED``, with the missing fact named (or the facts whose sources disagree).

Undetermined is never read as "does not apply": a miss stays a miss, and it becomes a question for a person.

**Facts.** Each fact is a ``Fact`` key on one ``Facet`` with a closed type: an enum member (``SystemKind``,
``InstallationStandard``, ``DocumentKind``), an integer (cents, a unit count), a date, or a plain code that is data
(a license class, a county). A ``FactValue`` tags the value with its ``Source``: the document, the profile, the date,
or a person's answer. ``Facts`` merges them. Two sources that give one fact are each tested; when they give the same
answer the answer stands, and when they do not the test is undetermined with both values named. jason never picks one.

**Conditions.** Frozen, hashable records: ``Is``, ``In``, ``AtLeast``, ``Below``, ``InForce``, ``AllOf``, ``AnyOf``,
``Not``, ``Except`` (a condition with its exclusions spelled out), and ``ALWAYS``. Each has ``describe()`` in plain
words and ``as_dict()``; ``condition_from_dict`` reads the JSON form back, turning each word into its symbol.

**Combining.** Strong Kleene logic. ``AllOf`` is false when any part is false, true when every part is true, else
undetermined; ``AnyOf`` is its dual; ``Not`` swaps true and false and leaves undetermined alone. A known false part
decides ``AllOf`` even beside an undetermined one, because no answer to the missing fact could change it.

General code only: the facets name kinds, never one association's systems, vendors, or places. A profile states its
own facts through ``Community.applicability_facts()`` (empty by default). Pure: no network, no store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Union

from jason.community.symbols import DocumentKind


# --- Facets and their closed sets -------------------------------------------------------------------------------


class Facet(Enum):
    """The seven facets a condition can test (docs/applicability.md, section 1)."""

    DOCUMENT = "document"
    SUBJECT = "subject"
    PARTY = "party"
    PROPERTY = "property"
    PLACE = "place"
    TRANSACTION = "transaction"
    TIME = "time"


class _Word(Enum):
    """An enum whose value is the word a JSON row stores, with a label for plain-words descriptions."""

    @property
    def label(self) -> str:
        return _LABELS.get(self, self.value.replace("_", " "))


class SystemKind(_Word):
    """A kind of building system or element a provision can be about. General kinds only; a profile's own systems
    (which building, which riser) are its records, not members here."""

    FIRE_SPRINKLER = "fire_sprinkler"
    STANDPIPE = "standpipe"
    FIRE_PUMP = "fire_pump"
    PRIVATE_FIRE_SERVICE_MAIN = "private_fire_service_main"
    FIRE_ALARM = "fire_alarm"
    FIRE_EXTINGUISHER = "fire_extinguisher"
    BACKFLOW = "backflow"
    ROOF = "roof"
    ELEVATED_ELEMENT = "elevated_element"      # a balcony, deck, stairway, or walkway (Civil Code 5551)
    ELEVATOR = "elevator"


class InstallationStandard(_Word):
    """The standard a system was installed under. A sprinkler system's standard decides which rules reach it."""

    NFPA_13 = "nfpa_13"          # sprinkler systems, any occupancy
    NFPA_13R = "nfpa_13r"        # sprinkler systems in low-rise residential occupancies
    NFPA_13D = "nfpa_13d"        # sprinkler systems in one- and two-family dwellings and manufactured homes
    NFPA_14 = "nfpa_14"          # standpipe and hose systems
    NFPA_20 = "nfpa_20"          # stationary fire pumps
    NFPA_72 = "nfpa_72"          # fire alarm and signaling


class Work(_Word):
    """What a vendor does to a system."""

    INSPECT = "inspect"
    TEST = "test"
    MAINTAIN = "maintain"
    REPAIR = "repair"
    INSTALL = "install"
    DESIGN = "design"
    MONITOR = "monitor"


class PartyRole(_Word):
    """Who a party is, in the association's terms."""

    ASSOCIATION = "association"
    OWNER = "owner"
    TENANT = "tenant"
    VENDOR = "vendor"
    MANAGER = "manager"
    PUBLIC_AGENCY = "public_agency"


class CommonInterest(_Word):
    """The kind of common interest development (Civil Code 4100)."""

    CONDOMINIUM = "condominium"
    PLANNED_DEVELOPMENT = "planned_development"
    STOCK_COOPERATIVE = "stock_cooperative"
    COMMUNITY_APARTMENT = "community_apartment"


class OccupancyClass(_Word):
    """The building code's residential occupancy groups."""

    R_1 = "r_1"
    R_2 = "r_2"
    R_3 = "r_3"
    R_4 = "r_4"


class SigningPlace(_Word):
    """Where a contract was signed, which some consumer rules turn on."""

    BUYER_RESIDENCE = "buyer_residence"
    SELLER_PREMISES = "seller_premises"
    REMOTE = "remote"                      # by mail, email, or an electronic signature
    ELSEWHERE = "elsewhere"


_LABELS: dict[Enum, str] = {
    SystemKind.FIRE_SPRINKLER: "fire sprinkler system",
    SystemKind.STANDPIPE: "standpipe system",
    SystemKind.PRIVATE_FIRE_SERVICE_MAIN: "private fire service main",
    SystemKind.FIRE_ALARM: "fire alarm system",
    SystemKind.BACKFLOW: "backflow prevention assembly",
    SystemKind.ELEVATED_ELEMENT: "elevated element (a balcony, deck, stairway, or walkway)",
    InstallationStandard.NFPA_13: "NFPA 13",
    InstallationStandard.NFPA_13R: "NFPA 13R",
    InstallationStandard.NFPA_13D: "NFPA 13D",
    InstallationStandard.NFPA_14: "NFPA 14",
    InstallationStandard.NFPA_20: "NFPA 20",
    InstallationStandard.NFPA_72: "NFPA 72",
    Work.INSPECT: "inspection",
    Work.TEST: "testing",
    Work.MAINTAIN: "maintenance",
    Work.REPAIR: "repair",
    Work.INSTALL: "installation",
    Work.DESIGN: "design",
    Work.MONITOR: "monitoring",
    PartyRole.ASSOCIATION: "the association",
    PartyRole.OWNER: "an owner",
    PartyRole.TENANT: "a tenant",
    PartyRole.VENDOR: "a vendor",
    PartyRole.MANAGER: "a manager",
    PartyRole.PUBLIC_AGENCY: "a public agency",
    CommonInterest.COMMUNITY_APARTMENT: "community apartment project",
    OccupancyClass.R_1: "R-1",
    OccupancyClass.R_2: "R-2",
    OccupancyClass.R_3: "R-3",
    OccupancyClass.R_4: "R-4",
    SigningPlace.BUYER_RESIDENCE: "the buyer's residence",
    SigningPlace.SELLER_PREMISES: "the seller's place of business",
    SigningPlace.REMOTE: "remote (by mail or electronic signature)",
    SigningPlace.ELSEWHERE: "elsewhere",
}

# The water-based fire protection systems (the scope of NFPA 25 and of Title 19's chapter on them). A general group.
WATER_BASED_FIRE_PROTECTION: frozenset[SystemKind] = frozenset({
    SystemKind.FIRE_SPRINKLER, SystemKind.STANDPIPE, SystemKind.FIRE_PUMP, SystemKind.PRIVATE_FIRE_SERVICE_MAIN})


@dataclass(frozen=True)
class FactSpec:
    facet: Facet
    kind: type
    noun: str                    # "the system": how ``describe()`` names the fact
    many: bool = False           # a set of values (the vendor's work, its license classes)
    article: bool = False        # the label takes "a"/"an" after "is"


class Fact(Enum):
    """A fact key. Place facts are keys whose values are plain data (a county, a water purveyor), never members."""

    DOCUMENT_KIND = "document_kind"
    SYSTEM = "system"
    INSTALLATION_STANDARD = "installation_standard"
    VENDOR_WORK = "vendor_work"
    LICENSE_CLASS = "license_class"
    PARTY = "party"
    COMMON_INTEREST = "common_interest"
    OCCUPANCY_CLASS = "occupancy_class"
    UNIT_COUNT = "unit_count"
    STATE = "state"
    COUNTY = "county"
    CITY = "city"
    WATER_PURVEYOR = "water_purveyor"
    AMOUNT = "amount"            # integer cents
    SIGNED_AT = "signed_at"
    BUYER = "buyer"
    AS_OF = "as_of"              # the date the question is asked for: a document's date, or today

    @property
    def spec(self) -> FactSpec:
        return _SPECS[self]

    @property
    def facet(self) -> Facet:
        return self.spec.facet

    @property
    def noun(self) -> str:
        return self.spec.noun

    def check(self, value: Any) -> Any:
        """The value in its stored form (a many-valued fact as a frozenset), or TypeError when it is not this fact's
        type: a word where a symbol belongs is caught here, not matched as a miss later."""
        spec = self.spec
        if spec.many and isinstance(value, (set, frozenset, tuple, list)):
            return frozenset(self._one(v) for v in value)
        value = self._one(value)
        return frozenset({value}) if spec.many else value

    def _one(self, value: Any) -> Any:
        kind = self.spec.kind
        if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
            raise TypeError(f"{self.value}: expected {kind.__name__}, got {value!r}")
        return value

    def parse(self, word: Any) -> Any:
        """A JSON word (or list of words) turned into this fact's symbol(s)."""
        if self.spec.many and isinstance(word, list):
            return frozenset(self._parse_one(w) for w in word)
        return self._parse_one(word)

    def _parse_one(self, word: Any) -> Any:
        kind = self.spec.kind
        if issubclass(kind, Enum):
            return kind(word)
        if kind is date:
            return date.fromisoformat(word)
        return self._one(word)

    def format(self, value: Any) -> str:
        """A value in plain words."""
        if self is Fact.AMOUNT:
            return f"${value // 100:,}.{value % 100:02d}"
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, _Word):
            return value.label
        if isinstance(value, Enum):
            return str(value.value).replace("_", " ")
        return str(value)

    def word(self, value: Any) -> Any:
        """A value in its JSON form."""
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, date):
            return value.isoformat()
        return value


_SPECS: dict[Fact, FactSpec] = {
    Fact.DOCUMENT_KIND: FactSpec(Facet.DOCUMENT, DocumentKind, "the document", article=True),
    Fact.SYSTEM: FactSpec(Facet.SUBJECT, SystemKind, "the system", article=True),
    Fact.INSTALLATION_STANDARD: FactSpec(Facet.SUBJECT, InstallationStandard, "the installation standard"),
    Fact.VENDOR_WORK: FactSpec(Facet.PARTY, Work, "the vendor's kinds of work", many=True),
    Fact.LICENSE_CLASS: FactSpec(Facet.PARTY, str, "the vendor's license classes", many=True),
    Fact.PARTY: FactSpec(Facet.PARTY, PartyRole, "the parties", many=True),
    Fact.COMMON_INTEREST: FactSpec(Facet.PROPERTY, CommonInterest, "the development", article=True),
    Fact.OCCUPANCY_CLASS: FactSpec(Facet.PROPERTY, OccupancyClass, "the occupancy classification"),
    Fact.UNIT_COUNT: FactSpec(Facet.PROPERTY, int, "the number of units"),
    Fact.STATE: FactSpec(Facet.PLACE, str, "the state"),
    Fact.COUNTY: FactSpec(Facet.PLACE, str, "the county"),
    Fact.CITY: FactSpec(Facet.PLACE, str, "the city"),
    Fact.WATER_PURVEYOR: FactSpec(Facet.PLACE, str, "the water purveyor"),
    Fact.AMOUNT: FactSpec(Facet.TRANSACTION, int, "the amount"),
    Fact.SIGNED_AT: FactSpec(Facet.TRANSACTION, SigningPlace, "the place of signing"),
    Fact.BUYER: FactSpec(Facet.TRANSACTION, PartyRole, "the buyer"),
    Fact.AS_OF: FactSpec(Facet.TIME, date, "the date"),
}
assert set(_SPECS) == set(Fact)


def _article(label: str) -> str:
    return ("an " if label[:1].lower() in "aeiou" else "a ") + label


def _value_words(fact: Fact, value: Any) -> str:
    words = fact.format(value)
    return _article(words) if fact.spec.article else words


def _same(a: Any, b: Any) -> bool:
    """Equality, ignoring case for plain-data codes (a county, a license class)."""
    if isinstance(a, str) and isinstance(b, str):
        return a.casefold() == b.casefold()
    return a == b


# --- Sources and facts ------------------------------------------------------------------------------------------


class Source(Enum):
    """Where a fact came from."""

    DOCUMENT = "document"        # the classifier, the vendor directory, the license reader, the term readers
    PROFILE = "profile"          # a ``Community`` method
    TIME = "time"                # the date asked for
    ANSWER = "answer"            # a person's answer to the question an undetermined verdict raised


@dataclass(frozen=True)
class FactValue:
    """One fact, its value, and where it came from (``where``: the page, the method, the question's id)."""

    fact: Fact
    value: Any
    source: Source
    where: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", self.fact.check(self.value))

    def describe(self) -> str:
        if self.fact.spec.many:
            shown = ", ".join(sorted(self.fact.format(v) for v in self.value)) or "none"
        else:
            shown = self.fact.format(self.value)
        at = f", {self.where}" if self.where else ""
        return f"{self.fact.noun}: {shown} ({self.source.value}{at})"

    def as_dict(self) -> dict[str, Any]:
        value = sorted(self.fact.word(v) for v in self.value) if self.fact.spec.many else self.fact.word(self.value)
        return {"fact": self.fact.value, "value": value, "source": self.source.value, "where": self.where}


@dataclass(frozen=True)
class Facts:
    """The facts a question is answered from, each tagged with its source. A fact may come from more than one source."""

    values: tuple[FactValue, ...] = ()

    def of(self, fact: Fact) -> tuple[FactValue, ...]:
        return tuple(v for v in self.values if v.fact is fact)

    def __contains__(self, fact: Fact) -> bool:
        return any(v.fact is fact for v in self.values)

    def merge(self, *others: Union["Facts", Iterable[FactValue]]) -> "Facts":
        out = list(self.values)
        for other in others:
            for value in (other.values if isinstance(other, Facts) else other):
                if value not in out:
                    out.append(value)
        return Facts(tuple(out))

    @classmethod
    def build(cls, *, document: Mapping[Fact, Any] | None = None, profile: Mapping[Fact, Any] | Iterable[FactValue] = (),
              as_of: date | None = None, document_where: str = "", profile_where: str = "") -> "Facts":
        """Facts from the document (a mapping read from it), the profile (a mapping, or ``FactValue`` rows such as
        ``profile_facts(community)``), and the date asked for."""
        out: list[FactValue] = []
        for fact, value in (document or {}).items():
            out.append(FactValue(fact, value, Source.DOCUMENT, document_where))
        if isinstance(profile, Mapping):
            out.extend(FactValue(fact, value, Source.PROFILE, profile_where) for fact, value in profile.items())
        else:
            out.extend(profile)
        if as_of is not None:
            out.append(FactValue(Fact.AS_OF, as_of, Source.TIME))
        return Facts(()).merge(out)

    def describe(self) -> str:
        return "\n".join(v.describe() for v in self.values)


def profile_facts(community: Any) -> tuple[FactValue, ...]:
    """The profile's facts: ``Community.applicability_facts()``, with the state and county read from
    ``Community.region`` ("<state>/<county>") where the profile does not give them. Empty for a profile that sets
    neither, so every condition on them is undetermined, not a crash."""
    given = tuple(community.applicability_facts() or ())
    named = {v.fact for v in given}
    region = community.region                    # a property on ``Community``; a stand-in may give a method
    region = ((region() if callable(region) else region) or "").strip("/")
    derived: list[FactValue] = []
    if region:
        state, _, county = region.partition("/")
        if state and Fact.STATE not in named:
            derived.append(FactValue(Fact.STATE, state, Source.PROFILE, "Community.region"))
        if county and Fact.COUNTY not in named:
            derived.append(FactValue(Fact.COUNTY, county, Source.PROFILE, "Community.region"))
    return given + tuple(derived)


# --- Answers ----------------------------------------------------------------------------------------------------


class Answer(Enum):
    APPLIES = "applies"
    DOES_NOT_APPLY = "does not apply"
    UNDETERMINED = "undetermined"


def _dedupe(items: Iterable[Any]) -> tuple[Any, ...]:
    out: list[Any] = []
    for item in items:
        if item not in out:
            out.append(item)
    return tuple(out)


@dataclass(frozen=True)
class Verdict:
    """An answer and why: the condition asked, the facts that decided it (with their sources), the facts missing,
    and the facts whose sources disagree. ``deciding`` on an undetermined verdict holds the facts known so far."""

    answer: Answer
    condition: "Condition"
    deciding: tuple[FactValue, ...] = ()
    missing: tuple[Fact, ...] = ()
    conflicting: tuple[FactValue, ...] = ()

    @property
    def applies(self) -> bool:
        return self.answer is Answer.APPLIES

    @property
    def undetermined(self) -> bool:
        return self.answer is Answer.UNDETERMINED

    def question(self) -> str:
        """What a person must settle for an undetermined verdict; empty otherwise."""
        if not self.undetermined:
            return ""
        parts = []
        if self.missing:
            parts.append("unknown: " + "; ".join(f.noun for f in self.missing))
        if self.conflicting:
            parts.append("sources disagree: " + "; ".join(v.describe() for v in self.conflicting))
        return " | ".join(parts)

    def explain(self) -> str:
        lines = [f"{self.answer.value}: {self.condition.describe()}"]
        lines += [f"  decided by {v.describe()}" for v in self.deciding] if not self.undetermined else \
                 [f"  known: {v.describe()}" for v in self.deciding]
        lines += [f"  missing: {f.noun}" for f in self.missing]
        lines += [f"  disagree: {v.describe()}" for v in self.conflicting]
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {"answer": self.answer.value, "condition": self.condition.as_dict(),
                "describe": self.condition.describe(), "deciding": [v.as_dict() for v in self.deciding],
                "missing": [f.value for f in self.missing], "conflicting": [v.as_dict() for v in self.conflicting]}


# --- Conditions -------------------------------------------------------------------------------------------------


class _Leaf:
    """A test of one fact against each value the facts hold for it."""

    fact: Fact

    def test(self, value: Any) -> bool:  # pragma: no cover - each leaf defines it
        raise NotImplementedError

    def _evaluate(self, facts: Facts) -> Verdict:
        values = facts.of(self.fact)
        if not values:
            return Verdict(Answer.UNDETERMINED, self, missing=(self.fact,))
        results = {self.test(v.value) for v in values}
        if len(results) > 1:
            return Verdict(Answer.UNDETERMINED, self, conflicting=values)
        return Verdict(Answer.APPLIES if results.pop() else Answer.DOES_NOT_APPLY, self, deciding=values)


@dataclass(frozen=True)
class Is(_Leaf):
    """The fact is this value; for a many-valued fact, the set includes it."""

    fact: Fact
    value: Any

    def __post_init__(self) -> None:
        self.fact._one(self.value)

    def test(self, value: Any) -> bool:
        if self.fact.spec.many:
            return any(_same(self.value, v) for v in value)
        return _same(self.value, value)

    def describe(self) -> str:
        verb = "include" if self.fact.spec.many else "is"
        return f"{self.fact.noun} {verb} {_value_words(self.fact, self.value)}"

    def negated(self) -> str:
        verb = "do not include" if self.fact.spec.many else "is not"
        return f"{self.fact.noun} {verb} {_value_words(self.fact, self.value)}"

    def as_dict(self) -> dict[str, Any]:
        return {"is": [self.fact.value, self.fact.word(self.value)]}


@dataclass(frozen=True)
class In(_Leaf):
    """The fact is one of these values (for a many-valued fact, the sets share one). ``label`` names the group in
    plain words ("a water-based fire protection system")."""

    fact: Fact
    values: frozenset
    label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", frozenset(self.values))
        if not self.values:
            raise ValueError("In needs at least one value")
        for v in self.values:
            self.fact._one(v)

    def test(self, value: Any) -> bool:
        if self.fact.spec.many:
            return any(_same(a, b) for a in self.values for b in value)
        return any(_same(a, value) for a in self.values)

    def _group(self) -> str:
        if self.label:
            return self.label
        return "one of: " + ", ".join(sorted(self.fact.format(v) for v in self.values))

    def describe(self) -> str:
        verb = "include" if self.fact.spec.many else "is"
        return f"{self.fact.noun} {verb} {self._group()}"

    def negated(self) -> str:
        verb = "include none of" if self.fact.spec.many else "is not"
        group = self._group().removeprefix("one of: ") if self.fact.spec.many else self._group()
        return f"{self.fact.noun} {verb} {group}"

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"in": [self.fact.value, sorted(self.fact.word(v) for v in self.values)]}
        if self.label:
            out["label"] = self.label
        return out


@dataclass(frozen=True)
class AtLeast(_Leaf):
    """A number fact (an amount in cents, a unit count) is at least this."""

    fact: Fact
    value: int

    def __post_init__(self) -> None:
        if self.fact.spec.kind is not int:
            raise TypeError(f"{self.fact.value} is not a number fact")
        self.fact._one(self.value)

    def test(self, value: Any) -> bool:
        return value >= self.value

    def describe(self) -> str:
        return f"{self.fact.noun} is at least {self.fact.format(self.value)}"

    def negated(self) -> str:
        return f"{self.fact.noun} is less than {self.fact.format(self.value)}"

    def as_dict(self) -> dict[str, Any]:
        return {"at_least": [self.fact.value, self.value]}


@dataclass(frozen=True)
class Below(_Leaf):
    """A number fact is less than this."""

    fact: Fact
    value: int

    def __post_init__(self) -> None:
        if self.fact.spec.kind is not int:
            raise TypeError(f"{self.fact.value} is not a number fact")
        self.fact._one(self.value)

    def test(self, value: Any) -> bool:
        return value < self.value

    def describe(self) -> str:
        return f"{self.fact.noun} is less than {self.fact.format(self.value)}"

    def negated(self) -> str:
        return f"{self.fact.noun} is at least {self.fact.format(self.value)}"

    def as_dict(self) -> dict[str, Any]:
        return {"below": [self.fact.value, self.value]}


@dataclass(frozen=True)
class InForce(_Leaf):
    """The date asked for falls on or after ``start`` and before ``end`` (either open). The same reading as
    ``statutory_terms.in_force``: a ``Prior`` holds before its ``until`` day, the current value from it on."""

    start: date | None = None
    end: date | None = None
    label: str = ""              # "under the law before AB 130"
    fact: Fact = field(default=Fact.AS_OF, init=False)

    def __post_init__(self) -> None:
        if self.start is None and self.end is None:
            raise ValueError("InForce needs a start or an end; a row in force always needs no condition")
        if self.start and self.end and self.end <= self.start:
            raise ValueError("InForce: end must come after start")

    @classmethod
    def before(cls, prior: Any, label: str = "") -> "InForce":
        """In force while the prior value held: before ``prior.until``."""
        statute = getattr(prior, "statute", "")
        return cls(None, prior.until, label or (f"until {statute}" if statute else ""))

    @classmethod
    def since(cls, prior: Any, label: str = "") -> "InForce":
        """In force from the day ``prior`` ended."""
        statute = getattr(prior, "statute", "")
        return cls(prior.until, None, label or (f"since {statute}" if statute else ""))

    def test(self, value: Any) -> bool:
        return (self.start is None or self.start <= value) and (self.end is None or value < self.end)

    def _span(self) -> str:
        if self.start and self.end:
            return f"on or after {self.start.isoformat()} and before {self.end.isoformat()}"
        if self.start:
            return f"on or after {self.start.isoformat()}"
        return f"before {self.end.isoformat()}"

    def describe(self) -> str:
        note = f" ({self.label})" if self.label else ""
        return f"the date is {self._span()}{note}"

    def negated(self) -> str:
        note = f" ({self.label})" if self.label else ""
        return f"the date is not {self._span()}{note}"

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"in_force": [self.start.isoformat() if self.start else None,
                                            self.end.isoformat() if self.end else None]}
        if self.label:
            out["label"] = self.label
        return out


@dataclass(frozen=True)
class _Always:
    """No condition: the row applies to everything it is asked about."""

    def _evaluate(self, facts: Facts) -> Verdict:
        return Verdict(Answer.APPLIES, self)

    def describe(self) -> str:
        return "always"

    def negated(self) -> str:
        return "never"

    def as_dict(self) -> dict[str, Any]:
        return {"always": True}


ALWAYS = _Always()


def _kleene_and(parts: tuple[Verdict, ...], condition: Any) -> Verdict:
    false = [p for p in parts if p.answer is Answer.DOES_NOT_APPLY]
    if false:
        return Verdict(Answer.DOES_NOT_APPLY, condition, deciding=_dedupe(v for p in false for v in p.deciding))
    if all(p.answer is Answer.APPLIES for p in parts):
        return Verdict(Answer.APPLIES, condition, deciding=_dedupe(v for p in parts for v in p.deciding))
    return Verdict(Answer.UNDETERMINED, condition,
                   deciding=_dedupe(v for p in parts if p.answer is Answer.APPLIES for v in p.deciding),
                   missing=_dedupe(f for p in parts for f in p.missing),
                   conflicting=_dedupe(v for p in parts for v in p.conflicting))


def _kleene_or(parts: tuple[Verdict, ...], condition: Any) -> Verdict:
    true = [p for p in parts if p.answer is Answer.APPLIES]
    if true:
        return Verdict(Answer.APPLIES, condition, deciding=_dedupe(v for p in true for v in p.deciding))
    if all(p.answer is Answer.DOES_NOT_APPLY for p in parts):
        return Verdict(Answer.DOES_NOT_APPLY, condition, deciding=_dedupe(v for p in parts for v in p.deciding))
    return Verdict(Answer.UNDETERMINED, condition,
                   deciding=_dedupe(v for p in parts if p.answer is Answer.DOES_NOT_APPLY for v in p.deciding),
                   missing=_dedupe(f for p in parts for f in p.missing),
                   conflicting=_dedupe(v for p in parts for v in p.conflicting))


_FLIP = {Answer.APPLIES: Answer.DOES_NOT_APPLY, Answer.DOES_NOT_APPLY: Answer.APPLIES,
         Answer.UNDETERMINED: Answer.UNDETERMINED}


@dataclass(frozen=True)
class AllOf:
    """Every part holds (Kleene and)."""

    parts: tuple

    def __init__(self, *parts: "Condition") -> None:
        if not parts:
            raise ValueError("AllOf needs at least one part")
        object.__setattr__(self, "parts", tuple(parts))

    def _evaluate(self, facts: Facts) -> Verdict:
        return _kleene_and(tuple(p._evaluate(facts) for p in self.parts), self)

    def describe(self) -> str:
        return " and ".join(_grouped(p) for p in self.parts)

    def negated(self) -> str:
        return "not (" + self.describe() + ")"

    def as_dict(self) -> dict[str, Any]:
        return {"all": [p.as_dict() for p in self.parts]}


@dataclass(frozen=True)
class AnyOf:
    """At least one part holds (Kleene or)."""

    parts: tuple

    def __init__(self, *parts: "Condition") -> None:
        if not parts:
            raise ValueError("AnyOf needs at least one part")
        object.__setattr__(self, "parts", tuple(parts))

    def _evaluate(self, facts: Facts) -> Verdict:
        return _kleene_or(tuple(p._evaluate(facts) for p in self.parts), self)

    def describe(self) -> str:
        return " or ".join(_grouped(p) for p in self.parts)

    def negated(self) -> str:
        return "neither " + " nor ".join(_grouped(p) for p in self.parts) if len(self.parts) > 1 \
            else self.parts[0].negated()

    def as_dict(self) -> dict[str, Any]:
        return {"any": [p.as_dict() for p in self.parts]}


@dataclass(frozen=True)
class Not:
    """The part does not hold. Undetermined stays undetermined."""

    part: "Condition"

    def _evaluate(self, facts: Facts) -> Verdict:
        inner = self.part._evaluate(facts)
        return Verdict(_FLIP[inner.answer], self, inner.deciding, inner.missing, inner.conflicting)

    def describe(self) -> str:
        return self.part.negated()

    def negated(self) -> str:
        return self.part.describe()

    def as_dict(self) -> dict[str, Any]:
        return {"not": self.part.as_dict()}


@dataclass(frozen=True)
class Except:
    """``base``, except where any of ``unless`` holds: the provision's own exclusions, spelled out. The same answer as
    ``AllOf(base, Not(AnyOf(*unless)))``, kept apart so the row reads as the text does."""

    base: "Condition"
    unless: tuple

    def __init__(self, base: "Condition", *unless: "Condition") -> None:
        if not unless:
            raise ValueError("Except needs at least one exclusion")
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "unless", tuple(unless))

    def _evaluate(self, facts: Facts) -> Verdict:
        inner = AllOf(self.base, Not(AnyOf(*self.unless)))._evaluate(facts)
        return Verdict(inner.answer, self, inner.deciding, inner.missing, inner.conflicting)

    def describe(self) -> str:
        return f"{self.base.describe()}, except where " + " or ".join(_grouped(u) for u in self.unless)

    def negated(self) -> str:
        return "not (" + self.describe() + ")"

    def as_dict(self) -> dict[str, Any]:
        return {"except": self.base.as_dict(), "unless": [u.as_dict() for u in self.unless]}


Condition = Union[Is, In, AtLeast, Below, InForce, AllOf, AnyOf, Not, Except, _Always]


def _grouped(condition: Condition) -> str:
    text = condition.describe()
    return f"({text})" if isinstance(condition, (AllOf, AnyOf, Except)) and len(getattr(condition, "parts", (1, 2))) > 1 \
        else text


def evaluate(condition: Condition, facts: Facts) -> Verdict:
    """Whether ``condition`` holds for ``facts``: applies, does not apply (with the facts that decided it), or
    undetermined (with the missing facts, or the facts whose sources disagree)."""
    return condition._evaluate(facts)


def facts_tested(condition: Condition) -> frozenset[Fact]:
    """Every fact a condition tests, anywhere in it. Empty for ``ALWAYS``. A caller uses it to tell what a row must be
    asked about: a row that tests a subject fact is asked of each system, one that tests none of the association."""
    if isinstance(condition, _Leaf):
        return frozenset({condition.fact})
    if isinstance(condition, (AllOf, AnyOf)):
        return frozenset().union(*(facts_tested(p) for p in condition.parts))
    if isinstance(condition, Not):
        return facts_tested(condition.part)
    if isinstance(condition, Except):
        return facts_tested(condition.base).union(*(facts_tested(u) for u in condition.unless))
    return frozenset()


@dataclass(frozen=True)
class Partition:
    """Rows sorted by their verdicts. The undetermined rows are kept, each with the question that settles it."""

    applies: tuple[tuple[Any, Verdict], ...] = ()
    does_not_apply: tuple[tuple[Any, Verdict], ...] = ()
    undetermined: tuple[tuple[Any, Verdict], ...] = ()


def partition(rows: Iterable[Any], facts: Facts,
              condition_of: Callable[[Any], Condition | None] = lambda row: getattr(row, "applies", None)) -> Partition:
    """Each row's verdict, in the rows' order. A row with no condition applies (``ALWAYS``)."""
    groups: dict[Answer, list[tuple[Any, Verdict]]] = {a: [] for a in Answer}
    for row in rows:
        verdict = evaluate(condition_of(row) or ALWAYS, facts)
        groups[verdict.answer].append((row, verdict))
    return Partition(tuple(groups[Answer.APPLIES]), tuple(groups[Answer.DOES_NOT_APPLY]),
                     tuple(groups[Answer.UNDETERMINED]))


# --- The JSON form ----------------------------------------------------------------------------------------------


def condition_from_dict(data: Mapping[str, Any]) -> Condition:
    """A condition from its ``as_dict()`` form: each word becomes its symbol, and an unknown word is an error."""
    if "always" in data:
        return ALWAYS
    if "is" in data:
        fact = Fact(data["is"][0])
        return Is(fact, fact._parse_one(data["is"][1]))
    if "in" in data:
        fact = Fact(data["in"][0])
        return In(fact, frozenset(fact._parse_one(w) for w in data["in"][1]), data.get("label", ""))
    if "at_least" in data:
        return AtLeast(Fact(data["at_least"][0]), data["at_least"][1])
    if "below" in data:
        return Below(Fact(data["below"][0]), data["below"][1])
    if "in_force" in data:
        start, end = (date.fromisoformat(d) if d else None for d in data["in_force"])
        return InForce(start, end, data.get("label", ""))
    if "all" in data:
        return AllOf(*(condition_from_dict(p) for p in data["all"]))
    if "any" in data:
        return AnyOf(*(condition_from_dict(p) for p in data["any"]))
    if "not" in data:
        return Not(condition_from_dict(data["not"]))
    if "except" in data:
        return Except(condition_from_dict(data["except"]), *(condition_from_dict(u) for u in data["unless"]))
    raise ValueError(f"not a condition: {data!r}")


__all__ = [
    "Facet", "SystemKind", "InstallationStandard", "Work", "PartyRole", "CommonInterest", "OccupancyClass",
    "SigningPlace", "WATER_BASED_FIRE_PROTECTION", "FactSpec", "Fact", "Source", "FactValue", "Facts",
    "profile_facts", "Answer", "Verdict", "Is", "In", "AtLeast", "Below", "InForce", "ALWAYS", "AllOf", "AnyOf",
    "Not", "Except", "Condition", "evaluate", "facts_tested", "Partition", "partition", "condition_from_dict",
]
