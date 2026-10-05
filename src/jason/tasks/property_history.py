"""Property histories: one Markdown report per parcel, and one spreadsheet.

The stores on disk are the only inputs: the ownership database, the index
cache, the tax database, and the deed scans. Nothing here calls PayHOA or
the recorder. Publishing the spreadsheet needs Google, and only that step
does. The Membership workbook is never written; the spreadsheet is new.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jason.community.base import assign_building
from jason.community.calendar import community_restoration_years
from jason.community.audit import reassessing_steps
from jason.community.index_cache import IndexCache
from jason.community.members import load_units, occupancies
from jason.community.ownership import OwnershipStore
from jason.community.parcel_history import ParcelHistory, build_parcel_history, parcel_notes
from jason.community.association_record import recorded_association
from jason.community.property_report import (
    association_markdown,
    building_markdown,
    dollars,
    home_brief,
    index_markdown,
    parcel_markdown,
    shared_filing_notes,
    solar_markdown,
)
from jason.community.scans import scan_index
from jason.community.tax import parcel_number
from jason.community.tax_store import TaxStore

PROPERTY_TABS = (
    "Parcels",
    "Deed chain",
    "Related documents",
    "Sale prices",
    "Tax calendar",
    "Audit",
    "Open items",
    "Members",
    "Liens and notices",
    "Governing records",
    "Tax standing",
    "Owner events",
    "Solar",
)


@dataclass
class PropertyHistoryReport:
    parcels: int
    open: int
    written: tuple[Path, ...] = ()
    spreadsheet_id: str = ""
    url: str = ""
    counts: tuple[tuple[str, int], ...] = ()

    def summary(self) -> str:
        parts = [f"parcels={self.parcels} open={self.open} files={len(self.written)}"]
        if self.spreadsheet_id:
            parts.append(f"spreadsheet={self.spreadsheet_id}")
            parts.append(" ".join(f"{name}={count}" for name, count in self.counts))
            parts.append(f"url={self.url}")
        return " ".join(parts)


def load_parcel_histories(community: Any, root: Path) -> tuple[ParcelHistory, ...]:
    """Every unit parcel, from the stores under ``root``."""
    developers = community.developers()
    reports = {report.building: report for report in community.public_reports()}
    ranges = community.buildings()
    blocks = community.unit_blocks()
    held = community.held_units()
    scans = scan_index(root, community.streets(), parcel_prefix=community.parcel_prefix())
    units = community.units()
    notes = parcel_notes(root / "parcel-notes.csv")
    periods_by_address: dict[str, list] = {}
    catalog = root / "payhoa.db"
    if catalog.is_file():
        records, people = load_units(str(catalog))
        for period in occupancies(records, people):
            periods_by_address.setdefault(situs(period.address).upper(), []).append(period)
    with OwnershipStore(root / "ownership.db") as store, TaxStore(root / "tax.db") as taxes, IndexCache(
        root / "index-cache.db"
    ) as cache:
        histories = {digits(h.apn): h for h in store.unit_histories(developers=developers)}
        chain_numbers = frozenset(step.conveyance.number for h in histories.values() for step in h.steps)
        currents = {digits(record.apn): record for record in store.records()}
        accounts = {digits(apn): taxes.get(parcel_number(apn)) for apn in units}
        restoration = community_restoration_years(
            tuple(
                (tuple(accounts[key].bills) if accounts.get(key) else (), reassessing_steps(history))
                for key, history in histories.items()
            )
        )
        found: list[ParcelHistory] = []
        for apn in units:
            key = digits(apn)
            account = accounts.get(key)
            address = situs(account.address) if account else ""
            building = assign_building(address, ranges) if address else None
            number = building.number if building is not None else _block_building(key, blocks)
            report = reports.get(number) if number is not None else None
            found.append(
                build_parcel_history(
                    key,
                    history=histories.get(key),
                    developers=developers,
                    address=address,
                    building=int(number) if number is not None else None,
                    report=report,
                    blocks=blocks,
                    held=held,
                    bills=tuple(account.bills) if account else (),
                    scans=scans,
                    load=cache.get,
                    notes=cache.notes,
                    current=currents.get(key),
                    restoration_years=restoration,
                    placed=cache.placed_on,
                    periods=tuple(periods_by_address.get(address.upper(), ())),
                    notes_for_parcel=notes.get(key, ()),
                    load_naming=cache.naming_party,
                    association_name=community.index_association(),
                    solar_program=community.solar_program(),
                    chain_numbers=chain_numbers,
                    roll_rules=community.utility_roll(),
                )
            )
        found.extend(_association_parcels(community, store, taxes, cache, scans, currents, notes, reports, ranges, developers))
    return tuple(found)


def _block_building(apn: str, blocks):
    """The building of a parcel by its plan block, for an address the flood ranges skip."""
    from jason.community.reports import plan_block

    found = plan_block(apn, blocks)
    return found.building if found is not None else None


def _association_parcels(community, store, taxes, cache, scans, currents, notes, reports, ranges, developers) -> list[ParcelHistory]:
    """The common-area parcels: each one's chain is the community deed that carries it, back through the land."""
    from jason.community.history_report import slice_history
    from jason.community.recorder import OwnershipHistory

    pinned = store.pinned_history(developers=developers)
    found: list[ParcelHistory] = []
    for apn in community.common_areas():
        key = digits(apn)
        current = currents.get(key)
        history = None
        if pinned is not None and current is not None and pinned.step(current.document_number) is not None:
            sliced = slice_history(pinned, current.document_number, depth=12)
            history = OwnershipHistory(key, sliced.steps, developers)
        account = taxes.get(parcel_number(apn))
        address = situs(account.address) if account else ""
        building = assign_building(address, ranges) if address else None
        report = reports.get(building.number) if building is not None else None
        found.append(
            build_parcel_history(
                key,
                history=history,
                developers=developers,
                address=address or parcel_number(apn),
                building=int(building.number) if building is not None else None,
                report=report,
                bills=tuple(account.bills) if account else (),
                scans=scans,
                load=cache.get,
                notes=cache.notes,
                current=current,
                notes_for_parcel=notes.get(key, ()),
                association=True,
            )
        )
    return found


def load_association_record(community: Any, root: Path):
    """The association's record from the index cache."""
    with IndexCache(root / "index-cache.db") as cache:
        items = list(cache.naming_word(community.index_project()))
        seen = {item.number for item in items}
        for item in cache.naming_word(community.index_association()):
            if item.number not in seen:
                items.append(item)
                seen.add(item.number)
        for item in cache.by_filing(("162", "324", "220", "225", "320", "301", "240", "435", "433", "285", "460", "307", "478", "499", "604", "188", "446", "494", "476")):
            if item.number not in seen:
                items.append(item)
                seen.add(item.number)
        # Mechanic's liens and what followed them, so the construction period's claims against the developers are read.
        for item in cache.by_filing(("389", "635", "232", "385", "223", "651", "291", "269", "270")):
            if item.number not in seen:
                items.append(item)
                seen.add(item.number)
    plans = tuple(number for pin in community.pins() for number in _numbers(pin.title))
    return recorded_association(
        tuple(items),
        project=community.index_project(),
        association=community.index_association(),
        developers=community.developers(),
        reports=community.public_reports(),
        plan_numbers=plans,
        supersessions=community.supersessions(),
    )


def _numbers(text: str) -> tuple[str, ...]:
    from jason.community.recorder import document_numbers

    return document_numbers(text)


def write_markdown(
    histories: tuple[ParcelHistory, ...],
    out_dir: Path,
    *,
    title: str,
    association=None,
    characteristics=None,
    plans=(),
    charts: bool = True,
    today=None,
    solar_program=None,
    community=None,
) -> tuple[Path, ...]:
    """One file per parcel, a market page, the association's record, and an index.

    Existing files with these names are replaced. ``charts`` draws the SVG
    images under ``charts/`` when matplotlib is installed; without it the
    pages still build, with the Mermaid charts only.
    """
    from jason.tasks.equity_charts import market_index, sales_of, unit_paths, unit_plan, unit_values
    from jason.tasks.market_report import market_markdown, valuations
    from jason.tasks.report_charts import MARKET_CHARTS, render_market_charts, render_unit_chart

    out_dir.mkdir(parents=True, exist_ok=True)
    characteristics = characteristics or {}
    written: list[Path] = []
    links: list[tuple[str, str]] = []
    sales = sales_of(histories, characteristics, plans)
    values = unit_values(histories, today=today, characteristics=characteristics, plans=plans) if sales else []
    worth = valuations(values) if values else {}
    images: dict[str, str] = {}
    unit_images: dict[str, str] = {}
    if charts and sales:
        buildings = tuple(sorted({sale.building for sale in sales}))
        index_rows = market_index(sales, buildings, today=today)
        path_rows = unit_paths(sales, values, today=today)
        for name, path in render_market_charts(sales, out_dir / "charts", today=today).items():
            images[MARKET_CHARTS[name]] = f"charts/{path.name}"
            written.append(path)
        for item in histories:
            if item.association or not item.address:
                continue
            path = render_unit_chart(item.address, item.building, sales, index_rows, path_rows, out_dir / "charts" / f"{item.apn}.svg")
            if path is not None:
                unit_images[item.apn] = f"charts/{path.name}"
                written.append(path)
    if sales:
        path = out_dir / "market.md"
        path.write_text(market_markdown(histories, characteristics, plans, title=f"{title}: the market", today=today, images=images), encoding="utf-8")
        written.append(path)
        links.append(("The market: prices by year, per square foot, and where each unit stands", "market.md"))
    if association is not None:
        path = out_dir / "association.md"
        path.write_text(association_markdown(association, title=f"{title}: the association's record"), encoding="utf-8")
        written.append(path)
        links.append(("The association's record: governing instruments, liens, and notices", "association.md"))
    if solar_program is not None and any(item.solar is not None for item in histories):
        path = out_dir / "solar.md"
        path.write_text(solar_markdown(histories, solar_program, title=f"{title}: solar leases by unit"), encoding="utf-8")
        written.append(path)
        links.append(("Solar leases by unit: who leases the shared panels, for escrow", "solar.md"))
    if any(item.liens for item in histories):
        from jason.community.title import title_markdown, title_watch

        path = out_dir / "liens.md"
        path.write_text(title_markdown(title_watch(histories), title=f"{title}: liens against the units", today=today), encoding="utf-8")
        written.append(path)
        links.append(("Liens against the units: what stands, what a person should check, what is only of record", "liens.md"))
    homes: dict[str, str] = {}
    shared = shared_filing_notes(histories)
    for item in histories:
        unit = characteristics.get(digits(item.apn))
        if unit is not None:
            homes[item.apn] = home_brief(unit, unit_plan(item, unit, plans))
        path = out_dir / f"{item.apn}.md"
        path.write_text(
            parcel_markdown(
                item, unit=unit, plan=unit_plan(item, unit, plans), value=worth.get(item.address),
                chart=unit_images.get(item.apn, ""), today=today, shared_filing=shared.get(item.apn, ""),
            ),
            encoding="utf-8",
        )
        written.append(path)
    reports_by_building = {int(report.building): report for report in community.public_reports()} if community is not None else {}
    annexations = {}
    if association is not None:
        for g in association.governing:
            if g.role == "annexation" and g.phase is not None and not g.superseded_by:
                annexations[g.phase] = g
    buildings = sorted({item.building for item in histories if item.building and not item.association})
    for building in buildings:
        report = reports_by_building.get(building)
        page = out_dir / f"building-{building}.md"
        page.write_text(
            building_markdown(
                building, histories, title=f"{title}: building {building}", report=report,
                annexation=annexations.get(report.phase) if report is not None else None, homes=homes, today=today,
            ),
            encoding="utf-8",
        )
        written.append(page)
    if buildings:
        links.append(("Buildings: " + ", ".join(f"[{b}](building-{b}.md)" for b in buildings), ""))
    index = out_dir / "README.md"
    index.write_text(index_markdown(histories, title=title, links=tuple(links), homes=homes), encoding="utf-8")
    written.append(index)
    return tuple(written)


def property_tabs(histories: tuple[ParcelHistory, ...]) -> dict[str, list[list[Any]]]:
    """The spreadsheet tabs, header row first."""
    return {
        "Parcels": parcel_values(histories),
        "Deed chain": chain_values(histories),
        "Related documents": related_values(histories),
        "Sale prices": price_values(histories),
        "Tax calendar": calendar_values(histories),
        "Audit": audit_values(histories),
        "Open items": open_values(histories),
        "Members": member_values(histories),
        "Liens and notices": lien_values(histories),
        "Tax standing": tax_values(histories),
        "Owner events": event_values(histories),
        "Solar": solar_values(histories),
    }


def parcel_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "APN", "Address", "Unit", "Building", "Phase", "Public report", "Developer",
        "First conveyance", "First buyer", "Deeds", "Sales", "Verified by scan",
        "Last sale", "Last price", "Price source", "Last enrolled base", "Current owner", "Current instrument",
        "Current recorded", "Current type", "Bills from", "Bills to", "Status", "Findings", "Members", "Notes",
    ]]
    for item in histories:
        first = item.steps[0] if item.steps else None
        last = item.last_sale
        rows.append([
            parcel_number(item.apn), item.address, item.unit or "", item.building or "", item.phase or "",
            item.report, item.developer,
            first.recorded.isoformat() if first and first.recorded else "",
            "\n".join(first.grantees) if first else "",
            len(item.steps), len(item.sales), item.verified,
            last.recorded.isoformat() if last and last.recorded else "",
            _money(last.price_or_base[0]) if last else "",
            last.price_or_base[1] if last else "",
            _money(last.enrolled_cents) if last else "",
            "\n".join(item.owners),
            item.current_number,
            item.current_date.isoformat() if item.current_date else "",
            item.current_type,
            item.first_year or "", item.last_year or "",
            ("common area, " if item.association else "") + ("open" if item.open else ("findings" if item.findings else "clean")),
            len(item.findings),
            item.membership.verdict if item.membership else ("common area" if item.association else ""),
            "\n".join(f"{note.note} ({note.source}{', ' + note.noted.isoformat() if note.noted else ''})" for note in item.notes),
        ])
    return rows


def chain_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "APN", "Address", "Step", "Recorded", "Document No", "Process", "Complete", "Reassesses",
        "Developer", "Grantors", "Grantees", "Prior", "Price", "Why unpriced", "County tax", "City tax", "Exempt",
        "Bill year", "Enrolled base", "Prior enrolled", "Placed by", "Scan", "Source", "Notes",
    ]]
    for item in histories:
        for step in item.steps:
            rows.append([
                parcel_number(item.apn), item.address, step.order,
                step.recorded.isoformat() if step.recorded else "", step.number, step.process,
                "yes" if step.complete else "", "yes" if step.reassesses else "", step.developer,
                "\n".join(step.grantors), "\n".join(step.grantees), "\n".join(step.priors),
                _money(step.price_cents), step.unpriced, _money(step.county_tax_cents), _money(step.city_tax_cents),
                "yes" if step.exempt else "",
                step.bill_year or "", _money(step.enrolled_cents), _money(step.prior_enrolled_cents),
                step.placement, step.scan, step.scan_source, "\n".join(step.notes),
            ])
    return rows


def related_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "APN", "Address", "Beside", "Role", "Document No", "Recorded", "Kind", "Filing",
        "Grantors", "Grantees", "Found", "Scan",
    ]]
    for item in histories:
        for step in item.steps:
            for related in step.related:
                rows.append([
                    parcel_number(item.apn), item.address, step.number, related.role, related.number,
                    related.recorded.isoformat() if related.recorded else "", related.kind, related.filing,
                    "\n".join(related.grantors), "\n".join(related.grantees), related.reason, related.scan,
                ])
    return rows


def price_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "APN", "Address", "Recorded", "Document No", "Process", "Seller", "Buyer",
        "Price", "Price source", "Why unpriced", "County tax", "City tax", "Bill year", "Enrolled base", "Prior enrolled", "Base vs price",
    ]]
    for item in histories:
        for step in item.sales:
            gap = ""
            if step.price_cents and step.enrolled_cents:
                gap = f"{(step.enrolled_cents - step.price_cents) * 100 / step.price_cents:+.1f}%"
            rows.append([
                parcel_number(item.apn), item.address,
                step.recorded.isoformat() if step.recorded else "", step.number, step.process,
                "\n".join(step.grantors), "\n".join(step.grantees),
                "exempt" if step.exempt else _money(step.price_or_base[0]),
                step.price_or_base[1], step.unpriced,
                _money(step.county_tax_cents), _money(step.city_tax_cents),
                step.bill_year or "", _money(step.enrolled_cents), _money(step.prior_enrolled_cents), gap,
            ])
    return rows


def calendar_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "APN", "Address", "Bill year", "Sale year", "Enrolled", "Prior year", "Prior enrolled", "Change", "Reading", "Document No",
    ]]
    for item in histories:
        for event in item.events:
            change = ""
            if event.prior_enrolled_cents:
                change = f"{(event.enrolled_cents - event.prior_enrolled_cents) * 100 / event.prior_enrolled_cents:+.1f}%"
            rows.append([
                parcel_number(item.apn), item.address, event.year, event.sale_year,
                _money(event.enrolled_cents), event.prior_year, _money(event.prior_enrolled_cents),
                change, event.kind, event.number,
            ])
    return rows


def audit_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [["APN", "Address", "Check", "Document No", "Year", "Detail"]]
    for item in histories:
        for finding in item.findings:
            rows.append([parcel_number(item.apn), item.address, finding.check, finding.number, finding.year or "", finding.detail])
    return rows


def tax_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [["APN", "Address", "Status", "Bills from", "Bills to", "Due", "Delinquent", "Oldest delinquent year", "Power to sell from", "Years with no bill"]]
    for item in histories:
        standing = item.taxes
        if standing is None:
            continue
        rows.append([
            parcel_number(item.apn), item.address, standing.status, standing.first_year or "", standing.last_year or "",
            _money(sum(cents for _, cents in standing.unpaid)) if standing.unpaid else "",
            _money(sum(cents for _, cents in standing.delinquent)) if standing.delinquent else "",
            standing.oldest_delinquent or "", standing.power_to_sell.isoformat() if standing.power_to_sell else "",
            ", ".join(str(year) for year in standing.missing_years),
        ])
    return rows


def event_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [["APN", "Address", "Recorded", "Document No", "Filing", "Event", "Owner", "Parties", "During tenure", "Decedent still on title"]]
    for item in histories:
        for event in item.owner_events:
            rows.append([
                parcel_number(item.apn), item.address, event.recorded.isoformat() if event.recorded else "", event.number, event.filing,
                event.kind, event.owner, "\n".join(event.parties), "yes" if event.during_tenure else "", "yes" if event.still_on_title else "",
            ])
    return rows


def lien_values(histories: tuple[ParcelHistory, ...], association=None) -> list[list[Any]]:
    """Every lifecycle naming an owner, then the association's own."""
    rows: list[list[Any]] = [[
        "APN", "Address", "Owner", "Process", "Opened", "Closed", "Status", "Debtor", "Claimant", "Steps", "Where",
    ]]
    for item in histories:
        for lien in item.liens:
            e = lien.encumbrance
            rows.append([
                parcel_number(item.apn), item.address, lien.owner, e.process.value,
                e.opened.recorded.isoformat() if e.opened.recorded else "", e.closed.isoformat() if e.closed else "",
                e.status, "\n".join(e.debtor), "\n".join(e.claimant),
                "\n".join(f"{s.filing} {s.number}" for s in e.steps), lien.where,
            ])
    if association is not None:
        for label, items in (("placed by the association", association.placed), ("against the association", association.against)):
            for e in items:
                rows.append([
                    "", "association", "", e.process.value,
                    e.opened.recorded.isoformat() if e.opened.recorded else "", e.closed.isoformat() if e.closed else "",
                    e.status, "\n".join(e.debtor), "\n".join(e.claimant),
                    "\n".join(f"{s.filing} {s.number}" for s in e.steps), label,
                ])
    return rows


def solar_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    """Each unit's solar standing, for escrow: who leases, from whom, under which filing."""
    rows: list[list[Any]] = [[
        "APN", "Address", "Building", "Current owner", "Standing", "Lessor", "Filing", "Recorded", "Terminated", "Filings on record", "Note",
    ]]
    shared = shared_filing_notes(histories)
    for item in histories:
        if item.association or item.solar is None:
            continue
        record = item.solar
        current = record.current_filing
        rows.append([
            parcel_number(item.apn), item.address, item.building or "", ", ".join(item.owners), record.standing.name.lower().replace("_", " "),
            record.lessor, current.number if current else "", current.recorded.isoformat() if current and current.recorded else "",
            "\n".join(f.closed.isoformat() for f in record.filings if f.closed),
            "\n".join(f"{f.number} {f.owner} ({f.status})" for f in record.filings),
            (record.note + " " + shared.get(item.apn, "")).strip(),
        ])
    return rows


def governing_values(association) -> list[list[Any]]:
    rows: list[list[Any]] = [["Recorded", "Document No", "Filing", "What it is", "Phase", "Delivery", "Recorded by", "Parties", "Cites"]]
    for r in association.governing:
        rows.append([
            r.recorded.isoformat() if r.recorded else "", r.number, r.filing, r.role, r.phase or "",
            r.delivery.value.replace("_", " "), r.developer, "\n".join(r.parties), "\n".join(r.cites),
        ])
    return rows


def member_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    """The current PayHOA members of each unit beside the grantees on its newest deed."""
    rows: list[list[Any]] = [[
        "APN", "Address", "Verdict", "Members", "On title", "On title, not a member", "Member, not on title",
        "Member since", "Occupancy periods",
    ]]
    for item in histories:
        check = item.membership
        if check is None:
            continue
        periods = "\n".join(
            f"{p.from_date.isoformat() if p.from_date else '?'} to {p.to_date.isoformat() if p.to_date else 'now'}: {', '.join(p.members)}"
            for p in item.occupancies
        )
        rows.append([
            parcel_number(item.apn), item.address, check.verdict,
            "\n".join(check.members), "\n".join(check.owners),
            "\n".join(check.unmatched_owners), "\n".join(check.unmatched_members),
            check.since.isoformat() if check.since else "",
            periods,
        ])
    return rows


def open_values(histories: tuple[ParcelHistory, ...]) -> list[list[Any]]:
    rows: list[list[Any]] = [["APN", "Address", "Oldest deed", "Oldest grantor", "What is missing"]]
    for item in histories:
        if not item.open:
            continue
        oldest = item.steps[0] if item.steps else None
        rows.append([
            parcel_number(item.apn), item.address,
            oldest.number if oldest else "", "\n".join(oldest.grantors) if oldest else "",
            "the developer's grant and every deed between it and the oldest deed stored" if oldest else "the assessor's current instrument and the chain behind it",
        ])
    return rows


COUNTY_TAB_NAMES = {
    "Ownership": "Assessor current",
    "Deed history": "Community deeds",
    "Association taxes": "Association taxes",
    "Taxes due": "Taxes due",
}


def merge_county_tabs(tabs: dict[str, list[list[Any]]], county: dict[str, list[list[Any]]]) -> dict[str, list[list[Any]]]:
    """Add the county tabs under names that do not collide with the property tabs.

    The county "Sale prices" tab is left out; the property tab of that name
    carries the deed price beside the enrolled base.
    """
    merged = dict(tabs)
    for name, values in county.items():
        target = COUNTY_TAB_NAMES.get(name)
        if target and target not in merged:
            merged[target] = values
    return merged


def refresh_property_sheet(sheets: Any, spreadsheet_id: str, tabs: dict[str, list[list[Any]]]) -> tuple[str, str, tuple[tuple[str, int], ...]]:
    """Overwrite each tab of an existing spreadsheet in place; add tabs it lacks.

    A tab that had more rows than the new values is padded with blank rows so
    nothing stale survives below the new table.
    """
    existing = sheets.get(spreadsheet_id, fields="sheets.properties")
    ids = {
        str(sheet.get("properties", {}).get("title")): int(sheet.get("properties", {}).get("sheetId", 0))
        for sheet in (existing.get("sheets") or [])
    }
    missing = [name for name in tabs if name not in ids and tabs[name]]
    if missing:
        added = sheets.batch_update(spreadsheet_id, [{"addSheet": {"properties": {"title": name}}} for name in missing])
        for reply in added.get("replies") or []:
            properties = reply.get("addSheet", {}).get("properties", {})
            if properties.get("title"):
                ids[str(properties["title"])] = int(properties.get("sheetId", 0))
    counts: list[tuple[str, int]] = []
    widths: dict[str, int] = {}
    for name, values in tabs.items():
        if not values:
            continue
        current = sheets.values_get(spreadsheet_id, f"'{name}'!A1:ZZ").get("values") or []
        width = max(len(values[0]), max((len(row) for row in current), default=0))
        padded = [list(row) + [""] * (width - len(row)) for row in values]
        for _ in range(len(current) - len(values)):
            padded.append([""] * width)
        sheets.values_update(spreadsheet_id, f"'{name}'!A1", padded)
        counts.append((name, max(0, len(values) - 1)))
        widths[name] = len(values[0])
    requests = format_requests({name: ids[name] for name in widths if name in ids}, widths)
    if requests:
        sheets.batch_update(spreadsheet_id, requests)
    return spreadsheet_id, f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}", tuple(counts)


def create_property_sheet(sheets: Any, title: str, tabs: dict[str, list[list[Any]]]) -> tuple[str, str, tuple[tuple[str, int], ...]]:
    """Create the spreadsheet, fill each tab, freeze and bold the headers, size the columns."""
    names = tuple(name for name in tabs if tabs[name])
    created = sheets.create(title, sheet_titles=names)
    spreadsheet_id = str(created.get("spreadsheetId") or "")
    if not spreadsheet_id:
        raise ValueError("spreadsheet was not created")
    counts: list[tuple[str, int]] = []
    for name in names:
        values = tabs[name]
        sheets.values_update(spreadsheet_id, f"'{name}'!A1", values)
        counts.append((name, max(0, len(values) - 1)))
    ids = {
        str(sheet.get("properties", {}).get("title")): int(sheet.get("properties", {}).get("sheetId", 0))
        for sheet in (created.get("sheets") or [])
    }
    requests = format_requests(ids, {name: len(tabs[name][0]) for name in names})
    if requests:
        sheets.batch_update(spreadsheet_id, requests)
    return spreadsheet_id, f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}", tuple(counts)


def format_requests(ids: dict[str, int], widths: dict[str, int]) -> list[dict[str, Any]]:
    """Freeze the header row, bold it, wrap cells, and auto-size the columns."""
    requests: list[dict[str, Any]] = []
    for name, sheet_id in ids.items():
        columns = widths.get(name, 0)
        if not columns:
            continue
        requests.append({
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        })
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93}}},
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        })
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
            }
        })
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": columns}
            }
        })
    return requests


def situs(address: str) -> str:
    """The street part of a tax-bill address: before the comma or the city."""
    text = address.split(",")[0]
    upper = text.upper()
    for city in (" SACRAMENTO", " SACTO"):
        if city in upper:
            text = text[: upper.index(city)]
            break
    return text.strip()


def digits(apn: str) -> str:
    return "".join(ch for ch in apn if ch.isdigit())


def _money(cents: int | None) -> Any:
    if cents is None:
        return ""
    return round(cents / 100, 2)


__all__ = [
    "PROPERTY_TABS",
    "PropertyHistoryReport",
    "create_property_sheet",
    "dollars",
    "format_requests",
    "load_parcel_histories",
    "merge_county_tabs",
    "refresh_property_sheet",
    "property_tabs",
    "write_markdown",
]
