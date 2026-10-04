"""The breadth-first walk out from a Placer builder, through the cached index.

Sacramento's ``index_cache.builder_leaf`` and ``descend`` search a developer
by name under a filing code and follow the detail pages' citations. Placer's
index has neither a filing filter on a plain name search nor citations, but
it filters by document type, and a party name takes ``%``. So:

* Leaf 1 is every fee deed and notice of completion the developer's name
  (``FORM%``) is on inside the date window, one type search split by halves
  until each window fits a page (``PlacerIndex.typed``). A deed whose grantor
  is a pinned developer is a developer grant: one lot's first conveyance.
  Each grant's numbered neighbors are stored too (the notice of completion
  before it, the buyer's deed of trust after it), in as few range searches
  as the numbers allow.
* Leaf 2 and on search each buyer's name once for the fee types and place
  each later deed the buyer granted, one leaf across every lot before any
  lot goes farther. A name too common to read whole is not followed.
* ``currents`` (APN to the assessor's current instrument) are loaded so a
  lot can meet its parcel: the same document, or a handoff by name
  (``index_cache.find_meets``). The detail page carries no APN, so the
  assessor's instrument is the only tie from a lot to a parcel.

Each lot becomes an ``OwnershipHistory`` (``succession`` over its deeds).
A deed reached from two lots (a buyer of two units) stays on both and is
listed as shared: the index cannot say which unit it conveys.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from asspy.core import FiledInstrument
from asspy.placer.filings import COMPLETION_TYPES, FEE_TYPES, type_ids
from jason.community.base import Developer
from jason.community.index_cache import Meet, find_meets, keeps_developer, skip_lender
from jason.community.placer.index import PlacerIndex
from jason.community.placer.parcel import conveyance, same_owner
from jason.community.recorder import (
    OwnershipHistory,
    _follow,
    index_name,
    owner_restatement,
    succession,
)

__all__ = ("PlacerDescent", "PlacerLot", "descend", "developer_seed", "later_deeds", "store_neighbors")

# Numbers before a grant its notice of completion can sit, and after it the buyer's deed of trust.
BEFORE = 3
AFTER = 4
# The widest range one neighbor search covers; farther grants get their own.
SPAN = 60


@dataclass(frozen=True)
class PlacerLot:
    """One developer grant and every later deed reached from it."""

    grant: FiledInstrument
    numbers: tuple[str, ...]
    history: OwnershipHistory
    apn: str = ""
    shared: tuple[str, ...] = ()

    @property
    def newest(self) -> str:
        return self.history.steps[0].conveyance.number if self.history.steps else self.grant.number


@dataclass(frozen=True)
class PlacerDescent:
    """A Placer subdivision's ownership reconstructed from its builder."""

    developers: tuple[Developer, ...]
    after: date
    before: date
    depth: int
    grants: tuple[FiledInstrument, ...]
    notices: tuple[FiledInstrument, ...]
    lots: tuple[PlacerLot, ...]
    meets: tuple[Meet, ...]
    wide: tuple[str, ...]
    # True when each deed's numbered neighbors were searched; False when only party searches filled the cache.
    neighbors: bool = True

    def lot(self, apn: str) -> PlacerLot | None:
        digits = "".join(ch for ch in apn if ch.isdigit())
        return next((item for item in self.lots if item.apn == digits), None)


def developer_seed(
    index: PlacerIndex,
    developers: tuple[Developer, ...],
    *,
    after: date,
    before: date,
) -> tuple[tuple[FiledInstrument, ...], tuple[FiledInstrument, ...]]:
    """The developer's grants and notices of completion in the window, by type search on each name form."""
    # The partial reconveyances of the builder's blanket loan ride along: a blanket release's seat.
    types = type_ids(FEE_TYPES + COMPLETION_TYPES + ("PARTIAL RECONVEYANCE",))
    forms: list[str] = []
    for developer in developers:
        for name in developer.names:
            query = " ".join(name.upper().split())
            query = query if "%" in query else f"{query}%"
            if query not in forms:
                forms.append(query)
    grants: dict[str, FiledInstrument] = {}
    notices: dict[str, FiledInstrument] = {}
    for query in forms:
        for item in index.instruments(index.typed(types, after=after, before=before, name=query)):
            if item.kind == "notice" and any(keeps_developer(name, developers) for name in (*item.grantors, *item.grantees)):
                notices.setdefault(item.number, item)
            elif item.kind == "fee" and any(keeps_developer(name, developers) for name in item.grantors):
                if all(keeps_developer(name, developers) for name in item.grantees if name.strip()):
                    index.cache.note(item.number, "developer to developer; not a lot sale")
                    continue
                if item.grantees and all(_association(name) for name in item.grantees if name.strip()):
                    index.cache.note(item.number, "common area deeded to the association; not a lot sale")
                    continue
                grants.setdefault(item.number, item)
    return tuple(sorted(grants.values(), key=_order)), tuple(sorted(notices.values(), key=_order))


def store_neighbors(index: PlacerIndex, numbers, *, before: int = BEFORE, after: int = AFTER, span: int = SPAN) -> int:
    """Store the numbers around each of ``numbers``, joining nearby windows into one range search. Returns the searches run."""
    windows: list[tuple[str, int, int]] = []
    for number in sorted(set(numbers)):
        year, _, seq = number.partition("-")
        if not seq.isdigit():
            continue
        low, high = max(int(seq) - before, 1), int(seq) + after
        if windows and windows[-1][0] == year and low <= windows[-1][2] + 1 and high - windows[-1][1] <= span:
            windows[-1] = (year, windows[-1][1], max(high, windows[-1][2]))
        else:
            windows.append((year, low, high))
    for year, low, high in windows:
        index.range(f"{year}-{low:07d}", f"{year}-{high:07d}")
    return len(windows)


def later_deeds(
    index: PlacerIndex,
    party: str,
    *,
    after: FiledInstrument,
    limit: int = 200,
) -> tuple[FiledInstrument, ...] | None:
    """The fee deeds and trustee's deeds ``party`` granted after the deed ``after``; None when the name is too common.

    The name is searched for every type first, so the one search also stores
    the buyer's deed of trust at the closing and the loans and liens that
    name them (``cache_owner_filings`` finds it in the cache); a name with
    more rows than ``limit`` is searched again for the fee types alone.
    """
    query = index_name(party) or " ".join(party.upper().split())
    if not query:
        return ()
    found = index.name(query, limit=limit)
    if found.wide:
        found = index.name(query, types=type_ids(FEE_TYPES), limit=limit)
    if found.wide:
        found = index.name(query, types=type_ids(FEE_TYPES), after=after.recorded, limit=limit)
        if found.wide:
            return None
    return tuple(
        item
        for item in index.instruments(found)
        if item.kind in ("fee", "foreclosure")
        and item.number != after.number
        and _later(item, after)
        and any(same_owner(party, name) for name in item.grantors)
    )


def descend(
    index: PlacerIndex,
    *,
    developers: tuple[Developer, ...],
    after: date,
    before: date | None = None,
    depth: int = 2,
    currents: dict[str, str] | None = None,
    limit: int = 200,
    neighbors: bool = True,
    note=None,
) -> PlacerDescent:
    """Walk out from the builder ``depth`` leaves (1: the grants; 2: each buyer's next deed; …).

    ``neighbors`` searches each deed's numbered neighbors (a range search per
    run of nearby numbers): complete, and slow on a large subdivision. Without
    it the cache holds what the builder's and buyers' own searches returned,
    which is every seat that names them (the notice, the buyer's loan, a
    companion vesting), and the readings say so (``PlacerDescent.neighbors``).
    """
    end = before or date.today()
    grants, notices = developer_seed(index, developers, after=after, before=end)
    if neighbors and grants:
        store_neighbors(index, tuple(item.number for item in grants))
    reached: dict[str, FiledInstrument] = {item.number: item for item in grants}
    sources: dict[str, list[str]] = {item.number: [] for item in grants}
    frontier = list(grants)
    wide: list[str] = []
    searched: set[str] = set()
    for leaf in range(2, max(depth, 1) + 1):
        layer: list[FiledInstrument] = []
        for item in frontier:
            for party in item.grantees:
                if not party.strip() or not _follow(party, developers) or skip_lender(party) or _association(party):
                    continue
                key = f"{index_name(party)}|{item.number}"
                if key in searched:
                    continue
                searched.add(key)
                if note is not None:
                    note(f"leaf {leaf}: {index_name(party)}")
                later = later_deeds(index, party, after=item, limit=limit)
                if later is None:
                    if index_name(party) not in wide:
                        wide.append(index_name(party))
                    continue
                for deed in later:
                    sources.setdefault(deed.number, [])
                    if item.number not in sources[deed.number]:
                        sources[deed.number].append(item.number)
                    if deed.number not in reached:
                        reached[deed.number] = deed
                        layer.append(deed)
                        if owner_restatement(deed.grantors, deed.grantees):
                            index.cache.note(deed.number, "same owner restatement; not a new buyer")
        if neighbors and layer:
            store_neighbors(index, tuple(deed.number for deed in layer))
        frontier = layer
        if not frontier:
            break

    current_side: dict[str, FiledInstrument] = {}
    for apn, number in (currents or {}).items():
        item = index.number(number)
        if item is None or item.kind not in ("fee", "foreclosure"):
            continue
        current_side[item.number] = item
        index.cache.set_apn(item.number, apn)
        index.cache.note(item.number, "assessor's current instrument")
    first_source = {number: (found[0] if found else "") for number, found in sources.items()}
    meets = find_meets(current_side, reached, {number: "" for number in current_side}, first_source)

    roots = {number: _roots(number, sources) for number in reached}
    lots: list[PlacerLot] = []
    for grant in grants:
        numbers = [number for number in sorted(reached, key=lambda each: _order(reached[each])) if grant.number in roots[number]]
        shared = tuple(number for number in numbers if len(roots[number]) > 1)
        apn = ""
        for meet in meets:
            if meet.developer in numbers:
                apn = next((key for key, value in (currents or {}).items() if value == meet.current), "")
                if meet.current not in numbers:
                    numbers.append(meet.current)
                for number in meet.numbers:
                    if number in reached and number not in numbers:
                        numbers.append(number)
                break
        items = tuple(item for number in numbers if (item := reached.get(number) or current_side.get(number)) is not None)
        digits = "".join(ch for ch in apn if ch.isdigit())
        history = succession(tuple(conveyance(item, digits) for item in items), apn=digits, developers=developers)
        if digits:
            for number in numbers:
                index.cache.note(number, f"lot of {digits} from builder grant {grant.number}")
        lots.append(PlacerLot(grant, tuple(numbers), history, digits, shared))
    return PlacerDescent(
        developers, after, end, depth, grants, notices, tuple(lots), meets, tuple(wide), neighbors,
    )


def _roots(number: str, sources: dict[str, list[str]]) -> frozenset[str]:
    """The developer grants a reached deed descends from."""
    found: set[str] = set()
    pending = [number]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        parents = sources.get(current, [])
        if not parents:
            found.add(current)
        pending.extend(parents)
    return frozenset(found)


def _later(item: FiledInstrument, earlier: FiledInstrument) -> bool:
    if item.recorded is None or earlier.recorded is None:
        return False
    if item.recorded > earlier.recorded:
        return True
    return item.recorded == earlier.recorded and item.number > earlier.number


def _order(item: FiledInstrument) -> tuple[date, str]:
    return (item.recorded or date.min, item.number)


def _association(name: str) -> bool:
    """An association party: a common-area deed's grantee is not a buyer to follow."""
    from asspy.associations import Kind, kind

    return kind(name) in (Kind.HOMEOWNERS, Kind.COMMERCIAL, Kind.MAINTENANCE, Kind.TIMESHARE)


