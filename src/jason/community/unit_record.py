"""A unit's effective record: what each component is now, and where each insurance column points for it.

The profile holds a plan's original specifications (``Community.original_specs()``) and the coverage lists
(``Community.unit_coverage()``). A unit's entries are the owner's improvements. This module is pure: it merges them and maps a
component's status to a *pointer*. A pointer is a lead, not a ruling: a column never says a thing is or is not insured. The
carrier decides coverage; the board and counsel decide responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ComponentKind(Enum):
    FLOORING = "flooring"
    CABINETS = "cabinets"
    BUILT_IN_APPLIANCE = "built-in appliance"
    APPLIANCE = "appliance"
    PLUMBING_FIXTURE = "plumbing fixture"
    ELECTRICAL_FIXTURE = "electrical fixture"
    HVAC = "heating and air conditioning"
    WATER_HEATER = "water heater"
    WALL_FINISH = "wall finish"
    CEILING_FINISH = "ceiling finish"
    DOORS = "doors"
    WINDOWS = "windows"
    OTHER = "other"


class ComponentStatus(Enum):
    ORIGINAL = "original"
    EQUIVALENT_REPLACEMENT = "equivalent replacement"
    UPGRADE = "upgrade"
    BUILDER_OPTION = "builder option"
    PERSONAL_PROPERTY = "personal property"
    UNKNOWN = "unknown"


class Visibility(Enum):
    PRIVATE = "private"
    SHARED = "shared"
    ASSOCIATION = "association"


@dataclass(frozen=True)
class OriginalSpec:
    plan: str
    component: str
    kind: ComponentKind
    value: str
    source: str  # an evidence address


@dataclass(frozen=True)
class ImprovementEntry:
    id: str
    unit: str
    component: str
    kind: ComponentKind
    what: str
    where: str = ""
    replaces: str = ""
    date: str = ""
    contractor: str = ""
    licence: str = ""
    permit: str = ""
    approval: str = ""
    cost_cents: int | None = None
    product: str = ""
    model: str = ""
    serial: str = ""
    warranty: str = ""
    photos: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()
    status: ComponentStatus = ComponentStatus.UPGRADE
    visibility: str = "private"  # private, shared, association (see Visibility)
    by: str = ""
    at: str = ""


@dataclass(frozen=True)
class EffectiveComponent:
    component: str
    kind: ComponentKind
    value: str
    status: ComponentStatus
    sources: tuple[str, ...] = ()
    entries: tuple[ImprovementEntry, ...] = ()
    verified: str = ""


@dataclass(frozen=True)
class UnitCoverage:
    """The two lists the association's documents draw, with the expressions that recite each."""

    declaration_kinds: tuple[ComponentKind, ...]
    policy_kinds: tuple[ComponentKind, ...]
    declaration_cite: tuple[str, ...] = ()
    policy_cite: tuple[str, ...] = ()
    differs_question: str = ""  # open-question key for a kind the two lists treat differently
    builder_question: str = ""  # open-question key for whether a builder option counts as original


class Points(Enum):
    MASTER_POLICY = "points to the master policy"
    OWNERS_POLICY = "points to the owner's policy"
    NOT_STATED = "not stated"
    ASK_A_PERSON = "ask a person"


@dataclass(frozen=True)
class CoverageReading:
    points: Points
    words_cites: tuple[str, ...] = ()  # expressions the loader recites; never the words themselves
    differs: str = ""  # an open-question key


def _newest(entries: Iterable[ImprovementEntry]) -> ImprovementEntry:
    return max(entries, key=lambda e: (e.date, e.at))


def effective(
    plan: str, specs: Iterable[OriginalSpec], entries: Iterable[ImprovementEntry]
) -> tuple[EffectiveComponent, ...]:
    """Each component of ``plan`` as it stands: the newest entry that replaces it, else the specification row.

    An entry that matches no component is added under its own name and status. A plan with no specification yields no
    ORIGINAL row: every component is UNKNOWN, since there is nothing to call original or equivalent to.
    """
    plan_specs = [s for s in specs if s.plan == plan]
    entries = tuple(entries)
    known = bool(plan_specs)

    by_target: dict[str, list[ImprovementEntry]] = {}
    for entry in entries:
        by_target.setdefault(entry.replaces or entry.component, []).append(entry)

    rows: list[EffectiveComponent] = []
    seen: set[str] = set()
    for spec in plan_specs:
        seen.add(spec.component)
        matched = by_target.get(spec.component)
        if matched:
            top = _newest(matched)
            rows.append(
                EffectiveComponent(
                    component=spec.component,
                    kind=spec.kind,
                    value=top.what,
                    status=top.status,
                    sources=(spec.source,),
                    entries=tuple(sorted(matched, key=lambda e: (e.date, e.at))),
                    verified=top.at,
                )
            )
        else:
            rows.append(
                EffectiveComponent(
                    component=spec.component,
                    kind=spec.kind,
                    value=spec.value,
                    status=ComponentStatus.ORIGINAL,
                    sources=(spec.source,),
                )
            )
    for target, matched in by_target.items():
        if target in seen:
            continue
        top = _newest(matched)
        rows.append(
            EffectiveComponent(
                component=target,
                kind=top.kind,
                value=top.what,
                status=top.status if known else ComponentStatus.UNKNOWN,
                entries=tuple(sorted(matched, key=lambda e: (e.date, e.at))),
                verified=top.at,
            )
        )
    if not known:
        rows = [
            EffectiveComponent(r.component, r.kind, r.value, ComponentStatus.UNKNOWN, r.sources, r.entries, r.verified)
            for r in rows
        ]
    return tuple(rows)


def coverage(
    kind: ComponentKind, status: ComponentStatus, unit_coverage: UnitCoverage | None
) -> tuple[CoverageReading, CoverageReading]:
    """(declaration reading, policy reading) for one component. Pointers only; see the module note."""
    if unit_coverage is None:
        ask = CoverageReading(Points.ASK_A_PERSON)
        return ask, ask
    decl_cite, pol_cite = unit_coverage.declaration_cite, unit_coverage.policy_cite
    if status in (ComponentStatus.ORIGINAL, ComponentStatus.EQUIVALENT_REPLACEMENT):
        in_decl = kind in unit_coverage.declaration_kinds
        in_pol = kind in unit_coverage.policy_kinds
        differs = unit_coverage.differs_question if in_decl != in_pol else ""
        return (
            CoverageReading(Points.MASTER_POLICY if in_decl else Points.NOT_STATED, decl_cite, differs),
            CoverageReading(Points.MASTER_POLICY if in_pol else Points.NOT_STATED, pol_cite, differs),
        )
    if status in (ComponentStatus.UPGRADE, ComponentStatus.PERSONAL_PROPERTY):
        reading = CoverageReading(Points.OWNERS_POLICY)
        return reading, reading
    differs = unit_coverage.builder_question if status is ComponentStatus.BUILDER_OPTION else ""
    reading = CoverageReading(Points.ASK_A_PERSON, (), differs)
    return reading, reading
