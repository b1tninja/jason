"""What the county's records say about each unit's owners: the latest grant deed, the homeowners' exemption, and where
the county mails the owner. Read from disk only (the deed chain in ``data/ownership.db``, the tax bills in
``data/tax.db``, the bulk secured roll), for the owner-information plan's occupancy and title checks.

- **The homeowners' exemption** is claimed only for the owner's principal residence: a claim is strong evidence the
  owner lives in the unit. Few owners claim it, so no claim proves little.
- **The county's mailing address** is where the tax bill goes. When it is not the property, the owner most likely lives
  elsewhere.
- **The latest deed** names who took title and when. A deed whose grantees share no name with PayHOA's owners means
  PayHOA's owners may be out of date (a sale, or a transfer to a trust under another name). A business entity as the
  grantee (an LLC, a corporation, a property trust) usually holds an investment.

Each is a lead for a person, not a finding: the owner's own answer on this year's form decides.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ENTITY = re.compile(r"\b(LLC|L\.?L\.?C\.?|INC\.?|INCORPORATED|CORP\.?|CORPORATION|COMPANY|LP|L\.P\.|LTD|PROPERTY TRUST|"
                    r"PROPERTIES|HOLDINGS|INVESTMENTS?|REALTY|BANK|N\.?A\.?|ASSOCIATION|PARTNERS(HIP)?|VENTURES|CAPITAL)\b")


@dataclass
class ParcelFacts:
    """One parcel's county facts, each with the date it describes. ``homeowner_exemption`` and ``county_mail`` are the
    facts as of their dates; ``current_exemption`` and ``current_county_mail`` are the same facts only when no deed has
    recorded since (otherwise they describe a former owner, and the reason is in ``stale``)."""

    apn: str
    unit: str
    homeowner_exemption: bool | None = None      # the roll's (or, without the roll, the latest annual bill's)
    exemption_as_of: date | None = None          # the lien date it describes (January 1 of its roll year)
    county_mail: str = ""                         # "property" or "elsewhere" (the secured roll); "" when not read
    roll_as_of: date | None = None               # the roll's lien date
    roll_deed: date | None = None                # the deed the roll knows (its recording date)
    latest_deed: date | None = None
    grantees: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)

    @property
    def entity(self) -> bool:
        return any(ENTITY.search(g.upper()) for g in self.grantees)

    def _roll_current(self) -> bool:
        """The roll describes the current owner: no deed recorded after its lien date, or it already knows that deed
        (the extract comes months after the lien date). A deed before the lien date that the roll does not name was no
        sale the county reappraised (a transfer to a trust, a correction), so it leaves the roll current."""
        if self.latest_deed is None or self.roll_as_of is None or self.latest_deed <= self.roll_as_of:
            return True
        return self.roll_deed is not None and self.roll_deed >= self.latest_deed

    @property
    def current_county_mail(self) -> str:
        return self.county_mail if self.county_mail and self._roll_current() else ""

    @property
    def current_exemption(self) -> bool | None:
        if self.homeowner_exemption is None or self.exemption_as_of is None:
            return self.homeowner_exemption
        if self.latest_deed is not None and self.latest_deed > self.exemption_as_of:
            return None
        return self.homeowner_exemption


def lien_date(published: date) -> date:
    """The lien date a secured roll describes: January 1 before the fiscal year it is published for (the roll comes out
    each July for the year that begins then)."""
    return date(published.year if published.month >= 7 else published.year - 1, 1, 1)


def _published(workbook: Path) -> date | None:
    """When the bulk workbook was made (its own document properties)."""
    import zipfile

    try:
        with zipfile.ZipFile(workbook) as book:
            core = book.read("docProps/core.xml").decode("utf-8", "replace")
    except (KeyError, OSError, zipfile.BadZipFile):
        return None
    found = re.search(r"<dcterms:created[^>]*>(\d{4}-\d{2}-\d{2})", core)
    return date.fromisoformat(found.group(1)) if found else None


def _digits(apn: str) -> str:
    return re.sub(r"\D", "", apn)


def read(data_dir: Path, *, roll: Path | None = None, parcels: Iterable[str] = ()) -> dict[str, ParcelFacts]:
    """Each unit's ``ParcelFacts``, by unit title (upper case). ``roll`` is the bulk secured workbook (read for
    ``parcels``, about half a minute); without it the county's mailing address is left unread."""
    from jason.tasks.parties import PartyResolver

    data_dir = Path(data_dir)
    apn_unit = PartyResolver._parcels(data_dir)                      # parcel digits to the unit's street address
    out = {unit: ParcelFacts(apn, unit) for apn, unit in apn_unit.items()}
    tax = data_dir / "tax.db"
    if tax.is_file():
        con = sqlite3.connect(f"file:{tax.as_posix()}?mode=ro", uri=True)
        try:                                    # annual bills only: a supplemental bill carries no exemption figure
            rows = con.execute("SELECT apn, year, homeowner_exemption_cents FROM bills WHERE year IS NOT NULL "
                               "AND homeowner_exemption_cents IS NOT NULL ORDER BY apn, year").fetchall()
        finally:
            con.close()
        for apn, year, ho in rows:
            facts = out.get(apn_unit.get(_digits(apn), ""))
            as_of = date(int(year), 1, 1)
            if facts is not None and (facts.exemption_as_of is None or as_of >= facts.exemption_as_of):
                facts.exemption_as_of, facts.homeowner_exemption = as_of, bool(ho)
    chain = data_dir / "ownership.db"
    if chain.is_file():
        con = sqlite3.connect(f"file:{chain.as_posix()}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT apn, recorded, grantees FROM chain WHERE recorded <> '' ORDER BY apn, recorded").fetchall()
        finally:
            con.close()
        for apn, recorded, grantees in rows:
            facts = out.get(apn_unit.get(_digits(apn), ""))
            if facts is None:
                continue
            try:
                when = date.fromisoformat(recorded[:10])
            except ValueError:
                continue
            if facts.latest_deed is None or when >= facts.latest_deed:
                facts.latest_deed = when
                facts.grantees = [g.strip() for g in (grantees or "").splitlines() if g.strip()]
    if roll is not None and Path(roll).is_file():
        from jason.community.secured import SecuredRoll

        published = _published(Path(roll))
        as_of = lien_date(published) if published else None
        for parcel in SecuredRoll(roll).filter(tuple(parcels)):
            facts = out.get(apn_unit.get(_digits(parcel.apn), ""))
            if facts is None:
                continue
            facts.county_mail = "property" if parcel.mails_to_situs else "elsewhere"
            facts.roll_as_of = as_of
            try:
                facts.roll_deed = date.fromisoformat(str(parcel.recording_date)[:10]) if parcel.recording_date else None
            except ValueError:
                facts.roll_deed = None
            if as_of is not None and (facts.exemption_as_of is None or as_of >= facts.exemption_as_of):
                facts.homeowner_exemption, facts.exemption_as_of = bool(parcel.homeowner_exemption_cents), as_of
    for facts in out.values():
        if facts.county_mail and not facts.current_county_mail:
            facts.stale.append(f"the county roll knows the deed of {facts.roll_deed or facts.roll_as_of}, not the "
                               f"{facts.latest_deed} one: its mailing address is the former owner's")
        if facts.homeowner_exemption is not None and facts.current_exemption is None:
            facts.stale.append(f"the exemption is as of {facts.exemption_as_of}, before the {facts.latest_deed} deed")
    return out


def names_match(owner_names: Iterable[str], grantees: Iterable[str]) -> bool | None:
    """Whether any PayHOA owner shares a family or given name (three letters or more) with the latest deed's grantees;
    None when the deed names no one."""
    from jason.tasks.parties import _tokens

    deed = set().union(*(set(_tokens(g)) for g in grantees)) if grantees else set()
    if not deed:
        return None
    return any(set(_tokens(n)) & deed for n in owner_names)


__all__ = ["ENTITY", "ParcelFacts", "lien_date", "names_match", "read"]
