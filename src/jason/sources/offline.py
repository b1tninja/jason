"""A bill-source registry that only routes: no store, no portal client, no network.

``BillSource.matches_transaction`` reads a transaction and the profile's rules and nothing else, so the registry the
attach engine routes with can be built without opening a bill database or signing in anywhere. The console's bill queue
routes the stored PayHOA snapshot with this registry (docs/console/handoff-mail-and-payment-attachments.md). Its order is
the engine's: the electric utility, the City's portal, each field-portal vendor the profile declares, then the county tax collector (receipts and bills a person imported). Unlike the live
registry it includes a declared vendor portal whether or not a credential is set, since routing does not need one.

A source built here cannot find, resolve, or fetch a bill; calling those raises.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.sources.county_tax import CountyTaxBillSource
from jason.sources.idoxs import IdoxsBillSource
from jason.sources.registry import BillSourceRegistry
from jason.sources.smud import SmudBillSource


def routing_registry(community: Any, settings: Any, data_dir: Path | str) -> BillSourceRegistry:
    from jason.sources.fieldportals import VendorPortalBillSource

    sources: list[Any] = [
        SmudBillSource(None, None, category_id=getattr(settings, "smud_category_id", None)),   # type: ignore[arg-type]
        IdoxsBillSource(None, None, category_id=getattr(settings, "idoxs_category_id", None)),  # type: ignore[arg-type]
    ]
    for portal in community.vendor_portals():
        if portal.platform.name == "FIELDPORTALS":
            sources.append(VendorPortalBillSource(portal, Path(data_dir)))
    sources.append(CountyTaxBillSource(data_dir, community))
    return BillSourceRegistry(sources)


__all__ = ["routing_registry"]
