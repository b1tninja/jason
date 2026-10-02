"""The governing instruments in the public index, read against 2792.23.

Title 10, section 2792.23(a), lists what the subdivider delivers to the
association. Several of those are recorded instruments the county index
holds under the project's name, the association's name, or a developer's:
the declaration and its restatement, each amendment, each phase's
declaration of annexation, the condominium plan and its amendments, the
subdivision and parcel maps, and the notices of completion. This module
classifies those instruments, ties each to the delivery it satisfies, and
says which phases still have no annexation on file.

Bylaws and articles are rarely recorded; the articles are a Secretary of
State filing and the bylaws are the association's own. Plans, bonds,
warranties, policies, and contracts are never recorded. Those stay with the
Drive pins in ``developer_file()``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date

from jason.community.filings import Family, instrument_class
from jason.community.recorder import FiledInstrument
from jason.community.symbols import DeveloperDelivery

_PHASE = re.compile(r"\bPHAS(?:E)?\s*(\d+)\b", re.IGNORECASE)

# What each recorded governing filing satisfies, and the label a report uses.
_ROLES: dict[str, tuple[str, DeveloperDelivery]] = {
    "162": ("declaration", DeveloperDelivery.DECLARATION),
    "324": ("declaration", DeveloperDelivery.DECLARATION),
    "220": ("restatement or amendment", DeveloperDelivery.DECLARATION),
    "225": ("amendment", DeveloperDelivery.DECLARATION),
    "320": ("annexation", DeveloperDelivery.DECLARATION),
    "478": ("covenant", DeveloperDelivery.DECLARATION),
    "499": ("covenant modification", DeveloperDelivery.DECLARATION),
    "604": ("cancellation of restrictions", DeveloperDelivery.DECLARATION),
    "188": ("covenant and agreement", DeveloperDelivery.RECIPROCAL_INSTRUMENT),
    "301": ("condominium plan", DeveloperDelivery.CONDOMINIUM_PLAN),
    "240": ("condominium plan amendment", DeveloperDelivery.CONDOMINIUM_PLAN),
    "435": ("subdivision map", DeveloperDelivery.SUBDIVISION_MAP),
    "433": ("parcel map", DeveloperDelivery.SUBDIVISION_MAP),
    "446": ("articles", DeveloperDelivery.ARTICLES),
    "494": ("bylaws", DeveloperDelivery.BYLAWS),
    "306": ("notice of completion", DeveloperDelivery.NOTICE_OF_COMPLETION),
    "190": ("easement", DeveloperDelivery.COMMON_AREA_DEED),
    "681": ("easement deed", DeveloperDelivery.COMMON_AREA_DEED),
}


RESTATED_DECLARATION = "restated declaration"


@dataclass(frozen=True)
class GoverningRecord:
    """One recorded governing instrument and the delivery it satisfies."""

    number: str
    recorded: date | None
    filing: str
    role: str
    delivery: DeveloperDelivery
    parties: tuple[str, ...]
    phase: int | None
    cites: tuple[str, ...]
    developer: str = ""
    superseded_by: str = ""
    """The later instrument that rescinded or replaced this one, when a spec fact says so."""

    @property
    def status(self) -> str:
        return f"rescinded and superseded by {self.superseded_by}" if self.superseded_by else "in force"


@dataclass(frozen=True)
class Supersession:
    """A recorded governing instrument a later one rescinded or replaced, as the later one's body states.

    The index carries no cross-reference for a rescission written into a
    recital, so the fact is pinned in the specification with its source.
    ``phase`` is the phase the rescinded instrument was for.
    """

    number: str
    superseded_by: str
    phase: int | None = None
    role: str = "annexation"
    reason: str = ""
    source: str = ""


def apply_supersessions(
    governing: tuple[GoverningRecord, ...] | list[GoverningRecord],
    unplaced: tuple[GoverningRecord, ...] | list[GoverningRecord],
    supersessions: tuple[Supersession, ...],
) -> tuple[tuple[GoverningRecord, ...], tuple[GoverningRecord, ...]]:
    """Place each superseded instrument by the spec fact: its phase, its role, and what replaced it.

    A superseded instrument moves from ``unplaced`` into ``governing`` when
    it was there, and keeps its position when it was already placed.
    """
    by_number = {fact.number: fact for fact in supersessions}
    placed: list[GoverningRecord] = []
    left: list[GoverningRecord] = []
    for record in list(governing) + list(unplaced):
        fact = by_number.get(record.number)
        if fact is None:
            (placed if record in governing else left).append(record)
            continue
        placed.append(replace(
            record,
            role=fact.role or record.role,
            phase=fact.phase if fact.phase is not None else record.phase,
            superseded_by=fact.superseded_by,
        ))
    # The instrument that replaced a declaration is the declaration now: a restatement indexed as an amended restriction.
    restating = {fact.superseded_by for fact in supersessions if fact.role == "declaration"}
    placed = [replace(record, role=RESTATED_DECLARATION) if record.number in restating else record for record in placed]
    placed.sort(key=lambda record: (record.recorded or date.min, record.number))
    return tuple(placed), tuple(left)


@dataclass(frozen=True)
class DeliveryStatus:
    """What the index holds for one 2792.23 delivery, and what is still missing."""

    delivery: DeveloperDelivery
    records: tuple[GoverningRecord, ...]
    missing: tuple[str, ...]

    @property
    def found(self) -> bool:
        return bool(self.records)


def locate_governing(
    items: tuple[FiledInstrument, ...] | list[FiledInstrument],
    *,
    developers: tuple = (),
) -> tuple[GoverningRecord, ...]:
    """Classify every governing, plan, map, and completion instrument in ``items``.

    A phase is read from a party such as ``MYSTIQUE PHASE 3``. An amended
    restriction that names a phase is that phase's annexation recorded under
    the other filing.
    """
    from jason.community.recorder import developer_for

    found: list[GoverningRecord] = []
    for item in sorted(items, key=lambda entry: (entry.recorded or date.min, entry.number)):
        klass = instrument_class(item.filing_code, item.filing_name)
        role = _ROLES.get(klass.code)
        if role is None:
            if klass.family in (Family.GOVERNING, Family.PLAN, Family.MAP):
                role = (klass.name.lower() or "governing instrument", DeveloperDelivery.DECLARATION)
            else:
                continue
        label, delivery = role
        parties = tuple(dict.fromkeys((*item.grantors, *item.grantees)))
        phase = _phase_of(parties)
        if klass.code == "220" and phase is not None:
            label = "annexation"
        developer = ""
        for party in parties:
            match = developer_for(party, developers) if developers else None
            if match is not None:
                developer = match.name
                break
        found.append(
            GoverningRecord(item.number, item.recorded, f"{klass.code} {klass.name}".strip(), label, delivery, parties, phase, item.cross_references, developer)
        )
    return tuple(found)


def delivery_status(
    records: tuple[GoverningRecord, ...],
    *,
    phases: tuple[int, ...] = (),
    annexed_phases: tuple[int, ...] = (),
) -> tuple[DeliveryStatus, ...]:
    """Each recorded delivery with its instruments and the phases still without one.

    ``phases`` are every phase of the project; ``annexed_phases`` are the ones
    the public reports say were annexed, so the original phase is not asked
    for an annexation. A missing annexation is listed by phase.
    """
    by_delivery: dict[DeveloperDelivery, list[GoverningRecord]] = {}
    for record in records:
        by_delivery.setdefault(record.delivery, []).append(record)
    found: list[DeliveryStatus] = []
    for delivery in (
        DeveloperDelivery.SUBDIVISION_MAP,
        DeveloperDelivery.CONDOMINIUM_PLAN,
        DeveloperDelivery.COMMON_AREA_DEED,
        DeveloperDelivery.DECLARATION,
        DeveloperDelivery.ARTICLES,
        DeveloperDelivery.BYLAWS,
        DeveloperDelivery.NOTICE_OF_COMPLETION,
        DeveloperDelivery.RECIPROCAL_INSTRUMENT,
    ):
        rows = tuple(by_delivery.get(delivery, ()))
        missing: list[str] = []
        if delivery is DeveloperDelivery.DECLARATION:
            # The declaration in force: the original, or the restatement that rescinded it.
            if not any(record.role in ("declaration", RESTATED_DECLARATION) and not record.superseded_by for record in rows):
                missing.append("the declaration in force")
            annexed = {record.phase for record in rows if record.role == "annexation" and record.phase is not None and not record.superseded_by}
            for phase in annexed_phases:
                if phase not in annexed:
                    missing.append(f"annexation of phase {phase}")
        elif delivery is DeveloperDelivery.CONDOMINIUM_PLAN and not rows:
            missing.append("a condominium plan")
        elif delivery is DeveloperDelivery.SUBDIVISION_MAP and not rows:
            missing.append("the final map is in the map books, not the document index; keep the Drive copy")
        elif delivery in (DeveloperDelivery.ARTICLES, DeveloperDelivery.BYLAWS) and not rows:
            missing.append("not a recorded instrument; the Secretary of State filing or the association's own copy is the record")
        found.append(DeliveryStatus(delivery, rows, tuple(missing)))
    return tuple(found)


def _phase_of(parties: tuple[str, ...]) -> int | None:
    for party in parties:
        hit = _PHASE.search(party)
        if hit:
            return int(hit.group(1))
    return None
