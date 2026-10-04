"""Pull the mechanic's lien filings for the developers, the association, and every owner into the cache.

A name the passes searched narrowly already has every filing under it. A
wide name was narrowed only under deeds and UCC filings, so its mechanic's
liens, releases, and notices of action were never fetched; this task
narrows those names under the lien filings too. A name never searched is
searched now under the narrow filings plus these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from jason.community.index_cache import (
    _PARTY_LIMIT,
    IndexCache,
    NARROW_FILINGS,
    _filing_code,
    _search_key,
    _store_rows,
    cache_party_search,
    skip_lender,
)
from jason.community.recorder import Filing, SacramentoCountyRecorder, developer_for, index_name

MECHANICS_FILINGS = (
    Filing.MECHANICS_LIEN,
    Filing.RELEASE_OF_MECHANICS_LIEN,
    Filing.EXTENSION_OF_MECHANICS_LIEN,
    Filing.NOTICE_OF_ACTION,
    Filing.AMENDED_NOTICE_OF_ACTION,
    Filing.WITHDRAWAL_OF_LIS_PENDENS,
    Filing.MECHANICS_LIEN_BOND,
    Filing.RELEASE_OF_LIEN_BOND,
)

# Every lien-family filing a wide name may hide: the association's, the utility's, the courts', the tax agencies', and the loan defaults.
LIEN_FILINGS = MECHANICS_FILINGS + (
    Filing.NOTICE_OF_ASSOCIATION_LIEN,
    Filing.RELEASE_OF_ASSOCIATION_LIEN,
    Filing.RELEASE_OF_LIEN,
    Filing.UTILITY_LIEN,
    Filing.UTILITY_TERMINATION,
    Filing.ABSTRACT_OF_JUDGMENT,
    Filing.STATE_TAX_LIEN,
    Filing.NOTICE_OF_ASSESSMENT,
    Filing.NOTICE_OF_DEFAULT,
    Filing.NOTICE_OF_SALE,
    Filing.RESCISSION,
    Filing.POWER_TO_SELL,
    Filing.RECONVEYANCE,
)


@dataclass
class LienSyncResult:
    names: int = 0
    searched: int = 0
    narrowed: int = 0
    skipped: int = 0
    added: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"lien filings names={self.names} searched={self.searched} narrowed={self.narrowed} "
            f"skipped={self.skipped} added={self.added} errors={len(self.errors)}"
        )


def lien_queries(community, histories) -> tuple[str, ...]:
    """The index queries: each developer spelling, the association, and every owner on a chain."""
    found: list[str] = []
    for developer in community.developers():
        found.extend(developer.names)
    found.append(community.index_association())
    for item in histories:
        if item.association:
            continue
        for step in item.steps:
            for name in step.grantees:
                if skip_lender(name) or developer_for(name, community.developers()):
                    continue
                query = index_name(name)
                if query:
                    found.append(query)
    return tuple(dict.fromkeys(" ".join(q.upper().split()) for q in found if q.strip()))


def sync_liens(
    cache: IndexCache,
    recorder: SacramentoCountyRecorder,
    queries: tuple[str, ...],
    *,
    project: str,
    association: str,
    developers: tuple,
    fetch=None,
    note=None,
    filings: tuple[Filing, ...] = MECHANICS_FILINGS,
) -> LienSyncResult:
    """Fetch the lien filings in ``filings`` for each query that does not have them yet."""
    result = LienSyncResult(names=len(queries))
    session = recorder.open_session(fetch=fetch)
    if session is None:
        result.errors.append("no index session")
        return result
    for query in queries:
        try:
            before = cache.count()
            key = _search_key(query, "", "cache", None, None)
            cached = cache.cached_search(key)
            if cached is None:
                cache_party_search(
                    recorder, cache, query, project=project, association=association, developers=developers,
                    filings=NARROW_FILINGS + filings, session=session, fetch=fetch, note=note,
                )
                result.searched += 1
            elif cached[0]:
                result.narrowed += _narrow(cache, recorder, query, filings, session=session, fetch=fetch, project=project, association=association, developers=developers, note=note)
            else:
                result.skipped += 1
            result.added += max(0, cache.count() - before)
        except Exception as exc:
            result.errors.append(f"{query}: {exc}")
    return result


def _narrow(cache, recorder, query, filings, *, session, fetch, project, association, developers, note) -> int:
    """Narrow a wide name under each filing it has not been narrowed under. Returns searches made."""
    searches = 0
    for filing in filings:
        filing_key = _search_key(query, _filing_code(filing), "cache", None, None)
        if cache.cached_search(filing_key) is not None:
            continue
        if note is not None:
            note(f"{query} {filing.value}")
        batch = recorder.search(name=query, filing=filing, limit=_PARTY_LIMIT + 1, session=session, fetch=fetch)
        searches += 1
        if len(batch) > _PARTY_LIMIT:
            cache.put_search(filing_key, (), wide=True)
            continue
        numbers = _store_rows(recorder, cache, batch, session=session, fetch=fetch, project=project, association=association, developers=developers)
        cache.put_search(filing_key, numbers, wide=False)
    return searches


def _unused(_: date) -> None:  # keeps the date import for type readers
    return None
