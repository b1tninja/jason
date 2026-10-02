"""Copy secured-roll rows for known parcels into the roll catalog.

The tax-bill catalog is left alone. A later read joins the two on the APN.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jason.community.secured import SecuredRoll
from jason.community.secured_store import SecuredCatalog


@dataclass
class SecuredSyncResult:
    parcels_synced: int = 0
    missed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"parcels={self.parcels_synced}",
            f"missed={len(self.missed)}",
        ]
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return ", ".join(parts)


def sync_secured(
    catalog: SecuredCatalog,
    roll: SecuredRoll,
    parcels: tuple[str, ...] | list[str],
) -> SecuredSyncResult:
    """Upsert each requested parcel that the roll contains.

    A parcel the roll does not list is a miss. The tax-bill catalog is not written.
    """
    result = SecuredSyncResult()
    run_id = catalog.start_run()
    try:
        found = roll.filter(parcels)
    except Exception as exc:
        result.errors.append(str(exc))
        catalog.finish_run(run_id, parcels_synced=0, missed=0, errors=result.errors)
        return result
    seen = {row.apn for row in found}
    for row in found:
        catalog.upsert(row)
        result.parcels_synced += 1
    for apn in parcels:
        digits = "".join(char for char in apn if char.isdigit())
        if digits not in seen:
            result.missed.append(apn)
    catalog.finish_run(
        run_id,
        parcels_synced=result.parcels_synced,
        missed=len(result.missed),
        errors=result.errors,
    )
    return result
