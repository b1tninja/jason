"""Where each recorded lien stands against a unit's title today.

A lien joins a unit through its owner's name, so a unit's history holds
liens on the current owner, on prior owners, and on the same people
elsewhere. ``lien_standing`` reads one lien against the chain and says
which of a closed set of standings it has: released, standing against
the current owner, presumed paid at a sale, a release the association
still owes, lapsed or expired, running with the land, or somewhere else.
``title_watch`` does that for every unit and returns the rows a board
member or an escrow officer reads. The standing is what the index shows;
it is not a title report, and a presumption is not a release.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Any

from jason.community import filings
from jason.community.filings import Process, same_party


class LienStanding(Enum):
    RELEASED = "released of record"
    ROLL_PAID = "a utility lien whose delinquency went onto this parcel's tax bill, and the bill is paid; satisfied, though no termination is recorded"
    ON_ROLL = "a utility lien whose delinquency is on this parcel's tax bill, still unpaid; it is collected with the taxes"
    AWAITING_ROLL = "a utility lien too recent for the stored tax bills to show; the next bill says whether it moved onto the roll"
    IN_DEFAULT = "a default or sale notice is running against the current owner"
    QUIET_DEFAULT = "a default notice over a year old with no sale since; cured, reinstated, or abandoned without a record in the index"
    STANDS = "stands against the current owner"
    CURRENT_LOAN = "the current owner's loan; paid off at their sale"
    SOLAR_LEASE = "a solar lessor's or solar lender's fixture filing on the current owner; a lease passes to a buyer, a solar loan is paid at the sale"
    STANDS_ON_PRIOR = "a prior owner's lien with no sale since; it still follows the property"
    RELEASE_DUE = "the association's lien on a prior owner, paid at a sale with no release of record; the association owes the release (Civil Code 5685)"
    PRESUMED_PAID = "a prior owner's lien, presumed paid at the sale that ended their tenure; no release in the index"
    FIXTURE_PRIOR = "a prior owner's fixture filing; the solar standing says whether the lease moved"
    LAPSED = "past its statutory life with no renewal; unenforceable, still of record"
    EXPIRED = "a mechanic's lien never sued on; unenforceable, still of record"
    RUNS_WITH_LAND = "a charge that runs with the land and passes to each buyer"
    ELSEWHERE = "names an owner at another time or on another property"


# Standings a person acts on, in the order a page lists them.
ATTENTION = (LienStanding.IN_DEFAULT, LienStanding.STANDS, LienStanding.STANDS_ON_PRIOR, LienStanding.RELEASE_DUE)
OF_RECORD = (LienStanding.LAPSED, LienStanding.EXPIRED)
_DEFAULTS = ("in default", "noticed for sale", "ordered for sale", "noticed for tax sale")
_WITH_LAND = (Process.PACE_ASSESSMENT, Process.SPECIAL_TAX)


# A trustee's sale follows a notice of default within months (Civil Code 2924). A default with no step for this
# long, and the owner still on title, was cured, reinstated, or abandoned without a record the index holds.
QUIET_DEFAULT_DAYS = 365


def _solar(claimant: tuple[str, ...]) -> bool:
    from jason.community.solar import SecuredPartyKind, classify_secured_party

    return classify_secured_party(tuple(claimant)) in (SecuredPartyKind.SOLAR_LESSOR, SecuredPartyKind.SOLAR_LENDER)


@dataclass(frozen=True)
class Reading:
    standing: LienStanding
    sale: date | None = None
    roll_year: int | None = None


def roll_charge_for(item, lien):
    """The charge on the parcel's own tax bill that carries this utility lien's delinquency, or None.

    The agency places a delinquency on the bill for the fiscal year that
    starts the July after the roll closes in August, so a lien recorded
    by August of year Y lands on the Y bill, later on the Y+1 bill; one more
    year is allowed for a late placement. The agency's name on the lien
    picks the charge code.
    """
    window = roll_window(lien)
    if window is None:
        return None
    for charge in getattr(item, "utility_roll", None) or ():
        if charge.rule is not None and charge.rule.claims(tuple(lien.encumbrance.claimant)) and window[0] <= charge.year <= window[1]:
            return charge
    return None


def roll_window(lien) -> tuple[int, int] | None:
    """The fiscal years whose tax bill could carry a utility lien's delinquency: the next roll, and one late."""
    e = lien.encumbrance
    if e.process is not Process.UTILITY_LIEN or e.opened.recorded is None:
        return None
    opened = e.opened.recorded
    first = opened.year if opened.month <= 8 else opened.year + 1
    return first, first + 1


def lien_standing(item, lien) -> Reading:
    """One lien's standing against the unit's title. ``item`` is the ``ParcelHistory``; ``lien`` one of its ``liens``."""
    e = lien.encumbrance
    if lien.where == "another time or property":
        return Reading(LienStanding.ELSEWHERE)
    if e.status == "closed":
        return Reading(LienStanding.RELEASED)
    charge = roll_charge_for(item, lien)
    if charge is not None:
        return Reading(LienStanding.ROLL_PAID if charge.paid else LienStanding.ON_ROLL, roll_year=charge.year)
    window = roll_window(lien)
    last_bill = getattr(getattr(item, "taxes", None), "last_year", None)
    if window is not None and last_bill is not None and window[1] > last_bill and getattr(item, "utility_roll", None) is not None:
        # The bills that could carry it are not issued yet, or not stored; "stands" would say more than we know.
        return Reading(LienStanding.AWAITING_ROLL, roll_year=window[0] if window[0] > last_bill else window[1])
    if e.process in _WITH_LAND:
        return Reading(LienStanding.RUNS_WITH_LAND)
    if e.status == "lapsed":
        return Reading(LienStanding.LAPSED)
    if e.status == "expired":
        return Reading(LienStanding.EXPIRED)
    current = any(same_party(lien.owner, name) for name in item.owners)
    if current:
        if e.status in _DEFAULTS:
            newest = max((step.recorded for step in e.steps if step.recorded), default=None)
            if newest is not None and (filings.today_for_status() - newest).days > QUIET_DEFAULT_DAYS:
                return Reading(LienStanding.QUIET_DEFAULT)
            return Reading(LienStanding.IN_DEFAULT)
        if e.process is Process.LOAN:
            return Reading(LienStanding.CURRENT_LOAN)
        if e.process is Process.FIXTURE_FILING and (lien.corroborated or _solar(e.claimant)):
            return Reading(LienStanding.SOLAR_LEASE)
        return Reading(LienStanding.STANDS)
    if e.process is Process.FIXTURE_FILING:
        return Reading(LienStanding.FIXTURE_PRIOR)
    opened = e.opened.recorded
    sale = next((step.recorded for step in item.sales if step.recorded and opened and step.recorded > opened), None)
    if sale is None:
        return Reading(LienStanding.STANDS_ON_PRIOR)
    if e.process is Process.ASSESSMENT_LIEN:
        return Reading(LienStanding.RELEASE_DUE, sale)
    return Reading(LienStanding.PRESUMED_PAID, sale)


@dataclass(frozen=True)
class TitleRow:
    apn: str
    address: str
    building: int | None
    owner: str
    current_owners: tuple[str, ...]
    process: str
    number: str
    recorded: date | None
    claimant: tuple[str, ...]
    status: str
    standing: LienStanding
    sale: date | None
    namesake_risk: bool
    until: date | None
    # Other units whose owner the same filing names: an owner of several units, one lien, one of them charged.
    shared_with: tuple[str, ...] = ()
    # The newest step's date: a notice of default, a renewal, or a release, where ``recorded`` is the opening.
    latest: date | None = None
    # The fiscal year of the tax bill that carries a utility lien's delinquency.
    roll_year: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "apn": self.apn, "address": self.address, "building": self.building, "owner": self.owner, "currentOwners": list(self.current_owners),
            "process": self.process, "number": self.number, "recorded": self.recorded.isoformat() if self.recorded else "",
            "claimant": list(self.claimant), "status": self.status, "standing": self.standing.name, "meaning": self.standing.value,
            "presumedPaidAt": self.sale.isoformat() if self.sale else "", "namesakeRisk": self.namesake_risk,
            "enforceableUntil": self.until.isoformat() if self.until else "",
            "sharedWith": list(self.shared_with),
            "latestStep": self.latest.isoformat() if self.latest else "",
            "taxBillYear": self.roll_year,
        }


def title_watch(histories, *, include: tuple[LienStanding, ...] = ()) -> tuple[TitleRow, ...]:
    """Every unit's liens with their standing, the ones a person acts on first. ``include`` limits the standings."""
    rows: list[TitleRow] = []
    for item in histories:
        if item.association:
            continue
        for lien in item.liens:
            reading = lien_standing(item, lien)
            if include and reading.standing not in include:
                continue
            e = lien.encumbrance
            rows.append(TitleRow(
                item.apn, item.address, item.building, lien.owner, tuple(item.owners), e.process.value, e.opened.number, e.opened.recorded,
                tuple(e.claimant), e.status, reading.standing, reading.sale, lien.namesake_risk, e.unenforceable_after,
                latest=max((step.recorded for step in e.steps if step.recorded), default=None),
                roll_year=reading.roll_year,
            ))
    # The index names the debtor, not the unit: one filing on an owner of several units joins each of them.
    units_of: dict[str, set[str]] = {}
    for row in rows:
        if row.standing is not LienStanding.ELSEWHERE:
            units_of.setdefault(row.number, set()).add(row.apn)
    rows = [
        replace(row, shared_with=tuple(sorted(units_of[row.number] - {row.apn}))) if len(units_of.get(row.number, ())) > 1 else row
        for row in rows
    ]
    order = {standing: index for index, standing in enumerate(LienStanding)}
    rows.sort(key=lambda r: (order[r.standing], r.apn, r.recorded or date.min, r.number))
    return tuple(rows)


def standing_counts(rows) -> dict[str, int]:
    found: dict[str, int] = {}
    for row in rows:
        found[row.standing.name] = found.get(row.standing.name, 0) + 1
    order = [s.name for s in LienStanding]
    return dict(sorted(found.items(), key=lambda kv: order.index(kv[0])))


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "/")


def _label(standing: LienStanding) -> str:
    return standing.name.lower().replace("_", " ")


def title_markdown(rows: tuple[TitleRow, ...], *, title: str, today: date | None = None) -> str:
    """The lien page: what stands against current owners, what a person should check, and what the index leaves of record."""
    from jason.community.tax import parcel_number

    lines = [f"# {title}", ""]
    lines.append(
        "Every recorded lien the index joins to a unit's owners, read against the chain. A lien indexes a person, not a parcel, "
        "so each row says where it stands against the unit's title today. This is what the index shows, not a title report: "
        "a presumption is not a release, and a release recorded under another spelling can be missing."
        + (f" Read {today.isoformat()}." if today else "")
    )
    lines.append("")
    here = [row for row in rows if row.standing is not LienStanding.ELSEWHERE]
    counts = standing_counts(here)
    lines.append("| Standing | Liens | Meaning |")
    lines.append("| --- | ---: | --- |")
    for name, count in counts.items():
        lines.append(f"| {name.lower().replace('_', ' ')} | {count} | {LienStanding[name].value} |")
    elsewhere = sum(1 for row in rows if row.standing is LienStanding.ELSEWHERE)
    lines.append("")
    lines.append(f"{elsewhere} more name an owner at another time or on another property, including other associations' liens; they are on each unit's page and not here.")
    lines.append("")

    def table(selected: list[TitleRow], *, sale: bool = False, roll: bool = False) -> None:
        head = "| Unit | Address | Owner | Lien | Recorded | Claimant | Status |" + (" Sale |" if sale else " Tax bill |" if roll else " Note |")
        lines.append(head)
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in selected:
            notes = []
            if row.namesake_risk:
                notes.append("names the owner by surname and given name only; confirm it is theirs")
            if row.shared_with:
                notes.append("the same filing names the owner of " + ", ".join(parcel_number(apn) for apn in row.shared_with) + "; it charges one of them")
            if row.until and row.standing in (LienStanding.LAPSED, LienStanding.EXPIRED):
                notes.append(f"enforceable until {row.until.isoformat()}")
            if roll:
                state = {LienStanding.ROLL_PAID: "paid", LienStanding.ON_ROLL: "unpaid"}.get(row.standing, "not issued or not stored yet")
                last = f"{row.roll_year}-{str(row.roll_year + 1)[-2:]}, {state}"
            else:
                last = row.sale.isoformat() if sale and row.sale else "; ".join(notes)
            lines.append(
                f"| [{parcel_number(row.apn)}]({row.apn}.md) | {_cell(row.address)} | {_cell(row.owner)} | {row.process} {row.number} "
                f"| {row.recorded.isoformat() if row.recorded else ''} | {_cell(', '.join(row.claimant[:2]))} | {_cell(row.status)} | {_cell(last)} |"
            )
        lines.append("")

    attention = [row for row in here if row.standing in ATTENTION]
    lines.append("## Needs a person")
    lines.append("")
    if attention:
        by_standing: dict[LienStanding, list[TitleRow]] = {}
        for row in attention:
            by_standing.setdefault(row.standing, []).append(row)
        for standing in ATTENTION:
            selected = by_standing.get(standing, [])
            if not selected:
                continue
            lines.append(f"### {_label(standing).capitalize()}")
            lines.append("")
            lines.append(standing.value[0].upper() + standing.value[1:] + ".")
            lines.append("")
            table(selected)
    else:
        lines.append("Nothing stands against a current owner, and no release is owed.")
        lines.append("")
    utility = [row for row in attention if row.process == "utility lien"]
    if utility:
        lines.append(
            f"{len(utility)} of those are city or county utility liens. Their terminations (filing 644) are fetched for a wide owner "
            "name only by `jason sync-liens --all`, so some may be paid and released off this page; the city's account is the proof."
        )
        lines.append("")
    quiet = [row for row in here if row.standing is LienStanding.QUIET_DEFAULT]
    if quiet:
        lines.append("## Defaults that went quiet")
        lines.append("")
        lines.append(LienStanding.QUIET_DEFAULT.value[0].upper() + LienStanding.QUIET_DEFAULT.value[1:] + ". The owner is still on title; the trustee's file says which.")
        lines.append("")
        table(quiet)
    record = [row for row in here if row.standing in OF_RECORD]
    if record:
        lines.append("## Unenforceable but of record")
        lines.append("")
        lines.append("A title officer may still ask for the release; the owner can petition for it.")
        lines.append("")
        table(record)
    roll = [row for row in here if row.standing in (LienStanding.ON_ROLL, LienStanding.ROLL_PAID, LienStanding.AWAITING_ROLL)]
    if roll:
        lines.append("## Utility liens on the tax roll")
        lines.append("")
        lines.append(
            "The city and the sewer district move a delinquent account onto the parcel's secured tax bill as a direct charge "
            "(codes 0202 and 0411). The bill is keyed to the parcel, so a paid bill with the charge settles the lien even with "
            "no termination in the index; an unpaid one is collected with the taxes."
        )
        lines.append("")
        table(roll, roll=True)
    presumed = [row for row in here if row.standing is LienStanding.PRESUMED_PAID]
    if presumed:
        lines.append("## Presumed paid at a sale")
        lines.append("")
        lines.append("A prior owner's lien with no release in the index, followed by a sale. Escrow pays the seller's liens, so each is presumed paid on the sale date shown; the release may be recorded under another spelling, or not at all.")
        lines.append("")
        table(presumed, sale=True)
    with_land = [row for row in here if row.standing is LienStanding.RUNS_WITH_LAND]
    if with_land:
        lines.append("## Runs with the land")
        lines.append("")
        table(with_land)
    solar = sum(1 for row in here if row.standing is LienStanding.SOLAR_LEASE)
    loans = sum(1 for row in here if row.standing is LienStanding.CURRENT_LOAN)
    lines.append("## Ordinary")
    lines.append("")
    lines.append(f"{loans} loans on current owners and {solar} solar program lease filings stand as expected; the unit pages list them, and [solar.md](solar.md) has the lease standings.")
    lines.append("")
    return "\n".join(lines)
