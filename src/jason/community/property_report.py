"""Markdown and Mermaid for one parcel's history, and an index over all of them.

The diagram reads from the developer's grant at the top to the current
instrument at the bottom. A node is a deed on the chain, colored by the
process it completed. A solid arrow is the handoff, labeled by what placed
it: the parcel number on the scan, a citation, or a name. A dotted node is
an instrument that belongs beside a deed and does not move the fee: the
notice of completion, the buyer's lien, the partial reconveyance, the
trustee's deed a resale cites. An open chain draws an unknown node above
its oldest deed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from jason.community.calendar import CONSTRUCTION, DECLINE, IMPROVEMENT, RESTORATION, SALE
from jason.community.characteristics import FloorPlan, UnitCharacteristics
from jason.community.parcel_history import HistoryStep, ParcelHistory, RelatedInstrument
from jason.community.tax import parcel_number
from jason.community.title import ATTENTION, lien_standing


@dataclass(frozen=True)
class Valuation:
    """What the values spreadsheet says about one unit, restated on its page. Cents."""

    last_price: int | None = None
    source: str = ""
    comps: int | None = None
    comps_basis: str = ""
    indexed: int | None = None
    size_estimate: int | None = None
    size_basis: str = ""
    per_sqft: int | None = None
    community_per_sqft: int | None = None
    appreciation_pct: float | None = None
    annual_pct: float | None = None
    rank: int | None = None
    building_units: int | None = None
    percentile: int | None = None
    assessed: int | None = None

_CLASS = {
    "developer closing": "developer",
    "blanket release": "developer",
    "developer grant": "developer",
    "resale": "sale",
    "foreclosure": "foreclosure",
    "reo resale": "reo",
    "excluded transfer": "excluded",
    "restatement": "restatement",
    "re-recording": "rerecording",
}

_STYLES = (
    "classDef developer fill:#dcfce7,stroke:#15803d,color:#14532d;",
    "classDef sale fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a;",
    "classDef foreclosure fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d;",
    "classDef reo fill:#ffedd5,stroke:#c2410c,color:#7c2d12;",
    "classDef excluded fill:#ede9fe,stroke:#6d28d9,color:#4c1d95;",
    "classDef restatement fill:#f3f4f6,stroke:#6b7280,color:#374151;",
    "classDef rerecording fill:#f3f4f6,stroke:#9ca3af,color:#4b5563,stroke-dasharray:4 2;",
    "classDef related fill:#fffbeb,stroke:#b45309,color:#78350f,stroke-dasharray:3 3;",
    "classDef unknown fill:#ffffff,stroke:#dc2626,color:#991b1b,stroke-dasharray:6 3;",
)


def dollars(cents: int | None) -> str:
    if cents is None:
        return ""
    return f"${cents // 100:,}"


def parcel_markdown(
    item: ParcelHistory,
    *,
    unit: UnitCharacteristics | None = None,
    plan: FloorPlan | None = None,
    value: Valuation | None = None,
    chart: str = "",
    today: date | None = None,
    shared_filing: str = "",
) -> str:
    """The full report for one parcel.

    ``unit`` is the assessor's record of the home, ``plan`` the developer's
    plan it matches, ``value`` the spreadsheet's valuation, ``chart`` the
    relative path of the unit's rendered value chart when one was drawn, and
    ``shared_filing`` the note when its solar filing also stands for another unit.
    """
    title = f"{item.address or parcel_number(item.apn)}"
    lines = [f"# {title}", "", *_facts(item, unit=unit, plan=plan), ""]
    if item.notes:
        lines.append("## Notes")
        lines.append("")
        for note in item.notes:
            when = f" ({note.noted.isoformat()})" if note.noted else ""
            source = f" — {note.source}" if note.source else ""
            lines.append(f"- {note.note}{source}{when}")
        lines.append("")
    lines.append("## Chain of title")
    lines.append("")
    lines.extend(_chain_table(item))
    lines.append("")
    lines.append("```mermaid")
    lines.append(mermaid_conveyances(item))
    lines.append("```")
    lines.append("")
    if item.sales:
        lines.append("## Who held it")
        lines.append("")
        lines.append("Each bar is one owner's tenure, from the deed that gave it to the deed that took it. A red bar ended in a foreclosure. A diamond is an instrument that moved no title.")
        lines.append("")
        lines.append("```mermaid")
        lines.append(mermaid_tenure(item, today=today))
        lines.append("```")
        lines.append("")
    if value is not None and not item.association:
        lines.append("## Value")
        lines.append("")
        lines.extend(_value(item, value, chart))
        lines.append("")
    if item.candidates:
        lines.append("## Placed on this parcel, not yet on the chain")
        lines.append("")
        lines.append("A pass read the parcel number or the address on these instruments. They are not stored until the chain from them reaches the developer with no gap.")
        lines.append("")
        lines.append("| Document | Recorded | Filing | From | To | Cites |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for found in item.candidates:
            filing = f"{found.filing_code} {found.filing_name}".strip() or found.kind
            lines.append(
                f"| {found.number} | {found.recorded.isoformat() if found.recorded else ''} | {_cell(filing)} "
                f"| {_cell(', '.join(found.grantors))} | {_cell(', '.join(found.grantees))} | {', '.join(found.cross_references)} |"
            )
        lines.append("")
    lines.append("## Related instruments")
    lines.append("")
    lines.extend(_related_table(item))
    lines.append("")
    lines.append("## Taxes")
    lines.append("")
    lines.extend(_taxes(item))
    lines.append("")
    if not item.association:
        lines.append("## Owner events")
        lines.append("")
        lines.extend(_events(item))
        lines.append("")
    lines.append("## Liens and notices")
    lines.append("")
    lines.extend(_liens(item))
    lines.append("")
    if item.solar is not None:
        lines.append("## Solar")
        lines.append("")
        lines.extend(_solar(item, shared_filing))
        lines.append("")
    lines.append("## PayHOA members")
    lines.append("")
    lines.extend(_members(item))
    lines.append("")
    lines.append("## Tax calendar")
    lines.append("")
    lines.extend(_calendar_table(item))
    lines.append("")
    lines.append("## Audit")
    lines.append("")
    if item.findings:
        for finding in item.findings:
            where = f" ({finding.number})" if finding.number else ""
            lines.append(f"- **{finding.check}**{where}: {finding.detail}")
    else:
        lines.append("Clean. The chain is in recording order, starts at the phase's developer inside its window, and agrees with the bills.")
    lines.append("")
    return "\n".join(lines)


def index_markdown(
    items: tuple[ParcelHistory, ...],
    *,
    title: str = "Property histories",
    links: tuple[tuple[str, str], ...] = (),
    homes: dict[str, str] | None = None,
) -> str:
    """One table over every parcel, then the open ones.

    ``links`` are (label, file) pairs to the other pages. ``homes`` is each
    parcel's home in a few words, by parcel digits, for the Home column.
    """
    homes = homes or {}
    lines = [f"# {title}", ""]
    total = len(items)
    proven = sum(1 for item in items if not item.open)
    verified = sum(item.verified for item in items)
    steps = sum(len(item.steps) for item in items)
    lines.append(
        f"{total} parcels. {proven} chains reach the developer with no gap. "
        f"{steps} deeds on those chains, {verified} of them placed by a scan. "
        f"{sum(1 for item in items if item.findings)} parcels carry an audit finding."
    )
    lines.append("")
    if links:
        for label, file in links:
            lines.append(f"- [{label}]({file})" if file else f"- {label}")
        lines.append("")
    lines.append("| Parcel | Address | Unit | Phase | Developer | Home | First conveyance | Sales | Last sale | Price | Base | Current owner | Status |")
    lines.append("| --- | --- | --- | ---: | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- |")
    for item in items:
        first = item.steps[0] if item.steps else None
        last = item.last_sale
        owner = ", ".join(item.owners)
        status = "open" if item.open else ("findings" if item.findings else "clean")
        if item.association:
            status = f"common area, {status}"
        lines.append(
            "| "
            + " | ".join(
                (
                    f"[{parcel_number(item.apn)}]({item.apn}.md)",
                    _cell(item.address),
                    str(item.unit or ""),
                    str(item.phase or ""),
                    item.developer,
                    homes.get(item.apn, ""),
                    first.recorded.isoformat() if first and first.recorded else "",
                    str(len(item.sales)),
                    last.recorded.isoformat() if last and last.recorded else "",
                    price_text(last) if last else "",
                    dollars(last.enrolled_cents) if last else "",
                    _cell(owner),
                    status,
                )
            )
            + " |"
        )
    open_items = [item for item in items if item.open]
    if open_items:
        lines.extend(["", "## Open", ""])
        for item in open_items:
            lines.append(f"- [{parcel_number(item.apn)}]({item.apn}.md) {item.address}: {item.findings[0].detail if item.findings else 'no chain reaches the developer'}")
    lines.append("")
    return "\n".join(lines)


def mermaid_conveyances(item: ParcelHistory) -> str:
    """Flowchart of the chain, colored by process, with the related instruments beside it."""
    rows = ["flowchart TD"]
    if not item.steps:
        rows.append(f"    none[\"{parcel_number(item.apn)}<br/>no deed stored\"]")
        rows.append("    class none unknown;")
        rows.extend(f"    {style}" for style in _STYLES)
        return "\n".join(rows)
    for step in item.steps:
        rows.append(f"    {_node(step.number)}[\"{_label(step)}\"]")
        rows.append(f"    class {_node(step.number)} {_CLASS.get(step.process, 'sale')};")
        for related in step.related:
            rows.append(f"    {_rnode(related.number)}[\"{_related_label(related)}\"]")
            rows.append(f"    class {_rnode(related.number)} related;")
            rows.append(f"    {_rnode(related.number)} -. {_edge(related.role)} .-> {_node(step.number)}")
    numbers = {step.number for step in item.steps}
    if item.open:
        oldest = item.steps[0]
        if not oldest.developer:
            rows.append(f"    unknown[\"unknown<br/>{_brief(oldest.grantors)}'s deed<br/>{_before(oldest)}\"]")
            rows.append("    class unknown unknown;")
            rows.append(f"    unknown -.-> {_node(oldest.number)}")
    for step in item.steps:
        for prior in step.priors:
            if prior in numbers:
                rows.append(f"    {_node(prior)} -->|{_edge(step.placement)}| {_node(step.number)}")
    rows.extend(f"    {style}" for style in _STYLES)
    return "\n".join(rows)


def mermaid_tenure(item: ParcelHistory, *, today: date | None = None) -> str:
    """Gantt of who held the parcel: one bar per sale, from its deed to the next, and the current owner to today.

    A tenure that ended in a foreclosure is drawn critical. A step that moved
    no title (a restatement, a re-recording, an excluded transfer that did not
    reassess) is a milestone on the day it recorded.
    """
    today = today or date.today()
    rows = ["gantt", "    title Who held it", "    dateFormat YYYY-MM-DD", "    axisFormat %Y"]
    sales = [step for step in item.sales if step.recorded]
    if sales:
        rows.append("    section Owners")
        for index, step in enumerate(sales):
            following = sales[index + 1] if index + 1 < len(sales) else None
            end = following.recorded if following and following.recorded else today
            if end <= step.recorded:
                end = step.recorded + timedelta(days=1)
            flags = []
            if following is None:
                flags.append("active")
            elif following.process == "foreclosure":
                flags.append("crit")
            else:
                flags.append("done")
            rows.append(f"    {_task(_brief(step.grantees) or 'unknown')} :{', '.join(flags)}, {step.recorded.isoformat()}, {end.isoformat()}")
    others = [step for step in item.steps if step.recorded and not step.reassesses]
    if others:
        rows.append("    section Other instruments")
        for step in others:
            rows.append(f"    {_task(step.process or 'deed')} {step.number} :milestone, {step.recorded.isoformat()}, 0d")
    return "\n".join(rows)


def building_markdown(
    building: int,
    items: tuple[ParcelHistory, ...],
    *,
    title: str,
    report=None,
    annexation=None,
    homes: dict[str, str] | None = None,
    today: date | None = None,
) -> str:
    """One building on one page: its phase and instruments, every unit with its owner and standing, all tenures on one gantt, and the sales by year."""
    today = today or date.today()
    homes = homes or {}
    units = sorted((item for item in items if item.building == building and not item.association), key=lambda i: i.address)
    lines = [f"# {title}", ""]
    facts = [f"- **Units** {len(units)}"]
    if report is not None:
        facts.append(f"- **Phase** {report.phase}, Bureau file {report.file_number}, sold by {report.developer}, first conveyance {report.first_conveyance.isoformat()}")
        if getattr(report, "annexation", None):
            facts.append(f"- **Annexed** {report.annexation.isoformat()}" + (f" by {annexation.number} ({annexation.filing})" if annexation is not None else ""))
    plans: dict[str, int] = {}
    for item in units:
        label = homes.get(item.apn, "")
        plan = label.rsplit(", ", 1)[-1] if label and ("Plan" in label or "Unit" in label) else ""
        if plan:
            plans[plan] = plans.get(plan, 0) + 1
    if plans:
        facts.append("- **Plans** " + ", ".join(f"{count} × {plan}" for plan, count in sorted(plans.items())))
    sales = [step for item in units for step in item.sales if step.recorded]
    priced = [step.price_or_base[0] for step in sales if step.price_or_base[0]]
    facts.append(f"- **Sales on record** {len(sales)}, {len(priced)} priced" + (f", median {dollars(int(sorted(priced)[len(priced) // 2]))}" if priced else ""))
    leased = sum(1 for item in units if item.solar is not None and item.solar.leased)
    if any(item.solar is not None and item.solar.standing.name != "OUTSIDE_PROGRAM" for item in units):
        facts.append(f"- **Solar** {leased} of {len(units)} units carry a lease filing on the current owner")
    lines.extend(facts)
    lines.append("")
    lines.append("| Address | Home | Owner | Since | Last price | Liens to act on | Solar | Taxes |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | --- | --- |")
    for item in units:
        last = item.last_sale
        open_liens = sum(1 for lien in item.liens if lien_standing(item, lien).standing in ATTENTION)
        solar = item.solar.standing.name.lower().replace("_", " ") if item.solar is not None else ""
        lines.append(
            f"| [{_cell(item.address)}]({item.apn}.md) | {_cell(homes.get(item.apn, ''))} | {_cell(', '.join(item.owners))} | {last.recorded.isoformat() if last and last.recorded else ''} "
            f"| {price_text(last) if last else ''} | {open_liens} | {solar} | {item.taxes.status if item.taxes else ''} |"
        )
    lines.append("")
    lines.append("## Who held each unit")
    lines.append("")
    lines.append("One section per unit; a bar runs from the deed that gave the unit to the deed that took it, the current owner's to today.")
    lines.append("")
    lines.append("```mermaid")
    lines.append(mermaid_building_tenure(units, today=today))
    lines.append("```")
    lines.append("")
    years = sorted({step.recorded.year for step in sales})
    if years:
        span = list(range(years[0], today.year + 1))
        counts = [sum(1 for step in sales if step.recorded.year == year) for year in span]
        medians: list[float] = []
        last_value = 0.0
        for year in span:
            values = sorted(step.price_or_base[0] for step in sales if step.recorded.year == year and step.price_or_base[0])
            if values:
                last_value = round(values[len(values) // 2] / 100, 2)
            medians.append(last_value)
        lines.append("## Sales by year")
        lines.append("")
        lines.append("```mermaid")
        lines.append("xychart-beta")
        lines.append(f'    title "Building {building}: sales each year and the median price"')
        lines.append("    x-axis [" + ", ".join(str(y) for y in span) + "]")
        lines.append('    y-axis "Dollars"')
        lines.append("    bar [" + ", ".join(str(c * (max(medians) / max(max(counts), 1)) if medians else c) for c in counts) + "]")
        lines.append("    line [" + ", ".join(str(m) for m in medians) + "]")
        lines.append("```")
        lines.append("")
        lines.append("The line is the median deed price (or enrolled base) of the building's sales that year, carried through a year with none; the bars are the count of sales, scaled to the same axis so both fit one chart. Counts per year: " + ", ".join(f"{y}: {c}" for y, c in zip(span, counts) if c) + ".")
        lines.append("")
    return "\n".join(lines)


def mermaid_building_tenure(units: tuple[ParcelHistory, ...] | list[ParcelHistory], *, today: date | None = None) -> str:
    today = today or date.today()
    rows = ["gantt", "    title Who held each unit", "    dateFormat YYYY-MM-DD", "    axisFormat %Y"]
    for item in units:
        sales = [step for step in item.sales if step.recorded]
        if not sales:
            continue
        rows.append(f"    section {_task(item.address.title())}")
        for index, step in enumerate(sales):
            following = sales[index + 1] if index + 1 < len(sales) else None
            end = following.recorded if following and following.recorded else today
            if end <= step.recorded:
                end = step.recorded + timedelta(days=1)
            flag = "active" if following is None else ("crit" if following.process == "foreclosure" else "done")
            rows.append(f"    {_task(_brief(step.grantees) or 'unknown')} :{flag}, {step.recorded.isoformat()}, {end.isoformat()}")
    return "\n".join(rows)


def _task(text: str) -> str:
    """A gantt task title: no colon, semicolon, or hash, since each has a meaning there."""
    return " ".join(text.replace(":", " ").replace(";", " ").replace("#", " ").split())


def _value(item: ParcelHistory, value: Valuation, chart: str) -> list[str]:
    last = item.last_sale
    lines: list[str] = []
    if value.last_price:
        how = "the deed states" if value.source == "deed" else "the base the county enrolled stands in for"
        when = f" on {last.recorded.isoformat()}" if last and last.recorded else ""
        sq = f", {dollars(value.per_sqft)} a square foot" if value.per_sqft else ""
        lines.append(f"- **Last price** {dollars(value.last_price)}{when}, which {how}{sq}")
    if value.assessed:
        lines.append(f"- **Assessed value** {dollars(value.assessed)} on the latest bill; it trails the market by the Proposition 13 factor")
    if value.comps:
        lines.append(f"- **Recent comps** {dollars(value.comps)}, the trailing median for {value.comps_basis}")
    if value.indexed:
        lines.append(f"- **Indexed from the last price** {dollars(value.indexed)}, carried by the community median since it sold")
    if value.size_estimate:
        sq = f" at {dollars(value.community_per_sqft)} a foot" if value.community_per_sqft else ""
        lines.append(f"- **Size-adjusted comps** {dollars(value.size_estimate)}, the measured area at the trailing median per square foot for {value.size_basis}{sq}")
    if value.appreciation_pct is not None:
        annual = f", {value.annual_pct:+.1f}% a year" if value.annual_pct is not None else ""
        rank = ""
        if value.rank and value.building_units:
            rank = f"; ranks {value.rank} of {value.building_units} in the building"
        pct = f" and sits at the {value.percentile}th percentile of the community" if value.percentile is not None else ""
        lines.append(f"- **Appreciation** {value.appreciation_pct:+.1f}% against the last price{annual}{rank}{pct}")
    if not lines:
        lines.append("No priced sale to value from.")
    lines.append("")
    lines.append("None of these is an appraisal. Comps are the community's own recorded sales, and a deed of trust does not state its balance, so equity above a loan is not in the record.")
    if chart:
        lines.append("")
        lines.append(f"![This unit's indexed value, its sales, and the community and building medians]({chart})")
    return lines


def _facts(item: ParcelHistory, *, unit: UnitCharacteristics | None = None, plan: FloorPlan | None = None) -> list[str]:
    current_owner = ", ".join(item.owners)
    if item.association:
        held = item.steps[-1] if item.steps else None
        return [
            f"- **Parcel** {parcel_number(item.apn)}, a common area of the association",
            f"- **Building** {item.building or 'unknown'}, phase {item.phase or 'unknown'}" + (f", public report {item.report}" if item.report else ""),
            f"- **Held by** {current_owner or 'unknown'}" + (f" since {held.recorded.isoformat()} under {held.number}" if held and held.recorded else ""),
            f"- **Current instrument** {item.current_number or 'none'}" + (f" recorded {item.current_date.isoformat()}" if item.current_date else ""),
            f"- **Bills on file** {item.first_year} to {item.last_year}" if item.first_year else "- **Bills on file** none",
            f"- **Chain** {len(item.steps)} deeds back through the land, {item.verified} placed by a scan",
        ]
    rows = [
        f"- **Parcel** {parcel_number(item.apn)}" + _unit_note(item),
        f"- **Building** {item.building or 'unknown'}, phase {item.phase or 'unknown'}" + (f", public report {item.report}" if item.report else ""),
        f"- **Sold by** {item.developer or 'unknown'}",
    ]
    if unit is not None:
        rows.append(_home(unit, plan))
    rows += [
        f"- **Current owner** {current_owner or 'unknown'}",
        f"- **Current instrument** {item.current_number or 'none'}" + (f" recorded {item.current_date.isoformat()}" if item.current_date else "")
        + ("" if item.current_conveys else ", a death record the assessor lists; it moves no title, and the trust or the surviving owner continues"),
        f"- **Bills on file** {item.first_year} to {item.last_year}" if item.first_year else "- **Bills on file** none",
        f"- **Chain** {len(item.steps)} deeds, {len(item.sales)} sales, {item.verified} placed by a scan"
        + (", reaches the developer" if not item.open else ", **does not reach the developer**"),
    ]
    return rows


def _home(unit: UnitCharacteristics, plan: FloorPlan | None) -> str:
    """The assessor's record of the home, and the developer's plan it matches."""
    parts: list[str] = []
    if unit.bedrooms:
        parts.append(f"{unit.bedrooms} bedrooms")
    if unit.baths:
        baths = f"{unit.baths:g}"
        parts.append(f"{baths} baths")
    if unit.living_sqft:
        parts.append(f"{unit.living_sqft:,} sq ft")
    if unit.year_built:
        parts.append(f"built {unit.year_built}")
    if unit.garage_sqft:
        parts.append(f"{unit.garage_sqft:,} sq ft garage")
    text = "- **Home** " + (", ".join(parts) if parts else "no residential record at the assessor")
    if plan is not None:
        text += f"; {plan.name} of {plan.developer}, stated at {plan.living_sqft:,} sq ft in the {plan.source}" if plan.source else f"; {plan.name} of {plan.developer}"
    elif unit.living_sqft:
        text += "; matches none of the developer's stated plans"
    return text


def home_brief(unit: UnitCharacteristics, plan: FloorPlan | None) -> str:
    """The home in a few words for a table cell: ``3 bd, 2.5 ba, 1,491 sf, Plan 1``."""
    parts: list[str] = []
    if unit.bedrooms:
        parts.append(f"{unit.bedrooms} bd")
    if unit.baths:
        parts.append(f"{unit.baths:g} ba")
    if unit.living_sqft:
        parts.append(f"{unit.living_sqft:,} sf")
    if plan is not None:
        parts.append(plan.name)
    return ", ".join(parts)


def _unit_note(item: ParcelHistory) -> str:
    """The unit under its building's numbering, and the other parcel that shares the number."""
    if not item.unit:
        return ""
    from jason.community import community as active
    from jason.community.reports import unit_parcels

    blocks = active().unit_blocks()
    others = [
        f"{parcel_number(apn)} on building {int(block.building)}"
        for block, apn in unit_parcels(item.unit, blocks)
        if "".join(ch for ch in apn if ch.isdigit()) != item.apn
    ]
    numbering = next((block.plan for block, apn in unit_parcels(item.unit, blocks) if "".join(ch for ch in apn if ch.isdigit()) == item.apn), "")
    text = f", unit {item.unit} under the {numbering}" if numbering else f", unit {item.unit}"
    if others:
        text += f" (the same number is {', '.join(others)}; a unit number does not place a deed)"
    return text


def _chain_table(item: ParcelHistory) -> list[str]:
    lines = [
        "| # | Recorded | Document | Process | From | To | Price | Bill year | Enrolled base | Placed by | Scan | Why unpriced |",
        "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for step in item.steps:
        process = step.process
        if step.developer:
            process = f"{process} by {step.developer}"
        lines.append(
            "| "
            + " | ".join(
                (
                    str(step.order),
                    step.recorded.isoformat() if step.recorded else "",
                    step.number,
                    process,
                    _cell(", ".join(step.grantors)),
                    _cell(", ".join(step.grantees)),
                    price_text(step),
                    str(step.bill_year or ""),
                    dollars(step.enrolled_cents),
                    step.placement,
                    _cell(step.scan),
                    step.unpriced,
                )
            )
            + " |"
        )
    return lines


def price_text(step: HistoryStep) -> str:
    """The deed price, or the enrolled base marked as a stand-in, or exempt."""
    if step.exempt:
        return "exempt"
    amount, source = step.price_or_base
    if source == "deed":
        return dollars(amount)
    if source == "base":
        return f"≈ {dollars(amount)} (base)"
    return ""


def _related_table(item: ParcelHistory) -> list[str]:
    lines = [
        "| Beside | Role | Document | Recorded | Filing | From | To | Found |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    count = 0
    for step in item.steps:
        for related in step.related:
            count += 1
            lines.append(
                "| "
                + " | ".join(
                    (
                        step.number,
                        related.role,
                        related.number,
                        related.recorded.isoformat() if related.recorded else "",
                        _cell(related.filing or related.kind),
                        _cell(", ".join(related.grantors)),
                        _cell(", ".join(related.grantees)),
                        related.reason,
                    )
                )
                + " |"
            )
    if not count:
        lines.append("| | | | | | | | |")
    return lines


def _calendar_table(item: ParcelHistory) -> list[str]:
    lines = [
        "| Bill year | Enrolled | Prior | Change | Reading | Deed |",
        "| ---: | ---: | ---: | ---: | --- | --- |",
    ]
    if not item.events:
        lines.append("| | | | | no year left the 2% track | |")
        return lines
    for event in item.events:
        change = ""
        if event.prior_enrolled_cents:
            change = f"{(event.enrolled_cents - event.prior_enrolled_cents) * 100 / event.prior_enrolled_cents:+.1f}%"
        lines.append(
            f"| {event.year} | {dollars(event.enrolled_cents)} | {dollars(event.prior_enrolled_cents)} | {change} | {_reading(event.kind)} | {event.number} |"
        )
    return lines


def _taxes(item: ParcelHistory) -> list[str]:
    standing = item.taxes
    if standing is None or standing.first_year is None:
        return ["No tax bill is on file."]
    lines = [f"Bills {standing.first_year} to {standing.last_year}: **{standing.status}**."]
    if standing.unpaid:
        lines.append("Due: " + ", ".join(f"{year} {dollars(cents)}" for year, cents in standing.unpaid) + ".")
    if standing.delinquent:
        lines.append("Delinquent: " + ", ".join(f"{year} {dollars(cents)}" for year, cents in standing.delinquent) + f". The tax collector may notice the parcel for sale on {standing.power_to_sell.isoformat()} if nothing is paid.")
    if standing.missing_years:
        span = _years(standing.missing_years)
        lines.append(f"No bill on file for {span}. On a common-area parcel that is the stretch the county carried it as tax-defaulted before the 2023 notice of power to sell; on a unit it is a bill the sync did not fetch.")
    return lines


def _events(item: ParcelHistory) -> list[str]:
    if not item.owner_events:
        return ["No death affidavit, power of attorney, or homestead names an owner of this parcel in the index cache."]
    lines = ["| Recorded | Document | Filing | Event | Owner | Parties | During tenure |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for event in item.owner_events:
        flag = " **decedent still on title**" if event.still_on_title else ""
        lines.append(
            f"| {event.recorded.isoformat() if event.recorded else ''} | {event.number} | {event.filing} | {event.kind}{flag} | {_cell(event.owner)} | {_cell(', '.join(event.parties))} | {'yes' if event.during_tenure else 'no'} |"
        )
    return lines


def _years(years: tuple[int, ...]) -> str:
    if not years:
        return ""
    runs: list[list[int]] = [[years[0]]]
    for year in years[1:]:
        if year == runs[-1][-1] + 1:
            runs[-1].append(year)
        else:
            runs.append([year])
    return ", ".join(f"{run[0]}" if len(run) == 1 else f"{run[0]} to {run[-1]}" for run in runs)


def _liens(item: ParcelHistory) -> list[str]:
    if item.association:
        return ["The association's own liens and notices are in the association record."]
    if not item.liens:
        return ["No lien, default, or release names an owner of this parcel in the index cache."]
    shown = [lien for lien in item.liens if lien.where != "another time or property"]
    elsewhere = [lien for lien in item.liens if lien.where == "another time or property"]
    lines = [
        "A lien indexes a person, not a parcel. One that opened while its owner held this unit is likely on it; one from another time is another property or another person of the same name, and is counted, not listed. A mechanic's lien reads expired when no suit was recorded within ninety days (Civil Code section 8460); it is unenforceable then, but stays of record until released.",
        "",
    ]
    if elsewhere:
        kinds: dict[str, int] = {}
        for lien in elsewhere:
            kinds[lien.encumbrance.process.value] = kinds.get(lien.encumbrance.process.value, 0) + 1
        names = sorted({lien.owner for lien in elsewhere})
        summary = ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items()))
        lines.append(f"{len(elsewhere)} lifecycles name {', '.join(names)} at another time or property ({summary}). They are on the spreadsheet's Liens tab.")
        lines.append("")
    if not shown:
        lines.append("None opened while an owner held this unit.")
        return lines
    lines += [
        "| Process | Opened | Closed | Status | Debtor | Claimant | Steps | Standing |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for lien in shown:
        e = lien.encumbrance
        steps = "; ".join(f"{step.filing} {step.number}" for step in e.steps)
        reading = lien_standing(item, lien)
        standing = reading.standing.name.lower().replace("_", " ")
        if reading.sale is not None:
            standing += f" at the {reading.sale.isoformat()} sale"
        if reading.roll_year is not None:
            standing += f" on the {reading.roll_year}-{str(reading.roll_year + 1)[-2:]} tax bill"
        if lien.namesake_risk:
            standing += "; names the owner by surname and given name only"
        lines.append(
            "| "
            + " | ".join(
                (
                    e.process.value,
                    e.opened.recorded.isoformat() if e.opened.recorded else "",
                    e.closed.isoformat() if e.closed else "",
                    e.status,
                    _cell(", ".join(e.debtor)),
                    _cell(", ".join(e.claimant)),
                    _cell(steps),
                    _cell(standing),
                )
            )
            + " |"
        )
    return lines


def _solar(item: ParcelHistory, shared: str = "") -> list[str]:
    record = item.solar
    if record is None:
        return []
    lines = [f"- **Program** {record.program}", f"- **Standing** {record.standing.value}"]
    if record.current_filing is not None:
        f = record.current_filing
        lines.append(f"- **Lease filing** {f.number} recorded {f.recorded.isoformat() if f.recorded else ''} by {f.lessor} against {f.owner}")
    if record.note:
        lines.append(f"- **Note** {record.note}")
    if shared:
        lines.append(f"- **Shared filing** {shared}")
    if record.filings:
        lines.append("")
        lines.append("| Recorded | Filing | Lessor | Against | Status | Terminated | During tenure |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for f in record.filings:
            lines.append(
                f"| {f.recorded.isoformat() if f.recorded else ''} | {'; '.join(f.steps)} | {_cell(f.lessor)} | {_cell(f.owner)} | {f.status} "
                f"| {f.closed.isoformat() if f.closed else ''} | {'yes' if f.during_tenure else 'no'} |"
            )
    return lines


def shared_filing_notes(items: tuple[ParcelHistory, ...] | list[ParcelHistory]) -> dict[str, str]:
    """A sentence per parcel whose current lease filing also stands for another unit of the same owner."""
    from jason.community.solar import shared_filings

    address = {item.apn: item.address for item in items}
    shared = shared_filings({item.apn: item.solar for item in items if item.solar is not None})
    return {
        apn: f"The same filing stands for {', '.join(address.get(other, other) for other in others)}: the owner holds more than one unit and the index names the debtor, not the unit, so one of them is leased and the record cannot say which."
        for apn, others in shared.items()
    }


def solar_markdown(items: tuple[ParcelHistory, ...], program, *, title: str) -> str:
    """The escrow list: every unit in the program's buildings and its solar standing."""
    lines = [f"# {title}", ""]
    lines.append(f"{program.name}. Developer: {program.developer}. Buildings {', '.join(str(int(b)) for b in program.buildings)}.")
    lines.append("")
    lines.append(f"Lease servicer: {program.servicer}." if program.servicer else "")
    lines.append("")
    if program.note:
        lines.append(program.note)
        lines.append("")
    lines.append("A leased share carries a UCC financing statement the lease fund recorded against the buyer; a termination ends it. The county indexes those by the debtor's name, so this page reads the filings that name each unit's owners. No filing is not proof of purchase: a filing can be missed or never recorded. The lessors on record: " + ", ".join(program.lessors[:3]) + ", and their affiliates.")
    lines.append("")
    units = [item for item in items if not item.association and item.solar is not None and program.covers(item.building)]
    counts: dict[str, int] = {}
    for item in units:
        key = item.solar.standing.name.lower().replace("_", " ")
        counts[key] = counts.get(key, 0) + 1
    lines.append("| Standing | Units |")
    lines.append("| --- | ---: |")
    for key, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {key} | {count} |")
    lines.append("")
    lines.append("| Building | Address | Current owner | Standing | Lessor | Filing | Recorded | Terminated | Note |")
    lines.append("| ---: | --- | --- | --- | --- | --- | --- | --- | --- |")
    shared = shared_filing_notes(units)
    for item in sorted(units, key=lambda i: (i.building or 0, i.address)):
        record = item.solar
        current = record.current_filing
        terminated = ", ".join(f.closed.isoformat() for f in record.filings if f.closed)
        note = record.note + (" " + shared[item.apn] if item.apn in shared else "")
        lines.append(
            f"| {item.building} | [{_cell(item.address)}]({item.apn}.md) | {_cell(', '.join(item.owners))} | {record.standing.name.lower().replace('_', ' ')} "
            f"| {_cell(record.lessor)} | {current.number if current else ''} | {current.recorded.isoformat() if current and current.recorded else ''} | {terminated} | {_cell(note)} |"
        )
    outside = [item for item in items if not item.association and item.solar is not None and not program.covers(item.building)]
    if outside:
        lines.append("")
        lines.append(f"{len(outside)} units in the other buildings are outside the program. A solar filing there is an owner's own lease or loan, listed on the unit's page under liens.")
    lines.append("")
    return "\n".join(lines)


def association_markdown(record, *, title: str) -> str:
    """The association's record: governing instruments, liens placed, liens against, notices."""
    lines = [f"# {title}", ""]
    lines.append("## Governing instruments the index holds")
    lines.append("")
    lines.append("Each row is a recorded instrument the subdivider had to deliver under Title 10 section 2792.23(a), or an amendment or annexation the association or a later developer recorded.")
    lines.append("")
    lines.append("| Recorded | Document | Filing | What it is | Phase | Recorded by | Cites | Status |")
    lines.append("| --- | --- | --- | --- | ---: | --- | --- | --- |")
    for item in record.governing:
        lines.append(
            f"| {item.recorded.isoformat() if item.recorded else ''} | {item.number} | {item.filing} | {item.role} | {item.phase or ''} | {_cell(item.developer or ', '.join(item.parties))} | {', '.join(item.cites)} | {item.status} |"
        )
    lines.append("")
    lines.append("## The 2792.23 deliveries")
    lines.append("")
    lines.append("| Delivery | In the index | Still missing |")
    lines.append("| --- | --- | --- |")
    for status in record.deliveries:
        numbers = ", ".join(f"{r.number}" + (f" (phase {r.phase})" if r.phase else "") + (" (rescinded)" if r.superseded_by else "") for r in status.records)
        lines.append(f"| {status.delivery.value.replace('_', ' ')} | {numbers or 'none'} | {_cell('; '.join(status.missing))} |")
    if record.unplaced:
        lines.append("")
        lines.append("Developer governing instruments recorded after the project opened that name no phase and match no annexation date; read the image before treating one as Mystique:")
        lines.append("")
        for item in record.unplaced:
            lines.append(f"- {item.number} {item.recorded.isoformat() if item.recorded else ''} {item.filing} by {item.developer or ', '.join(item.parties)}")
    lines.append("")
    lines.append("## Mechanic's liens from construction")
    lines.append("")
    lines.append("A contractor's claim of lien recorded against a developer during construction. Civil Code section 8460 gives the claimant ninety days from recording to sue; an unsued lien expires and is unenforceable, though it stays of record until a release or a court order. A lien that survived a unit's conveyance would follow that unit.")
    lines.append("")
    lines.extend(_encumbrance_table(record.construction, debtor_label="Developer"))
    lines.append("")
    lines.append("## Liens the association placed")
    lines.append("")
    lines.extend(_encumbrance_table(record.placed, debtor_label="Owner"))
    lines.append("")
    lines.append("## Liens and notices against the association")
    lines.append("")
    lines.extend(_encumbrance_table(record.against, debtor_label="Debtor"))
    lines.append("")
    lines.append("## Notices the association recorded")
    lines.append("")
    if record.notices:
        for item in record.notices:
            lines.append(f"- {item.number} {item.recorded.isoformat() if item.recorded else ''} {item.filing_code} {item.filing_name}: {', '.join(item.grantors)} → {', '.join(item.grantees) or 'the public'}")
    else:
        lines.append("None in the cache.")
    lines.append("")
    return "\n".join(lines)


def _encumbrance_table(items, *, debtor_label: str) -> list[str]:
    lines = [
        f"| Process | Opened | Closed | Status | {debtor_label} | Claimant | Steps |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not items:
        lines.append("| none | | | | | | |")
        return lines
    for e in items:
        steps = "; ".join(f"{step.filing} {step.number}" for step in e.steps)
        lines.append(
            f"| {e.process.value} | {e.opened.recorded.isoformat() if e.opened.recorded else ''} | {e.closed.isoformat() if e.closed else ''} | {e.status} | {_cell(', '.join(e.debtor))} | {_cell(', '.join(e.claimant))} | {_cell(steps)} |"
        )
    return lines


def _members(item: ParcelHistory) -> list[str]:
    check = item.membership
    lines: list[str] = []
    if item.association:
        return ["A common area. The association holds it for the members; no member is on title."]
    if check is None:
        return ["No PayHOA record was read for this parcel."]
    owners = ", ".join(check.owners) or "nobody on a stored deed"
    members = ", ".join(check.members) or "nobody"
    since = f" since {check.since.isoformat()}" if check.since else ""
    lines.append(f"Title: {owners}. Members: {members}. **{check.verdict}**{since}.")
    if check.unmatched_owners:
        lines.append(f"On title but not a member: {', '.join(check.unmatched_owners)}.")
    if check.unmatched_members:
        lines.append(f"A member but not on title: {', '.join(check.unmatched_members)}.")
    if item.occupancies:
        lines.append("")
        lines.append("| From | To | Members |")
        lines.append("| --- | --- | --- |")
        for period in item.occupancies:
            start = period.from_date.isoformat() if period.from_date else ""
            end = period.to_date.isoformat() if period.to_date else "current"
            lines.append(f"| {start} | {end} | {_cell(', '.join(period.members))} |")
    return lines


def _reading(kind: str) -> str:
    return {
        SALE: "sale",
        CONSTRUCTION: "construction enrolled",
        RESTORATION: "Proposition 8 restoration",
        IMPROVEMENT: "improvement",
        DECLINE: "decline",
    }.get(kind, kind)


def _label(step: HistoryStep) -> str:
    when = step.recorded.isoformat() if step.recorded else ""
    process = step.process or "deed"
    if step.developer:
        process = f"{process}<br/>{step.developer}"
    money = ""
    if step.exempt:
        money = "<br/>no transfer tax"
    elif step.price_cents:
        money = f"<br/>{dollars(step.price_cents)}"
    elif step.price_or_base[1] == "base":
        money = f"<br/>about {dollars(step.enrolled_cents)}, from the base"
    base = f"<br/>base {dollars(step.enrolled_cents)} on the {step.bill_year} bill" if step.enrolled_cents else ""
    text = f"{step.number}<br/>{when}<br/>{process}<br/>{_brief(step.grantors)} to {_brief(step.grantees)}{money}{base}"
    return text.replace('"', "'")


def _related_label(related: RelatedInstrument) -> str:
    when = related.recorded.isoformat() if related.recorded else ""
    filing = related.filing or related.kind or related.role
    parties = ""
    if related.grantors or related.grantees:
        parties = f"<br/>{_brief(related.grantors)} to {_brief(related.grantees)}"
    found = "" if related.reason == "present" else f"<br/>({related.reason})"
    return f"{related.number}<br/>{when}<br/>{filing}{parties}{found}".replace('"', "'")


def _before(step: HistoryStep) -> str:
    return f"before {step.recorded.isoformat()}" if step.recorded else ""


def _edge(text: str) -> str:
    return text.replace("|", "/").replace('"', "'")


def _brief(names: tuple[str, ...]) -> str:
    if not names:
        return ""
    first = names[0]
    if len(first) > 36:
        first = first[:35] + "…"
    if len(names) == 1:
        return first
    return f"{first} +{len(names) - 1}"


def _node(number: str) -> str:
    return "d" + "".join(ch for ch in number if ch.isalnum())


def _rnode(number: str) -> str:
    return "r" + "".join(ch for ch in number if ch.isalnum())


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "/").split())
