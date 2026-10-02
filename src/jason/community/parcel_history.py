"""One parcel's history, assembled from every record on disk.

The chain in the ownership store says which deeds carried the fee. This
module says what each of those deeds was (the process it completed), what
it cost (the transfer tax on its scan), what the assessor enrolled after it
(the bill calendar), how it was placed on the parcel (the scan, a citation,
or a name handoff), and which other instruments belong beside it (the
notice of completion, the buyer's lien, the partial reconveyance, the
trustee's deed). The audit findings ride along. Nothing here searches; it
reads the stores, the cache, and the scans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from jason.community.association_record import ParcelLien, parcel_liens
from jason.community.solar import SolarProgram, SolarRecord, solar_notices, solar_record
from jason.community.audit import ChainAudit, ChainFinding, audit_chain, reassessing_steps
from jason.community.base import Developer
from jason.community.calendar import CalendarEvent, classify
from jason.community.members import MemberCheck, Occupancy, check_members
from jason.community.ownership import OwnershipRecord
from jason.community.filings import Process
from jason.community.processes import COMPANION_DAYS, Reading, beside_step, gather, read
from jason.community.recorder import ChainStep, FiledInstrument, OwnershipHistory, developer_for
from jason.community.reports import HeldUnits, PlanBlock, PublicReport, plan_unit
from jason.community.scans import DeedScan, placement
from jason.community.standing import OwnerEvent, TaxStanding, owner_events, tax_standing
from jason.community.tax import RollCharge, TaxBill, reassessment_year_for, roll_charges

# Slot reasons that name an instrument worth listing beside the anchor. A
# neighbor that turned out to be someone else's instrument is not listed.
_LISTED = frozenset({"present", "wrong date", "unloaded"})


@dataclass(frozen=True)
class ParcelNote:
    """A fact a person supplied about a parcel, with its date and source."""

    apn: str
    noted: date | None
    note: str
    source: str


def parcel_notes(path) -> dict[str, tuple[ParcelNote, ...]]:
    """``data/parcel-notes.csv``: ``apn, date, note, source``, by fourteen-digit parcel."""
    import csv
    from pathlib import Path

    file = Path(path)
    if not file.is_file():
        return {}
    found: dict[str, list[ParcelNote]] = {}
    with file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            digits = "".join(ch for ch in str(row.get("apn") or "") if ch.isdigit())
            text = " ".join(str(row.get("note") or "").split())
            if len(digits) != 14 or not text:
                continue
            when = str(row.get("date") or "").strip()
            noted = date.fromisoformat(when) if when else None
            found.setdefault(digits, []).append(ParcelNote(digits, noted, text, str(row.get("source") or "").strip()))
    return {apn: tuple(items) for apn, items in found.items()}


@dataclass(frozen=True)
class RelatedInstrument:
    """An instrument a process expects beside a deed, and whether it was found."""

    role: str
    number: str
    reason: str
    recorded: date | None = None
    kind: str = ""
    filing: str = ""
    grantors: tuple[str, ...] = ()
    grantees: tuple[str, ...] = ()
    scan: str = ""


@dataclass(frozen=True)
class HistoryStep:
    """One deed on the chain, read against everything else on disk."""

    order: int
    number: str
    recorded: date | None
    grantors: tuple[str, ...]
    grantees: tuple[str, ...]
    priors: tuple[str, ...]
    process: str
    complete: bool
    reassesses: bool
    developer: str
    price_cents: int | None
    county_tax_cents: int | None
    city_tax_cents: int | None
    exempt: bool
    bill_year: int | None
    enrolled_cents: int | None
    prior_enrolled_cents: int | None
    placement: str
    scan: str
    scan_source: str
    related: tuple[RelatedInstrument, ...] = ()
    notes: tuple[str, ...] = ()
    unpriced: str = ""

    @property
    def price_or_base(self) -> tuple[int | None, str]:
        """The price when the deed gives one, else the base the next bill enrolled.

        The second value says which: ``deed``, ``base``, or empty when neither.
        The base is within about two percent of the price on every deed that
        has both, so it stands in when the scan is missing.
        """
        if self.price_cents:
            return self.price_cents, "deed"
        if self.enrolled_cents and self.reassesses:
            return self.enrolled_cents, "base"
        return None, ""


@dataclass(frozen=True)
class ParcelHistory:
    """Everything known about one parcel's title."""

    apn: str
    address: str
    unit: int | None
    building: int | None
    phase: int | None
    report: str
    developer: str
    current_number: str
    current_date: date | None
    current_owners: tuple[str, ...]
    steps: tuple[HistoryStep, ...]
    events: tuple[CalendarEvent, ...]
    findings: tuple[ChainFinding, ...]
    reaches_developer: bool
    first_year: int | None
    last_year: int | None
    reassessing: dict[int, str] = field(default_factory=dict)
    candidates: tuple[FiledInstrument, ...] = ()
    occupancies: tuple[Occupancy, ...] = ()
    membership: MemberCheck | None = None
    current_type: str = ""
    notes: tuple[ParcelNote, ...] = ()
    association: bool = False
    liens: tuple[ParcelLien, ...] = ()
    taxes: TaxStanding | None = None
    owner_events: tuple[OwnerEvent, ...] = ()
    solar: SolarRecord | None = None
    # Delinquent-utility charges on this parcel's own tax bills, which settle a utility lien paid through the roll.
    utility_roll: tuple[RollCharge, ...] | None = None

    @property
    def open_liens(self) -> tuple[ParcelLien, ...]:
        return tuple(item for item in self.liens if item.encumbrance.status != "closed" and item.where != "another time or property")

    @property
    def current_conveys(self) -> bool:
        """False when the assessor's current instrument is a death record, which moves no title."""
        return self.current_type.upper() not in ("DETH", "DEATH")

    @property
    def owners(self) -> tuple[str, ...]:
        """The grantees of the newest deed on the chain, or of the assessor's current instrument."""
        if self.steps:
            return self.steps[-1].grantees
        return self.current_owners

    @property
    def sales(self) -> tuple[HistoryStep, ...]:
        return tuple(step for step in self.steps if step.reassesses)

    @property
    def last_sale(self) -> HistoryStep | None:
        """The newest sale, priced or not; its ``price_or_base`` says what it is worth."""
        return self.sales[-1] if self.sales else None

    @property
    def open(self) -> bool:
        return not self.reaches_developer

    @property
    def verified(self) -> int:
        """Steps placed by the parcel number or the plan unit on a scan."""
        return sum(1 for step in self.steps if step.placement.startswith("scan:"))


def build_parcel_history(
    apn: str,
    *,
    history: OwnershipHistory | None,
    developers: tuple[Developer, ...],
    address: str = "",
    building: int | None = None,
    report: PublicReport | None = None,
    blocks: tuple[PlanBlock, ...] = (),
    held: tuple[HeldUnits, ...] = (),
    bills: tuple[TaxBill, ...] | list[TaxBill] = (),
    scans: dict[str, DeedScan] | None = None,
    load: Callable[[str], FiledInstrument | None] | None = None,
    notes: Callable[[str], tuple[str, ...]] | None = None,
    current: OwnershipRecord | None = None,
    restoration_years: frozenset[int] | set[int] = frozenset(),
    placed: Callable[[str], tuple[FiledInstrument, ...]] | None = None,
    periods: tuple[Occupancy, ...] = (),
    notes_for_parcel: tuple[ParcelNote, ...] = (),
    association: bool = False,
    load_naming: Callable[[str], tuple[FiledInstrument, ...]] | None = None,
    association_name: str = "",
    solar_program: SolarProgram | None = None,
    chain_numbers: frozenset[str] = frozenset(),
    roll_rules: tuple = (),
) -> ParcelHistory:
    """Assemble one parcel.

    ``load`` reads the index cache, ``placed`` lists the cache rows a pass
    put on this parcel, and ``scans`` is ``scan_index``. Placed rows not on
    the chain are the parcel's candidates.
    """
    scans = scans or {}
    loader = load or (lambda number: None)
    digits = "".join(ch for ch in apn if ch.isdigit())
    years = sorted({bill.year for bill in bills if bill.year is not None})
    on_chain = {step.conveyance.number for step in history.steps} if history else set()
    candidates = tuple(item for item in (placed(digits) if placed else ()) if item.number not in on_chain)
    if history is None or not history.steps:
        return ParcelHistory(
            digits, address, plan_unit(digits, blocks), building,
            report.phase if report else None, report.file_number if report else "",
            report.developer if report else "",
            current.document_number if current else "", current.document_date if current else None,
            current.grantees if current else (),
            (), (), (ChainFinding("root", "no deed is stored for this parcel"),), False,
            years[0] if years else None, years[-1] if years else None,
            {}, candidates, periods,
            None if association else check_members(digits, address, current.grantees if current else (), periods),
            current.document_type if current else "", notes_for_parcel, association,
            (), tax_standing(bills), (),
        )
    prices = {number: scan.price_cents for number, scan in scans.items() if scan.price_cents}
    audit = audit_chain(
        history,
        developers=developers,
        report=None if association else report,
        blocks=blocks,
        held=held,
        bills=bills,
        prices=prices,
        restoration_years=restoration_years,
        current_instrument=current.document_date if current else None,
    )
    ordered = sorted(history.steps, key=lambda step: (step.conveyance.recorded or date.min, step.conveyance.number))
    root = ordered[0].conveyance
    first_conveyance = root.recorded if developer_for(_first(root.grantors), developers) else None
    current_year = reassessment_year_for(current.document_date) if current and current.document_date else None
    events = classify(
        bills,
        audit.reassessing,
        first_conveyance=first_conveyance,
        base=_base(ordered, history, prices, years),
        restoration_years=restoration_years,
        current_year=current_year,
    )
    by_event = {event.number: event for event in events if event.number}
    filed = tuple(_filed(step.conveyance, loader) for step in history.steps)
    closings = [step.conveyance.recorded for step in ordered if step.conveyance.recorded]

    def _program_filing(encumbrance) -> bool:
        """A claimant or a date ties the filing to this unit: the solar program's lessor, or a loan at a closing."""
        if solar_program is not None and any(solar_program.is_lessor(party) for party in encumbrance.claimant):
            return True
        when = encumbrance.opened.recorded
        return encumbrance.process is Process.LOAN and when is not None and any(abs((when - day).days) <= COMPANION_DAYS for day in closings)

    liens = (
        parcel_liens(load_naming, tuple(ordered), association=association_name, developers=developers, corroborates=_program_filing)
        if load_naming and not association else ()
    )
    steps = tuple(
        _step(index + 1, step, history, digits, address, developers, blocks, scans, loader, notes, filed, by_event, audit, association)
        for index, step in enumerate(ordered)
    )
    if load_naming and not association:
        steps = _with_beside(steps, load_naming, loader, chain_numbers)
    return ParcelHistory(
        digits,
        address,
        plan_unit(digits, blocks),
        building,
        report.phase if report else None,
        report.file_number if report else "",
        report.developer if report else "",
        current.document_number if current else (ordered[-1].conveyance.number if ordered else ""),
        current.document_date if current else None,
        current.grantees if current else (),
        steps,
        events,
        tuple(item for item in audit.findings if not (association and item.check in ("root", "developer", "phase"))),
        association or (history.reached_developer and not history.gaps),
        years[0] if years else None,
        years[-1] if years else None,
        dict(audit.reassessing),
        candidates,
        periods,
        None if association else check_members(digits, address, steps[-1].grantees if steps else (), periods),
        current.document_type if current else "",
        notes_for_parcel,
        association,
        liens,
        tax_standing(bills),
        owner_events(load_naming, tuple(ordered), current_owners=steps[-1].grantees if steps else ()) if load_naming and not association else (),
        solar_record(
            building, steps[-1].grantees if steps else (), liens, solar_program,
            sales=tuple(step.recorded for step in steps if step.reassesses and step.recorded),
            notices=solar_notices(load_naming, tuple(ordered), solar_program) if load_naming else (),
        ) if solar_program is not None and not association else None,
        roll_charges(bills, roll_rules) if roll_rules else None,
    )


def _step(
    order: int,
    step: ChainStep,
    history: OwnershipHistory,
    apn: str,
    address: str,
    developers: tuple[Developer, ...],
    blocks: tuple[PlanBlock, ...],
    scans: dict[str, DeedScan],
    loader: Callable[[str], FiledInstrument | None],
    notes: Callable[[str], tuple[str, ...]] | None,
    filed: tuple[FiledInstrument, ...],
    by_event: dict[str, CalendarEvent],
    audit: ChainAudit,
    association: bool = False,
) -> HistoryStep:
    item = step.conveyance
    anchor = _filed(item, loader)
    around = tuple(gather(loader, anchor)) + tuple(other for other in filed if other.number != anchor.number)
    reading = _reading(read(anchor, around, developers))
    developer = developer_for(_first(item.grantors), developers)
    scan = scans.get(item.number)
    placed, scan_path, source = _placement(scan, apn, blocks, address, anchor, step, association)
    event = by_event.get(item.number)
    reassesses = any(number == item.number for number in audit.reassessing.values())
    price = scan.price if scan is not None else None
    process_name = reading.process if reading else ("developer grant" if developer else "")
    return HistoryStep(
        order,
        item.number,
        item.recorded,
        item.grantors,
        item.grantees,
        step.priors,
        process_name,
        reading.complete if reading else False,
        reassesses,
        developer.name if developer else "",
        price.price_cents if price else None,
        price.county_tax_cents if price else None,
        price.city_tax_cents if price else None,
        bool(price.exempt) if price else False,
        event.year if event else None,
        event.enrolled_cents if event else None,
        event.prior_enrolled_cents if event else None,
        placed,
        scan_path,
        source,
        _related(reading, anchor, loader, scans) if reading else (),
        notes(item.number) if notes else (),
        unpriced_reason(scan, reassesses, process_name),
    )


def unpriced_reason(scan: DeedScan | None, reassesses: bool, process: str) -> str:
    """Why a sale carries no price, in one phrase. Empty when it has one or needs none."""
    if not reassesses:
        return ""
    price = scan.price if scan is not None else None
    if price is not None and price.price_cents:
        return ""
    if scan is None:
        return "no scan on disk"
    if price is not None and price.exempt:
        return "exempt from transfer tax"
    if price is not None and price.county_tax_cents == 0:
        return "tax declared separately, not on the deed"
    if process == "foreclosure":
        return "trustee's deed prints the bid, not a tax"
    if price is not None and price.county_tax_cents and price.city_tax_cents:
        return "county and city figures disagree"
    return "tax line not readable on the scan"


def _reading(readings: tuple[Reading, ...]) -> Reading | None:
    if not readings:
        return None
    for reading in readings:
        if reading.complete:
            return reading
    return readings[0]


def _with_beside(steps: tuple[HistoryStep, ...], load_naming, loader, chain_numbers: frozenset[str] = frozenset()) -> tuple[HistoryStep, ...]:
    """Each step with the re-recordings and companion transfers the index holds beside it.

    The process reading lists what a deed's same-day neighbors are. A
    correcting deed recorded weeks later, or a family transfer filed at the
    closing under a number the reading did not reach, is found by the
    step's grantees and ``processes.beside_step``. A chain step of any
    parcel (``chain_numbers``) is never listed beside another: a buyer who
    took two units the same day has two deeds, not a deed and its twin.
    """
    from dataclasses import replace

    chain = {step.number for step in steps} | set(chain_numbers)
    out: list[HistoryStep] = []
    for step in steps:
        listed = {item.number for item in step.related}
        step_doc = loader(step.number)
        extra: list[RelatedInstrument] = []
        for name in step.grantees:
            if not name.strip():
                continue
            for item in load_naming(name):
                if item.number in chain or item.number in listed:
                    continue
                found = beside_step(item, step.number, step_doc, step.grantees)
                if found is None:
                    continue
                listed.add(item.number)
                role, why = found
                extra.append(RelatedInstrument(
                    role, item.number, why, item.recorded, item.kind, f"{item.filing_code} {item.filing_name}".strip(), item.grantors, item.grantees,
                ))
        out.append(replace(step, related=step.related + tuple(sorted(extra, key=lambda r: (r.recorded or date.min, r.number)))) if extra else step)
    return tuple(out)


def _related(
    reading: Reading,
    anchor: FiledInstrument,
    loader: Callable[[str], FiledInstrument | None],
    scans: dict[str, DeedScan],
) -> tuple[RelatedInstrument, ...]:
    found: list[RelatedInstrument] = []
    for slot in reading.slots:
        if not slot.number or slot.number == anchor.number or slot.reason not in _LISTED:
            continue
        item = loader(slot.number)
        scan = scans.get(slot.number)
        if item is None:
            found.append(RelatedInstrument(slot.role, slot.number, slot.reason, scan=str(scan.path.name) if scan else ""))
            continue
        found.append(
            RelatedInstrument(
                slot.role,
                slot.number,
                slot.reason,
                item.recorded,
                item.kind,
                f"{item.filing_code} {item.filing_name}".strip(),
                item.grantors,
                item.grantees,
                str(scan.path.name) if scan else "",
            )
        )
    return tuple(found)


def _placement(
    scan: DeedScan | None,
    apn: str,
    blocks: tuple[PlanBlock, ...],
    address: str,
    anchor: FiledInstrument,
    step: ChainStep,
    association: bool = False,
) -> tuple[str, str, str]:
    if scan is not None:
        how = placement(scan, apn, blocks, address)
        if association and how in ("other parcel", "other unit"):
            # A land deed lists every parcel it conveys; naming others is not a contradiction here.
            how = ""
        if how == "other parcel":
            return ("scan prints another parcel", scan.path.name, scan.source)
        if how == "other unit":
            return ("scan prints another unit", scan.path.name, scan.source)
        if how:
            return (f"scan: {how}", scan.path.name, scan.source)
    if any(prior in anchor.cross_references for prior in step.priors):
        return ("citation", scan.path.name if scan else "", scan.source if scan else "")
    if step.priors:
        return ("handoff", scan.path.name if scan else "", scan.source if scan else "")
    return ("root", scan.path.name if scan else "", scan.source if scan else "")


def _base(
    ordered: list[ChainStep],
    history: OwnershipHistory,
    prices: dict[str, int],
    years: list[int],
) -> tuple[int, int] | None:
    if not years:
        return None
    reassessing = reassessing_steps(history)
    best: tuple[int, int] | None = None
    for year, number in sorted(reassessing.items()):
        price = prices.get(number)
        if year <= years[0] and price:
            best = (year, price)
    return best


def _filed(item, loader: Callable[[str], FiledInstrument | None]) -> FiledInstrument:
    cached = loader(item.number)
    if cached is not None:
        return cached
    kind = "foreclosure" if any("TRUSTEE" in name.upper() or " RECON" in f" {name.upper()}" for name in item.grantors) and len(item.grantors) > 1 else "fee"
    return FiledInstrument(item.number, item.recorded, kind, item.grantors, item.grantees, item.cross_references)


def _first(names: tuple[str, ...]) -> str:
    for name in names:
        if name.strip():
            return name
    return ""
