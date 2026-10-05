"""Bureau public reports and the documents recorded with each phase.

The file number is the Bureau's number without the form suffix. ``130654SA``
matches every copy of that report. An annexation pin joins the phase named in
its title. A related file is a document of that phase that is not the report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from jason.community.documents import DocumentPin
from jason.community.symbols import Building, DocumentKind

_FILE_NUMBER = re.compile(r"(\d{6}SA)\b", re.IGNORECASE)
_PHASE = re.compile(r"\bPhase\s+(\d+)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PhaseFile:
    """A document of one phase that is not itself the public report."""

    title: str
    drive_id: str
    role: str


@dataclass(frozen=True)
class PublicReport:
    """One phase on the Buildings tab, and the Bureau file that covers it.

    ``assessment_cents`` is the monthly assessment when that tab states one.
    Phase 1 leaves the amount blank, so it stays unset. ``first_conveyance``
    is a deed date of that building, not always the earliest one.
    ``opened`` is an earlier day unit sales begin, when the common-area deed
    and the first completion notices fall before that date.
    ``issued`` is the day the Bureau issued the public report. Sales under
    that report do not start before it.
    """

    file_number: str
    building: Building
    phase: int
    units: int
    first_conveyance: date
    developer: str
    annexation: date | None = None
    assessment_cents: int | None = None
    related: tuple[PhaseFile, ...] = ()
    opened: date | None = None
    issued: date | None = None


@dataclass(frozen=True)
class PlanBlock:
    """One building whose assessor subparcel still follows the original plan.

    Subparcel 0001 is ``first_unit``. The next subparcel is the next unit.
    A common-area subparcel past ``count`` is not a unit. ``parent_parcels``
    are the numbers a deed printed before the assessor split the building;
    a unit number places a deed only when the deed prints one of them, since
    a later developer reused the same unit numbers on other buildings. A
    block with no parent parcels never places a deed by unit number.
    ``first_subparcel`` is the subparcel of ``first_unit`` when the assessor
    did not start the units at 0001. ``plan`` names the numbering the block
    follows, so two blocks that share a unit number are told apart.
    ``book_page`` is the assessor's map book and page the block is on, as
    the first seven digits of its parcels' fourteen (``1234560`` for book
    123, page 4560): a unit's parcel is built from it, so a block without
    one names no parcel.
    """

    building: Building
    block: str
    first_unit: int
    count: int
    parent_parcels: tuple[str, ...] = ()
    first_subparcel: int = 1
    plan: str = "2007 plan"
    book_page: str = ""

    def parcel(self, subparcel: int) -> str:
        """The fourteen-digit parcel number of ``subparcel`` on this block, or "" when the block names no map page."""
        return f"{self.book_page}{self.block}{subparcel:04d}" if self.book_page else ""

    @property
    def last_unit(self) -> int:
        return self.first_unit + self.count - 1


@dataclass(frozen=True)
class HeldUnits:
    """Units of one building that a bulk deed still held.

    A unit of that building missing from ``units`` had already been conveyed.
    A later deed of a missing unit is a resale, not that bulk grantee's first sale.
    """

    number: str
    recorded: date
    building: Building
    units: tuple[int, ...]


@dataclass(frozen=True)
class CatalogedReport:
    """One public report, the pinned copies, and the phase's other files."""

    report: PublicReport
    copies: tuple[DocumentPin, ...]
    annexations: tuple[DocumentPin, ...]


def report_file_number(title: str) -> str:
    """The Bureau file number in a title, or empty when the title has none."""
    hit = _FILE_NUMBER.search(title)
    return hit.group(1).upper() if hit else ""


def catalog_reports(reports: tuple[PublicReport, ...], pins: tuple[DocumentPin, ...]) -> tuple[CatalogedReport, ...]:
    """Join each report to the pinned copies and annexations of that phase."""
    found: list[CatalogedReport] = []
    for report in reports:
        copies = tuple(
            row
            for row in pins
            if row.kind is DocumentKind.DRE_REPORT and report_file_number(row.title) == report.file_number
        )
        annexations = tuple(
            row
            for row in pins
            if row.kind is DocumentKind.ANNEXATION and _phase_of(row.title) == report.phase
        )
        found.append(CatalogedReport(report, copies, annexations))
    return tuple(found)


def parcel_block(apn: str) -> str:
    """The assessor parcel block inside a book and page.

    Fourteen digits are book, page, parcel, and subparcel. One phase is one
    parcel block. A unit on a different street in that block is the same phase.
    """
    digits = "".join(ch for ch in apn if ch.isdigit())
    if len(digits) != 14:
        return ""
    return digits[7:10]


def phases_for_blocks(
    situated: tuple[tuple[str, Building | None], ...],
    reports: tuple[PublicReport, ...],
) -> dict[str, PublicReport]:
    """The phase of each assessor block.

    ``situated`` is an APN and the flood building of that address, or None
    when the street is outside the flood ranges. A block with one building
    takes that building's phase, including the address the flood range skips.
    A block with two buildings is left out.
    """
    grouped: dict[str, set[Building]] = {}
    for apn, building in situated:
        block = parcel_block(apn)
        if not block:
            continue
        grouped.setdefault(block, set())
        if building is not None:
            grouped[block].add(building)
    by_building = {item.building: item for item in reports}
    found: dict[str, PublicReport] = {}
    for block, buildings in grouped.items():
        if len(buildings) != 1:
            continue
        report = by_building.get(next(iter(buildings)))
        if report is not None:
            found[block] = report
    return found


def deed_in_phase(recorded: date, report: PublicReport, *, lead_days: int = 3) -> bool:
    """True when this recording can be a deed of that building.

    The tabulated first conveyance is one deed date of the building. A later
    grant still belongs to the phase. A grant more than ``lead_days`` before
    the earlier of that date and ``opened`` is a different project, and a
    grant before ``issued`` is not a sale under that report. The original
    phase can open on the common-area deed, before the date kept for a later
    closing.
    """
    if lead_days < 0:
        raise ValueError("lead_days must be zero or more")
    floor = report.first_conveyance
    if report.opened is not None and report.opened < floor:
        floor = report.opened
    earliest = floor - timedelta(days=lead_days)
    if report.issued is not None and report.issued < earliest:
        earliest = report.issued
    if report.issued is not None and recorded < report.issued:
        return False
    return recorded >= earliest


def plan_unit(apn: str, blocks: tuple[PlanBlock, ...]) -> int | None:
    """The condominium-plan unit for this assessor number, or None.

    The block has to be one of ``blocks``, and the subparcel has to fall
    inside that building's unit count. The plan unit is what an early deed
    names in its legal description while its header prints the parent
    parcel, so ``unit_parcel`` is how such a deed is placed. A unit number
    can still be mistyped on a deed or a letter, so confirm it against the
    address or the parcel number when either is printed.
    """
    found = plan_block(apn, blocks)
    if found is None:
        return None
    subparcel = int("".join(ch for ch in apn if ch.isdigit())[10:14])
    return found.first_unit + subparcel - found.first_subparcel


def plan_block(apn: str, blocks: tuple[PlanBlock, ...]) -> PlanBlock | None:
    """The plan block this assessor number falls in, or None."""
    digits = "".join(ch for ch in apn if ch.isdigit())
    if len(digits) != 14:
        return None
    subparcel = int(digits[10:14])
    for item in blocks:
        if item.block == digits[7:10] and item.first_subparcel <= subparcel < item.first_subparcel + item.count:
            return item
    return None


def unit_parcels(unit: int, blocks: tuple[PlanBlock, ...]) -> tuple[tuple[PlanBlock, str], ...]:
    """Every parcel a unit number could mean, with the block it is on.

    More than one answer is the overlap: the same number on two buildings.
    A block that names no map page (``PlanBlock.book_page``) names no parcel.
    """
    found: list[tuple[PlanBlock, str]] = []
    for item in blocks:
        if item.first_unit <= unit <= item.last_unit and item.book_page:
            found.append((item, item.parcel(unit - item.first_unit + item.first_subparcel)))
    return tuple(found)


def unit_parcel(unit: int, blocks: tuple[PlanBlock, ...]) -> str | None:
    """The one assessor number for a plan unit, or None when there is none or more than one.

    The inverse of ``plan_unit``. Book and page are the community's, so this
    only answers for the blocks given. A unit on two blocks is ambiguous and
    returns None; ``unit_parcels`` lists both.
    """
    found = unit_parcels(unit, blocks)
    return found[0][1] if len(found) == 1 else None


def parent_parcel(apn: str) -> bool:
    """True for a parcel whose subparcel is 0000.

    A deed recorded before the assessor split the building prints that
    number. It names the land, not a unit, so it places nothing by itself.
    """
    digits = "".join(ch for ch in apn if ch.isdigit())
    return len(digits) == 14 and digits[10:14] == "0000"


def still_held(apn: str, blocks: tuple[PlanBlock, ...], held: HeldUnits) -> bool | None:
    """Whether ``held`` still included this parcel.

    True when the plan unit is one of the units that deed names. False when
    the unit is on that building and the deed left it out, so it had already
    been conveyed. None when the parcel is not a unit of that building.
    """
    unit = plan_unit(apn, blocks)
    if unit is None:
        return None
    building = next(item.building for item in blocks if item.block == parcel_block(apn))
    if building is not held.building:
        return None
    return unit in held.units


def phase_on(
    recorded: date,
    reports: tuple[PublicReport, ...],
    *,
    lead_days: int = 3,
) -> PublicReport | None:
    """The phase a developer grant belongs to when the street does not name one.

    The first conveyance is a deed date of that building. A unit sometimes
    records a few days before the date kept for the phase. The phase is the
    one whose first conveyance is the latest date still on or before this
    recording plus that lead. A street that names a flood building uses that
    building, including a later sale after the next phase has opened.
    """
    if lead_days < 0:
        raise ValueError("lead_days must be zero or more")
    opened = recorded + timedelta(days=lead_days)
    candidates = tuple(item for item in reports if item.first_conveyance <= opened)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.first_conveyance)


def _phase_of(title: str) -> int | None:
    hit = _PHASE.search(title)
    if hit is None:
        return None
    return int(hit.group(1))
