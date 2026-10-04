"""County-neutral instrument bundles from Placer: what an instrument graph reads for a parcel or a subdivision.

A bundle carries only shared shapes, so a reader built from Sacramento
takes it as it is:

* ``instruments``: every ``FiledInstrument`` the bundle touched (asspy's
  record; ``kind`` the walk kind, ``filing_code`` the shared class code from
  Placer's type name), in number order.
* ``histories``: ``OwnershipHistory`` chains (``Conveyance`` steps with their
  priors), one per parcel or lot.
* ``readings``: the process reading of each chain step (``ProcessStep``:
  process, complete, reassesses, the seats it filled, the same-day
  instruments of its closing).
* ``formations``: instruments recorded together that a reader should see as
  one event. A ``closing`` is a builder's or owner's sale with its seats (the
  notice of completion, the grant, the buyer's deed of trust, a companion
  vesting, a partial reconveyance). A ``community`` is a governing instrument
  with the same-day neighbors that form or change the community beside it
  (declaration, annexation, condominium plan, bylaws, map, the deed of the
  common area to the association), joined by a shared business party or an
  association's name.
* ``liens``: each owner's lien lifecycles by tenure (``ParcelLien``), for a
  parcel bundle.

``as_dict`` is the JSON form docs/placer.md documents. A formation is a
reading of numbers and names, a lead for a person, not a pin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from asspy.core import FiledInstrument
from asspy.filings import Family, instrument_class
from asspy.placer.filings import GOVERNING_TYPES, type_ids
from jason.community.base import Developer
from jason.community.placer.descent import PlacerDescent, _association
from jason.community.placer.index import PlacerIndex
from jason.community.placer.parcel import PlacerParcelRecord
from jason.community.placer.processes import ProcessStep, read_chain
from jason.community.recorder import OwnershipHistory, same_party

__all__ = (
    "Formation",
    "InstrumentBundle",
    "Member",
    "closing_formation",
    "community_formations",
    "governing_instruments",
    "parcel_bundle",
    "subdivision_bundle",
)

# Numbers on either side of a governing instrument read for the rest of its community's formation.
REACH = 4

_ROLES = {
    "162": "declaration", "324": "declaration", "320": "annexation", "220": "amendment", "225": "amendment",
    "499": "amendment", "604": "termination", "301": "condominium plan", "240": "condominium plan amendment",
    "494": "bylaws", "446": "articles", "476": "resolution", "435": "subdivision map", "433": "parcel map",
    "285": "map correction", "460": "lot line adjustment", "307": "plans and specifications", "306": "notice of completion",
    "188": "covenant and agreement", "478": "restrictive covenant",
}
_FORMING = (Family.GOVERNING, Family.PLAN, Family.MAP)


@dataclass(frozen=True)
class Member:
    """One instrument of a formation, the seat it takes, and why it was joined."""

    role: str
    instrument: FiledInstrument
    why: str = ""


@dataclass(frozen=True)
class Formation:
    """Instruments recorded together as one event: a ``closing`` or a ``community`` formation."""

    kind: str
    anchor: FiledInstrument
    members: tuple[Member, ...]

    @property
    def numbers(self) -> tuple[str, ...]:
        return (self.anchor.number, *(item.instrument.number for item in self.members))


@dataclass(frozen=True)
class InstrumentBundle:
    """A parcel's or a subdivision's instruments, chains, readings, and formations, in shared shapes."""

    county: str
    scope: str
    label: str
    instruments: tuple[FiledInstrument, ...]
    histories: tuple[OwnershipHistory, ...]
    readings: tuple[ProcessStep, ...]
    formations: tuple[Formation, ...]
    liens: tuple = ()
    parcels: tuple[tuple[str, str], ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    def instrument(self, number: str) -> FiledInstrument | None:
        return next((item for item in self.instruments if item.number == number), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "county": self.county,
            "scope": self.scope,
            "label": self.label,
            "instruments": [_instrument(item) for item in self.instruments],
            "histories": [_history(item) for item in self.histories],
            "readings": [_reading(item) for item in self.readings],
            "formations": [
                {
                    "kind": item.kind,
                    "anchor": item.anchor.number,
                    "recorded": _day(item.anchor.recorded),
                    "members": [{"role": member.role, "number": member.instrument.number, "why": member.why} for member in item.members],
                }
                for item in self.formations
            ],
            "liens": [_lien(item) for item in self.liens],
            "parcels": [{"apn": apn, "newest": number} for apn, number in self.parcels],
            "notes": list(self.notes),
        }


def closing_formation(step: ProcessStep, load) -> Formation | None:
    """A chain step's closing: the seats its reading filled and the same-day instruments that name its parties."""
    anchor = load(step.number)
    if anchor is None:
        return None
    members: list[Member] = []
    seen = {anchor.number}
    for slot in step.reading.slots if step.reading is not None else ():
        if slot.reason != "present" or not slot.number or slot.number in seen:
            continue
        item = load(slot.number)
        if item is None:
            continue
        seen.add(item.number)
        members.append(Member(slot.role, item, f"{step.process} seat"))
    for item in step.companions:
        if item.number in seen:
            continue
        seen.add(item.number)
        members.append(Member(_role(item), item, "same day, names a party of the deed"))
    if not members:
        return None
    return Formation("closing", anchor, tuple(sorted(members, key=lambda member: member.instrument.number)))


def community_formations(index: PlacerIndex, governing, *, reach: int = REACH, search: bool = True) -> tuple[Formation, ...]:
    """Each governing instrument with the same-day neighbors that form its community, read within ``reach`` numbers.

    A neighbor joins when it is a governing instrument, plan, map, or notice
    of completion that shares a business party with the anchor or names an
    association, or a fee deed into an association (the common area). A
    neighbor already in an earlier formation joins that one, not a new one.
    """
    formations: list[Formation] = []
    placed: set[str] = set()
    for anchor in sorted(governing, key=lambda item: item.number):
        if anchor.number in placed:
            continue
        members: list[Member] = []
        for item in index.around(anchor.number, before=reach, after=reach, search=search):
            if item.number == anchor.number or item.recorded != anchor.recorded or item.recorded is None:
                continue
            why = _joins(anchor, item)
            if why:
                members.append(Member(_role(item), item, why))
        placed.add(anchor.number)
        placed.update(member.instrument.number for member in members)
        formations.append(Formation("community", anchor, tuple(members)))
    return tuple(formations)


def governing_instruments(
    index: PlacerIndex,
    names: tuple[str, ...],
    *,
    after: date,
    before: date,
) -> tuple[FiledInstrument, ...]:
    """The governing instruments, plans, and maps naming any of ``names`` (``%`` wildcards) in the window."""
    found: dict[str, FiledInstrument] = {}
    types = type_ids(GOVERNING_TYPES)
    for name in names:
        query = " ".join(name.upper().split())
        if not query:
            continue
        query = query if "%" in query else f"{query}%"
        for item in index.instruments(index.typed(types, after=after, before=before, name=query)):
            if instrument_class(item.filing_code, item.filing_name, item.kind).family in _FORMING:
                found.setdefault(item.number, item)
    return tuple(sorted(found.values(), key=lambda item: item.number))


def parcel_bundle(
    record: PlacerParcelRecord,
    index: PlacerIndex,
    *,
    developers: tuple[Developer, ...] = (),
    governing_years: int = 5,
) -> InstrumentBundle:
    """One Placer parcel as a bundle: its chain, readings, closings, liens, and, given its developer, the community's formation.

    The governing instruments are searched by the developer's names from
    ``governing_years`` before the developer's grant to a year after it.
    """
    history = record.history
    load = index.cache.get
    formations = [found for step in record.processes if (found := closing_formation(step, load)) is not None]
    root = next((step.conveyance for step in reversed(history.steps) if history.from_developer(step.conveyance)), None)
    if developers and root is not None and root.recorded is not None:
        names = tuple(name for developer in developers for name in developer.names)
        governing = governing_instruments(
            index, names,
            after=root.recorded - timedelta(days=365 * governing_years), before=root.recorded + timedelta(days=365),
        )
        formations.extend(community_formations(index, governing))
    numbers = set(history.numbers)
    for formation in formations:
        numbers.update(formation.numbers)
    for lien in record.parcel_history.liens:
        numbers.update(step.number for step in lien.encumbrance.steps)
    instruments = tuple(sorted((item for number in numbers if (item := load(number)) is not None), key=lambda item: item.number))
    return InstrumentBundle(
        "placer", "parcel", record.parcel.apn or record.parcel.document_number, instruments, (history,), record.processes,
        tuple(formations), record.parcel_history.liens,
        ((record.parcel.apn, history.steps[0].conveyance.number),) if record.parcel.apn and history.steps else (),
        ("Placer's index cites no prior deed; each step is joined by party, a lead for a person to confirm.",),
    )


def subdivision_bundle(
    descent: PlacerDescent,
    index: PlacerIndex,
    *,
    readings: bool = True,
    governing: bool = True,
    label: str = "",
) -> InstrumentBundle:
    """A builder's subdivision as a bundle: every lot's chain, each step's reading and closing, and the community's formation."""
    load = index.cache.get
    steps: list[ProcessStep] = []
    formations: list[Formation] = []
    if readings:
        for lot in descent.lots:
            found = read_chain(lot.history, index=index, developers=descent.developers, search=descent.neighbors)
            steps.extend(found)
            formations.extend(item for step in found if (item := closing_formation(step, load)) is not None)
    if governing:
        names = tuple(name for developer in descent.developers for name in developer.names)
        found = governing_instruments(index, names, after=descent.after - timedelta(days=365 * 5), before=descent.before)
        formations.extend(community_formations(index, found))
    numbers: set[str] = {item.number for item in descent.notices}
    for lot in descent.lots:
        numbers.update(lot.numbers)
    for formation in formations:
        numbers.update(formation.numbers)
    instruments = tuple(sorted((item for number in numbers if (item := load(number)) is not None), key=lambda item: item.number))
    notes = []
    if descent.wide:
        notes.append(f"{len(descent.wide)} buyer names were too common to follow; their lots stop at that buyer.")
    shared = sorted({number for lot in descent.lots for number in lot.shared})
    if shared:
        notes.append(f"{len(shared)} deeds were reached from more than one lot; the index cannot say which unit each conveys.")
    return InstrumentBundle(
        "placer", "subdivision", label or ", ".join(developer.name for developer in descent.developers),
        instruments, tuple(lot.history for lot in descent.lots), tuple(steps), tuple(formations), (),
        tuple((lot.apn, lot.newest) for lot in descent.lots if lot.apn), tuple(notes),
    )


def _joins(anchor: FiledInstrument, item: FiledInstrument) -> str:
    klass = instrument_class(item.filing_code, item.filing_name, item.kind)
    parties = [name for name in (*anchor.grantors, *anchor.grantees) if name.strip()]
    shared = [name for name in (*item.grantors, *item.grantees) if any(same_party(name, other) for other in parties) and _business(name)]
    association = [name for name in (*item.grantors, *item.grantees) if _association(name)]
    if klass.family is Family.CONVEYANCE and any(_association(name) for name in item.grantees):
        return "deed into an association the same day" + (f", from {shared[0]}" if shared else "")
    if klass.family in _FORMING or klass.code == "306":
        if shared:
            return f"same day, shares {shared[0]}"
        if association:
            return f"same day, names {association[0]}"
    return ""


def _role(item: FiledInstrument) -> str:
    klass = instrument_class(item.filing_code, item.filing_name, item.kind)
    if klass.family is Family.CONVEYANCE and any(_association(name) for name in item.grantees):
        return "common-area deed"
    if klass.code in _ROLES:
        return _ROLES[klass.code]
    if item.kind == "lien":
        return "deed of trust"
    if item.kind == "release":
        return "reconveyance"
    if item.kind in ("fee", "foreclosure"):
        return "companion vesting"
    return (item.filing_name or item.kind or "instrument").lower()


_BUSINESS = ("LLC", "INC", "CORP", "CO", "LP", "LTD", "COMPANY", "HOMES", "PARTNERS", "ASSN", "ASSOCIATION", "DEVELOPMENT", "COMMUNITIES", "BUILDERS")


def _business(name: str) -> bool:
    """A company or an association, not a person: the party a builder's formation instruments share."""
    words = set(" ".join(name.upper().replace(",", " ").replace(".", " ").split()).split())
    return bool(words & set(_BUSINESS)) or _association(name)


def _day(value: date | None) -> str:
    return value.isoformat() if value else ""


def _instrument(item: FiledInstrument) -> dict[str, Any]:
    klass = instrument_class(item.filing_code, item.filing_name, item.kind)
    return {
        "number": item.number,
        "recorded": _day(item.recorded),
        "kind": item.kind,
        "filingCode": item.filing_code,
        "filingName": item.filing_name,
        "family": klass.family.name.lower(),
        "grantors": list(item.grantors),
        "grantees": list(item.grantees),
        "crossReferences": list(item.cross_references),
    }


def _history(history: OwnershipHistory) -> dict[str, Any]:
    return {
        "apn": history.apn,
        "developers": [developer.name for developer in history.developers],
        "reachedDeveloper": history.reached_developer,
        "gaps": list(history.gaps),
        "steps": [
            {
                "number": step.conveyance.number,
                "recorded": _day(step.conveyance.recorded),
                "grantors": list(step.conveyance.grantors),
                "grantees": list(step.conveyance.grantees),
                "priors": list(step.priors),
                "cited": list(step.cited),
            }
            for step in history.steps
        ],
    }


def _reading(step: ProcessStep) -> dict[str, Any]:
    return {
        "number": step.number,
        "recorded": _day(step.recorded),
        "kind": step.kind,
        "filingName": step.filing_name,
        "process": step.process,
        "complete": step.complete,
        "reassesses": step.reassesses,
        "slots": [
            {
                "role": slot.role, "required": slot.required, "reason": slot.reason, "number": slot.number,
                "after": _day(slot.after), "before": _day(slot.before),
            }
            for slot in (step.reading.slots if step.reading is not None else ())
        ],
        "companions": [item.number for item in step.companions],
    }


def _lien(lien) -> dict[str, Any]:
    e = lien.encumbrance
    return {
        "owner": lien.owner,
        "process": e.process.value if e.process is not None else "",
        "status": e.status,
        "duringTenure": lien.during_tenure,
        "community": lien.community,
        "debtor": list(e.debtor),
        "claimant": list(e.claimant),
        "steps": [{"number": step.number, "recorded": _day(step.recorded), "filing": step.filing, "effect": step.effect} for step in e.steps],
    }
