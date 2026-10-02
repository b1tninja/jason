"""Sacramento County assessor parcel viewer.

A parcel's ownership document is ``DocumentBook`` plus ``DocumentPage`` padded
to four digits. That string is the county recorder document number. The
assessor call is public. The recorder call uses a session key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from urllib.request import Request, urlopen

from typing import TYPE_CHECKING

from jason.community.recorder import InstrumentDetail, SacramentoCountyRecorder, _open_session

if TYPE_CHECKING:
    from jason.community.ownership import OwnershipStore

PARCEL_URL = "https://assessorparcelviewer.saccounty.gov/GISWebService/api/gisapps/parcels/public/"
CHARACTERISTICS_URL = "https://assessorparcelviewer.saccounty.gov/GISWebService/api/gisapps/parcels/{apn}/buildingcharacteristics"


@dataclass(frozen=True)
class Parcel:
    """One assessor parcel and the instrument that last transferred it."""

    apn: str
    address: str
    document_type: str
    document_type_description: str
    document_book: str
    document_page: str
    document_date: date | None = None

    @property
    def document_number(self) -> str:
        """Recorder document number: book plus a four-digit page."""
        if not self.document_book or not self.document_page:
            return ""
        return self.document_book + self.document_page.zfill(4)


class SacramentoCountyAssessor:
    """Sacramento County assessor's parcel map. Public parcel endpoint."""

    name = "Sacramento"

    def parcel(self, apn: str, *, fetch=None) -> Parcel | None:
        getter = _parcel_get if fetch is None else fetch
        payload = getter(PARCEL_URL + "".join(ch for ch in str(apn) if ch.isdigit()))
        if not payload or not payload.get("APN"):
            return None
        return Parcel(
            apn=str(payload.get("APN") or ""),
            address=str(payload.get("FullAddress") or ""),
            document_type=str(payload.get("DocumentType") or ""),
            document_type_description=str(payload.get("DocumentTypeDescription") or ""),
            document_book=str(payload.get("DocumentBook") or ""),
            document_page=str(payload.get("DocumentPage") or ""),
            document_date=_parcel_date(str(payload.get("DocumentDate") or "")),
        )

    def characteristics(self, apn: str, *, fetch=None):
        """The residential characteristics the viewer publishes for a parcel. Public call."""
        from jason.community.characteristics import parse_characteristics

        getter = _parcel_get if fetch is None else fetch
        digits = "".join(ch for ch in str(apn) if ch.isdigit())
        payload = getter(CHARACTERISTICS_URL.format(apn=digits))
        return parse_characteristics(payload, digits)

    def ownership(
        self,
        apn: str,
        *,
        recorder: SacramentoCountyRecorder | None = None,
        fetch=None,
        recorder_fetch=None,
        store: OwnershipStore | None = None,
    ) -> InstrumentDetail | None:
        """The current ownership instrument: assessor book/page, then the recorder index.

        When ``store`` already has this document number and date, the recorder
        is not called.
        """
        found = self.parcel(apn, fetch=fetch)
        if found is None or not found.document_number:
            return None
        if store is not None and not store.changed(found):
            return None
        index = recorder or SacramentoCountyRecorder()
        getter = recorder_fetch
        session = None if getter is None else _open_session(getter)
        rows = index.search(number=found.document_number, rows=5, session=session, fetch=getter)
        match = next((row for row in rows if row.number == found.document_number), None)
        if match is None:
            return None
        detail = index.detail(match.internal_id, session=session, fetch=getter)
        if store is not None and detail is not None:
            store.remember(found, grantors=detail.grantors, grantees=detail.grantees)
        return detail


def _parcel_date(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parcel_get(url: str) -> dict | None:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8").strip()
    if not body or body == "null":
        return None
    parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else None
