"""Pull every UCC filing the solar lessors recorded into the index cache.

The county indexes a fixture filing by the debtor's name, so an owner the
passes never searched has no filing in the cache. Searching the lessor's
name instead returns every filing it recorded in the county, and the
parcel model then matches the debtors to the units' owners. A row already
cached keeps its detail; a new row is stored from the search page alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jason.community.index_cache import IndexCache
from jason.community.recorder import FiledInstrument, Filing, SacramentoCountyRecorder
from jason.community.solar import SolarProgram

FILINGS = (Filing.UCC_FINANCING, Filing.UCC_TERMINATION)


@dataclass
class SolarSyncResult:
    searched: int = 0
    rows: int = 0
    added: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"solar filings searched={self.searched} rows={self.rows} added={self.added} errors={len(self.errors)}"


def sync_solar(
    cache: IndexCache,
    recorder: SacramentoCountyRecorder,
    program: SolarProgram,
    *,
    fetch=None,
    page: int = 100,
) -> SolarSyncResult:
    """Search each lessor query under each UCC filing and cache the rows that name a lessor."""
    result = SolarSyncResult()
    session = recorder.open_session(fetch=fetch) if fetch is not None else None
    for query in program.index_queries:
        for filing in FILINGS:
            try:
                rows = recorder.search(name=query, filing=filing, rows=page, session=session, fetch=fetch)
            except Exception as exc:
                result.errors.append(f"{query} {filing.value}: {exc}")
                continue
            result.searched += 1
            numbers: list[str] = []
            for row in rows:
                # The index prints each party with its side, "(R) NAME" or "(E) NAME"; the row's
                # grantors and grantees are the names without the side.
                if not any(program.is_lessor(name) for name in (*row.grantors, *row.grantees)):
                    continue
                result.rows += 1
                numbers.append(row.number)
                if cache.get(row.number) is not None:
                    continue
                cache.put(FiledInstrument(
                    row.number, row.recorded, "", row.grantors, row.grantees, (), row.filing_code, row.filing_name,
                ))
                result.added += 1
            cache.put_search(f"{query}|{filing.value}|lessor||", tuple(numbers), wide=False)
    return result
