"""Cached index hits, and a breadth-first walk out from the builder.

``IndexCache`` stores every document a search returns and the cross-references
on its detail page, not only the rows that matched the party filter. A later
pass can use those rows. Inferences are written back onto the document row:
a parcel APN, a note that two parties are the same owner, a cited prior, or
a row that belongs to another community.

``builder_leaf`` starts on the developer side inside a date window. Leaf 1 is
the developer grant itself. Leaf 2 is each buyer's next deed, one step across
every sale before any branch goes farther. A meet is not stored.
``chain_ready`` is that test: one developer grant, no gap, and one prior on
each later deed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from asspy.cache import IndexCache as _AsspyIndexCache
from asspy.cache import lines as _lines
from asspy.names import name_keeps
from jason.community.base import Developer
from jason.community.recorder import (
    Conveyance,
    DocType,
    FILING_NAMES,
    FiledInstrument,
    Filing,
    IndexedInstrument,
    IndexRole,
    InstrumentDetail,
    NARROW_FILINGS,
    OwnershipHistory,
    SacramentoCountyRecorder,
    _follow,
    advances_chain,
    closing_numbers,
    instrument_kind,
    name_covers,
    other_community,
    owner_restatement,
    party_key,
    party_role,
)

# Role words the index appends. They are not a different person.
_ROLE = frozenset({
    "TRUSTEE", "TRUST", "LLC", "INC", "CORP", "CORPORATION", "TR",
    "FMLY", "FAMILY", "REVOCABLE", "REV", "ETC",
})

_FEE = (Filing.GRANT_DEED, Filing.QUITCLAIM)
_FORECLOSURE = (DocType.TDSL, DocType.DILF)
_RELEASE = (DocType.RCNV,)
_PARTY_LIMIT = 40


def keeps_developer(name: str, developers: tuple[Developer, ...]) -> bool:
    """True when ``name`` is a pinned developer, not a longer business name.

    ``WL HOMES`` keeps ``WL HOMES LLC``. It does not keep ``WL HOMES INVS LLC``.
    ``WATT COMMUNITIES AT MYSTIQUE`` does not keep ``WATT COMMUNITIES LLC``.
    """
    return any(name_keeps(form, name) for developer in developers for form in developer.names)


def chain_ready(history: OwnershipHistory) -> bool:
    """True when one developer grant is the only root and each later deed has one prior.

    A root is a developer grant with no prior. A developer grant that hands
    off from an earlier one is that grant re-recorded, and it is a step, not
    a second root. Two priors mean more than one deed still fits. That chain
    is not stored.
    """
    roots = [
        step for step in history.steps if history.from_developer(step.conveyance) and not step.priors
    ]
    if not history.reached_developer or history.gaps or len(roots) != 1:
        return False
    return all(len(step.priors) <= 1 for step in history.steps)


def _identity(name: str) -> tuple[str, ...]:
    tokens = [part for part in " ".join(name.upper().split()).split() if part not in _ROLE]
    return tuple(sorted(tokens))


def _query_name(party: str) -> str:
    """The text the index matches from the front of a name.

    Role words are left off. The remaining words stay, so ``CAYMUS CAPITAL``
    is not every Caymus fund and ``VANTERPOOL LINH`` is not every Linh.
    ``ROE RICHARD P JR`` does not match the name without ``JR``.
    """
    tokens = [part for part in party_key(party).split() if part not in _ROLE]
    return " ".join(tokens)


def _filing_code(filing: Filing | DocType) -> str:
    return filing.code if isinstance(filing, DocType) else filing.value


def _search_key(query: str, filing: str, role: str, after: date | None, before: date | None) -> str:
    return "|".join((
        query,
        filing,
        role,
        after.isoformat() if after else "",
        before.isoformat() if before else "",
    ))


def _window(recorded: date | None, after: date | None, before: date | None) -> bool:
    if recorded is None:
        return False
    if after is not None and recorded < after:
        return False
    if before is not None and not recorded < before:
        return False
    return True


class IndexCache(_AsspyIndexCache):
    """County index cache (asspy) plus HOA walk annotations.

    Prefer ``County("sacramento").cache()`` for new code. Existing jason tasks
    still pass an explicit path under ``data/``.
    """

    def __init__(self, path: str | Path, *, county: str = "") -> None:
        super().__init__(path, county=county or Path(path).stem)

    def _annotate(self, item: FiledInstrument) -> None:
        """Write walk inferences onto the row after a classify or refresh."""
        super()._annotate(item)
        if item.kind == "fee" and owner_restatement(item.grantors, item.grantees):
            self.note(item.number, "same owner restatement; not a new buyer")
        if any(other_community(name) for name in (*item.grantors, *item.grantees)):
            self.note(item.number, "other community or association; not a unit sale")


@dataclass(frozen=True)
class Meet:
    """One place the two sides join, and the document numbers on that path."""

    kind: str
    current: str
    developer: str
    numbers: tuple[str, ...]


@dataclass(frozen=True)
class LeafResult:
    """One breadth-first step out from the builder.

    ``leaf`` 1 is the developer grant. ``leaf`` 2 is each buyer's next deed.
    ``sales`` are the developer grants still in play. ``reached`` is every fee
    or foreclosure on the builder frontier after this leaf. ``meets`` joins an
    open current deed. A meet is not stored.
    """

    leaf: int
    sales: tuple[str, ...]
    reached: tuple[str, ...]
    meets: tuple[Meet, ...]
    cached: int


@dataclass(frozen=True)
class Descent:
    """How far a multi-leaf walk went, and where the two sides joined."""

    depth: int
    meets: tuple[Meet, ...]
    current: tuple[str, ...]
    developer: tuple[str, ...]


def builder_leaf(
    recorder: SacramentoCountyRecorder,
    cache: IndexCache,
    *,
    currents: dict[str, str],
    developers: tuple[Developer, ...],
    after: date,
    before: date | None = None,
    leaf: int = 1,
    exclude: frozenset[str] = frozenset(),
    limit: int = _PARTY_LIMIT,
    session=None,
    fetch=None,
    note=None,
) -> LeafResult:
    """One leaf out from the builder across every branch.

    Leaf 1 searches each pinned developer for fee deeds in the date window and
    caches every returned row. A sale is walked when the grantor is a pinned
    developer and its number is not already on a solved chain. The same-day
    neighbors of each sale are loaded into the cache. Leaf 2 searches each
    buyer's next grant once, across every sale, and does not walk farther.
    ``currents`` maps an undashed APN to its current document number. Those
    deeds are loaded so a meet can be found. They are not expanded on the
    builder leaf.
    """
    if leaf < 1:
        return LeafResult(0, (), (), (), cache.count())
    session = session or recorder.open_session(fetch=fetch)
    if session is None:
        return LeafResult(leaf, (), (), (), cache.count())
    walker = _Walker(
        recorder,
        cache,
        developers=developers,
        after=after,
        developer_after=after,
        before=before,
        exclude=exclude,
        limit=limit,
        session=session,
        fetch=fetch,
        note=note,
    )
    current_side: dict[str, FiledInstrument] = {}
    current_from: dict[str, str] = {}
    for apn, number in currents.items():
        item = walker.load(number)
        if item is None or item.kind not in ("fee", "foreclosure"):
            continue
        current_side[item.number] = item
        current_from[item.number] = ""
        cache.set_apn(item.number, apn)
        cache.note(item.number, "assessor's current instrument")

    walker.seed_developers()
    sales = tuple(walker.developer)
    if leaf == 1:
        for number in sales:
            walker.cache_day(number)
            cache.note(number, "developer grant leaf 1")
    else:
        frontier = list(sales)
        for step in range(2, leaf + 1):
            walker.expand_developers(frontier)
            frontier = walker.take_developer()
            for number in frontier:
                walker.cache_day(number)
                cache.note(number, f"builder leaf {step}")
            if not frontier:
                break

    meets = find_meets(current_side, walker.developer, current_from, walker.developer_from)
    for meet in meets:
        cache.note(meet.current, f"meets {meet.developer} by {meet.kind}")
        cache.note(meet.developer, f"meets {meet.current} by {meet.kind}")
        for apn, number in currents.items():
            if number == meet.current or number in meet.numbers:
                cache.set_apn(meet.developer, apn)
                for item in meet.numbers:
                    cache.set_apn(item, apn)
    return LeafResult(leaf, sales, tuple(walker.developer), meets, cache.count())


def descend(
    recorder: SacramentoCountyRecorder,
    cache: IndexCache,
    *,
    current: tuple[str, ...],
    developers: tuple[Developer, ...],
    after: date | None = None,
    developer_after: date | None = None,
    depth: int = 1,
    developer_depth: int | None = None,
    exclude: frozenset[str] = frozenset(),
    limit: int = _PARTY_LIMIT,
    session=None,
    fetch=None,
    note=None,
) -> Descent:
    """Walk builder leaves first, then one current leaf at a time.

    Depth 1 is the developer grants. A later depth expands every buyer's next
    deed before any branch goes farther. The current deeds are loaded from the
    start so a meet can be found. Current grantors are walked only after the
    builder leaves for that depth are done, and only one leaf across all of them.
    """
    if depth < 1:
        return Descent(0, (), (), ())
    steps = developer_depth if developer_depth is not None else depth
    opened = after
    session = session or recorder.open_session(fetch=fetch)
    if session is None:
        return Descent(0, (), (), ())
    walker = _Walker(
        recorder,
        cache,
        developers=developers,
        after=opened,
        developer_after=opened if developer_after is None else developer_after,
        before=None,
        exclude=exclude,
        limit=limit,
        session=session,
        fetch=fetch,
        note=note,
    )
    for number in current:
        item = walker.load(number)
        if item is not None and item.kind in ("fee", "foreclosure"):
            walker.current[item.number] = item
            walker.current_from[item.number] = ""
    builder_depth = max(0, min(steps, depth))
    meets: tuple[Meet, ...] = ()
    if builder_depth >= 1:
        currents = {f"current{index}": number for index, number in enumerate(current)}
        found = builder_leaf(
            recorder,
            cache,
            currents=currents,
            developers=developers,
            after=opened or date(1965, 1, 1),
            before=None,
            leaf=builder_depth,
            exclude=exclude,
            limit=limit,
            session=session,
            fetch=fetch,
            note=note,
        )
        for number in found.reached:
            item = cache.get(number)
            if item is not None:
                walker.developer[number] = item
                walker.developer_from.setdefault(number, "")
        meets = find_meets(walker.current, walker.developer, walker.current_from, walker.developer_from)
        if meets or depth <= builder_depth:
            return Descent(builder_depth, meets or found.meets, tuple(walker.current), tuple(walker.developer))
    elif depth <= 0:
        return Descent(0, (), tuple(walker.current), ())
    current_layer = list(walker.current)
    for level in range(1, depth - builder_depth + 1):
        walker.expand_current(current_layer)
        current_layer = walker.take_current()
        meets = find_meets(walker.current, walker.developer, walker.current_from, walker.developer_from)
        if meets:
            return Descent(builder_depth + level, meets, tuple(walker.current), tuple(walker.developer))
    return Descent(depth, meets, tuple(walker.current), tuple(walker.developer))


def find_meets(
    current: dict[str, FiledInstrument],
    developer: dict[str, FiledInstrument],
    current_from: dict[str, str],
    developer_from: dict[str, str],
) -> tuple[Meet, ...]:
    """Documents, citations, and handoffs that sit on both sides."""
    found: list[Meet] = []
    seen: set[tuple[str, str, str]] = set()
    for number, item in current.items():
        if number in developer:
            _add(found, seen, "document", item, developer[number], current_from, developer_from)
        for cited in item.cross_references:
            other = developer.get(cited)
            if other is not None:
                _add(found, seen, "citation", item, other, current_from, developer_from)
    for number, item in developer.items():
        for cited in item.cross_references:
            other = current.get(cited)
            if other is not None:
                _add(found, seen, "citation", other, item, current_from, developer_from)
    for later in current.values():
        if later.kind not in ("fee", "foreclosure"):
            continue
        for earlier in developer.values():
            if earlier.kind not in ("fee", "foreclosure"):
                continue
            if not _window(earlier.recorded, None, later.recorded):
                continue
            if _hands_off(earlier, later):
                _add(found, seen, "handoff", later, earlier, current_from, developer_from)
    return tuple(found)


def _add(found, seen, kind, current: FiledInstrument, developer: FiledInstrument, current_from, developer_from) -> None:
    key = (kind, current.number, developer.number)
    if key in seen:
        return
    seen.add(key)
    found.append(
        Meet(kind, current.number, developer.number, _path(current_from, developer_from, current.number, developer.number))
    )


def _hands_off(earlier: FiledInstrument, later: FiledInstrument) -> bool:
    for grantor in later.grantors:
        for grantee in earlier.grantees:
            if name_keeps(grantor, grantee):
                return True
    return False


def _path(current_from: dict[str, str], developer_from: dict[str, str], current: str, developer: str) -> tuple[str, ...]:
    found: list[str] = []
    for source, start in ((current_from, current), (developer_from, developer)):
        node = start
        seen: set[str] = set()
        while node and node not in seen:
            seen.add(node)
            if node not in found:
                found.append(node)
            node = source.get(node, "")
    return tuple(found)


def _stamp(number: str) -> str:
    return "".join(ch for ch in number if ch.isdigit())


class _Walker:
    def __init__(
        self,
        recorder,
        cache,
        *,
        developers,
        after,
        developer_after,
        before,
        exclude,
        limit,
        session,
        fetch,
        note,
    ) -> None:
        self.recorder = recorder
        self.cache = cache
        self.developers = developers
        self.after = after
        self.developer_after = developer_after
        self.before = before
        self.exclude = exclude
        self.limit = limit
        self.session = session
        self.fetch = fetch
        self.note = note
        self.current: dict[str, FiledInstrument] = {}
        self.developer: dict[str, FiledInstrument] = {}
        self.current_from: dict[str, str] = {}
        self.developer_from: dict[str, str] = {}
        self._current_new: list[str] = []
        self._developer_new: list[str] = []
        self._expanded: set[tuple[str, str]] = set()

    def load(self, number: str) -> FiledInstrument | None:
        stamp = _stamp(number)
        parsed = self.recorder.parse(stamp)
        if parsed is None:
            return None
        cached = self.cache.get(parsed.number)
        if cached is not None:
            return cached
        rows = self.recorder.search(number=parsed.number, limit=1, session=self.session, fetch=self.fetch)
        if not rows:
            return None
        item = self._file(rows[0])
        self.cache.put(item)
        return item

    def cache_day(self, number: str) -> None:
        """Keep the same-day instruments beside a known recording."""
        for neighbor in closing_numbers(number):
            if not neighbor:
                continue
            item = self.load(neighbor)
            if item is not None:
                self.cache.note(item.number, f"same day as {number}")

    def seed_developers(self) -> None:
        forms: list[str] = []
        for developer in self.developers:
            for name in developer.names:
                if name not in forms:
                    forms.append(name)
        for name in forms:
            for filing in _FEE:
                self._search(
                    name,
                    filing,
                    role="grantor",
                    after=self.developer_after,
                    before=self.before,
                    capped=False,
                    query=name,
                )
                key = _search_key(name, _filing_code(filing), "grantor", self.developer_after, self.before)
                cached = self.cache.cached_search(key)
                if cached is None:
                    continue
                for number in cached[1]:
                    item = self.cache.get(number)
                    if item is None:
                        continue
                    if any(keeps_developer(party, self.developers) for party in item.grantors):
                        self._place_developer(item, "")
                    else:
                        self.cache.note(item.number, "not a pinned developer grantor")

    def expand_current(self, numbers: list[str]) -> None:
        for number in numbers:
            if ("current", number) in self._expanded:
                continue
            self._expanded.add(("current", number))
            item = self.current.get(number) or self.load(number)
            if item is None:
                continue
            self._cite(item, before=item.recorded, place=self._place_current, source=item.number)
            if item.kind not in ("fee", "foreclosure"):
                continue
            for party in item.grantors:
                if not _follow(party, self.developers):
                    continue
                self._backward(party, before=item.recorded, source=item.number)

    def expand_developers(self, numbers: list[str]) -> None:
        for number in numbers:
            if ("developer", number) in self._expanded:
                continue
            self._expanded.add(("developer", number))
            item = self.developer.get(number)
            if item is None or not advances_chain(item.kind, item.grantors, item.grantees):
                continue
            self._cite(item, before=None, place=self._place_developer, source=item.number, after=item.recorded)
            for party in item.grantees:
                if not _follow(party, self.developers) or other_community(party):
                    continue
                self._forward(party, after=item.recorded, source=item.number)

    def take_current(self) -> list[str]:
        layer = self._current_new
        self._current_new = []
        return layer

    def take_developer(self) -> list[str]:
        layer = self._developer_new
        self._developer_new = []
        return layer

    def _backward(self, party: str, *, before: date | None, source: str) -> None:
        for filing in (*_FEE, *_FORECLOSURE):
            for item in self._search(party, filing, role="grantee", after=self.after, before=before, capped=True):
                self._place_current(item, source)
        for item in self._search(party, DocType.RCNV, role="grantee", after=None, before=before, capped=True):
            self._cite(item, before=before, place=self._place_current, source=source)

    def _forward(self, party: str, *, after: date | None, source: str) -> None:
        opened = _day_after(after)
        for filing in _FEE:
            for item in self._search(party, filing, role="grantor", after=opened, before=None, capped=True):
                if owner_restatement(item.grantors, item.grantees):
                    self.cache.note(item.number, "same owner restatement; not a new buyer")
                    continue
                if not advances_chain(item.kind, item.grantors, item.grantees):
                    continue
                self._place_developer(item, source)

    def _cite(self, item: FiledInstrument, *, before, place, source: str, after: date | None = None) -> None:
        opened = self.after if after is None else after
        for number in item.cross_references:
            cited = self.load(number)
            if cited is None or not _window(cited.recorded, opened, before):
                continue
            if cited.kind in ("fee", "foreclosure") and place is not None:
                if advances_chain(cited.kind, cited.grantors, cited.grantees):
                    place(cited, source)
            elif cited.kind in ("lien", "substitution"):
                for deeper in cited.cross_references:
                    grant = self.load(deeper)
                    if grant is None or not advances_chain(grant.kind, grant.grantors, grant.grantees):
                        continue
                    if place is not None and _window(grant.recorded, opened, before):
                        place(grant, source)

    def _place_current(self, item: FiledInstrument, source: str) -> None:
        if item.number in self.exclude or item.number in self.current:
            return
        if not advances_chain(item.kind, item.grantors, item.grantees):
            return
        self.current[item.number] = item
        self.current_from[item.number] = source
        self._current_new.append(item.number)

    def _place_developer(self, item: FiledInstrument, source: str) -> None:
        if item.number in self.exclude or item.number in self.developer:
            return
        if not advances_chain(item.kind, item.grantors, item.grantees):
            return
        self.developer[item.number] = item
        self.developer_from[item.number] = source
        self._developer_new.append(item.number)

    def _search(
        self,
        party: str,
        filing: Filing | DocType,
        *,
        role: str,
        after: date | None,
        before: date | None,
        capped: bool,
        query: str = "",
    ) -> tuple[FiledInstrument, ...]:
        """Cache every returned row. Return only the rows that match ``role``.

        A wide personal name still caches the page that came back, marks the
        search wide, and returns nothing to walk. A date-bounded developer
        search is not capped and keeps every row.
        """
        query = query or _query_name(party)
        if not query:
            return ()
        code = _filing_code(filing)
        key = _search_key(query, code, role, after, before)
        cached = self.cache.cached_search(key)
        if cached is not None:
            wide, numbers = cached
            items = tuple(item for number in numbers if (item := self.cache.get(number)) is not None)
            if wide:
                return ()
            return tuple(item for item in items if _matches_item(party, item, role))
        if self.note is not None:
            self.note(f"{query} {code} {role}".strip())
        rows = self.recorder.search(
            name=query,
            filing=filing,
            after=after,
            before=before,
            limit=(self.limit + 1) if capped else 0,
            session=self.session,
            fetch=self.fetch,
        )
        wide = capped and len(rows) > self.limit
        kept: list[FiledInstrument] = []
        matched: list[FiledInstrument] = []
        seen: set[str] = set()
        for row in rows[: self.limit] if wide else rows:
            if row.number in seen or not _window(row.recorded, after, before):
                continue
            seen.add(row.number)
            item = self._file(row)
            kept.append(item)
            if _matches(party, row, role):
                matched.append(item)
        for item in kept:
            self.cache.put(item)
        self.cache.put_search(key, tuple(item.number for item in kept), wide=wide)
        if wide:
            return ()
        return tuple(matched)

    def _file(self, row: IndexedInstrument) -> FiledInstrument:
        cached = self.cache.get(row.number)
        if cached is not None:
            return cached
        detail = None
        if row.internal_id:
            detail = self.recorder.detail(row.internal_id, session=self.session, fetch=self.fetch)
        return _filed(row, detail)


def _matches(party: str, row: IndexedInstrument, role: str) -> bool:
    if role == "grantor":
        names = row.grantors
    elif role == "grantee":
        names = row.grantees
    else:
        names = (*row.grantors, *row.grantees)
    return any(name_keeps(party, name) for name in names)


def _matches_item(party: str, item: FiledInstrument, role: str) -> bool:
    if role == "grantor":
        names = item.grantors
    elif role == "grantee":
        names = item.grantees
    else:
        names = (*item.grantors, *item.grantees)
    return any(name_keeps(party, name) for name in names)


def _filed(row: IndexedInstrument, detail: InstrumentDetail | None) -> FiledInstrument:
    if detail is None:
        code = row.filing_code
        name = row.filing_name or (FILING_NAMES.get(code, "") if code else "")
        kind = instrument_kind((code,) if code else (), (name,) if name else ())
        return FiledInstrument(
            row.number,
            row.recorded,
            kind,
            row.grantors,
            row.grantees,
            (),
            code,
            name,
        )
    codes = tuple(item.code for item in detail.filings)
    descriptions = tuple(item.description for item in detail.filings)
    if not codes and row.filing_code:
        codes = (row.filing_code,)
        descriptions = (row.filing_name or FILING_NAMES.get(row.filing_code, ""),)
    cited = tuple(dict.fromkeys(number for number in detail.cross_references if number))
    code = codes[0] if codes else row.filing_code
    name = descriptions[0] if descriptions else (row.filing_name or FILING_NAMES.get(code, ""))
    return FiledInstrument(
        detail.number or row.number,
        detail.recorded or row.recorded,
        instrument_kind(codes, descriptions),
        detail.grantors or row.grantors,
        detail.grantees or row.grantees,
        _clean_refs(cited),
        code,
        name,
    )


def backfill_empty_kinds(
    recorder: SacramentoCountyRecorder,
    cache: IndexCache,
    *,
    developers: tuple[Developer, ...] = (),
    session=None,
    fetch=None,
    note=None,
) -> dict[str, int]:
    """Refresh filing code and kind for every blank-kind cached document.

    One document number at a time. No new name search. Shape fills in when the
    county still leaves the filing blank: a developer grantor with no grantee
    is a notice of completion; an empty kind that cites another number is
    treated as substitution paperwork.
    """
    session = session or recorder.open_session(fetch=fetch)
    if session is None:
        return cache.kind_counts()
    for number in cache.empty_kind_numbers():
        if note is not None:
            note(number)
        rows = recorder.search(number=number, limit=1, session=session, fetch=fetch)
        if not rows:
            _infer_shape(cache, number, developers)
            continue
        row = rows[0]
        detail = None
        if row.internal_id:
            detail = recorder.detail(row.internal_id, session=session, fetch=fetch)
        item = _filed(row, detail)
        if not item.kind:
            item = _shape_kind(item, developers)
        cache.put(item)
        if not item.kind:
            _infer_shape(cache, number, developers)
    return cache.kind_counts()


def _shape_kind(item: FiledInstrument, developers: tuple[Developer, ...]) -> FiledInstrument:
    """Classify from parties when the filing is still blank."""
    kind = item.kind
    code = item.filing_code
    name = item.filing_name
    if not kind and item.grantors and not item.grantees and any(keeps_developer(g, developers) for g in item.grantors):
        kind, code, name = "notice", code or "306", name or "NOTICE OF COMPLETION"
    elif not kind and item.cross_references and not item.grantees:
        kind, code, name = "substitution", code or "239", name or "SUBSTITUTION OF TRUSTEE"
    elif not kind and any(" DEC" in g.upper() or g.upper().endswith(" DEC") or "DECEDENT" in g.upper() for g in item.grantors):
        kind, code, name = "death", code or "153", name or "AFFIDAVIT OF DEATH"
    if kind == item.kind and code == item.filing_code:
        return item
    return FiledInstrument(
        item.number,
        item.recorded,
        kind,
        item.grantors,
        item.grantees,
        item.cross_references,
        code,
        name,
    )


def _infer_shape(cache: IndexCache, number: str, developers: tuple[Developer, ...]) -> None:
    item = cache.get(number)
    if item is None or item.kind:
        return
    shaped = _shape_kind(item, developers)
    if shaped.kind:
        cache.put(shaped)


def _clean_refs(numbers: tuple[str, ...]) -> tuple[str, ...]:
    parser = SacramentoCountyRecorder()
    found: list[str] = []
    for number in numbers:
        parsed = parser.parse(number)
        if parsed is None or parsed.number in found:
            continue
        found.append(parsed.number)
    return tuple(found)


def _day_after(day: date | None) -> date | None:
    if day is None:
        return None
    return date.fromordinal(day.toordinal() + 1)


def conveyance(item: FiledInstrument) -> Conveyance:
    """The succession row for one cached instrument."""
    return Conveyance(item.number, item.recorded, item.grantors, item.grantees, item.cross_references)


_COMMUNITY_FILINGS = NARROW_FILINGS + (
    Filing.DECLARATION,
    Filing.AMENDMENT,
    Filing.AMENDED_RESTRICTION,
    Filing.DECLARATION_OF_ANNEXATION,
    Filing.DECLARATION_OF_RESTRICTION,
    Filing.NOTICE_OF_COMPLETION,
    Filing.CONDOMINIUM_PLAN,
    Filing.RESTRICTIVE_COVENANT,
    Filing.BYLAWS,
)


@dataclass(frozen=True)
class NameCacheResult:
    """What one name search put into the cache."""

    query: str
    wide: bool
    added: int
    numbers: tuple[str, ...]
    skipped: str = ""


def skip_lender(name: str) -> bool:
    """True for a lender, MERS, or a government that must not be searched."""
    folded = party_key(name)
    if not folded:
        return True
    if any(token in folded for token in ("FEDERAL NATL", "WACHOVIA", "MERS", "SUNRUN", "SACTO MUNI")):
        return True
    if folded.startswith("COUNTY OF ") or folded.startswith("CITY OF ") or folded.startswith("STATE OF "):
        return True
    if folded.startswith("BANK ") or " BANK " in f" {folded} " or folded.endswith(" BK") or " BK " in f" {folded} ":
        return True
    if "CR UN" in folded or "CREDIT UNION" in folded or "MTG" in folded or "MORTGAGE" in folded:
        return True
    return False


def cache_party_search(
    recorder: SacramentoCountyRecorder,
    cache: IndexCache,
    query: str,
    *,
    project: str = "MYSTIQUE",
    association: str = "MYSTIQUE COMMUNITY",
    developers: tuple[Developer, ...] = (),
    after: date | None = None,
    before: date | None = None,
    filings: tuple[Filing, ...] = NARROW_FILINGS,
    limit: int = _PARTY_LIMIT,
    session=None,
    fetch=None,
    note=None,
) -> NameCacheResult:
    """Search one indexed name and store every returned document.

    ``query`` is sent as LastName. A result count over ``limit`` is narrowed
    under each filing in ``filings``. A filing that is still wide is noted and
    not walked. Every other row is detailed and cached, including parties that
    would fail ``name_keeps``. Mystique-named parties are labeled association,
    phase, developer, or other.
    """
    query = " ".join(query.upper().split())
    if not query:
        return NameCacheResult("", False, 0, (), "empty")
    if skip_lender(query):
        return NameCacheResult(query, False, 0, (), "lender")
    session = session or recorder.open_session(fetch=fetch)
    if session is None:
        return NameCacheResult(query, False, 0, (), "no session")
    if note is not None:
        note(query)
    key = _search_key(query, "", "cache", after, before)
    cached = cache.cached_search(key)
    if cached is not None:
        wide, numbers = cached
        return NameCacheResult(query, wide, 0, numbers)
    probe = recorder.search(
        name=query,
        after=after,
        before=before,
        limit=limit + 1,
        session=session,
        fetch=fetch,
    )
    if len(probe) > limit:
        kept: list[str] = []
        for filing in filings:
            filing_key = _search_key(query, _filing_code(filing), "cache", after, before)
            prior = cache.cached_search(filing_key)
            if prior is not None:
                if not prior[0]:
                    kept.extend(prior[1])
                continue
            batch = recorder.search(
                name=query,
                filing=filing,
                after=after,
                before=before,
                limit=limit + 1,
                session=session,
                fetch=fetch,
            )
            if len(batch) > limit:
                cache.put_search(filing_key, (), wide=True)
                if note is not None:
                    note(f"{query} {_filing_code(filing)} wide")
                continue
            before_count = cache.count()
            numbers = _store_rows(
                recorder, cache, batch, session=session, fetch=fetch,
                project=project, association=association, developers=developers,
            )
            cache.put_search(filing_key, numbers, wide=False)
            kept.extend(numbers)
            _ = before_count
        uniq = tuple(dict.fromkeys(kept))
        cache.put_search(key, uniq, wide=True)
        return NameCacheResult(query, True, len(uniq), uniq)
    before_count = cache.count()
    rows = recorder.search(
        name=query,
        after=after,
        before=before,
        session=session,
        fetch=fetch,
    )
    numbers = _store_rows(
        recorder, cache, rows, session=session, fetch=fetch,
        project=project, association=association, developers=developers,
    )
    cache.put_search(key, numbers, wide=False)
    return NameCacheResult(query, False, max(0, cache.count() - before_count), numbers)


def cache_community_names(
    recorder: SacramentoCountyRecorder,
    cache: IndexCache,
    *,
    names: tuple[str, ...] = ("MYSTIQUE", "MYSTIQUE COMMUNITY"),
    project: str = "MYSTIQUE",
    association: str = "MYSTIQUE COMMUNITY",
    developers: tuple[Developer, ...] = (),
    session=None,
    fetch=None,
    note=None,
) -> tuple[NameCacheResult, ...]:
    """Cache every instrument indexed under the project and association words.

    No date floor: the declaration may predate the first unit sale. A wide
    name is narrowed under community filings. Association deeds are labeled
    and do not advance a buyer walk.
    """
    session = session or recorder.open_session(fetch=fetch)
    if session is None:
        return ()
    before = cache.count()
    found: list[NameCacheResult] = []
    for name in names:
        result = cache_party_search(
            recorder,
            cache,
            name,
            project=project,
            association=association,
            developers=developers,
            after=None,
            filings=_COMMUNITY_FILINGS,
            session=session,
            fetch=fetch,
            note=note,
        )
        found.append(result)
    # Recount added relative to before for the first call that actually inserts.
    return tuple(found)


def cache_known_parties(
    recorder: SacramentoCountyRecorder,
    cache: IndexCache,
    names: tuple[str, ...],
    *,
    project: str = "MYSTIQUE",
    association: str = "MYSTIQUE COMMUNITY",
    developers: tuple[Developer, ...] = (),
    after: date | None = None,
    session=None,
    fetch=None,
    note=None,
) -> tuple[NameCacheResult, ...]:
    """Cache every document for each known person, without fanning out.

    The query keeps the full indexed spelling (role words dropped). Developers,
    association leading names, and lenders are skipped.
    """
    session = session or recorder.open_session(fetch=fetch)
    if session is None:
        return ()
    seen: set[str] = set()
    found: list[NameCacheResult] = []
    for raw in names:
        query = _query_name(raw) or party_key(raw)
        if not query or query in seen:
            continue
        seen.add(query)
        if keeps_developer(raw, developers) or keeps_developer(query, developers):
            found.append(NameCacheResult(query, False, 0, (), "developer"))
            continue
        folded = party_key(query)
        if folded in {party_key(project), party_key(association)} or name_covers(association, query):
            found.append(NameCacheResult(query, False, 0, (), "association"))
            continue
        if skip_lender(raw) or skip_lender(query):
            found.append(NameCacheResult(query, False, 0, (), "lender"))
            continue
        result = cache_party_search(
            recorder,
            cache,
            query,
            project=project,
            association=association,
            developers=developers,
            after=after,
            filings=NARROW_FILINGS,
            session=session,
            fetch=fetch,
            note=note,
        )
        found.append(result)
    return tuple(found)


def cache_cited_numbers(
    recorder: SacramentoCountyRecorder,
    cache: IndexCache,
    *,
    developers: tuple[Developer, ...] = (),
    project: str = "MYSTIQUE",
    association: str = "MYSTIQUE COMMUNITY",
    session=None,
    fetch=None,
    note=None,
    limit: int = 500,
) -> tuple[str, ...]:
    """Load cited document numbers that are not yet in the cache, one at a time."""
    session = session or recorder.open_session(fetch=fetch)
    if session is None:
        return ()
    wanted: list[str] = []
    for row in cache._conn.execute("SELECT cross_references FROM documents").fetchall():
        for number in _lines(row["cross_references"]):
            if cache.get(number) is None and number not in wanted:
                wanted.append(number)
    loaded: list[str] = []
    for number in wanted[:limit]:
        if note is not None:
            note(number)
        rows = recorder.search(number=number, limit=1, session=session, fetch=fetch)
        if not rows:
            continue
        detail = None
        if rows[0].internal_id:
            detail = recorder.detail(rows[0].internal_id, session=session, fetch=fetch)
        item = _filed(rows[0], detail)
        if not item.kind:
            item = _shape_kind(item, developers)
        cache.put(item)
        _label_mystique_parties(cache, item, project=project, association=association, developers=developers)
        loaded.append(item.number)
    return tuple(loaded)


def _store_rows(
    recorder,
    cache: IndexCache,
    rows: tuple[IndexedInstrument, ...] | list[IndexedInstrument],
    *,
    session,
    fetch,
    project: str,
    association: str,
    developers: tuple[Developer, ...],
) -> tuple[str, ...]:
    before = {row["number"] for row in cache._conn.execute("SELECT number FROM documents").fetchall()}
    numbers: list[str] = []
    for row in rows:
        if not row.number:
            continue
        existing = cache.get(row.number)
        if existing is not None and existing.filing_code:
            numbers.append(row.number)
            _label_mystique_parties(cache, existing, project=project, association=association, developers=developers)
            continue
        detail = None
        if row.internal_id:
            detail = recorder.detail(row.internal_id, session=session, fetch=fetch)
        item = _filed(row, detail)
        if not item.kind:
            item = _shape_kind(item, developers)
        cache.put(item)
        _label_mystique_parties(cache, item, project=project, association=association, developers=developers)
        numbers.append(item.number)
    return tuple(numbers)


def _label_mystique_parties(
    cache: IndexCache,
    item: FiledInstrument,
    *,
    project: str,
    association: str,
    developers: tuple[Developer, ...],
) -> None:
    for party in (*item.grantors, *item.grantees):
        if not name_covers(project, party) and "MYSTIQUE" not in party_key(party):
            continue
        role = party_role(party, project=project, association=association, developers=developers)
        if role is IndexRole.ASSOCIATION:
            cache.note(item.number, f"association party {party}")
        elif role is IndexRole.PHASE:
            cache.note(item.number, f"phase party {party}")
        elif role is IndexRole.DEVELOPER:
            cache.note(item.number, f"developer party {party}")
        elif role is IndexRole.PROJECT:
            cache.note(item.number, f"project party {party}")
        else:
            cache.note(item.number, f"other Mystique party {party}")
