"""County recorder indexes. A city mixes in the county that files its instruments.

``history`` links document numbers already known for one parcel. It walks from
the latest deed back toward the developer. It does not search a grantor by
name: that search returns the grantor's other parcels. ``trace`` does search
names, and only the names already known for this community: each buyer and
owner, then the other party on those instruments. A developer is not searched.
``descend`` walks one step at a time from the current deed and from the
developer, and caches each document and its cross-references.

Sacramento County document numbers are twelve digits. The first eight are the
recording date and the last four are that day's sequence: ``200709120758`` is
2007-09-12, sequence 0758. The public index is
``recordersdocumentindex.saccounty.gov``. Search sends a document number, a
filing code, or a name. It does not send a captured session key.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jason.community.base import Developer


class Filing(Enum):
    """Instrument types an association looks up. Values are Sacramento filing codes."""

    DECLARATION = "162"
    AMENDMENT = "225"
    AMENDED_RESTRICTION = "220"
    DECLARATION_OF_ANNEXATION = "320"
    DECLARATION_OF_RESTRICTION = "324"
    RESTRICTIVE_COVENANT = "478"
    CONDOMINIUM_PLAN = "301"
    NOTICE_OF_COMPLETION = "306"
    BYLAWS = "494"
    GRANT_DEED = "685"
    QUITCLAIM = "689"
    DEED_OF_TRUST = "230"
    RECONVEYANCE = "238"
    UCC_FINANCING = "368"
    UCC_TERMINATION = "372"
    NOTICE_OF_ASSOCIATION_LIEN = "386"
    RELEASE_OF_ASSOCIATION_LIEN = "655"
    RELEASE_OF_LIEN = "624"
    UTILITY_LIEN = "401"
    UTILITY_TERMINATION = "644"
    NOTICE_OF_DEFAULT = "531"
    NOTICE_OF_SALE = "543"
    RESCISSION = "720"
    POWER_TO_SELL = "802"
    REQUEST_FOR_NOTICE = "546"
    ABSTRACT_OF_JUDGMENT = "376"
    STATE_TAX_LIEN = "400"
    NOTICE_OF_ASSESSMENT = "387"
    EASEMENT = "190"
    EASEMENT_DEED = "681"
    RIGHT_OF_WAY = "485"
    AFFIDAVIT_OF_DEATH = "153"
    TERMINATING_JOINT_TENANCY = "156"
    POWER_OF_ATTORNEY = "466"
    MECHANICS_LIEN = "389"
    RELEASE_OF_MECHANICS_LIEN = "635"
    EXTENSION_OF_MECHANICS_LIEN = "232"
    NOTICE_OF_ACTION = "385"
    AMENDED_NOTICE_OF_ACTION = "223"
    WITHDRAWAL_OF_LIS_PENDENS = "651"
    PARTIAL_DISCHARGE_OF_ACTION = "291"
    RELEASE_OF_LIEN_BOND = "269"
    MECHANICS_LIEN_BOND = "270"
    NOTICE_OF_CESSATION = "305"
    NOTICE_OF_NON_RESPONSIBILITY = "539"


class DocType(Enum):
    """Assessor deed-type token. The member name is that token.

    ``value`` is the description the parcel viewer prints. ``code`` is the
    Sacramento recorder filing code when the token is one filing. ``GD`` is the
    assessor's bucket for a grant deed, a corporate deed, a gift deed, and a
    joint-tenancy deed, and its recorder code is the grant-deed filing.
    ``from_code`` returns the first token that uses a number. A deed of trust
    is not a member.
    """

    def __new__(cls, label: str, code: str = "", interest: str = ""):
        obj = object.__new__(cls)
        obj._value_ = label
        obj.code = code
        obj.interest = interest
        return obj

    @property
    def token(self) -> str:
        return self.name

    @classmethod
    def from_code(cls, code: str) -> DocType | None:
        return _BY_CODE.get(code)

    # Fee. The recorder number is set when the county catalog has one filing.
    GD = ("GRANT DEED/CORP. DEED/GIFT DEED/JNT TEN DEED", "685", "fee")
    QC = ("QUITCLAIM DEED", "689", "fee")
    DE = ("DEED", "680", "fee")
    TD = ("TRUSTEES DEED", "694", "fee")
    TDSL = ("TRUSTEES DEED UPON SALE", "695", "fee")
    TXD = ("TAX DEED", "692", "fee")
    DILF = ("DEED IN LIEU FORECLOS", "801", "fee")
    RTDD = ("REVOCABLE TRANSFER ON DEATH DEED", "697", "fee")
    DD = ("DECREE OF DISTRIBUTION", "339", "fee")
    DEQT = ("DECREE QUIETING TITLE", "342", "fee")
    DETJ = ("DECREE TERMINATING JOINT TENANCY", "", "fee")
    JTDE = ("JOINT TENANCY DEED", "", "fee")
    TCGD = ("TENANCY IN COMMON DEED", "", "fee")
    SD = ("SHERIFF DEED", "", "fee")
    DETH = ("DEATH OF OWNER", "", "fee")
    # Easement. These do not replace the owner of the fee.
    EASD = ("EASEMENT DEED", "681", "easement")
    EASE = ("GRANT OF EASEMENT", "190", "easement")
    ROW = ("RIGHT OF WAY", "485", "easement")
    ROWD = ("RIGHT OF WAY DEED", "", "easement")
    # Recorded, and not a transfer of the fee.
    DEAN = ("DECLARATION OF ANNEXATION", "320", "")
    RCNV = ("RECONVEYANCE", "238", "")
    NOD = ("NOTICE OF DEFAULT", "531", "")
    NTS = ("NOTICE OF TRUSTEES SALE", "543", "")
    DISC = ("DISCLAIMER", "488", "")
    CS = ("CONTRACT OF SALE(ON REAL ESTATES)", "", "")
    AFDT = ("AFFIDAVIT, GENERAL", "", "")
    PC = ("PC ALLOCATION", "", "")
    FD = ("FINAL DIVORCE", "", "")


class IndexRole(Enum):
    """Which community name an index party is.

    The recorder matches a last name from the front of the indexed name.
    The project, the association, a phase, and a developer are different
    leading names. A business that only shares the project's first word is
    ``OTHER``.
    """

    PROJECT = "project"
    ASSOCIATION = "association"
    PHASE = "phase"
    DEVELOPER = "developer"
    OTHER = "other"


_BY_CODE: dict[str, DocType] = {}
for _item in DocType:
    if _item.code and _item.code not in _BY_CODE:
        _BY_CODE[_item.code] = _item


def _doc_type(code: str) -> DocType | None:
    found = DocType.from_code(code)
    if found is not None:
        return found
    try:
        return DocType[code]
    except KeyError:
        return None


def conveys(code: str) -> bool:
    """True when this recorder code or assessor token can pass the fee or an easement."""
    found = _doc_type(code)
    return found is not None and found.interest in ("fee", "easement")


def conveys_fee(code: str) -> bool:
    """True when this recorder code or assessor token can pass ownership of the parcel."""
    found = _doc_type(code)
    return found is not None and found.interest == "fee"


@dataclass(frozen=True)
class RecorderNumber:
    """One stamped document number, parsed by the county that issued it."""

    number: str
    recorded: date
    sequence: str


class CountyRecorder:
    """How one county clerk-recorder numbers and classifies instruments."""

    name: str

    def parse(self, number: str) -> RecorderNumber | None:
        raise NotImplementedError


class SacramentoCountyRecorder(CountyRecorder):
    """Sacramento County Clerk-Recorder. Index: recordersdocumentindex.saccounty.gov."""

    name = "Sacramento"

    def parse(self, number: str) -> RecorderNumber | None:
        digits = "".join(ch for ch in number if ch.isdigit())
        if len(digits) != 12:
            return None
        try:
            recorded = date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
        return RecorderNumber(digits, recorded, digits[8:])

    def search(
        self,
        *,
        number: str = "",
        number_to: str = "",
        filing: Filing | DocType | None = None,
        name: str = "",
        text: str = "",
        start: int = 0,
        rows: int = 10,
        after: date | None = None,
        before: date | None = None,
        limit: int = 0,
        session: IndexSession | None = None,
        fetch=None,
    ) -> tuple[IndexedInstrument, ...]:
        """Search the public index. ``fetch`` replaces the HTTP call in tests.

        The capture sends ``EncryptedKey`` and ``Password`` from ``GetSecureKey``
        on the search request. A last-name search uses ``LastName``. ``text``
        keeps a row only when that second name is the same party. The county
        ``SearchText`` field does not combine with ``LastName``, so the second
        name is applied here. ``number_to`` is the end of a document-number
        range. When ``after`` and ``before`` are omitted, the recorded dates
        are the county's minimum and maximum. ``limit`` stops a wide name
        after that many rows.
        """
        getter = _index_get if fetch is None else fetch
        session = session or _open_session(getter)
        if session is None:
            return ()
        headers = {"EncryptedKey": session.encrypted_key, "Password": session.password}
        bounds = None
        found: list[IndexedInstrument] = []
        offset = start
        while True:
            params = _search_params(
                self,
                number=number,
                number_to=number_to,
                filing=filing,
                name=name,
                start=offset,
                rows=rows,
                after=after,
                before=before,
            )
            if "MinRecordedDate" not in params or "MaxRecordedDate" not in params:
                if bounds is None:
                    bounds = getter(DATES_URL, {}, headers) or {}
                params.setdefault("MinRecordedDate", str(bounds.get("MinimumDate") or ""))
                params.setdefault("MaxRecordedDate", str(bounds.get("MaximumDate") or ""))
            payload = getter(SEARCH_URL, params, headers)
            batch = instruments(payload, self)
            found.extend(batch)
            count = int((payload or {}).get("ResultCount") or 0)
            offset += len(batch)
            if not batch or offset >= count or (limit and not text.strip() and len(found) >= limit):
                break
        if text.strip():
            from jason.community.index_cache import name_keeps

            needle = text
            found = [
                row for row in found
                if any(name_keeps(needle, party) for party in (*row.grantors, *row.grantees))
            ]
        if limit:
            return tuple(found[:limit])
        return tuple(found)

    def for_parties(
        self,
        names: tuple[str, ...],
        *,
        after: date | None = None,
        before: date | None = None,
        limit: int = 30,
        developers: tuple[Developer, ...] = (),
        filings: tuple[Filing, ...] = (),
        session: IndexSession | None = None,
        fetch=None,
    ) -> tuple[NameSearch, ...]:
        """Search each known person once. A developer name is skipped.

        The query is the surname and given name. One request asks for ``limit``
        rows. A result count above that is kept as a wide search and its rows
        are not returned: that name is too common to follow. When ``filings``
        is set, a wide name is searched again under each of those filings, and
        a filing that is still wide is left out.
        """
        getter = _index_get if fetch is None else fetch
        session = session or _open_session(getter)
        if session is None:
            return ()
        found: list[NameSearch] = []
        seen: set[str] = set()
        page = max(limit, 1)
        for name in names:
            query = index_name(name)
            if not query or query in seen or not _follow(name, developers):
                continue
            seen.add(query)
            headers = {"EncryptedKey": session.encrypted_key, "Password": session.password}
            params = _search_params(self, name=query, rows=page, after=after, before=before)
            if "MinRecordedDate" not in params or "MaxRecordedDate" not in params:
                bounds = getter(DATES_URL, {}, headers) or {}
                params.setdefault("MinRecordedDate", str(bounds.get("MinimumDate") or ""))
                params.setdefault("MaxRecordedDate", str(bounds.get("MaximumDate") or ""))
            payload = getter(SEARCH_URL, params, headers) or {}
            total = int(payload.get("ResultCount") or 0)
            if total > limit:
                if not filings:
                    found.append(NameSearch(query, total, ()))
                    continue
                narrowed = self._narrow(
                    query,
                    filings,
                    after=after,
                    before=before,
                    limit=limit,
                    session=session,
                    fetch=getter,
                )
                if not narrowed:
                    found.append(NameSearch(query, total, ()))
                else:
                    found.append(NameSearch(query, len(narrowed), tuple(narrowed)))
                continue
            batch = list(instruments(payload, self))
            if len(batch) < total:
                batch.extend(
                    self.search(
                        name=query,
                        start=len(batch),
                        rows=page,
                        after=after,
                        before=before,
                        session=session,
                        fetch=getter,
                    )
                )
            found.append(NameSearch(query, total, tuple(batch)))
        return tuple(found)

    def _narrow(
        self,
        query: str,
        filings: tuple[Filing, ...],
        *,
        after: date | None,
        before: date | None,
        limit: int,
        session: IndexSession,
        fetch,
    ) -> list[IndexedInstrument]:
        """Rows for a wide name, one filing at a time. A filing still over ``limit`` is skipped."""
        kept: list[IndexedInstrument] = []
        seen: set[str] = set()
        for filing in filings:
            rows = self.search(
                name=query,
                filing=filing,
                after=after,
                before=before,
                rows=max(limit, 1),
                limit=limit + 1,
                session=session,
                fetch=fetch,
            )
            if len(rows) > limit:
                continue
            for row in rows:
                if row.number in seen:
                    continue
                seen.add(row.number)
                kept.append(row)
        return kept

    def trace(
        self,
        names: tuple[str, ...],
        *,
        after: date | None = None,
        before: date | None = None,
        limit: int = 30,
        hops: int = 2,
        developers: tuple[Developer, ...] = (),
        session: IndexSession | None = None,
        fetch=None,
    ) -> tuple[NameSearch, ...]:
        """Search known buyers and owners, then the other party on each hit.

        A later deed meets an earlier one when its grantor was that earlier
        deed's grantee. Searching the other party is how the two sides reach
        the same document. A developer is not searched, and a wide name is not
        followed. ``hops`` counts those extra sides after the names given.
        """
        getter = _index_get if fetch is None else fetch
        session = session or _open_session(getter)
        if session is None:
            return ()
        pending = list(names)
        seen: set[str] = set()
        found: list[NameSearch] = []
        for hop in range(hops + 1):
            wave = tuple(name for name in pending if index_name(name) not in seen)
            pending = []
            if not wave:
                break
            results = self.for_parties(
                wave,
                after=after,
                before=before,
                limit=limit,
                developers=developers,
                session=session,
                fetch=getter,
            )
            found.extend(results)
            for result in results:
                seen.add(result.query)
                if result.wide or hop == hops:
                    continue
                for row in result.rows:
                    for name in next_parties(row, developers):
                        query = index_name(name)
                        if query and query not in seen:
                            pending.append(name)
        return tuple(found)

    def names(self, internal_id: str, *, page: int = 1, per_page: int = 1000, session: IndexSession | None = None, fetch=None) -> tuple[IndexParty, ...]:
        """Parties on one instrument, including each cross-referenced document number."""
        getter = _index_get if fetch is None else fetch
        session = session or _open_session(getter)
        if session is None:
            return ()
        headers = {"EncryptedKey": session.encrypted_key, "Password": session.password}
        url = f"{API}search/GetNamesForPagination/{internal_id}/{page}/{per_page}"
        return index_parties(getter(url, {}, headers))

    def detail(self, internal_id: str, *, session: IndexSession | None = None, fetch=None) -> InstrumentDetail | None:
        """Filing types, status, page count, and parties for one index row."""
        getter = _index_get if fetch is None else fetch
        session = session or _open_session(getter)
        if session is None:
            return None
        headers = {"EncryptedKey": session.encrypted_key, "Password": session.password}
        payload = getter(f"{API}search/GetDocumentDetails/{internal_id}", {}, headers)
        summary = (payload or {}).get("DocumentSummary") or {}
        if not summary:
            return None
        return InstrumentDetail(
            number=str(summary.get("DocumentNumber") or ""),
            recorded=_index_date(str(summary.get("DocumentDate") or "")),
            status=str(summary.get("DocumentStatus") or ""),
            pages=summary.get("Pages") if isinstance(summary.get("Pages"), int) else None,
            apn=str(summary.get("APN") or ""),
            filings=tuple(
                FilingType(str(row.get("FilingCodeName") or ""), str(row.get("Description") or ""))
                for row in (summary.get("FilingCodes") or [])
            ),
            parties=self.names(internal_id, session=session, fetch=getter),
        )

    def history(
        self,
        numbers: tuple[str, ...],
        *,
        apn: str = "",
        developers: tuple[Developer, ...] = (),
        session: IndexSession | None = None,
        fetch=None,
    ) -> OwnershipHistory:
        """Link known document numbers for one parcel, newest deed first.

        Each number is read from the index. A later deed links to an earlier
        one when it cites that document number, or when its grantor is that
        earlier deed's grantee. A name search is not used: the same grantor
        is on other parcels. A grant from one of ``developers`` is that
        subdivider's conveyance, and an earlier deed that conveyed the land
        to the developer stays linked when its number is in the set. A cited number
        that was not in ``numbers`` stays on the step as a document still to fetch.
        """
        getter = _index_get if fetch is None else fetch
        session = session or _open_session(getter)
        loaded: list[Conveyance] = []
        seen: set[str] = set()
        for raw in numbers:
            parsed = self.parse(raw)
            number = parsed.number if parsed is not None else "".join(ch for ch in raw if ch.isdigit())
            if not number or number in seen:
                continue
            seen.add(number)
            loaded.append(self._conveyance(number, apn=apn, session=session, fetch=getter))
        return succession(tuple(loaded), apn=apn, developers=developers)

    def _conveyance(
        self,
        number: str,
        *,
        apn: str,
        session: IndexSession | None,
        fetch,
    ) -> Conveyance:
        parsed = self.parse(number)
        recorded = parsed.recorded if parsed is not None else None
        if session is None:
            return Conveyance(number, recorded, (), (), (), apn)
        rows = self.search(number=number, session=session, fetch=fetch)
        if not rows:
            return Conveyance(number, recorded, (), (), (), apn)
        row = rows[0]
        if not row.internal_id:
            return Conveyance(
                row.number or number,
                row.recorded or recorded,
                row.grantors,
                row.grantees,
                (),
                apn,
            )
        detail = self.detail(row.internal_id, session=session, fetch=fetch)
        if detail is None:
            return Conveyance(
                row.number or number,
                row.recorded or recorded,
                row.grantors,
                row.grantees,
                (),
                apn,
            )
        return Conveyance(
            detail.number or row.number or number,
            detail.recorded or row.recorded or recorded,
            detail.grantors or row.grantors,
            detail.grantees or row.grantees,
            _document_refs(detail.cross_references),
            _parcel_apn(detail.apn) or apn,
        )

    def prior_candidates(
        self,
        grantor: str,
        *,
        before: date,
        filing: Filing | DocType | None = Filing.GRANT_DEED,
        session: IndexSession | None = None,
        fetch=None,
    ) -> tuple[IndexedInstrument, ...]:
        """Grant deeds before ``before`` on which ``grantor`` is the grantee.

        These rows are not a chain. A builder name matches other parcels.
        Keep a row only when its document number is already known for this one.
        """
        rows = self.search(name=grantor, filing=filing, session=session, fetch=fetch)
        return tuple(
            row
            for row in rows
            if row.recorded is not None
            and row.recorded < before
            and any(same_party(grantor, name) for name in row.grantees)
        )

    def forward_hits(
        self,
        developer: str,
        party: str,
        *,
        before: date,
        developers: tuple[Developer, ...],
        after: date | None = None,
        exclude: frozenset[str] = frozenset(),
        filing: Filing | DocType | None = Filing.GRANT_DEED,
        session: IndexSession | None = None,
        fetch=None,
    ) -> tuple[IndexedInstrument, ...]:
        """Grant deeds by ``developer`` to ``party`` recorded before ``before``.

        The search starts at the developer, so it lists the homes that
        developer sold. ``after`` drops sales from before the report was
        issued. ``exclude`` drops document numbers already on a solved chain.
        A row is a hit when ``party`` is the grantee. The other buyers are
        other parcels. Resolving Penhallow against Watt Communities at Mystique
        hits the Watt deed to Penhallow. A hit is the possible root to load
        with the later deed this party granted. It is not stored until that
        chain reaches one developer and has no gap.
        """
        if not party:
            return ()
        return tuple(
            row
            for row in self.forward_sales(
                developer,
                developers=developers,
                after=after,
                before=before,
                exclude=exclude,
                filing=filing,
                session=session,
                fetch=fetch,
            )
            if any(_same_owner(party, name, developers) for name in row.grantees)
        )

    def forward_sales(
        self,
        developer: str,
        *,
        developers: tuple[Developer, ...],
        after: date | None = None,
        before: date | None = None,
        exclude: frozenset[str] = frozenset(),
        filing: Filing | DocType | None = Filing.GRANT_DEED,
        session: IndexSession | None = None,
        fetch=None,
    ) -> tuple[IndexedInstrument, ...]:
        """Grant deeds by ``developer`` that are not already on a solved chain.

        ``exclude`` is that set of document numbers. A sale whose number is
        in it stays out, including the later deeds of that same chain.
        """
        rows = self.search(
            name=developer,
            filing=filing,
            after=after,
            before=before,
            session=session,
            fetch=fetch,
        )
        return tuple(
            row
            for row in rows
            if row.number not in exclude
            and row.recorded is not None
            and (before is None or row.recorded < before)
            and any(is_developer(name, developers) for name in row.grantors)
        )


def parties(names: list[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split an index name list into grantors ``(R)`` and grantees ``(E)``."""
    grantors = tuple(name[4:] for name in names if name.startswith("(R)"))
    grantees = tuple(name[4:] for name in names if name.startswith("(E)"))
    return grantors, grantees


def party_key(name: str) -> str:
    """Index spelling with case and extra spaces removed."""
    return " ".join(name.upper().split())


def same_party(left: str, right: str) -> bool:
    """True when two index names are the same party.

    A shorter name matches a longer one when the longer name continues it
    with another word. ``WATT COMMUNITIES AT MYSTIQUE`` matches
    ``WATT COMMUNITIES AT MYSTIQUE LLC``.
    """
    a, b = party_key(left), party_key(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer.startswith(shorter + " ")


def is_developer(name: str, developers: tuple[Developer, ...]) -> bool:
    """True when this grantor is one of the pinned subdividers.

    A shorter pinned name matches the index form that continues it, so
    ``WL HOMES`` matches ``WL HOMES LLC``. Punctuation is ignored.
    ``WATT COMMUNITIES LLC`` does not match ``WATT COMMUNITIES AT MYSTIQUE``.
    """
    return developer_for(name, developers) is not None


def developer_for(name: str, developers: tuple[Developer, ...]) -> Developer | None:
    """The pinned subdivider this index name belongs to."""
    folded = _letters(name)
    if not folded:
        return None
    for developer in developers:
        for form in developer.names:
            key = _letters(form)
            if key and (folded == key or folded.startswith(key + " ")):
                return developer
    return None


def _letters(name: str) -> str:
    """Index spelling with case, punctuation, and extra spaces removed."""
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in name)
    return " ".join(cleaned.upper().split())


_INDEX_SKIP = frozenset({
    "TRUSTEE", "TRUST", "LLC", "INC", "JR", "SR", "II", "III", "IV", "TR",
    "AND", "THE", "REV", "REVOCABLE", "FAMILY", "FMLY", "ETC", "&",
})

# Fee transfers. A deed of trust and a UCC are not walked to the next party.
_CONVEYANCE_CODES = frozenset({"680", "685", "689", "692", "694", "695", "801"})

# A wide personal name is searched again under these filings.
NARROW_FILINGS = (
    Filing.GRANT_DEED,
    Filing.QUITCLAIM,
    Filing.UCC_FINANCING,
    Filing.UCC_TERMINATION,
)

_HANDOFF_TOKEN = {
    "ASSN": "ASSOCIATION",
    "ASSOC": "ASSOCIATION",
    "PHAS": "PHASE",
}

_ENTITY = frozenset({
    "LLC", "INC", "CORP", "CORPORATION", "LTD", "COMPANY", "CO",
    "ASSN", "ASSOC", "ASSOCIATION", "HOMES", "BANK", "BK", "TRUST", "TRUSTEE",
    "PHASE", "PHAS", "COMMUNITY", "COMMUNITIES", "COMMUNIITIES",
    "COUNTY", "CITY", "PARTNERSHIP", "LP", "PTP", "PLLC",
})


def _person_tokens(name: str) -> frozenset[str]:
    """Significant words of a person's name, ignoring order."""
    return frozenset(
        token
        for token in _letters(name).split()
        if len(token) > 1 and token not in _INDEX_SKIP
    )


def index_name(name: str) -> str:
    """Surname and given name, which is the index query for one person.

    ``index_name("FENWICK HAROLD R SR TRUSTEE")`` is ``FENWICK HAROLD``.
    A single remaining word is used as-is.
    """
    parts = [
        part for part in party_key(name).split()
        if part not in _INDEX_SKIP and len(part) > 1
    ]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[1]}"


@dataclass(frozen=True)
class NameCandidate:
    """A shorter spelling and the longer word it may stand for.

    The assessor and the recorder abbreviate the same owner differently.
    A candidate is that pair. It joins two deed parties only when the other
    words of the two names already match.
    """

    short: str
    long: str
    count: int = 1


def name_candidates(assessor: str, *recorder: str) -> tuple[NameCandidate, ...]:
    """Abbreviation pairs suggested by one owner's two spellings.

    Put the assessor's owner beside the recorder's parties. A one-letter
    token pairs with the single longer word that starts with it. A token
    that is the other word with its vowels removed pairs too, so ``FMLY``
    pairs with ``FAMILY``. ``TR`` does not pair with ``TRAN`` or ``TRUST``.
    """
    assessor_tokens = _letters(assessor).split()
    recorder_tokens: list[str] = []
    for name in recorder:
        recorder_tokens.extend(_letters(name).split())
    shared = set(assessor_tokens) & set(recorder_tokens)
    left = [token for token in assessor_tokens if token not in shared]
    right = [token for token in recorder_tokens if token not in shared]
    found: list[NameCandidate] = []
    used: set[str] = set()
    letters = [token for token in (*left, *right) if len(token) == 1]
    longer = [token for token in (*left, *right) if len(token) >= 3]
    for letter in dict.fromkeys(letters):
        choices = [token for token in longer if token.startswith(letter) and token not in used]
        if len(choices) != 1:
            continue
        used.add(letter)
        used.add(choices[0])
        found.append(NameCandidate(letter, choices[0]))
    for token in left:
        if token in used:
            continue
        for other in right:
            if other in used or token == other:
                continue
            short, long = (token, other) if len(token) <= len(other) else (other, token)
            if len(short) < 3 or short == long or long.startswith(short):
                continue
            if short == _skeleton(long):
                used.add(token)
                used.add(other)
                found.append(NameCandidate(short, long))
                break
    return tuple(sorted(found, key=lambda item: (item.short, item.long)))


@dataclass(eq=False, frozen=True)
class OwnerName:
    """One party on a deed. ``==`` compares spellings.

    Python 3 has no ``__cmp__``. Two names are equal when they hand off,
    including a candidate abbreviation that accounts for every remaining
    word. Equality depends on both full names, so the object is not hashed.
    """

    name: str
    __hash__ = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OwnerName):
            return _same_owner(self.name, other.name)
        if isinstance(other, str):
            return _same_owner(self.name, other)
        return NotImplemented


def merge_candidates(found: tuple[NameCandidate, ...] | list[NameCandidate]) -> tuple[NameCandidate, ...]:
    """One row per spelling. ``count`` is how many owners showed that pair."""
    totals: dict[tuple[str, str], int] = {}
    for item in found:
        key = (item.short, item.long)
        totals[key] = totals.get(key, 0) + item.count
    rows = tuple(NameCandidate(short, long, count) for (short, long), count in totals.items())
    return tuple(sorted(rows, key=lambda item: (-item.count, item.short, item.long)))


def _skeleton(word: str) -> str:
    """The word with vowels after the first letter removed."""
    if len(word) < 2:
        return ""
    vowels = set("AEIOU")
    return word[0] + "".join(ch for ch in word[1:] if ch not in vowels)


def handoff_key(name: str) -> str:
    """Party spelling used to join two deeds.

    ``ASSN`` and ``ASSOC`` fold to ``ASSOCIATION``. ``PHAS`` folds to ``PHASE``.
    """
    return " ".join(_HANDOFF_TOKEN.get(token, token) for token in _letters(name).split())


def _is_person(name: str) -> bool:
    """False for a company, an association, a phase, or a government."""
    tokens = _letters(name).split()
    return bool(tokens) and not any(token in _ENTITY for token in tokens)


def name_covers(query: str, indexed: str) -> bool:
    """True when a last-name search for ``query`` returns this indexed party.

    The index matches from the start of the name. ``MYSTIQUE`` matches
    ``MYSTIQUE PHASE 3`` and does not match ``WATT COMMUNITIES AT MYSTIQUE``.
    """
    folded_query, folded_name = party_key(query), party_key(indexed)
    if not folded_query or not folded_name:
        return False
    return folded_name == folded_query or folded_name.startswith(folded_query + " ")


def party_role(
    name: str,
    *,
    project: str,
    association: str,
    developers: tuple[Developer, ...],
) -> IndexRole:
    """Classify one indexed party against the community's leading names."""
    if developer_for(name, developers) is not None:
        return IndexRole.DEVELOPER
    folded = party_key(name)
    project_key = party_key(project)
    if project_key and folded == project_key:
        return IndexRole.PROJECT
    if association and name_covers(association, name):
        return IndexRole.ASSOCIATION
    tokens = folded.split()
    if len(tokens) >= 2 and tokens[0] == project_key and tokens[1] in ("PHASE", "PHAS"):
        return IndexRole.PHASE
    return IndexRole.OTHER


def nearby_numbers(number: str, *, before: int = 3, after: int = 0) -> tuple[str, ...]:
    """Same-day document numbers around this one, nearest first.

    A notice of completion is usually the number just before the developer's
    first grant deed. A spouse deed or a second notice can sit in between.
    """
    parsed = SacramentoCountyRecorder().parse(number)
    if parsed is None or before < 0 or after < 0:
        return ()
    sequence = int(parsed.sequence)
    day = parsed.number[:8]
    found: list[str] = []
    for delta in range(1, before + 1):
        nxt = sequence - delta
        if nxt >= 0:
            found.append(f"{day}{nxt:04d}")
    for delta in range(1, after + 1):
        nxt = sequence + delta
        if nxt <= 9999:
            found.append(f"{day}{nxt:04d}")
    return tuple(found)


def closing_numbers(number: str) -> tuple[str, str]:
    """The same-day numbers immediately before and after a developer grant deed.

    The preceding number is the notice of completion. The following number is
    the partial reconveyance or the buyer's deed of trust. Either side is
    empty when that number would leave the day.
    """
    earlier = nearby_numbers(number, before=1, after=0)
    later = nearby_numbers(number, before=0, after=1)
    return (earlier[0] if earlier else "", later[0] if later else "")


def expected_companions(number: str) -> tuple[tuple[str, str], ...]:
    """Numbers beside a developer grant, and the filing each one usually is.

    The previous number is the notice of completion, filing 306. The next
    number is the buyer's deed of trust, filing 230, unless a partial
    reconveyance of an earlier builder lien, filing 613, was recorded there
    instead. A trustee's deed upon sale, filing 695, is not on that day: it
    cites the buyer's deed of trust.
    """
    earlier, later = closing_numbers(number)
    found: list[tuple[str, str]] = []
    if earlier:
        found.append((earlier, "306"))
    if later:
        found.append((later, "230"))
    return tuple(found)


@dataclass(frozen=True)
class IndexQuery:
    """One public-index search: a leading name, and a filing when the name alone is too broad."""

    name: str
    filing: Filing | None
    role: IndexRole


def index_queries(
    project: str,
    association: str,
    developers: tuple[Developer, ...],
) -> tuple[IndexQuery, ...]:
    """Searches that separate this community's instruments.

    Notices of completion are filed under the developer, not under the project
    word. The declaration is filed under the project word. The association's
    deeds are filed under the association's leading name. An annexation may
    be under the phase or only under the developer.
    """
    found: list[IndexQuery] = []
    if project:
        for filing in (
            Filing.DECLARATION_OF_RESTRICTION,
            Filing.AMENDED_RESTRICTION,
            Filing.DECLARATION_OF_ANNEXATION,
            Filing.AMENDMENT,
        ):
            found.append(IndexQuery(party_key(project), filing, IndexRole.PROJECT))
    if association:
        found.append(IndexQuery(party_key(association), None, IndexRole.ASSOCIATION))
    for developer in developers:
        for name in developer.names:
            query = party_key(name)
            found.append(IndexQuery(query, Filing.NOTICE_OF_COMPLETION, IndexRole.DEVELOPER))
            found.append(IndexQuery(query, Filing.GRANT_DEED, IndexRole.DEVELOPER))
            found.append(IndexQuery(query, Filing.DECLARATION_OF_ANNEXATION, IndexRole.DEVELOPER))
    return tuple(found)


def _follow(name: str, developers: tuple[Developer, ...] = ()) -> bool:
    """False for a developer or a lender. Those names match other parcels."""
    folded = party_key(name)
    if not folded or is_developer(name, developers):
        return False
    if any(token in folded for token in ("ULTRALIGHT", "WACHOVIA", "FEDERAL NATL", "SUNRUN", "SACTO MUNI")):
        return False
    return not (
        folded.startswith("COUNTY OF ")
        or folded.startswith("CITY OF ")
        or folded.startswith("STATE OF ")
        or folded.startswith("BANK ")
        or " BANK " in f" {folded} "
    )


_LIEN_CODES = frozenset({"230"})
_RELEASE_CODES = frozenset({"238", "613"})
_FORECLOSURE_CODES = frozenset({"694", "695", "801"})
_NOTICE_CODES = frozenset({"306"})
_DEFAULT_CODES = frozenset({"531", "543"})
_SUBSTITUTION_CODES = frozenset({"239"})
_DEATH_CODES = frozenset({"153", "156", "157", "155"})
_ASSIGNMENT_CODES = frozenset({"366"})  # UCC assignment; deed-of-trust assignments match by description
_EASEMENT_CODES = frozenset({"190", "215", "485", "681"})


def instrument_kind(codes: tuple[str, ...] = (), descriptions: tuple[str, ...] = ()) -> str:
    """Classify an instrument for the ownership walk.

    ``fee`` is a grant, quitclaim, or other fee conveyance. ``foreclosure`` is a
    trustee's deed or deed in lieu. ``lien`` is a deed of trust. ``release`` is a
    reconveyance (and wins over a paired substitution). ``notice`` is a notice of
    completion. ``default`` is a notice of default or a notice of trustee's sale:
    it cites the deed of trust and does not transfer the fee. ``substitution``
    is a substitution of trustee. ``death`` is an
    affidavit of death or similar. ``assignment`` is an assignment of a lien or
    UCC. ``easement`` does not replace the fee owner. Empty means still unknown.
    """
    folded = " ".join(descriptions).upper()
    if any(code in _RELEASE_CODES for code in codes) or "RECONVEYANCE" in folded:
        return "release"
    if foreclosure_deed(codes, descriptions):
        return "foreclosure"
    if (
        any(code in _DEFAULT_CODES for code in codes)
        or "NOTICE OF DEFAULT" in folded
        or "NOTICE OF TRUSTEES SALE" in folded
    ):
        return "default"
    if any(code in _LIEN_CODES for code in codes) or "DEED OF TRUST" in folded:
        if "ASSIGNMENT" in folded:
            return "assignment"
        return "lien"
    if any(code in _SUBSTITUTION_CODES for code in codes) or "SUBSTITUTION OF TRUSTEE" in folded:
        return "substitution"
    if any(code in _NOTICE_CODES for code in codes) or "NOTICE OF COMPLETION" in folded:
        return "notice"
    if (
        any(code in _DEATH_CODES for code in codes)
        or "AFFIDAVIT OF DEATH" in folded
        or folded.startswith("DEATH OF")
        or "AFFIDAVIT TERMINATING" in folded
    ):
        return "death"
    if any(code in _ASSIGNMENT_CODES for code in codes) or (
        "ASSIGNMENT" in folded and "DEED OF TRUST" not in folded
    ):
        return "assignment"
    if any(code in _EASEMENT_CODES for code in codes) or "EASEMENT" in folded or "RIGHT OF WAY" in folded:
        return "easement"
    if any(code in _CONVEYANCE_CODES for code in codes):
        return "fee"
    if folded.startswith("GRANT DEED") or folded.startswith("QUITCLAIM") or folded == "DEED":
        return "fee"
    return ""


def foreclosure_deed(codes: tuple[str, ...] = (), descriptions: tuple[str, ...] = ()) -> bool:
    """True for a trustee's deed upon sale or a deed in lieu of foreclosure.

    Both transfer the fee. The trustee's deed is the lien sale: the trustee
    conveys, and the grantee is the buyer, often the beneficiary when nobody
    else bids. A later grant from that beneficiary is the resale, not the sale.
    The cited deed of trust names the owner who lost the property. A
    reconveyance is the other ending: the loan was paid and the owner stayed.
    """
    folded = " ".join(descriptions).upper()
    if any(code in _FORECLOSURE_CODES for code in codes):
        return True
    return "TRUSTEES DEED" in folded or "DEED IN LIEU" in folded


def party_roles(kind: str) -> tuple[str, str]:
    """Index grantor role, then index grantee role.

    On a deed of trust the grantor is the trustor, who owns the fee, and the
    grantee is the beneficiary, the lender. On a reconveyance the grantee is
    the owner whose lien is released. On a grant deed both are owners. A
    notice of completion names the builder and has no buyer. A substitution
    of trustee is lien paperwork. A death affidavit is not a grant.
    """
    if kind == "foreclosure":
        return ("trustee", "buyer")
    if kind == "lien":
        return ("trustor", "beneficiary")
    if kind == "release":
        return ("trustee", "owner")
    if kind == "notice":
        return ("builder", "")
    if kind == "substitution":
        return ("trustee", "trustee")
    if kind == "death":
        return ("decedent", "affiant")
    if kind == "assignment":
        return ("assignor", "assignee")
    if kind == "easement":
        return ("grantor", "grantee")
    return ("grantor", "grantee")


_RESTATEMENT_SKIP = frozenset({
    "TRUSTEE", "TRUST", "TR", "REV", "REVOCABLE", "FAMILY", "FMLY", "ETC",
    "LLC", "INC", "LIVING", "LIV", "THE", "AND",
})


def owner_restatement(grantors: tuple[str, ...], grantees: tuple[str, ...]) -> bool:
    """True when a fee deed restates the same owner, often into that owner's trust.

    The fee did not change hands. A later leaf must not treat the trust as a
    new buyer. ``TRUSTEE`` and ``TRUST`` are ignored so ``MERRIWEATHER ADA M``
    matches ``MERRIWEATHER ADA M TRUSTEE`` and ``ADA M MERRIWEATHER REV FAMILY TRUST``.
    """
    if not grantors or not grantees:
        return False
    for grantor in grantors:
        for grantee in grantees:
            if _same_owner(grantor, grantee):
                return True
            left, right = _restatement_key(grantor), _restatement_key(grantee)
            if left and left == right:
                return True
    return False


def _restatement_key(name: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            token
            for token in party_key(name).split()
            if len(token) > 1 and token not in _RESTATEMENT_SKIP
        )
    )


def other_community(name: str) -> bool:
    """True for an association or another subdivision that is not a unit buyer."""
    folded = party_key(name)
    if not folded:
        return False
    if folded.startswith("MYSTIQUE COMMUNITY"):
        return True
    if "RIVAGE" in folded:
        return True
    if "VALENCIA COMMUNITY" in folded or folded.startswith("VALENCIA ASS"):
        return True
    return False


def advances_chain(kind: str, grantors: tuple[str, ...] = (), grantees: tuple[str, ...] = ()) -> bool:
    """True when this instrument can move the buyer frontier one step.

    A notice of completion, notice of default, notice of trustee's sale,
    substitution, death affidavit, assignment, lien, release, or easement
    does not. A fee that only restates the same owner
    into a trust does not. An association or another community's deed does not.
    """
    if kind not in ("fee", "foreclosure"):
        return False
    if kind == "fee" and owner_restatement(grantors, grantees):
        return False
    if any(other_community(name) for name in (*grantors, *grantees)):
        return False
    return True


def buyer_lien(grantees: tuple[str, ...], trustors: tuple[str, ...]) -> bool:
    """True when a deed of trust's trustor is the grant deed's grantee.

    The lien does not transfer the fee. A same-day deed of trust whose trustor
    is someone else is a different parcel.
    """
    return any(_same_owner(owner, trustor) for owner in grantees for trustor in trustors)


@dataclass(frozen=True)
class FiledInstrument:
    """One instrument with its kind, parties, filings, and the numbers it cites."""

    number: str
    recorded: date | None
    kind: str
    grantors: tuple[str, ...]
    grantees: tuple[str, ...]
    cross_references: tuple[str, ...] = ()
    filing_code: str = ""
    filing_name: str = ""


@dataclass(frozen=True)
class InstrumentLink:
    """How one instrument sits beside the subject."""

    number: str
    recorded: date | None
    kind: str
    relation: str
    grantor_role: str
    grantee_role: str
    grantors: tuple[str, ...]
    grantees: tuple[str, ...]
    cross_references: tuple[str, ...]
    before_community: bool


def relate_instruments(
    subject: FiledInstrument,
    others: tuple[FiledInstrument, ...],
    *,
    issued: date | None = None,
) -> tuple[InstrumentLink, ...]:
    """Label the subject, a same-day neighbor, and a document it cites.

    ``buyer lien`` means the deed of trust's trustor is the grant's grantee.
    ``released lien`` means a reconveyance cites that deed of trust. ``same
    citation`` means the neighbor cites that same number. ``same parties``
    means another fee deed names the same owner. ``other parties`` means the
    neighbor does not. ``before_community`` is set when the instrument was
    recorded before ``issued``.
    """
    links = [_instrument_link(subject, "subject", issued)]
    seen = {subject.number}
    for other in others:
        if other.number in seen:
            continue
        seen.add(other.number)
        links.append(_instrument_link(other, _relation(subject, other), issued))
    return tuple(links)


def _relation(subject: FiledInstrument, other: FiledInstrument) -> str:
    if subject.kind == "fee" and other.kind == "lien" and buyer_lien(subject.grantees, other.grantors):
        return "buyer lien"
    if other.number in subject.cross_references and subject.kind == "release" and other.kind == "lien":
        return "released lien"
    if other.number in subject.cross_references or subject.number in other.cross_references:
        return "cited"
    if set(subject.cross_references) & set(other.cross_references):
        return "same citation"
    if subject.kind == "fee" and other.kind == "fee" and _shares_owner(subject, other):
        return "same parties"
    return "other parties"


def _shares_owner(left: FiledInstrument, right: FiledInstrument) -> bool:
    parties = (*left.grantors, *left.grantees)
    return any(_same_owner(name, other) for name in parties for other in (*right.grantors, *right.grantees))


def _instrument_link(item: FiledInstrument, relation: str, issued: date | None) -> InstrumentLink:
    grantor_role, grantee_role = party_roles(item.kind)
    before = item.recorded is not None and issued is not None and item.recorded < issued
    return InstrumentLink(
        item.number,
        item.recorded,
        item.kind,
        relation,
        grantor_role,
        grantee_role,
        item.grantors,
        item.grantees,
        item.cross_references,
        before,
    )


def conveys_row(row: IndexedInstrument) -> bool:
    """True when this index row transfers the fee, not a lien or a deed of trust."""
    if row.filing_code in _CONVEYANCE_CODES:
        return True
    label = row.filing_name.upper()
    if "DEED OF TRUST" in label or "UCC" in label:
        return False
    return label.startswith("GRANT DEED") or label.startswith("QUITCLAIM") or label == "DEED" or "TRUSTEES DEED" in label


def fee_deeds(results: tuple[NameSearch, ...]) -> tuple[Conveyance, ...]:
    """Fee transfers from a party trace, one row per document number."""
    found: dict[str, Conveyance] = {}
    for result in results:
        for row in result.rows:
            if row.number in found or not conveys_row(row):
                continue
            found[row.number] = Conveyance(row.number, row.recorded, row.grantors, row.grantees)
    return tuple(found.values())


def next_parties(row: IndexedInstrument, developers: tuple[Developer, ...] = ()) -> tuple[str, ...]:
    """Grantors and grantees worth searching on the other side of a fee deed.

    A UCC stays on the debtor who was searched. Its secured party is not followed.
    """
    if not conveys_row(row):
        return ()
    found: list[str] = []
    for name in (*row.grantors, *row.grantees):
        if _follow(name, developers) and name not in found:
            found.append(name)
    return tuple(found)


def document_numbers(*texts: str) -> tuple[str, ...]:
    """Twelve-digit Sacramento document numbers in filenames or cells.

    ``document_numbers("GD 200709281731.pdf")`` yields ``200709281731``. A digit
    run that is not a recording date is left out. Order is the order they
    appear, without repeats.
    """
    parser = SacramentoCountyRecorder()
    found: list[str] = []
    for text in texts:
        for match in re.finditer(r"\d{12}", text):
            parsed = parser.parse(match.group())
            if parsed is None or parsed.number in found:
                continue
            found.append(parsed.number)
    return tuple(found)


def find_deeds(
    items: tuple[Conveyance, ...],
    *,
    grantor: str = "",
    grantee: str = "",
) -> tuple[Conveyance, ...]:
    """Deeds matching a grantor, a grantee, or both. An empty side is not filtered."""
    if not grantor and not grantee:
        return items
    found: list[Conveyance] = []
    for item in items:
        if grantor and not any(same_party(grantor, name) for name in item.grantors):
            continue
        if grantee and not any(same_party(grantee, name) for name in item.grantees):
            continue
        found.append(item)
    return tuple(found)


def in_documents(
    rows: tuple[IndexedInstrument, ...], numbers: tuple[str, ...]
) -> tuple[IndexedInstrument, ...]:
    """Index rows whose document number is already in ``numbers``.

    A name search returns a grantor's other parcels. This keeps the rows that
    belong to the document list under analysis.
    """
    parser = SacramentoCountyRecorder()
    wanted: set[str] = set()
    for number in numbers:
        parsed = parser.parse(number)
        if parsed is not None:
            wanted.add(parsed.number)
    return tuple(row for row in rows if row.number in wanted)


@dataclass(frozen=True)
class DeedFindings:
    """Index rows already pinned, and rows that are only a search hit."""

    pinned: tuple[IndexedInstrument, ...]
    candidates: tuple[IndexedInstrument, ...]


def classify_deeds(
    rows: tuple[IndexedInstrument, ...], numbers: tuple[str, ...]
) -> DeedFindings:
    """Split a search into pinned document numbers and candidates.

    A candidate is not an association fact. A new pin is a grant-deed file
    added to the community pins. The pinned numbers are what a later analysis
    starts from when the ownership database is gone.
    """
    pinned = in_documents(rows, numbers)
    known = {row.number for row in pinned}
    return DeedFindings(pinned, tuple(row for row in rows if row.number not in known))


class RecordedIn:
    """Mixin for a city whose recorded instruments are filed with one county."""

    county_recorder: CountyRecorder


class Sacramento(RecordedIn):
    """City of Sacramento. Recorded instruments are filed with Sacramento County.

    Building and operating permits are on Citizen Access, ``citizen_access``.
    Property tax accounts are ``tax``. The assessor's secured roll is
    ``secured_roll``.
    """

    county_recorder = SacramentoCountyRecorder()

    @staticmethod
    def citizen_access():
        from jason.community.accela import SacramentoCitizenAccess

        return SacramentoCitizenAccess()

    @staticmethod
    def tax():
        from jason.community.tax import SacramentoCountyTax

        return SacramentoCountyTax()

    @staticmethod
    def secured_roll(path):
        from jason.community.secured import SecuredRoll

        return SecuredRoll(path)


# Sacramento filing codes. The association subset is ``Filing``.
FILING_NAMES: dict[str, str] = {
    "151": "AFFIDAVIT",
    "153": "AFFIDAVIT OF DEATH",
    "156": "AFFIDAVIT TERMINATING JOINT TENANCY",
    "157": "AFFIDAVIT TERMINATING LIFE ESTATE",
    "190": "EASEMENT",
    "215": "CONSERVATION EASEMENT",
    "339": "DECREE OF DISTRIBUTION",
    "342": "DECREE QUIETING TITLE",
    "380": "CERTIFICATE OF SALE",
    "455": "FINAL ORDER OF CONDEMNATION",
    "465": "PATENT",
    "485": "RIGHT OF WAY",
    "642": "SURRENDER OF LIFE ESTATE",
    "155": "AFFIDAVIT TERMINATING HOMESTEAD INTEREST",
    "162": "DECLARATION",
    "188": "COVENANT AND AGREEMENT",
    "220": "AMENDED RESTRICTION",
    "225": "AMENDMENT",
    "240": "AMENDMENT TO CONDO PLAN",
    "301": "CONDOMINIUM PLAN",
    "306": "NOTICE OF COMPLETION",
    "239": "SUBSTITUTION OF TRUSTEE",
    "613": "PARTIAL RECONVEYANCE",
    "320": "DECLARATION OF ANNEXATION",
    "324": "DECLARATION OF RESTRICTION",
    "386": "NOTICE OF ASSOCIATION LIEN",
    "433": "PARCEL MAP",
    "435": "SUBDIVISION MAP",
    "446": "ARTICLES OF INCORPORATION",
    "476": "RESOLUTION",
    "478": "RESTRICTIVE COVENANT",
    "494": "BY LAWS",
    "499": "RESTRICTIVE COVENANT MODIFICATION",
    "604": "CANCELLATION OF RESTRICTIONS",
    "655": "RELEASE OF ASSESSMENT OF ASSOCIATION LIEN",
    "680": "DEED",
    "681": "EASEMENT DEED",
    "685": "GRANT DEED",
    "689": "QUITCLAIM DEED",
    "692": "TAX DEED",
    "694": "TRUSTEES DEED",
    "695": "TRUSTEES DEED UPON SALE",
    "531": "NOTICE OF DEFAULT",
    "543": "NOTICE OF TRUSTEES SALE",
    "697": "REVOCABLE TRANSFER ON DEATH DEED",
    "801": "DEED IN LIEU OF FORECLOSURE",
    "365": "UCC AMENDMENT",
    "366": "UCC ASSIGNMENT",
    "367": "UCC CONTINUATION",
    "368": "UCC FINANCING STATEMENT",
    "370": "UCC PARTIAL RELEASE",
    "371": "UCC RELEASE",
    "372": "UCC TERMINATION",
    "389": "NOTICE OF CLAIM OR MECHANICS LIEN",
    "635": "RELEASE OF MECHANICS LIEN",
    "232": "EXTENSION MECHANICS LIEN",
    "385": "NOTICE OF ACTION",
    "223": "AMENDED NOTICE OF ACTION LIS PENDENS",
    "651": "WITHDRAWAL OF LIS PENDENS",
    "291": "CERTIFICATE OF PARTIAL DISCHARGE OF NOTICE OF PENDING ACTION",
    "269": "RELEASE OF LIEN BOND",
    "270": "BONDS TO GUARANTEE MECHANIC LIEN",
    "305": "NOTICE OF CESSATION",
    "539": "NOTICE OF NON RESPONSIBILITY",
}

API = "https://recordersdocumentindex.saccounty.gov/SearchService/api/"
SEARCH_URL = API + "Search/GetSearchResults"
SECURE_URL = API + "SearchConfiguration/GetSecureKey"
DATES_URL = API + "SearchConfiguration/GetMinMaxDate/OfficialRecords"


@dataclass(frozen=True)
class IndexSession:
    """A key the index issued for this process. It is not stored."""

    encrypted_key: str
    password: str


@dataclass(frozen=True)
class FilingType:
    """One filing code on an instrument. A row can carry more than one."""

    code: str
    description: str


@dataclass(frozen=True)
class InstrumentDetail:
    """The index detail page: type, status, and the parties."""

    number: str
    recorded: date | None
    status: str
    pages: int | None
    apn: str
    filings: tuple[FilingType, ...]
    parties: tuple[IndexParty, ...]

    @property
    def grantors(self) -> tuple[str, ...]:
        return tuple(party.name for party in self.parties if party.role == "Grantor")

    @property
    def grantees(self) -> tuple[str, ...]:
        return tuple(party.name for party in self.parties if party.role == "Grantee")

    @property
    def cross_references(self) -> tuple[str, ...]:
        return tuple(party.cross_reference for party in self.parties if party.cross_reference)


@dataclass(frozen=True)
class IndexParty:
    """One name on an instrument. ``cross_reference`` is another document number."""

    name: str
    role: str
    cross_reference: str


@dataclass(frozen=True)
class IndexedInstrument:
    """One row from a county index search."""

    number: str
    recorded: date | None
    sequence: str
    filing_code: str
    filing_name: str
    names: tuple[str, ...]
    internal_id: str = ""

    @property
    def grantors(self) -> tuple[str, ...]:
        return parties(list(self.names))[0]

    @property
    def grantees(self) -> tuple[str, ...]:
        return parties(list(self.names))[1]


@dataclass(frozen=True)
class NameSearch:
    """One person's index query, how many rows matched, and the rows kept.

    ``wide`` is a query that matched more parcels than ``limit``. Its rows are
    empty so those other parcels are not followed.
    """

    query: str
    total: int
    rows: tuple[IndexedInstrument, ...]

    @property
    def wide(self) -> bool:
        return self.total > len(self.rows)


@dataclass(frozen=True)
class Conveyance:
    """One recorded transfer. ``apn`` is the parcel this number was collected for.

    The index often leaves the parcel field as ``Reference``. The caller supplies
    the APN from the assessor or the research sheet.
    """

    number: str
    recorded: date | None
    grantors: tuple[str, ...]
    grantees: tuple[str, ...]
    cross_references: tuple[str, ...] = ()
    apn: str = ""


@dataclass(frozen=True)
class ChainStep:
    """One instrument, the earlier deeds it connects to, and cited numbers not yet loaded."""

    conveyance: Conveyance
    priors: tuple[str, ...] = ()
    cited: tuple[str, ...] = ()


@dataclass(frozen=True)
class OwnershipHistory:
    """Document numbers for one parcel, newest first, back toward a developer."""

    apn: str
    steps: tuple[ChainStep, ...]
    developers: tuple[Developer, ...] = ()

    def from_developer(self, item: Conveyance) -> bool:
        """True when a grantor is one of the pinned subdividers."""
        return any(is_developer(name, self.developers) for name in item.grantors)

    @property
    def numbers(self) -> tuple[str, ...]:
        return tuple(step.conveyance.number for step in self.steps)

    @property
    def reached_developer(self) -> bool:
        return any(self.from_developer(step.conveyance) for step in self.steps)

    @property
    def gaps(self) -> tuple[str, ...]:
        """Deeds that do not reach an earlier document and are not the developer grant."""
        return tuple(
            step.conveyance.number
            for step in self.steps
            if not step.priors and not self.from_developer(step.conveyance)
        )

    def step(self, number: str) -> ChainStep | None:
        for item in self.steps:
            if item.conveyance.number == number:
                return item
        return None

    def granted_by(self, name: str) -> tuple[Conveyance, ...]:
        return find_deeds(tuple(item.conveyance for item in self.steps), grantor=name)

    def granted_to(self, name: str) -> tuple[Conveyance, ...]:
        return find_deeds(tuple(item.conveyance for item in self.steps), grantee=name)

    def paths(self, number: str) -> tuple[tuple[str, ...], ...]:
        """Walk backward from ``number``. Two priors produce two paths.

        Each path starts at ``number`` and ends at a deed with no earlier
        document in this history. A repeated number ends that path.
        """
        if self.step(number) is None:
            return ()
        found: list[tuple[str, ...]] = []

        def walk(current: str, trail: tuple[str, ...]) -> None:
            if current in trail:
                found.append(trail)
                return
            nxt = trail + (current,)
            item = self.step(current)
            priors = item.priors if item is not None else ()
            if not priors:
                found.append(nxt)
                return
            for prior in priors:
                walk(prior, nxt)

        walk(number, ())
        return tuple(found)


@dataclass(frozen=True)
class AnchorExpansion:
    """Deeds placed from known anchors, and the candidates still loose.

    A parcel is solved when its current document joins an anchor by citation
    or by a party handoff. A deed that would join two different parcels stays
    contested and remains a candidate. Anchor documents stay available for
    every parcel.
    """

    solved: tuple[tuple[str, str, tuple[str, ...]], ...]
    open_deeds: tuple[tuple[str, str], ...]
    remaining: tuple[str, ...]
    contested: tuple[tuple[str, tuple[str, ...]], ...]


def expand_anchors(
    items: tuple[Conveyance, ...],
    *,
    anchors: tuple[str, ...] = (),
    currents: tuple[tuple[str, str], ...] = (),
    developers: tuple[Developer, ...] = (),
) -> AnchorExpansion:
    """Grow placed deeds out from anchors until no new deed joins.

    Anchors are the known document numbers, plus any deed whose grantor is a
    pinned developer. Each pass adds a deed that connects to a placed deed and
    does not connect two different parcels. A current document that becomes
    placed is a solved chain: the path runs from that document back to an
    anchor. What never joins is the candidate pool for the next pass.
    """
    by_number: dict[str, Conveyance] = {}
    for item in items:
        by_number.setdefault(item.number, item)
    anchor_ids = set(anchors)
    for item in by_number.values():
        if any(is_developer(name, developers) for name in item.grantors):
            anchor_ids.add(item.number)
    placed = {number for number in anchor_ids if number in by_number}
    neighbors: dict[str, set[str]] = {number: set() for number in placed}
    contested: dict[str, tuple[str, ...]] = {}

    changed = True
    while changed:
        changed = False
        for item in by_number.values():
            if item.number in placed:
                continue
            links = [
                other
                for other in by_number.values()
                if other.number in placed and _deeds_connect(other, item, developers)
            ]
            if not links:
                continue
            if not _one_chain(links, anchor_ids):
                contested[item.number] = tuple(sorted(link.number for link in links))
                continue
            contested.pop(item.number, None)
            placed.add(item.number)
            neighbors[item.number] = {link.number for link in links}
            for link in links:
                neighbors.setdefault(link.number, set()).add(item.number)
            changed = True

    solved: list[tuple[str, str, tuple[str, ...]]] = []
    open_deeds: list[tuple[str, str]] = []
    for apn, number in currents:
        if number not in placed:
            open_deeds.append((apn, number))
            continue
        solved.append((apn, number, _path_to_anchor(number, neighbors, anchor_ids)))
    remaining = tuple(
        number for number in sorted(by_number) if number not in placed
    )
    held = tuple(sorted(contested.items()))
    return AnchorExpansion(tuple(solved), tuple(open_deeds), remaining, held)


def _deeds_connect(
    left: Conveyance,
    right: Conveyance,
    developers: tuple[Developer, ...],
) -> bool:
    """True when one deed cites the other, or the parties hand off on one parcel."""
    earlier, later = _earlier_deed(left, right)
    if earlier is None or later is None:
        return False
    if earlier.number in later.cross_references:
        return True
    if not _handed_off(earlier, later, developers):
        return False
    return _apns_agree(earlier, later)


def _earlier_deed(
    left: Conveyance, right: Conveyance
) -> tuple[Conveyance | None, Conveyance | None]:
    if _recorded_before(left, right):
        return left, right
    if _recorded_before(right, left):
        return right, left
    return None, None


def _apns_agree(left: Conveyance, right: Conveyance) -> bool:
    one, two = _apn_digits(left.apn), _apn_digits(right.apn)
    if not one or not two:
        return True
    return one == two


def _apn_digits(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits if len(digits) == 14 else ""


def _one_chain(links: list[Conveyance], anchors: set[str]) -> bool:
    """True when the placed deeds are anchors, or they name one parcel."""
    owned = [item for item in links if item.number not in anchors]
    if not owned:
        return True
    parcels = {_apn_digits(item.apn) for item in owned}
    parcels.discard("")
    return len(parcels) <= 1


def _path_to_anchor(
    start: str,
    neighbors: dict[str, set[str]],
    anchors: set[str],
) -> tuple[str, ...]:
    """Document numbers from ``start`` back to the first anchor reached."""
    if start in anchors:
        return (start,)
    parent: dict[str, str] = {}
    queue = [start]
    seen = {start}
    found = ""
    while queue:
        current = queue.pop(0)
        for nxt in sorted(neighbors.get(current, ())):
            if nxt in seen:
                continue
            parent[nxt] = current
            if nxt in anchors:
                found = nxt
                queue = []
                break
            seen.add(nxt)
            queue.append(nxt)
    if not found:
        return (start,)
    path = [found]
    while path[-1] != start:
        path.append(parent[path[-1]])
    path.reverse()
    return tuple(path)


def succession(
    items: tuple[Conveyance, ...],
    *,
    apn: str = "",
    developers: tuple[Developer, ...] = (),
) -> OwnershipHistory:
    """Order known instruments from the latest deed back to the developer.

    A cross-reference is the prior deed when that number is in the set. Otherwise
    a later grantor who was the earlier grantee is the link. Association
    abbreviations and a person's dropped initial use the same party. Two
    spellings of one pinned developer do too. ``WATT COMMUNITIES LLC`` does
    not hand off to ``WATT COMMUNITIES AT MYSTIQUE``. Several earlier deeds
    can match; each stays on the step. A developer grantor is still linked
    to the earlier deed that conveyed the land to that developer.
    """
    by_number: dict[str, Conveyance] = {}
    for item in items:
        by_number.setdefault(item.number, item)
    steps: list[ChainStep] = []
    for item in sorted(by_number.values(), key=_newest_first, reverse=True):
        known, missing = _cited_priors(item, by_number)
        if known:
            priors = known
        else:
            priors = tuple(
                other.number
                for other in sorted(by_number.values(), key=_newest_first, reverse=True)
                if other.number != item.number
                and _recorded_before(other, item)
                and _handed_off(other, item, developers)
            )
        steps.append(ChainStep(item, priors, missing))
    return OwnershipHistory(apn, tuple(steps), developers)


def _cited_priors(
    item: Conveyance, by_number: dict[str, Conveyance]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    known: list[str] = []
    missing: list[str] = []
    for number in item.cross_references:
        if number == item.number:
            continue
        earlier = by_number.get(number)
        if earlier is None:
            if number not in missing:
                missing.append(number)
            continue
        if _recorded_before(earlier, item) and number not in known:
            known.append(number)
    return tuple(known), tuple(missing)


def _handed_off(
    earlier: Conveyance,
    later: Conveyance,
    developers: tuple[Developer, ...] = (),
) -> bool:
    for grantor in later.grantors:
        for grantee in earlier.grantees:
            if _same_owner(grantor, grantee, developers):
                return True
    return False


def _same_owner(left: str, right: str, developers: tuple[Developer, ...] = ()) -> bool:
    """True when two index spellings are one grantor handing off to the next deed.

    Exact spelling matches. ``ASSN`` and ``ASSOC`` match ``ASSOCIATION``.
    ``PHAS`` matches ``PHASE``. A person matches on surname and given name, so
    a dropped initial or a third name still joins. The same words in either
    order are one person. A name candidate joins the two spellings when a
    shared word anchors them and every other word is one of those pairs. Two
    spellings of one pinned developer match. A different company that shares
    a leading word does not.
    """
    if not left or not right:
        return False
    if handoff_key(left) == handoff_key(right):
        return True
    left_developer = developer_for(left, developers)
    if left_developer is not None and left_developer is developer_for(right, developers):
        return True
    if _is_person(left) and _is_person(right):
        query = index_name(left)
        if query and " " in query and query == index_name(right):
            return True
        left_tokens = _person_tokens(left)
        right_tokens = _person_tokens(right)
        if len(left_tokens) >= 2 and left_tokens == right_tokens:
            return True
    return _explained_by_candidates(left, right)


def _explained_by_candidates(left: str, right: str) -> bool:
    """True when name candidates account for every word the two names do not share."""
    left_tokens = _letters(left).split()
    right_tokens = _letters(right).split()
    shared = set(left_tokens) & set(right_tokens)
    if not any(len(token) > 1 for token in shared):
        return False
    pairs = name_candidates(left, right)
    if not pairs:
        return False
    explained = {token for pair in pairs for token in (pair.short, pair.long)}
    extras = [token for token in (*left_tokens, *right_tokens) if token not in shared]
    return bool(extras) and all(token in explained for token in extras)


def _recorded_before(earlier: Conveyance, later: Conveyance) -> bool:
    if earlier.recorded is None or later.recorded is None:
        return False
    return earlier.recorded < later.recorded


def _newest_first(item: Conveyance) -> tuple[bool, date, str]:
    return (item.recorded is not None, item.recorded or date.min, item.number)


def _document_refs(numbers: tuple[str, ...]) -> tuple[str, ...]:
    parser = SacramentoCountyRecorder()
    found: list[str] = []
    for number in numbers:
        parsed = parser.parse(number)
        if parsed is None or parsed.number in found:
            continue
        found.append(parsed.number)
    return tuple(found)


def _parcel_apn(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 14:
        return ""
    return f"{digits[0:3]}-{digits[3:7]}-{digits[7:10]}-{digits[10:14]}"


def instruments(payload: dict | None, recorder: CountyRecorder | None = None) -> tuple[IndexedInstrument, ...]:
    """Read ``SearchResults`` rows. A null index body is an empty tuple."""
    if not payload or not payload.get("SearchResults"):
        return ()
    parser = recorder or SacramentoCountyRecorder()
    found: list[IndexedInstrument] = []
    for result in payload["SearchResults"]:
        number = str(result.get("PrimaryDocNumber") or "")
        parsed = parser.parse(number)
        raw_names = str(result.get("Names") or "")
        names = tuple(part for part in raw_names.replace("<br/>", "|").split("|") if part)
        raw_code = str(result.get("FilingCode") or "")
        if raw_code.isdigit():
            code, label = raw_code, FILING_NAMES.get(raw_code, "")
        else:
            code, label = "", raw_code.replace("<br/>", "; ")
        recorded = _index_date(str(result.get("DocumentDate") or ""))
        if recorded is None and parsed is not None:
            recorded = parsed.recorded
        found.append(
            IndexedInstrument(
                number=number,
                recorded=recorded,
                sequence=parsed.sequence if parsed else "",
                filing_code=code,
                filing_name=label,
                names=names,
                internal_id=str(result.get("ID") or ""),
            )
        )
    return tuple(found)


def index_parties(payload: dict | None) -> tuple[IndexParty, ...]:
    rows = (payload or {}).get("NamesForPagination") or []
    return tuple(
        IndexParty(
            str(row.get("Fullname") or ""),
            str(row.get("NameTypeDesc") or ""),
            str(row.get("CrossRefDocNumber") or ""),
        )
        for row in rows
    )


def _index_date(value: str) -> date | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _open_session(getter) -> IndexSession | None:
    payload = getter(SECURE_URL, {}, None)
    if not payload or not payload.get("EncryptedKey"):
        return None
    return IndexSession(str(payload["EncryptedKey"]), str(payload.get("Password") or ""))


def _index_get(url: str, params: dict[str, str], headers: dict[str, str] | None) -> dict | None:
    target = url + ("?" + urlencode(params) if params else "")
    sent = {
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://recordersdocumentindex.saccounty.gov/",
    }
    sent.update(headers or {})
    request = Request(target, headers=sent)
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8").strip()
    if not body or body == "null":
        return None
    parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else None


def _search_params(
    recorder: SacramentoCountyRecorder,
    *,
    number: str = "",
    number_to: str = "",
    filing: Filing | DocType | None = None,
    name: str = "",
    start: int = 0,
    rows: int = 10,
    after: date | None = None,
    before: date | None = None,
) -> dict[str, str]:
    params = {
        "DocumentClass": "OfficialRecords",
        "IsBasicSearch": "false",
        "ProfileID": "Public",
        "NameTypeID": "0",
        "StartRow": str(start),
        "Rows": str(rows),
        "LastName": name,
        "DocNumberFrom": "",
        "DocNumberTo": "",
        "FilingCode": "",
    }
    if after is not None:
        params["MinRecordedDate"] = after.strftime("%m/%d/%Y")
    if before is not None:
        params["MaxRecordedDate"] = before.strftime("%m/%d/%Y")
    if number:
        params["DocNumberFrom"] = number
        params["DocNumberTo"] = number_to or number
        parsed = recorder.parse(number)
        if parsed is not None and (not number_to or number_to == number):
            stamp = parsed.recorded.strftime("%m/%d/%Y")
            params["MinRecordedDate"] = stamp
            params["MaxRecordedDate"] = stamp
    if filing is not None:
        params["FilingCode"] = filing.code if isinstance(filing, DocType) else filing.value
    return params
