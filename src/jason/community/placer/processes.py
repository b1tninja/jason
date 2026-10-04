"""Conveyance process readings for Placer chain steps.

Placer numbers run through the year (``YYYY-NNNNNNN``), and a closing's
instruments take consecutive numbers just as Sacramento's do: the notice of
completion before a builder's grant, the buyer's deed of trust after it, a
reconveyance of the seller's loan beside it. So each chain deed is read with
the numbers around it, fetched in one number-range search, and
``processes.read`` names the process with the Placer recorder's numbering.
A neighbor recorded on another day does not fill a same-day seat.

Two things differ from Sacramento. KoFile lists a document that is two
instruments (a substitution of trustee and its reconveyance) as two rows
with one number; ``filed_instruments`` makes them one. And the index lists no
citations, so a prior-deed seat is filled from the chain's earlier deeds by
party (the deed that vested this grantor), never by searching.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from asspy.placer.filings import filed_instruments
from jason.community.base import Developer
from jason.community.placer.filings import filed_instrument
from jason.community.placer.recorder import PlacerCountyRecorder, PlacerSession, normalize_document_number
from jason.community.processes import _NOTICE_REACH, Reading, read
from jason.community.recorder import (
    Conveyance,
    FiledInstrument,
    IndexedInstrument,
    OwnershipHistory,
    same_party,
)

# Numbers read after a chain deed: the buyer's deed of trust, companion vestings, a same-day reconveyance.
AFTER = 4


@dataclass(frozen=True)
class ProcessStep:
    """One chain deed with its process reading and the same-day instruments around it."""

    number: str
    recorded: date | None
    kind: str
    filing_name: str
    grantors: tuple[str, ...]
    grantees: tuple[str, ...]
    process: str
    complete: bool
    reassesses: bool
    companions: tuple[FiledInstrument, ...]
    reading: Reading | None


def neighbors(
    recorder: PlacerCountyRecorder,
    number: str,
    *,
    before: int = _NOTICE_REACH,
    after: int = AFTER,
    session: PlacerSession | None = None,
    fetch=None,
    index=None,
    search: bool = True,
) -> tuple[FiledInstrument, ...]:
    """The instruments numbered around ``number``, the anchor included, one per number.

    One number-range search covers them; a document listed as two rows is one instrument.
    With ``index`` (a ``PlacerIndex``) the range is read from the cache, and searched and
    stored only the first time; ``search=False`` reads only what the cache holds.
    """
    if index is not None:
        return index.around(number, before=before, after=after, search=search)
    around = recorder.nearby(number, before=before, after=after)
    if not around:
        return ()
    low, high = min((number, *around)), max((number, *around))
    rows = recorder.search(number=low, number_to=high, rows=before + after + 20, session=session, fetch=fetch)
    return filed_instruments(rows)


def read_chain(
    history: OwnershipHistory,
    *,
    recorder: PlacerCountyRecorder | None = None,
    session: PlacerSession | None = None,
    fetch=None,
    developers: tuple[Developer, ...] = (),
    index=None,
    search: bool = True,
) -> tuple[ProcessStep, ...]:
    """Process reading for each step on a walked ownership history.

    The anchor is the index's own instrument for the step's number (a
    trustee's deed reads as a foreclosure, a quitclaim as a fee), with the
    parties the detail page named. The chain's other deeds ride along so a
    resale's prior deed can be found by party. ``index`` (a ``PlacerIndex``)
    reads each step's neighbors from the cache; with ``search=False`` it reads
    only the rows party searches already stored there, and searches nothing.
    """
    county = recorder or (index.recorder if index is not None else PlacerCountyRecorder())
    active = session
    if active is None and index is None:
        active = county.open_session(fetch=fetch)
        if active is None:
            return ()
    chain = tuple(_chain_instrument(step.conveyance) for step in history.steps)
    steps: list[ProcessStep] = []
    for step, deed in zip(history.steps, chain):
        item = step.conveyance
        nearby = neighbors(county, item.number, session=active, fetch=fetch, index=index, search=search)
        anchor = _anchor(deed, next((found for found in nearby if found.number == deed.number), None))
        around = tuple(found for found in nearby if found.number != anchor.number) + tuple(
            other for other in chain if other.number != anchor.number and other.number not in {found.number for found in nearby}
        )
        readings = read(anchor, around, developers or history.developers, recorder=county)
        reading = _best(readings)
        companions = _related(anchor, nearby, reading)
        steps.append(
            ProcessStep(
                number=item.number,
                recorded=anchor.recorded,
                kind=anchor.kind,
                filing_name=anchor.filing_name,
                grantors=anchor.grantors,
                grantees=anchor.grantees,
                process=reading.process if reading else "",
                complete=reading.complete if reading else False,
                reassesses=reading.reassesses if reading else True,
                companions=companions,
                reading=reading,
            )
        )
    return tuple(steps)


def process_markdown(steps: tuple[ProcessStep, ...]) -> str:
    """Table of process readings and the related seats each one still needs."""
    lines = [
        "## Conveyance processes",
        "",
        "| Document | Recorded | Kind | Process | Complete | Reassesses | Same-day instruments of this closing |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not steps:
        lines.append("| | | | | | | |")
    for step in steps:
        companions = ", ".join(
            f"{item.number} ({item.kind or item.filing_name})" for item in step.companions
        )
        lines.append(
            f"| {step.number} | {step.recorded or ''} | {step.kind} | {step.process} | "
            f"{'yes' if step.complete else ''} | {'yes' if step.reassesses else ''} | {companions} |"
        )
    seats = [
        (step.number, item.role, item.reason, item.number)
        for step in steps
        if step.reading is not None
        for item in step.reading.slots
        if item.required or item.reason == "present"
    ]
    if seats:
        lines.extend(["", "### Seats", "", "| Document | Seat | Status | Filled by |", "| --- | --- | --- | --- |"])
        for number, role, reason, filled in seats:
            lines.append(f"| {number} | {role} | {reason} | {filled if reason == 'present' else ''} |")
    lines.append("")
    return "\n".join(lines)


def _anchor(deed: FiledInstrument, indexed: FiledInstrument | None) -> FiledInstrument:
    """The index's instrument for this number with the detail page's parties; the chain's deed when the index has none."""
    if indexed is None:
        return deed
    return FiledInstrument(
        deed.number,
        indexed.recorded or deed.recorded,
        indexed.kind or deed.kind,
        deed.grantors or indexed.grantors,
        deed.grantees or indexed.grantees,
        (),
        indexed.filing_code,
        indexed.filing_name,
    )


def _chain_instrument(item: Conveyance) -> FiledInstrument:
    """A chain step as a fee instrument: the walk kept it because it conveys."""
    found = filed_instrument(_row_from_conveyance(item))
    return FiledInstrument(
        normalize_document_number(item.number) or item.number,
        item.recorded,
        found.kind or "fee",
        item.grantors,
        item.grantees,
        (),
        found.filing_code,
        found.filing_name,
    )


def _related(anchor: FiledInstrument, nearby: tuple[FiledInstrument, ...], reading: Reading | None) -> tuple[FiledInstrument, ...]:
    """The same-day neighbors that belong to this closing: a filled seat, or one naming a party of the deed.

    A neighbor that names none of them is another parcel's closing.
    """
    filled = {item.number for item in (reading.slots if reading else ()) if item.reason == "present"}
    parties = [name for name in (*anchor.grantors, *anchor.grantees) if name.strip()]
    return tuple(
        item
        for item in nearby
        if item.number != anchor.number
        and anchor.recorded is not None
        and item.recorded == anchor.recorded
        and (item.number in filled or any(same_party(a, b) for a in parties for b in (*item.grantors, *item.grantees)))
    )


def _best(readings: tuple[Reading, ...]) -> Reading | None:
    if not readings:
        return None
    for reading in readings:
        if reading.complete:
            return reading
    return readings[0]


def _row_from_conveyance(item: Conveyance) -> IndexedInstrument:
    names = tuple(f"(R) {name}" for name in item.grantors) + tuple(
        f"(E) {name}" for name in item.grantees
    )
    return IndexedInstrument(
        number=item.number,
        recorded=item.recorded,
        sequence=item.number.split("-")[-1] if "-" in item.number else "",
        filing_code="",
        filing_name="DEED",
        names=names,
        internal_id="",
    )
