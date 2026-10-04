"""Walk Placer deed history from the assessor's current instrument.

Starts at one parcel's current recorder number, searches each grantor for
earlier fee deeds on which that person was the grantee, and links the loaded
instruments with the shared ``succession`` graph. Each fee step then gets a
conveyance process reading (resale, restatement, foreclosure, …) with
same-day companions gathered by party. The Mermaid diagram is the same
succession report Sacramento uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from asspy.placer.filings import conveys
from jason.community.base import Developer
from jason.community.history_report import history_markdown, mermaid_succession
from jason.community.placer.assessor import PlacerCountyAssessor, PlacerParcel
from jason.community.placer.processes import ProcessStep, process_markdown, read_chain
from jason.community.placer.recorder import PlacerCountyRecorder, PlacerSession, normalize_document_number
from jason.community.recorder import (
    OwnershipHistory,
    _follow,
    is_developer,
)


@dataclass(frozen=True)
class PlacerOwnershipWalk:
    """One parcel's walked deed history, process readings, and report text."""

    parcel: PlacerParcel
    history: OwnershipHistory
    processes: tuple[ProcessStep, ...]
    markdown: str

    @property
    def mermaid(self) -> str:
        return mermaid_succession(self.history)


def walk_ownership(
    query: str,
    *,
    kind: str = "idaddress",
    hops: int = 6,
    priors_per_grantor: int = 3,
    name_limit: int = 40,
    developers: tuple[Developer, ...] = (),
    assessor: PlacerCountyAssessor | None = None,
    recorder: PlacerCountyRecorder | None = None,
    session: PlacerSession | None = None,
    fetch=None,
) -> PlacerOwnershipWalk | None:
    """Trace fee deeds back from a Placer address, APN, or document number.

    ``kind`` is an assessor search kind when ``query`` is not already an APN
    or document number: ``idaddress``, ``idasmt``, ``idfeeparcel``, or
    ``idowner``.
    """
    asr = assessor or PlacerCountyAssessor()
    index = recorder or PlacerCountyRecorder()
    parcel = _resolve_parcel(asr, query, kind=kind, fetch=fetch)
    if parcel is None or not parcel.document_number:
        return None
    active = session or index.open_session(fetch=fetch)
    if active is None:
        return None
    numbers = _discover_numbers(
        index,
        parcel.document_number,
        hops=hops,
        priors_per_grantor=priors_per_grantor,
        name_limit=name_limit,
        developers=developers,
        session=active,
        fetch=fetch,
    )
    history = index.history(
        tuple(numbers),
        apn=parcel.apn,
        developers=developers,
        session=active,
        fetch=fetch,
    )
    processes = read_chain(
        history,
        recorder=index,
        session=active,
        fetch=fetch,
        developers=developers,
    )
    title = parcel.address or parcel.apn
    note = (
        f"Placer County APN {parcel.apn}. Current instrument "
        f"{parcel.document_number}"
        + (f" recorded {parcel.document_date.isoformat()}." if parcel.document_date else ".")
    )
    body = history_markdown(title, history, note=note).rstrip() + "\n\n" + process_markdown(processes)
    return PlacerOwnershipWalk(
        parcel=parcel,
        history=history,
        processes=processes,
        markdown=body,
    )


def _resolve_parcel(
    assessor: PlacerCountyAssessor,
    query: str,
    *,
    kind: str,
    fetch=None,
) -> PlacerParcel | None:
    text = str(query or "").strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    # Placer APNs are twelve digits and do not start with a recording year.
    if len(digits) == 12 and text.replace("-", "").isdigit() and not normalize_document_number(text):
        return assessor.parcel(digits, fetch=fetch)
    doc = normalize_document_number(text)
    if doc:
        # Document number alone: synthesize a parcel shell; caller still walks deeds.
        return PlacerParcel(apn="", address="", document_number=doc)
    hits = assessor.search(text, kind=kind, fetch=fetch)
    if not hits:
        return None
    return assessor.parcel(hits[0].apn, fetch=fetch)


def _discover_numbers(
    recorder: PlacerCountyRecorder,
    start: str,
    *,
    hops: int,
    priors_per_grantor: int,
    name_limit: int,
    developers: tuple[Developer, ...],
    session: PlacerSession,
    fetch=None,
) -> list[str]:
    """Breadth-first prior-deed discovery from the current instrument."""
    start_number = normalize_document_number(start) or start
    pending = [start_number]
    ordered: list[str] = []
    seen: set[str] = set()
    for _ in range(max(hops, 0) + 1):
        wave: list[str] = []
        for number in pending:
            if not number or number in seen:
                continue
            seen.add(number)
            ordered.append(number)
            conveyance = recorder._conveyance(number, apn="", session=session, fetch=fetch)
            if any(is_developer(name, developers) for name in conveyance.grantors):
                continue
            if conveyance.recorded is None:
                continue
            for grantor in conveyance.grantors:
                if not _follow(grantor, developers):
                    continue
                priors = recorder.prior_candidates(
                    grantor,
                    before=conveyance.recorded,
                    limit=name_limit,
                    session=session,
                    fetch=fetch,
                )
                fee = [row for row in priors if conveys(row)]
                fee.sort(key=lambda row: row.recorded or date.min, reverse=True)
                for row in fee[: max(priors_per_grantor, 0)]:
                    prior = normalize_document_number(row.number) or row.number
                    if prior and prior not in seen:
                        wave.append(prior)
        pending = wave
        if not pending:
            break
    return ordered
