"""The association's own record in the public index, and each parcel's liens.

Two readings of the same cache. The first is the association's: the
governing instruments recorded for the project, tied to the 2792.23
deliveries; the assessment liens the association placed on owners and how
each ended; the liens and notices recorded against the association itself,
such as the city's utility liens on the common-area accounts and the tax
collector's notice of power to sell; and the notices the association filed,
such as a request for notice of default. The second is a parcel's: every
lifecycle that names one of its owners, marked by whether it opened while
that owner held this unit, since a lien indexes a person and not a parcel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from jason.community.filings import (
    Encumbrance,
    Family,
    NameMatch,
    Process,
    encumbrances,
    instrument_class,
    name_match,
    naming,
    same_party,
)
from jason.community.governing import DeliveryStatus, GoverningRecord, Supersession, apply_supersessions, delivery_status, locate_governing
from jason.community.index_cache import skip_lender
from jason.community.recorder import FiledInstrument, developer_for


@dataclass(frozen=True)
class RecordedAssociation:
    """What the index holds about the association."""

    governing: tuple[GoverningRecord, ...]
    deliveries: tuple[DeliveryStatus, ...]
    placed: tuple[Encumbrance, ...]
    against: tuple[Encumbrance, ...]
    notices: tuple[FiledInstrument, ...]
    unplaced: tuple[GoverningRecord, ...]
    construction: tuple[Encumbrance, ...] = ()
    """Mechanic's liens recorded against a developer: the construction period's claims and how each ended."""


@dataclass(frozen=True)
class ParcelLien:
    """One lifecycle naming an owner of a parcel, and whether it belongs to their time here."""

    owner: str
    encumbrance: Encumbrance
    during_tenure: bool
    community: bool
    name_match: NameMatch = NameMatch.FULL
    corroborated: bool = False

    @property
    def namesake_risk(self) -> bool:
        """The filing names the owner by surname and given name only, so it may be someone else's.

        The association's own liens, and a filing whose claimant ties it to
        this community (the solar program's lessor), are never a namesake.
        """
        return self.name_match is NameMatch.BARE and not self.community and not self.corroborated

    @property
    def where(self) -> str:
        if self.community:
            return "this community"
        if self.encumbrance.process is Process.ASSESSMENT_LIEN:
            # Another association's assessment lien is on a unit in that community, never on this one.
            return "another time or property"
        return "while owning here" if self.during_tenure else "another time or property"


def recorded_association(
    items: tuple[FiledInstrument, ...] | list[FiledInstrument],
    *,
    project: str,
    association: str,
    developers: tuple,
    reports: tuple = (),
    plan_numbers: tuple[str, ...] = (),
    supersessions: tuple[Supersession, ...] = (),
) -> RecordedAssociation:
    """Read every cached instrument that names the project, a phase, or the association.

    ``reports`` give the annexation date of each phase, which is how a
    developer's declaration of annexation with no phase in its name is
    placed. ``plan_numbers`` are condominium plans pinned on Drive.
    ``supersessions`` are the instruments a later one rescinded, which the
    index does not cross-reference and the specification pins.
    """
    project_word = project.upper()
    assn = association.upper()
    annexation_dates = {report.annexation: report.phase for report in reports if getattr(report, "annexation", None)}
    original = min((report.first_conveyance for report in reports), default=None)
    ours: list[FiledInstrument] = []
    developer_governing: list[FiledInstrument] = []
    for item in items:
        parties = (*item.grantors, *item.grantees)
        klass = instrument_class(item.filing_code, item.filing_name)
        if any(_leads(party, project_word) for party in parties) or item.number in plan_numbers:
            ours.append(item)
        elif klass.family in (Family.GOVERNING, Family.PLAN, Family.MAP) and any(
            developer_for(name, developers) for name in parties
        ):
            # A party that is neither a developer nor the project is another project's name.
            if all(developer_for(name, developers) or _leads(name, project_word) for name in parties):
                developer_governing.append(item)
    cited_by_ours = {number for item in ours for number in item.cross_references}
    placed_by_date: list[FiledInstrument] = []
    unplaced: list[FiledInstrument] = []
    for item in developer_governing:
        if item.recorded in annexation_dates or item.number in cited_by_ours or item.number in plan_numbers:
            placed_by_date.append(item)
        elif original and item.recorded and item.recorded >= original:
            unplaced.append(item)
    governing = list(locate_governing(tuple(ours) + tuple(placed_by_date), developers=developers))
    governing.extend(_common_area_deeds(ours, assn, developers))
    governing = [_with_phase(record, annexation_dates) for record in governing]
    governing.sort(key=lambda record: (record.recorded or date.min, record.number))
    unplaced_records = tuple(locate_governing(tuple(unplaced), developers=developers))
    if supersessions:
        governing_placed, unplaced_records = apply_supersessions(tuple(governing), unplaced_records, supersessions)
        governing = list(governing_placed)
    phases = tuple(sorted({report.phase for report in reports}))
    annexed = tuple(sorted({report.phase for report in reports if getattr(report, "annexation", None)}))
    deliveries = delivery_status(tuple(governing), phases=phases, annexed_phases=annexed)
    lifecycles = encumbrances(ours, association=association)
    placed = tuple(item for item in lifecycles if _names(item.claimant, assn) and not _names(item.debtor, assn))
    against = tuple(item for item in lifecycles if _names(item.debtor, assn))
    mechanics = [
        item for item in items
        if instrument_class(item.filing_code, item.filing_name).process is Process.MECHANICS_LIEN
        or item.filing_code in ("385", "223", "651", "291", "269", "624")
    ]
    construction = tuple(
        item for item in encumbrances(tuple(dict.fromkeys(mechanics + ours)), association=association)
        if item.process is Process.MECHANICS_LIEN
        and any(developer_for(name, developers) or _leads(name, project_word) for name in item.debtor)
    )
    notices = tuple(
        item for item in ours
        if instrument_class(item.filing_code, item.filing_name).family is Family.NOTICE
        and assn in " ".join((*item.grantors, *item.grantees)).upper()
        and item.filing_code != "306"
    )
    return RecordedAssociation(
        tuple(governing),
        deliveries,
        placed,
        against,
        notices,
        unplaced_records,
        construction,
    )


def parcel_liens(
    load_naming,
    steps: tuple,
    *,
    association: str,
    developers: tuple,
    corroborates=None,
) -> tuple[ParcelLien, ...]:
    """Every lifecycle naming an owner on ``steps``, marked by tenure.

    ``corroborates(encumbrance)`` says a claimant ties the filing to this
    community on its own, such as the solar program's lessor, so a bare
    name on it is not a namesake risk.

    ``load_naming(party)`` returns the cached instruments naming a party.
    ``steps`` are the parcel's chain steps oldest first, each with
    ``recorded`` and ``grantees``. A developer, a lender, or the association
    is not an owner here. A lifecycle is kept once, under the first owner
    it names.
    """
    assn = association.upper()
    owners: list[tuple[str, date | None, date | None]] = []
    plain = [getattr(step, "conveyance", step) for step in steps]
    for index, step in enumerate(plain):
        until = plain[index + 1].recorded if index + 1 < len(plain) else None
        for name in step.grantees:
            # An empty association name is contained in every name; it excludes no one.
            if not name.strip() or skip_lender(name) or developer_for(name, developers) or (assn and assn in name.upper()):
                continue
            owners.append((name, step.recorded, until))
    found: list[ParcelLien] = []
    seen: set[str] = set()
    for name, start, until in owners:
        items = load_naming(name)
        for lifecycle in encumbrances(items, association=association):
            if not any(same_party(name, party) for party in lifecycle.debtor):
                continue
            opened = lifecycle.opened.number
            if opened in seen:
                continue
            seen.add(opened)
            # An owner can hold several steps (a re-vesting, an added co-owner); any of their tenures counts.
            owner, during = _tenure_of(lifecycle.opened.recorded, lifecycle.debtor, owners, fallback=name)
            # An assessment lien is ours when it names us, or names no other association (a trustee or
            # collection agent filing for us). Another association's lien is on a unit in that community.
            community = _names(lifecycle.claimant, assn) or (
                lifecycle.process is Process.ASSESSMENT_LIEN and not _another_association(lifecycle.claimant, assn)
            )
            grades = [m for m in (name_match(owner, party) for party in lifecycle.debtor) if m is not None]
            # The closest spelling on the filing decides: any full name beats a bare one.
            match = min(grades, key=lambda m: list(NameMatch).index(m)) if grades else NameMatch.FULL
            tied = bool(corroborates and corroborates(lifecycle))
            found.append(ParcelLien(owner, lifecycle, during, community, match, tied))
    found.sort(key=lambda item: (item.encumbrance.opened.recorded or date.min, item.encumbrance.opened.number))
    return tuple(found)


_ASSOCIATION_WORDS = ("ASSOCIATION", "ASSN", "HOMEOWNERS", "HOA", "OWNERS ASS")


def _another_association(parties: tuple[str, ...], assn: str) -> bool:
    """A party named like a community association that is not this one, such as RANCH COMMUNITY ASSOCIATION."""
    for party in parties:
        folded = " ".join(party.upper().split())
        if assn and assn in folded:
            continue
        if any(word in folded.split() or word in folded for word in _ASSOCIATION_WORDS):
            return True
    return False


def _tenure_of(when: date | None, parties: tuple[str, ...], owners, *, fallback: str) -> tuple[str, bool]:
    """The owner among ``parties`` whose tenure holds ``when``, and whether one does.

    ``owners`` is (name, start, until) per chain step. The same person on two
    steps has two spans; a date inside either is during their ownership.
    """
    for name, start, until in owners:
        if not any(same_party(name, party) for party in parties):
            continue
        if when is not None and start is not None and when >= start and (until is None or when <= until):
            return name, True
    return fallback, False


def _common_area_deeds(ours, assn: str, developers: tuple) -> list[GoverningRecord]:
    """Grant deeds into the association: the common-area conveyances 2792.23 asks for."""
    from jason.community.symbols import DeveloperDelivery

    found: list[GoverningRecord] = []
    for item in ours:
        klass = instrument_class(item.filing_code, item.filing_name)
        if klass.family is not Family.CONVEYANCE or not _names(item.grantees, assn):
            continue
        developer = ""
        for party in item.grantors:
            match = developer_for(party, developers)
            if match is not None:
                developer = match.name
                break
        found.append(
            GoverningRecord(
                item.number, item.recorded, f"{klass.code} {klass.name}".strip(), "common area deed",
                DeveloperDelivery.COMMON_AREA_DEED, tuple(dict.fromkeys((*item.grantors, *item.grantees))),
                None, item.cross_references, developer,
            )
        )
    return found


def _with_phase(record: GoverningRecord, annexation_dates: dict) -> GoverningRecord:
    if record.phase is not None or record.recorded not in annexation_dates:
        return record
    if record.role not in ("annexation", "restatement or amendment"):
        return record
    return GoverningRecord(
        record.number, record.recorded, record.filing, "annexation", record.delivery,
        record.parties, annexation_dates[record.recorded], record.cites, record.developer,
    )


def _names(parties: tuple[str, ...], word: str) -> bool:
    return any(word in party.upper() for party in parties)


def _leads(party: str, word: str) -> bool:
    """True when the index name starts with the project word: MYSTIQUE, MYSTIQUE PHASE 3, MYSTIQUE COMMUNITY ASSN.

    A developer whose name merely contains the word, such as WATT COMMUNITIES
    AT MYSTIQUE, does not lead with it.
    """
    upper = " ".join(party.upper().split())
    return upper == word or upper.startswith(word + " ")


_WEEK = date.resolution * 7
