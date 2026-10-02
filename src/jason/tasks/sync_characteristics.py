"""Copy the assessor's residential characteristics for each unit into the local store.

The viewer's call is public and needs no sign-in. A parcel the viewer does
not know, or one with no residential record, is a miss. One parcel's error
does not stop the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jason.community.assessor import SacramentoCountyAssessor
from jason.community.characteristics import CharacteristicsStore


@dataclass
class CharacteristicsSyncResult:
    synced: int = 0
    missed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"characteristics synced={self.synced} missed={len(self.missed)} errors={len(self.errors)}"


def sync_characteristics(
    store: CharacteristicsStore,
    assessor: SacramentoCountyAssessor,
    parcels: tuple[str, ...] | list[str],
    *,
    fetch=None,
) -> CharacteristicsSyncResult:
    """Fetch each parcel's characteristics and store the ones the viewer returns."""
    result = CharacteristicsSyncResult()
    for apn in parcels:
        try:
            found = assessor.characteristics(apn, fetch=fetch)
        except Exception as exc:
            result.errors.append(f"{apn}: {exc}")
            continue
        if found is None:
            result.missed.append(apn)
            continue
        store.remember(found)
        result.synced += 1
    return result
