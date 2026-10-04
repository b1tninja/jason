"""County assessors — HTTP in asspy; the owner's instrument through the county's recorder here."""

from __future__ import annotations

from typing import TYPE_CHECKING

from asspy.core import Parcel
from asspy.sacramento import SacramentoCountyAssessor as _AsspyAssessor
from jason.community.recorder import InstrumentDetail, SacramentoCountyRecorder

if TYPE_CHECKING:
    from jason.community.ownership import OwnershipStore

__all__ = ("Parcel", "ParcelOwnership", "SacramentoCountyAssessor")


class ParcelOwnership:
    """The instrument that vests a parcel's current owner, read from the county's recorder.

    The assessor names the document; the recorder's detail page names its
    parties. A county mixes this in ahead of its asspy assessor and names its
    recorder in ``recorder``.
    """

    def recorder(self):
        raise NotImplementedError

    def ownership(
        self,
        apn: str,
        *,
        recorder=None,
        fetch=None,
        recorder_fetch=None,
        store: OwnershipStore | None = None,
    ) -> InstrumentDetail | None:
        """Current ownership instrument: the assessor's document number, then the recorder index."""
        found = self.parcel(apn, fetch=fetch)
        if found is None or not found.document_number:
            return None
        if store is not None and not store.changed(found):
            return None
        index = recorder or self.recorder()
        session = None if recorder_fetch is None else index.open_session(fetch=recorder_fetch)
        rows = index.search(number=found.document_number, rows=5, session=session, fetch=recorder_fetch)
        match = next((row for row in rows if _same_number(index, row.number, found.document_number)), None)
        if match is None:
            return None
        detail = index.row_detail(match, session=session, fetch=recorder_fetch)
        if store is not None and detail is not None:
            store.remember(found, grantors=detail.grantors, grantees=detail.grantees)
        return detail


def _same_number(recorder, left: str, right: str) -> bool:
    """Two spellings of one document number, as the county parses them."""
    a, b = recorder.parse(left), recorder.parse(right)
    if a is not None and b is not None:
        return a.number == b.number
    return left == right


class SacramentoCountyAssessor(ParcelOwnership, _AsspyAssessor):
    """Sacramento assessor; the owner's instrument from the Sacramento recorder."""

    def recorder(self):
        return SacramentoCountyRecorder()
