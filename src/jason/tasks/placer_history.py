"""Placer parcel and subdivision reports from the cached index: Markdown, the shared sheet tabs, and the bundle JSON.

The Placer counterpart of ``property_history`` and ``county_report`` for a
parcel or a builder's subdivision outside Sacramento. It reads the public
index through one ``PlacerIndex`` (read-only, one session, renewed on a
failed search, ``pause`` seconds between searches) and writes only under
``out_dir``. The rows name owners, so ``out_dir`` belongs under ``data/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jason.community.base import Developer
from jason.community.parcel_history import ParcelHistory
from jason.community.placer.assessor import PlacerParcel
from jason.community.placer.bundle import InstrumentBundle, parcel_bundle, subdivision_bundle
from jason.community.placer.descent import PlacerDescent, descend
from jason.community.placer.index import PlacerIndex, placer_index
from jason.community.placer.parcel import (
    PlacerParcelRecord,
    cache_owner_filings,
    parcel_record,
    placer_parcel_history,
)
from jason.community.title import title_watch

__all__ = ("PlacerReport", "lot_histories", "placer_parcel_report", "placer_subdivision_report")


@dataclass(frozen=True)
class PlacerReport:
    """What one run wrote, and the bundle it built."""

    paths: tuple[Path, ...]
    bundle: InstrumentBundle
    histories: tuple[ParcelHistory, ...]


def lot_histories(
    descent: PlacerDescent,
    index: PlacerIndex,
    *,
    association: str = "",
    owner_filings: bool = False,
) -> tuple[ParcelHistory, ...]:
    """Each lot as the shared ``ParcelHistory``, so ``property_tabs`` and ``title_watch`` read a whole subdivision.

    ``owner_filings`` searches every owner's other filings first (one name
    search each), which the liens need; without it the liens are what the
    cache already holds.
    """
    found: list[ParcelHistory] = []
    for lot in descent.lots:
        if owner_filings:
            cache_owner_filings(index, lot.history, developers=descent.developers, association=association)
        newest = index.cache.get(lot.newest)
        parcel = PlacerParcel(
            apn=lot.apn,
            address="",
            document_number=lot.newest if lot.apn else "",
            document_date=newest.recorded if newest is not None else None,
        )
        found.append(placer_parcel_history(parcel, lot.history, index, developers=descent.developers, association=association))
    return tuple(found)


def placer_parcel_report(
    query: str,
    out_dir: Path,
    *,
    kind: str = "idaddress",
    developers: tuple[Developer, ...] = (),
    association: str = "",
    index: PlacerIndex | None = None,
    assessor=None,
    pause: float = 1.0,
) -> PlacerReport | None:
    """One parcel's page (``<apn>.md``) and bundle (``<apn>.json``) under ``out_dir``."""
    active = index or placer_index(pause=pause)
    record: PlacerParcelRecord | None = parcel_record(
        query, kind=kind, index=active, assessor=assessor, developers=developers, association=association,
    )
    if record is None:
        return None
    bundle = parcel_bundle(record, active, developers=developers)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = record.parcel.apn or record.parcel.document_number
    page = out_dir / f"{stem}.md"
    page.write_text(record.markdown, encoding="utf-8")
    data = out_dir / f"{stem}.json"
    data.write_text(json.dumps(bundle.as_dict(), indent=1), encoding="utf-8")
    return PlacerReport((page, data), bundle, (record.parcel_history,))


def placer_subdivision_report(
    developers: tuple[Developer, ...],
    out_dir: Path,
    *,
    after: date,
    before: date | None = None,
    depth: int = 2,
    currents: dict[str, str] | None = None,
    association: str = "",
    owner_filings: bool = False,
    index: PlacerIndex | None = None,
    pause: float = 1.0,
) -> PlacerReport:
    """A builder's subdivision: ``subdivision.md`` (lots and formations), ``subdivision.json`` (the bundle), ``liens.md``."""
    active = index or placer_index(pause=pause)
    found = descend(active, developers=developers, after=after, before=before, depth=depth, currents=currents)
    bundle = subdivision_bundle(found, active)
    histories = lot_histories(found, active, association=association, owner_filings=owner_filings)
    out_dir.mkdir(parents=True, exist_ok=True)
    page = out_dir / "subdivision.md"
    page.write_text(_subdivision_markdown(found, bundle), encoding="utf-8")
    data = out_dir / "subdivision.json"
    data.write_text(json.dumps(bundle.as_dict(), indent=1), encoding="utf-8")
    liens = out_dir / "liens.md"
    liens.write_text(_liens_markdown(histories), encoding="utf-8")
    return PlacerReport((page, data, liens), bundle, histories)


def _subdivision_markdown(found: PlacerDescent, bundle: InstrumentBundle) -> str:
    names = ", ".join(developer.name for developer in found.developers)
    lines = [
        f"# {bundle.label or names}",
        "",
        f"Placer County. The builder's grants and notices of completion from {found.after.isoformat()} to "
        f"{found.before.isoformat()}, walked {found.depth} leaves out by name. Placer's index cites no prior deed "
        "and its detail page names no parcel, so each later deed joins a lot by its grantor's name, and a lot "
        "meets a parcel only through the assessor's current instrument. A step is a lead for a person to confirm.",
        "",
        f"{len(found.grants)} grants, {len(found.notices)} notices of completion, {len(found.lots)} lots, "
        f"{sum(1 for lot in found.lots if lot.apn)} placed on a parcel.",
        "",
    ]
    lines.extend(f"- {note}" for note in bundle.notes)
    if bundle.notes:
        lines.append("")
    readings = {step.number: step for step in bundle.readings}
    lines.extend(["## Lots", "", "| Builder grant | Recorded | Deeds | Newest | Parcel | Closing |", "| --- | --- | ---: | --- | --- | --- |"])
    for lot in found.lots:
        step = readings.get(lot.grant.number)
        closing = f"{step.process}{' (complete)' if step.complete else ''}" if step is not None else ""
        lines.append(
            f"| {lot.grant.number} | {lot.grant.recorded or ''} | {len(lot.numbers)} | {lot.newest} | {lot.apn} | {closing} |"
        )
    community = [item for item in bundle.formations if item.kind == "community"]
    lines.extend(["", "## Community formation", ""])
    if not community:
        lines.append("No governing instrument in the window names the builder.")
    for formation in community:
        anchor = formation.anchor
        lines.append(f"- {anchor.number} {anchor.filing_name} ({anchor.recorded or ''})")
        for member in formation.members:
            lines.append(f"  - {member.role}: {member.instrument.number} {member.instrument.filing_name} ({member.why})")
    lines.append("")
    return "\n".join(lines)


def _liens_markdown(histories: tuple[ParcelHistory, ...]) -> str:
    rows = title_watch(histories)
    lines = [
        "# Liens on the lots' owners",
        "",
        "Each lien joins a lot through its owner's name. The standing is what the index shows, not a title report.",
        "",
        "| Lot newest deed | Owner | Process | Opened | Recorded | Status | Standing |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    by_apn = {item.apn: item for item in histories}
    for row in rows:
        lot = by_apn.get(row.apn)
        newest = lot.steps[-1].number if lot is not None and lot.steps else ""
        lines.append(
            f"| {newest} | {' '.join(row.owner.split())} | {row.process} | {row.number} | "
            f"{row.recorded.isoformat() if row.recorded else ''} | {row.status} | {row.standing.name.lower().replace('_', ' ')} |"
        )
    lines.append("")
    return "\n".join(lines)
