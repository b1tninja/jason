"""One Placer parcel's history from the cached index, in Sacramento's ``ParcelHistory`` shape.

The steps are Sacramento's, read against Placer's index:

1. The assessor names the parcel's current instrument (Placer prints it as
   ``YYYYRNNNNNNN``; the detail page carries no APN, so the assessor is the
   only tie from a number to a parcel).
2. Each grantor's earlier fee deeds are found by name, narrowed to the fee
   types, kept when the grantor was their grantee (``chain_numbers``). No
   detail page cites a prior deed, so the link is always the party handoff.
3. ``succession`` orders them into an ``OwnershipHistory``.
4. Each step's numbered neighbors are stored (one range search per step),
   and every owner's other filings are stored by name (``cache_owner_filings``):
   the loans, liens, releases, defaults, and notices that name them.
5. ``read_chain`` names each step's process with Placer's numbering, and
   ``build_parcel_history`` assembles the same ``ParcelHistory`` a
   Sacramento unit has: steps with related instruments, the liens by
   tenure (``parcel_liens`` over ``asspy.filings.encumbrances``), owner
   events, and each lien's standing (``title.lien_standing``).

Everything is read through one ``PlacerIndex``, so a second run searches
nothing it has seen. A reading is a lead, not a pin: a handoff by name can
join a namesake's deed, and the report says how each step was placed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from asspy.core import FiledInstrument, Parcel
from asspy.names import name_keeps
from asspy.placer.filings import FEE_TYPES, LIEN_TYPES, type_ids
from jason.community.base import Developer
from jason.community.history_report import history_markdown, mermaid_succession
from jason.community.index_cache import skip_lender
from jason.community.ownership import OwnershipRecord
from jason.community.parcel_history import ParcelHistory, build_parcel_history
from jason.community.placer.assessor import PlacerCountyAssessor
from jason.community.placer.history import _resolve_parcel
from jason.community.placer.index import PlacerIndex, Searched, placer_index
from jason.community.placer.processes import ProcessStep, process_markdown, read_chain
from jason.community.placer.recorder import normalize_document_number
from jason.community.recorder import (
    Conveyance,
    OwnershipHistory,
    _follow,
    developer_for,
    index_name,
    is_developer,
    same_party,
    succession,
)
from jason.community.title import lien_standing

__all__ = (
    "PlacerParcelRecord",
    "cache_owner_filings",
    "chain_numbers",
    "conveyance",
    "parcel_markdown",
    "parcel_record",
    "placer_parcel_history",
    "prior_deeds",
)

# The most rows one owner's name may return before it is narrowed to the lien types.
OWNER_LIMIT = 200


@dataclass(frozen=True)
class PlacerParcelRecord:
    """One Placer parcel: the assessor's parcel, its chain, the Placer readings, and the shared ``ParcelHistory``."""

    parcel: Parcel
    history: OwnershipHistory
    processes: tuple[ProcessStep, ...]
    parcel_history: ParcelHistory
    owner_searches: tuple[Searched, ...] = ()

    @property
    def mermaid(self) -> str:
        return mermaid_succession(self.history)

    @property
    def markdown(self) -> str:
        return parcel_markdown(self)


_SUFFIXES = frozenset({"JR", "SR", "II", "III", "IV"})


def same_owner(left: str, right: str) -> bool:
    """One owner under two index spellings, strict enough to keep a namesake out.

    ``same_party`` lets an index drop a middle initial (``SAMPLE ANN`` is
    ``SAMPLE ANN M``); a hyphen is not a different name; but a generational
    suffix on one side and not the other is another person.
    """
    a, b = left.replace("-", ""), right.replace("-", "")
    if name_keeps(a, b):
        return True
    if not same_party(a, b):
        return False
    return {word for word in a.upper().split() if word in _SUFFIXES} == {word for word in b.upper().split() if word in _SUFFIXES}


def conveyance(item: FiledInstrument, apn: str = "") -> Conveyance:
    """The succession row for one cached instrument."""
    return Conveyance(item.number, item.recorded, item.grantors, item.grantees, item.cross_references, apn)


def prior_deeds(
    index: PlacerIndex,
    grantor: str,
    *,
    before: date,
    limit: int = 40,
) -> tuple[FiledInstrument, ...]:
    """Fee deeds recorded before ``before`` on which ``grantor`` is a grantee, newest first.

    The name is searched once for the fee types and reused for every date;
    only when that is wider than ``limit`` is it searched again up to
    ``before``. A name still wide is not followed: the deed it needs may be
    among the rows left out.
    """
    query = index_name(grantor) or " ".join(grantor.upper().split())
    if not query:
        return ()
    fee = type_ids(FEE_TYPES)
    found = index.name(query, types=fee, limit=limit)
    if found.wide:
        found = index.name(query, types=fee, before=before, limit=limit)
        if found.wide:
            return ()
    items = [
        item
        for item in index.instruments(found)
        if item.kind in ("fee", "foreclosure")
        and item.recorded is not None
        and item.recorded < before
        and any(same_owner(grantor, name) for name in item.grantees)
    ]
    items.sort(key=lambda item: (item.recorded or date.min, item.number), reverse=True)
    return tuple(items)


def chain_numbers(
    index: PlacerIndex,
    start: str,
    *,
    hops: int = 6,
    priors_per_grantor: int = 3,
    name_limit: int = 40,
    developers: tuple[Developer, ...] = (),
) -> tuple[str, ...]:
    """Breadth-first prior-deed discovery from one instrument, through the cache.

    A grant from a pinned developer ends its branch: that is the subdivider's
    first conveyance of the lot.
    """
    first = normalize_document_number(start) or start
    pending = [first]
    ordered: list[str] = []
    seen: set[str] = set()
    for _ in range(max(hops, 0) + 1):
        wave: list[str] = []
        for number in pending:
            if not number or number in seen:
                continue
            seen.add(number)
            item = index.number(number)
            if item is None:
                continue
            ordered.append(item.number)
            if item.recorded is None or any(is_developer(name, developers) for name in item.grantors):
                continue
            for grantor in item.grantors:
                if not _follow(grantor, developers):
                    continue
                for prior in prior_deeds(index, grantor, before=item.recorded, limit=name_limit)[: max(priors_per_grantor, 0)]:
                    if prior.number not in seen:
                        wave.append(prior.number)
        pending = wave
        if not pending:
            break
    return tuple(ordered)


def cache_owner_filings(
    index: PlacerIndex,
    history: OwnershipHistory,
    *,
    developers: tuple[Developer, ...] = (),
    association: str = "",
    limit: int = OWNER_LIMIT,
) -> tuple[Searched, ...]:
    """Store every filing that names an owner on the chain: loans, liens, releases, defaults, notices.

    Placer's name search returns every type at once. A name with more rows
    than ``limit`` is searched again under the loan and lien types alone; a
    developer, a lender, and the association are not searched.
    """
    found: list[Searched] = []
    seen: set[str] = set()
    assn = " ".join(association.upper().split())
    for step in history.steps:
        for name in (*step.conveyance.grantees, *step.conveyance.grantors):
            query = index_name(name)
            if not query or query in seen:
                continue
            seen.add(query)
            if developer_for(name, developers) or skip_lender(name) or (assn and assn in name.upper()):
                continue
            searched = index.name(query, limit=limit)
            if searched.wide:
                searched = index.name(query, types=type_ids(LIEN_TYPES), limit=limit)
            found.append(searched)
    return tuple(found)


def placer_parcel_history(
    parcel: Parcel,
    history: OwnershipHistory,
    index: PlacerIndex,
    *,
    developers: tuple[Developer, ...] = (),
    association: str = "",
    solar_program=None,
) -> ParcelHistory:
    """The shared ``ParcelHistory`` for a Placer chain, read from the cache with Placer's numbering."""
    cache = index.cache
    if parcel.document_number:
        number = normalize_document_number(parcel.document_number) or parcel.document_number
        if cache.get(number) is not None and parcel.apn:
            cache.set_apn(number, parcel.apn)
            cache.note(number, "assessor's current instrument")
    current_item = cache.get(normalize_document_number(parcel.document_number) or parcel.document_number) if parcel.document_number else None
    current = (
        OwnershipRecord(
            parcel.apn,
            current_item.number,
            current_item.recorded or parcel.document_date or date.min,
            current_item.grantors,
            current_item.grantees,
            current_item.filing_name,
        )
        if current_item is not None
        else None
    )
    return build_parcel_history(
        parcel.apn,
        history=history,
        developers=developers,
        address=parcel.address,
        load=cache.get,
        notes=cache.notes,
        current=current,
        placed=cache.placed_on,
        load_naming=cache.naming_party,
        association_name=association,
        solar_program=solar_program,
        chain_numbers=frozenset(history.numbers),
        recorder=index.recorder,
    )


def parcel_record(
    query: str,
    *,
    kind: str = "idaddress",
    index: PlacerIndex | None = None,
    assessor: PlacerCountyAssessor | None = None,
    developers: tuple[Developer, ...] = (),
    association: str = "",
    solar_program=None,
    hops: int = 6,
    priors_per_grantor: int = 3,
    name_limit: int = 40,
    owner_filings: bool = True,
    fetch=None,
) -> PlacerParcelRecord | None:
    """Walk one Placer parcel (address, APN, or document number) into its full record, through the cache.

    ``fetch`` replaces the assessor's HTTP; the index's own ``fetch`` is set on ``index``.
    """
    asr = assessor or PlacerCountyAssessor()
    active = index or placer_index()
    parcel = _resolve_parcel(asr, query, kind=kind, fetch=fetch)
    if parcel is None or not parcel.document_number:
        return None
    numbers = chain_numbers(
        active,
        parcel.document_number,
        hops=hops,
        priors_per_grantor=priors_per_grantor,
        name_limit=name_limit,
        developers=developers,
    )
    loaded = tuple(item for number in numbers if (item := active.number(number)) is not None)
    history = succession(tuple(conveyance(item, parcel.apn) for item in loaded), apn=parcel.apn, developers=developers)
    for step in history.steps:
        active.around(step.conveyance.number)
    searches = cache_owner_filings(active, history, developers=developers, association=association) if owner_filings else ()
    processes = read_chain(history, index=active, developers=developers)
    built = placer_parcel_history(parcel, history, active, developers=developers, association=association, solar_program=solar_program)
    return PlacerParcelRecord(parcel, history, processes, built, searches)


def parcel_markdown(record: PlacerParcelRecord) -> str:
    """The chain table, the Mermaid succession, the process readings, and the liens with their standing."""
    parcel = record.parcel
    title = parcel.address or parcel.apn or parcel.document_number
    note = (
        f"Placer County APN {parcel.apn or 'unknown'}. Current instrument {parcel.document_number}"
        + (f" recorded {parcel.document_date.isoformat()}." if parcel.document_date else ".")
        + " Placer's index cites no prior deed, so each step is joined to the one before by the grantor's name;"
        " a namesake's deed can join the chain, and a person confirms a step from the deed's copy."
    )
    lines = [history_markdown(title, record.history, note=note).rstrip(), "", process_markdown(record.processes).rstrip(), ""]
    lines.extend(_liens_markdown(record.parcel_history))
    return "\n".join(lines).rstrip() + "\n"


def _liens_markdown(item: ParcelHistory) -> list[str]:
    lines = ["## Liens on the owners", ""]
    if not item.liens:
        lines.extend(["No loan, lien, or default in the cache names an owner on the chain.", ""])
        return lines
    lines.extend([
        "Each lifecycle names an owner by name; the standing is what the index shows, not a title report.",
        "",
        "| Owner | Process | Opened | Recorded | Status | Standing |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for lien in item.liens:
        e = lien.encumbrance
        reading = lien_standing(item, lien)
        lines.append(
            f"| {_cell(lien.owner)} | {e.process.value} | {e.opened.number} | "
            f"{e.opened.recorded.isoformat() if e.opened.recorded else ''} | {_cell(e.status)} | {reading.standing.name.lower().replace('_', ' ')} |"
        )
    lines.append("")
    return lines


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "/")
