"""Placer County clerk-recorder — HTTP in asspy; the ownership walks are ``OwnershipWalks``."""

from __future__ import annotations

from datetime import date

from asspy.core import NameSearch
from asspy.placer.filings import FEE_TYPES, conveys, type_ids
from asspy.placer.recorder import (
    PlacerCountyRecorder as _AsspyPlacerRecorder,
    PlacerSession,
    SearchFailed,
    normalize_document_number,
    parse_detail,
    parse_search_results,
)
from jason.community.base import Developer
from jason.community.recorder import (
    OwnershipWalks,
    RecordedIn,
    _follow,
    index_name,
    same_party,
)

__all__ = (
    "Placer",
    "PlacerCountyRecorder",
    "PlacerSession",
    "normalize_document_number",
    "parse_detail",
    "parse_search_results",
)


class PlacerCountyRecorder(OwnershipWalks, _AsspyPlacerRecorder):
    """Placer index plus ownership history and party walks.

    CountyFusion's name search does not filter by filing, so a name search
    keeps only the fee transfers, read by Placer's type names
    (``asspy.placer.filings.conveys``: a deed in lieu conveys, a request for
    notice of a trustee's deed does not). A name too common to read whole is
    narrowed by document type instead (``types=`` on the search), which
    CountyFusion does filter.
    """

    deeds_only = True

    def for_parties(
        self,
        names: tuple[str, ...],
        *,
        after: date | None = None,
        before: date | None = None,
        limit: int = 30,
        developers: tuple[Developer, ...] = (),
        filings: tuple = (),
        session=None,
        fetch=None,
    ) -> tuple[NameSearch, ...]:
        """Search each known person once for fee transfers; a developer name is skipped.

        ``filings`` are Placer type names (``FEE_TYPES`` by default) a wide
        name is searched again under; a name still wide under them is kept
        wide, with no rows.
        """
        session = session or self.open_session(fetch=fetch)
        narrowing = type_ids(tuple(filings) or FEE_TYPES)
        found: list[NameSearch] = []
        seen: set[str] = set()
        for name in names:
            query = index_name(name)
            if not query or query in seen or not _follow(name, developers):
                continue
            seen.add(query)
            result = self.name_search(query, limit=limit, after=after, before=before, session=session, fetch=fetch)
            if result.wide and narrowing:
                try:
                    total, rows = self.search_page(
                        name=query, types=narrowing, rows=limit + 1, after=after, before=before, session=session, fetch=fetch,
                    )
                except SearchFailed:
                    total, rows = result.total, ()
                result = NameSearch(query, total, rows if total <= limit else ())
            if not result.wide:
                deeds = tuple(row for row in result.rows if conveys(row))
                result = NameSearch(query, len(deeds), deeds)
            found.append(result)
        return tuple(found)

    def prior_candidates(
        self,
        grantor: str,
        *,
        before: date,
        limit: int = 30,
        session: PlacerSession | None = None,
        fetch=None,
    ):
        """Fee deeds before ``before`` on which ``grantor`` is the grantee."""
        query = index_name(grantor) or grantor
        rows = self.search(
            name=query,
            before=before,
            rows=max(limit, 1),
            session=session,
            fetch=fetch,
        )
        return tuple(
            row
            for row in rows
            if conveys(row)
            and row.recorded is not None
            and row.recorded < before
            and any(same_party(grantor, name) for name in row.grantees)
        )


class Placer(RecordedIn):
    """Placer County recorded instruments and assessor parcels."""

    county_recorder = PlacerCountyRecorder()

    @staticmethod
    def assessor():
        from jason.community.placer.assessor import PlacerCountyAssessor

        return PlacerCountyAssessor()
