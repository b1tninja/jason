"""Where Mystique's building permits are: the City of Sacramento's Accela Citizen Access portal.

The board's account keeps the association's records in one collection, "Mystique" (collection 138277, read September 29,
2026): 33 Building records from the 2019 addressing and sales trailer through the 2019 rooftop solar permits, the 2022
monument sign, and the 2026 vehicle damage repair at 3031 Enchanted Walk (COM-2616861). jason reads it with
``SacramentoCitizenAccess`` (``jason.community.accela``), signed in with the Keeper record named ``accela_record_uid``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermitPortal:
    agency: str
    base: str
    collection: str
    record_key: str


ACCELA = PermitPortal(agency="SACRAMENTO", base="https://aca-prod.accela.com", collection="Mystique", record_key="accela")

# A record in one of these states needs nothing more; the rest are read in full on each sync.
CLOSED_STATUSES: tuple[str, ...] = ("Finaled", "Closed", "Expired", "Withdrawn", "Void", "Cancelled", "Complete", "Issued - Finaled")
