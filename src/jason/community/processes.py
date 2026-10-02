"""Reconveyance processes. Each one names the filings that complete it.

A process is one way the fee moves. It is not a chain and it does not search.
The anchor is the instrument that transfers the fee, or the restatement that
does not. Companion filings sit on a known seat: the previous number, the
next number, the same day, or a document the anchor cites. A process is
complete when every required seat is filled. A missing seat names the filing
still to collect, and the date window that seat must fall in. It does not
name a lender, and it does not send the walk on to that lender's other parcels.

Date windows are relative to the anchor's recorded day. Same-day seats share
that calendar day (notice of completion, companion vesting, buyer lien,
partial reconveyance). Earlier seats were recorded on a prior day (the deed
of trust a trustee's deed cites, the builder lien a partial reconveyance
releases, the prior deed a resale cites). A follow-on search for the buyer's
later grant or foreclosure starts the day after the closing.

Each process says whether the assessor reassesses on it. A sale does. A
restatement, a re-recording of the same conveyance, and an excluded transfer
between family or affiliates do not, so the tax bills stay on the 2% track.
``jason.community.calendar`` reads the bills against those flags.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from jason.community.index_cache import _ROLE, keeps_developer, name_keeps, skip_lender
from jason.community.recorder import (
    FiledInstrument,
    closing_numbers,
    nearby_numbers,
    owner_restatement,
)

# A grant recorded again within this many days, with the same parties, is the
# same conveyance re-recorded to correct the first instrument.
TWIN_DAYS = 120

# Leading words that do not identify a family or a company.
_NOT_A_NAME = frozenset({"THE", "A", "AN", "OF", "AND", "&", "TRUSTEE", "TRUST"})

# Generational suffixes a lender's title company drops from the trustor.
_SUFFIX = frozenset({"JR", "SR", "II", "III", "IV"})

# How many same-day numbers before a developer grant the notice of completion can sit,
# when companion vestings of the buyer are recorded between them.
_NOTICE_REACH = 3


@dataclass(frozen=True)
class Slot:
    """One filing a process expects, and where that filing sits.

    ``timing`` is relative to the anchor's recorded date. ``same-day`` must
    share that calendar day. ``earlier`` must be recorded on a prior day.
    Empty timing means the seat geometry alone is enough.
    """

    role: str
    seat: str
    kinds: tuple[str, ...] = ()
    required: bool = True
    timing: str = ""


@dataclass(frozen=True)
class Finding:
    """Whether one expected filing was in hand.

    ``after`` and ``before`` are inclusive recorded-date bounds for a gap.
    A collector sends them as MinRecordedDate and MaxRecordedDate. They are
    empty when the seat has no date constraint or the anchor has no date.
    """

    role: str
    required: bool
    reason: str
    number: str = ""
    after: date | None = None
    before: date | None = None


@dataclass(frozen=True)
class Reading:
    """One process applied to an anchor and the instruments around it."""

    process: str
    continues: bool
    slots: tuple[Finding, ...]
    reassesses: bool = True

    @property
    def complete(self) -> bool:
        return all(item.reason == "present" for item in self.slots if item.required)

    @property
    def gaps(self) -> tuple[Finding, ...]:
        return tuple(item for item in self.slots if item.required and item.reason != "present")


class PurchaseMoney:
    """Mixin. A financed sale records the buyer's deed of trust.

    The trustor is the grantee of the fee deed. The deed of trust does not
    transfer the fee. A cash sale has no deed of trust, so the slot is not
    required except on a developer's first closing. When present, it is
    recorded the same day as the grant.
    """

    def lien_slot(self, *, required: bool = False) -> Slot:
        return Slot("buyer lien", "buyer lien", ("lien",), required, "same-day")


class CompanionVesting:
    """Mixin. The number beside a grant sometimes vests the same buyer again.

    That recording is a fee deed into the buyer, or the buyer's power of
    attorney. It does not replace the buyer, and its grantor is not the next
    leaf. The deed of trust is the number after that companion. A neighboring
    number that does not name the buyer is a different parcel and is not followed.
    It shares the grant's recording day.
    """

    def companion_slot(self) -> Slot:
        return Slot("companion vesting", "companion", ("fee",), False, "same-day")


class CitesPrior:
    """Mixin. The anchor is complete when it cites one earlier instrument.

    The cited kind is the prior this process continues. That prior was
    recorded on an earlier day than the anchor. A citation that is not
    loaded yet is collected by that document number inside the earlier
    window. An anchor that cites nothing does not become a search of the
    grantor's other deeds.
    """

    prior_role = "prior"
    prior_kinds: tuple[str, ...] = ()

    def prior_slot(self) -> Slot:
        return Slot(self.prior_role, "cites", self.prior_kinds, True, "earlier")


class DeveloperClosing(PurchaseMoney, CompanionVesting):
    """A builder's first sale of a unit.

    The previous number is the notice of completion, filing 306, or the
    nearest earlier number behind a run of the buyer's companion vestings.
    The anchor is the grant. The buyer's deed of trust, filing 230, names
    the grantee as trustor, often without a middle initial or a junior.
    When the next numbers are further deeds into that buyer, or that
    buyer's power of attorney, the deed of trust is the first number after
    that run. An order of sale does not fill the notice. A neighbor that does
    not name the buyer does not fill the lien. Notice, companion, and lien
    share the grant's recording day.
    """

    name = "developer closing"
    continues = True
    reassesses = True

    def slots(self) -> tuple[Slot, ...]:
        return (
            Slot("notice of completion", "previous", ("notice",), True, "same-day"),
            Slot("grant", "anchor", ("fee",), True),
            self.companion_slot(),
            self.lien_slot(required=True),
        )


class BlanketRelease(PurchaseMoney):
    """A later sale of a unit the builder still held under an earlier lien.

    The same day records a partial reconveyance, filing 613, often together
    with a substitution of trustee, filing 239. The reconveyance completes
    the release when it cites that earlier deed of trust. The released lien
    was recorded on a prior day, often when the builder took the unit. The
    buyer's own deed of trust is recorded the same day when the sale was
    financed and is absent when it was not.
    """

    name = "blanket release"
    continues = True
    reassesses = True

    def slots(self) -> tuple[Slot, ...]:
        return (
            Slot("grant", "anchor", ("fee",), True),
            Slot("partial reconveyance", "same day", ("release",), True, "same-day"),
            Slot("released lien", "release cites", ("lien",), True, "earlier"),
            self.lien_slot(required=False),
        )


class ForeclosureSale(CitesPrior):
    """The lien sale. The trustee's deed transfers the fee.

    Filing 695 is the trustee's deed upon sale. Filing 694 is a trustee's
    deed and filing 801 is a deed in lieu. The deed cites the deed of trust,
    which was recorded on an earlier day. The notice of default, filing 531,
    and the notice of trustee's sale, filing 543, cite that same deed and do
    not transfer the fee, so they are not required to complete the sale. The
    grantee, often the beneficiary, is not a name this process searches.
    """

    name = "foreclosure"
    continues = True
    reassesses = True
    prior_role = "deed of trust"
    prior_kinds = ("lien",)

    def slots(self) -> tuple[Slot, ...]:
        return (
            Slot("trustee's deed", "anchor", ("foreclosure",), True),
            self.prior_slot(),
        )


class ReoResale(PurchaseMoney, CitesPrior):
    """A grant by the buyer at the lien sale.

    The grant completes the resale when it cites the trustee's deed. That
    trustee's deed was recorded on an earlier day. A grant that cites nothing
    still belongs to this process: the missing document is a trustee's deed
    to this grantor, searched only by number when cited, never by walking the
    lender. A same-day deed of trust is present when the resale was financed.
    """

    name = "reo resale"
    continues = True
    reassesses = True
    prior_role = "trustee's deed"
    prior_kinds = ("foreclosure",)

    def slots(self) -> tuple[Slot, ...]:
        return (
            Slot("grant", "anchor", ("fee",), True),
            self.prior_slot(),
            self.lien_slot(required=False),
        )


class Resale(PurchaseMoney, CitesPrior):
    """A grant from one owner to the next.

    The prior deed is the instrument this grant cites. It was recorded on an
    earlier day. A grant that cites nothing leaves that seat empty. The empty
    seat is not a search of every earlier deed that names the grantor. A
    same-day deed of trust belongs to the sale when its trustor is the grantee.
    """

    name = "resale"
    continues = True
    reassesses = True
    prior_role = "prior deed"
    prior_kinds = ("fee", "foreclosure")

    def slots(self) -> tuple[Slot, ...]:
        return (
            Slot("grant", "anchor", ("fee",), True),
            self.prior_slot(),
            self.lien_slot(required=False),
        )


class ExcludedTransfer(CitesPrior):
    """A grant that changes the owner without a reassessment.

    A parent to a child, one spouse to the other, or an owner into a company
    or trust the same people hold, keeps the base value. In the index the two
    sides share a surname or a leading company word. That is a reading, not
    proof of the exclusion; the bill calendar is the proof. The process
    continues: the grantor's own deed is the prior, cited or not, and it is
    not a search of every deed that names the grantor.
    """

    name = "excluded transfer"
    continues = True
    reassesses = False
    prior_role = "prior deed"
    prior_kinds = ("fee", "foreclosure")

    def slots(self) -> tuple[Slot, ...]:
        return (
            Slot("grant", "anchor", ("fee",), True),
            self.prior_slot(),
        )


class Rerecording:
    """The same conveyance recorded a second time.

    A title company re-records a grant to correct a name, a legal
    description, or a missing page, usually within a few months. The earlier
    twin is the conveyance. This instrument moves nothing, lands on no bill,
    and is not a resale by the buyer to the buyer. The seat is an earlier fee
    deed with the same grantors and grantees recorded within ``TWIN_DAYS``.
    Without the twin in hand the anchor reads as its parties suggest.
    """

    name = "re-recording"
    continues = False
    reassesses = False

    def slots(self) -> tuple[Slot, ...]:
        return (
            Slot("re-recorded grant", "anchor", ("fee",), True),
            Slot("first recording", "earlier twin", ("fee",), True, "earlier"),
        )


class Restatement:
    """The same owner, usually into that owner's trust.

    The fee did not change hands. There is no companion filing and the
    process does not continue. It does not identify the deed that first
    vested the owner.
    """

    name = "restatement"
    continues = False
    reassesses = False

    def slots(self) -> tuple[Slot, ...]:
        return (Slot("restatement", "anchor", ("fee",), True),)


@dataclass(frozen=True)
class FollowOn:
    """One search the next process needs after this reading.

    ``party`` is sent as LastName. ``role`` is grantor or grantee. A lender
    is never a follow-on party. The filings are the kinds that transfer the
    fee for that next process, not every instrument that names the party.
    ``after`` is the day after the closing. ``before`` stays open unless a
    later known deed on the parcel closes the window.
    """

    party: str
    role: str
    filings: tuple[str, ...]
    after: date | None = None
    before: date | None = None
    reason: str = ""


def window(slot: Slot, anchor: FiledInstrument) -> tuple[date | None, date | None]:
    """Inclusive recorded-date bounds for ``slot`` relative to ``anchor``.

    Same-day seats use the anchor's day as both ends. Earlier seats end the
    day before the anchor. Later seats start the day after. Empty timing, or
    an undated anchor, returns no bounds.
    """
    recorded = anchor.recorded
    if recorded is None or not slot.timing:
        return (None, None)
    if slot.timing == "same-day":
        return (recorded, recorded)
    if slot.timing == "earlier":
        return (None, recorded - timedelta(days=1))
    if slot.timing == "later":
        return (recorded + timedelta(days=1), None)
    return (None, None)


def gather(
    load: Callable[[str], FiledInstrument | None],
    anchor: FiledInstrument,
    *,
    before: int = _NOTICE_REACH,
    after: int = 4,
) -> tuple[FiledInstrument, ...]:
    """Load the numbers a process reading needs around this anchor.

    Same-day neighbors cover the notice of completion, a companion vesting
    run, the buyer's deed of trust, and a same-day partial reconveyance.
    Citations on the anchor and on those neighbors are loaded next. This
    does not search a party name and does not walk a lender.
    """
    wanted: list[str] = list(nearby_numbers(anchor.number, before=before, after=after))
    wanted.extend(number for number in anchor.cross_references if number)
    found: list[FiledInstrument] = []
    seen = {anchor.number}
    index = 0
    while index < len(wanted):
        number = wanted[index]
        index += 1
        if not number or number in seen:
            continue
        seen.add(number)
        item = load(number)
        if item is None:
            continue
        found.append(item)
        for cited in item.cross_references:
            if cited and cited not in seen:
                wanted.append(cited)
    return tuple(found)


def follow_on(
    reading: Reading,
    anchor: FiledInstrument,
    *,
    until: date | None = None,
) -> tuple[FollowOn, ...]:
    """The party searches that complete the next process after this reading.

    A complete developer closing or blanket release looks for the buyer's
    later grant or trustee's deed, starting the day after the closing.
    ``until`` is an inclusive end date when a later known deed on the parcel
    closes the window. A complete foreclosure does not search the lender who
    bought at the sale. An incomplete REO resale does not invent a
    foreclosed owner. An incomplete resale does not fan out into every
    earlier deed that names the grantor. A restatement does not continue.
    """
    if not reading.continues:
        return ()
    if reading.process in ("developer closing", "blanket release") and reading.complete:
        opened = _day_after(anchor.recorded)
        found: list[FollowOn] = []
        for party in anchor.grantees:
            if not party.strip() or skip_lender(party):
                continue
            found.append(
                FollowOn(
                    party,
                    "grantor",
                    ("685", "689", "695", "694", "801"),
                    after=opened,
                    before=until,
                    reason="buyer leaves",
                )
            )
        return tuple(found)
    if reading.process == "foreclosure" and reading.complete:
        return ()
    if reading.process == "reo resale" and not reading.complete:
        return ()
    if reading.process == "resale" and not reading.complete:
        return ()
    return ()


def _day_after(value: date | None) -> date | None:
    if value is None:
        return None
    return value + timedelta(days=1)


def read(
    anchor: FiledInstrument,
    around: tuple[FiledInstrument, ...] = (),
    developers: tuple = (),
) -> tuple[Reading, ...]:
    """The processes this anchor can be, given the instruments already in hand.

    A notice of completion on the previous number is a developer closing. A
    same-day partial reconveyance is a blanket release. A developer grant
    with neither evidence is read both ways, and each reading names the
    filing it still needs. A fee deed that restates the same owner is only
    a restatement. A fee deed whose earlier twin is in hand is only a
    re-recording. A lender grantor is only an REO resale. A grant between
    people who share a surname, or companies that share a leading word, is
    an excluded transfer.
    """
    if anchor.kind == "fee" and owner_restatement(anchor.grantors, anchor.grantees):
        return (assess(Restatement(), anchor, around),)
    if anchor.kind == "foreclosure":
        return (assess(ForeclosureSale(), anchor, around),)
    if anchor.kind == "fee" and earlier_twin(anchor, around) is not None:
        return (assess(Rerecording(), anchor, around),)
    if any(keeps_developer(name, developers) for name in anchor.grantors):
        return _builder(anchor, around)
    if any(skip_lender(name) for name in anchor.grantors if name.strip()):
        return (assess(ReoResale(), anchor, around),)
    if anchor.kind == "fee" and family_transfer(anchor.grantors, anchor.grantees):
        return (assess(ExcludedTransfer(), anchor, around),)
    if anchor.kind == "fee":
        return (assess(Resale(), anchor, around),)
    return ()


def assess(process, anchor: FiledInstrument, around: tuple[FiledInstrument, ...]) -> Reading:
    """Fill each slot of ``process`` from ``anchor`` and ``around``."""
    found = tuple(_finding(slot, anchor, around) for slot in process.slots())
    return Reading(process.name, process.continues, found, process.reassesses)


def same_parties(left: FiledInstrument, right: FiledInstrument) -> bool:
    """True when both instruments vest the same grantees from the same grantor.

    Every grantee on one side has to keep a grantee on the other, in both
    directions, so an added spouse or a dropped junior is a different set.
    The grantors only have to share one name: a re-recording sometimes adds
    the builder's parent company beside the builder.
    """
    if not _covers(left.grantees, right.grantees):
        return False
    return any(
        name_keeps(a, b) for a in left.grantors if a.strip() for b in right.grantors if b.strip()
    )


def earlier_twin(anchor: FiledInstrument, around: tuple[FiledInstrument, ...]) -> FiledInstrument | None:
    """The earlier fee deed this anchor re-records, when it is in ``around``.

    The twin has the same parties and was recorded before the anchor, within
    ``TWIN_DAYS``. The nearest earlier one wins. A twin recorded the same
    day is a companion vesting, not a re-recording, and is left out.
    """
    if anchor.recorded is None:
        return None
    found: FiledInstrument | None = None
    for item in around:
        if item.number == anchor.number or item.kind != "fee" or item.recorded is None:
            continue
        gap = (anchor.recorded - item.recorded).days
        if gap < 1 or gap > TWIN_DAYS or not same_parties(anchor, item):
            continue
        if found is None or item.recorded > (found.recorded or item.recorded):
            found = item
    return found


def twins(items: tuple[FiledInstrument, ...]) -> tuple[tuple[FiledInstrument, FiledInstrument], ...]:
    """Every ``(first, re-recording)`` pair among ``items``.

    The first recording is the conveyance. The store keeps that number; the
    re-recording is noted and not walked.
    """
    fees = tuple(item for item in items if item.kind == "fee" and item.recorded is not None)
    found: list[tuple[FiledInstrument, FiledInstrument]] = []
    for later in fees:
        first = earlier_twin(later, fees)
        if first is not None:
            found.append((first, later))
    return tuple(found)


def family_transfer(grantors: tuple[str, ...], grantees: tuple[str, ...]) -> bool:
    """True when a grantor and a grantee share a leading name and the owner changed.

    The leading word of an indexed person is the surname, and of a company
    its first word. A shared one on both sides reads as family or affiliates.
    A restatement into the same owner is not this; ``owner_restatement``
    comes first.
    """
    if owner_restatement(grantors, grantees):
        return False
    left = {_leading(name) for name in grantors} - {""}
    right = {_leading(name) for name in grantees} - {""}
    return bool(left & right)


# A family transfer this many days from a chain step, sharing a party with it, is part of that closing.
COMPANION_DAYS = 3
RERECORDING = "re-recording"
COMPANION = "companion transfer"
SAME_DAY_TWIN = "same-day deed, same parties"


def beside_step(
    item: FiledInstrument, step_number: str, step_doc: FiledInstrument | None, step_grantees: tuple[str, ...],
) -> tuple[str, str] | None:
    """How a conveyance sits beside a chain step, as (role, why), or None.

    A re-recording cites the step, or vests the same parties from the same
    grantor on a later day within ``TWIN_DAYS``; the same parties the same
    day is a ``SAME_DAY_TWIN``, which the index cannot tell from a second
    unit bought at one closing. A companion transfer is a family transfer
    within ``COMPANION_DAYS`` that shares a party with the step's grantees,
    such as a spouse's quitclaim at the closing. Anything else is not beside
    the step. ``step_doc`` is the step's own index row when it is cached.
    """
    from jason.community.filings import Family, instrument_class, same_party

    if item.number == step_number:
        return None
    if instrument_class(item.filing_code, item.filing_name, item.kind).family is not Family.CONVEYANCE:
        return None
    if step_number in item.cross_references:
        return RERECORDING, f"cites chain step {step_number}"
    if step_doc is None or item.recorded is None or step_doc.recorded is None:
        return None
    gap = abs((item.recorded - step_doc.recorded).days)
    if gap == 0 and same_parties(item, step_doc):
        # A buyer who takes two units at one closing records two deeds with the same parties the same day.
        return SAME_DAY_TWIN, f"same parties as chain step {step_number} the same day: another parcel the buyer took, or a duplicate; read the copy"
    if gap <= TWIN_DAYS and same_parties(item, step_doc):
        return RERECORDING, f"same parties as chain step {step_number}, {gap} days apart"
    shares = any(same_party(a, b) for a in (*item.grantors, *item.grantees) for b in step_grantees)
    if gap <= COMPANION_DAYS and shares and family_transfer(item.grantors, item.grantees):
        return COMPANION, f"family transfer {gap} days from chain step {step_number}"
    return None


def _leading(name: str) -> str:
    for token in " ".join(name.upper().split()).split():
        if token in _NOT_A_NAME or token in _ROLE or len(token) < 2:
            continue
        return token
    return ""


def _covers(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    one = [name for name in left if name.strip()]
    two = [name for name in right if name.strip()]
    if not one or not two:
        return False
    return all(any(name_keeps(a, b) for b in two) for a in one) and all(
        any(name_keeps(b, a) for a in one) for b in two
    )


def _builder(anchor: FiledInstrument, around: tuple[FiledInstrument, ...]) -> tuple[Reading, ...]:
    earlier, _later = closing_numbers(anchor.number)
    previous = _by_number(around).get(earlier)
    notice = previous is not None and previous.kind == "notice"
    release = any(_related_release(anchor, item) for item in around)
    if notice and not release:
        return (assess(DeveloperClosing(), anchor, around),)
    if release and not notice:
        return (assess(BlanketRelease(), anchor, around),)
    return (
        assess(DeveloperClosing(), anchor, around),
        assess(BlanketRelease(), anchor, around),
    )


def _finding(slot: Slot, anchor: FiledInstrument, around: tuple[FiledInstrument, ...]) -> Finding:
    after, before = window(slot, anchor)
    if slot.seat == "anchor":
        if anchor.kind in slot.kinds:
            return Finding(slot.role, slot.required, "present", anchor.number, after, before)
        return Finding(slot.role, slot.required, "missing", anchor.number, after, before)
    if slot.seat == "previous":
        return _previous(slot, anchor, around, after, before)
    if slot.seat == "companion":
        return _companion_finding(slot, anchor, around, after, before)
    if slot.seat == "buyer lien":
        return _buyer_lien(slot, anchor, around, after, before)
    if slot.seat == "same day":
        return _same_day_slot(slot, anchor, around, after, before)
    if slot.seat == "cites":
        return _cited(slot, anchor, around, after, before)
    if slot.seat == "release cites":
        return _released(slot, anchor, around, after, before)
    if slot.seat == "earlier twin":
        twin = earlier_twin(anchor, around)
        if twin is None:
            return Finding(slot.role, slot.required, "missing", "", after, before)
        return _dated(slot, twin, "present", after, before)
    return Finding(slot.role, slot.required, "missing", "", after, before)


def _previous(
    slot: Slot,
    anchor: FiledInstrument,
    around: tuple[FiledInstrument, ...],
    after: date | None,
    before: date | None,
) -> Finding:
    """The notice is the previous number, or the first number behind the buyer's companion run."""
    by_number = _by_number(around)
    earlier, _later = closing_numbers(anchor.number)
    candidates = nearby_numbers(anchor.number, before=_NOTICE_REACH, after=0)
    for number in candidates:
        item = by_number.get(number)
        if _companion(anchor, item):
            continue
        return _placed(slot, item, number, after, before)
    return _placed(slot, by_number.get(earlier), earlier, after, before)


def _companion_finding(
    slot: Slot,
    anchor: FiledInstrument,
    around: tuple[FiledInstrument, ...],
    after: date | None,
    before: date | None,
) -> Finding:
    earlier, later = closing_numbers(anchor.number)
    by_number = _by_number(around)
    for number in (earlier, later):
        item = by_number.get(number)
        if _companion(anchor, item):
            return _dated(slot, item, "present", after, before)
    return Finding(slot.role, slot.required, "missing", "", after, before)


def _buyer_lien(
    slot: Slot,
    anchor: FiledInstrument,
    around: tuple[FiledInstrument, ...],
    after: date | None,
    before: date | None,
) -> Finding:
    for item in around:
        if _same_day(anchor, item) and item.kind == "lien" and _trusts(anchor, item):
            return _dated(slot, item, "present", after, before)
    by_number = _by_number(around)
    _earlier, later = closing_numbers(anchor.number)
    nxt = by_number.get(later)
    if _companion(anchor, nxt):
        return _after_companions(slot, anchor, nxt, by_number, after, before)
    if nxt is not None and nxt.kind == "lien":
        return Finding(slot.role, slot.required, "other parties", nxt.number, after, before)
    if nxt is not None:
        return Finding(slot.role, slot.required, "other", nxt.number, after, before)
    return Finding(slot.role, slot.required, "missing", later, after, before)


def _after_companions(
    slot: Slot,
    anchor: FiledInstrument,
    companion: FiledInstrument,
    by_number: dict[str, FiledInstrument],
    after: date | None,
    before: date | None,
) -> Finding:
    """The buyer's lien is the first number after a run of companion vestings."""
    seen = {anchor.number}
    current = companion
    while _companion(anchor, current) and current.number not in seen:
        seen.add(current.number)
        following = _step(current.number)
        held = by_number.get(following)
        if held is None:
            return Finding(slot.role, slot.required, "missing", following, after, before)
        current = held
    if current.kind == "lien" and _trusts(anchor, current):
        return _dated(slot, current, "present", after, before)
    return Finding(slot.role, slot.required, "other", current.number, after, before)


def _companion(anchor: FiledInstrument, item: FiledInstrument | None) -> bool:
    """True when this neighbor vests the buyer again, or is the buyer's power of attorney."""
    if item is None or not _same_day(anchor, item):
        return False
    if item.kind == "fee" and any(_buyer_is(anchor, name) for name in item.grantees):
        return True
    parties = (*item.grantors, *item.grantees)
    return item.filing_code == "466" and any(_buyer_is(anchor, name) for name in parties)


def _trusts(anchor: FiledInstrument, item: FiledInstrument) -> bool:
    return any(_buyer_is(anchor, name) for name in item.grantors)


def _buyer_is(anchor: FiledInstrument, name: str) -> bool:
    """True when ``name`` is one of the grantees, or that grantee with an initial or a suffix dropped.

    The lender's title company indexes the trustor from the loan file, which
    often leaves off a middle initial or a junior. On the same day and the
    next number that is still the buyer. A different given name is not.
    """
    return any(name_keeps(buyer, name) or _shortened(buyer, name) for buyer in anchor.grantees)


def _shortened(buyer: str, name: str) -> bool:
    full = [token for token in buyer.upper().split() if token not in _ROLE]
    short = [token for token in name.upper().split() if token not in _ROLE]
    if len(short) < 2 or len(short) > len(full):
        return False
    kept = [token for token in full if token not in _SUFFIX and len(token) > 1]
    trimmed = [token for token in short if token not in _SUFFIX]
    if len(trimmed) < 2:
        return False
    # Surname and given name must match; what the short form keeps must be in the full form.
    return trimmed[0] == kept[0] and trimmed[1] == kept[1] and all(token in full for token in trimmed)


def _step(number: str) -> str:
    later = nearby_numbers(number, before=0, after=1)
    return later[0] if later else ""


def _same_day_slot(
    slot: Slot,
    anchor: FiledInstrument,
    around: tuple[FiledInstrument, ...],
    after: date | None,
    before: date | None,
) -> Finding:
    matches = [item for item in around if _same_day(anchor, item) and item.kind in slot.kinds]
    if "release" in slot.kinds:
        matches = [item for item in matches if _related_release(anchor, item)]
    if matches:
        return _dated(slot, matches[0], "present", after, before)
    _earlier, later = closing_numbers(anchor.number)
    other = _by_number(around).get(later)
    if other is not None and other.kind not in slot.kinds:
        return Finding(slot.role, slot.required, "other", other.number, after, before)
    return Finding(slot.role, slot.required, "missing", later, after, before)


def _cited(
    slot: Slot,
    anchor: FiledInstrument,
    around: tuple[FiledInstrument, ...],
    after: date | None,
    before: date | None,
) -> Finding:
    if not anchor.cross_references:
        return Finding(slot.role, slot.required, "missing", "", after, before)
    by_number = _by_number(around)
    for number in anchor.cross_references:
        item = by_number.get(number)
        if item is not None and item.kind in slot.kinds:
            return _dated(slot, item, "present", after, before)
    pending = [number for number in anchor.cross_references if number not in by_number]
    if pending:
        return Finding(slot.role, slot.required, "unloaded", pending[0], after, before)
    return Finding(slot.role, slot.required, "other", anchor.cross_references[0], after, before)


def _released(
    slot: Slot,
    anchor: FiledInstrument,
    around: tuple[FiledInstrument, ...],
    after: date | None,
    before: date | None,
) -> Finding:
    releases = [item for item in around if _related_release(anchor, item)]
    if not releases:
        return Finding(slot.role, slot.required, "missing", "", after, before)
    by_number = _by_number(around)
    for release in releases:
        for number in release.cross_references:
            item = by_number.get(number)
            if item is not None and item.kind in slot.kinds:
                return _dated(slot, item, "present", after, before)
        pending = [number for number in release.cross_references if number not in by_number]
        if pending:
            return Finding(slot.role, slot.required, "unloaded", pending[0], after, before)
    return Finding(slot.role, slot.required, "missing", releases[0].number, after, before)


def _placed(
    slot: Slot,
    item: FiledInstrument | None,
    number: str,
    after: date | None,
    before: date | None,
) -> Finding:
    if item is None:
        return Finding(slot.role, slot.required, "missing", number, after, before)
    if item.kind in slot.kinds:
        return _dated(slot, item, "present", after, before)
    return Finding(slot.role, slot.required, "other", item.number, after, before)


def _dated(
    slot: Slot,
    item: FiledInstrument,
    reason: str,
    after: date | None,
    before: date | None,
) -> Finding:
    """Keep a present hit only when its recorded date sits in the slot window."""
    if reason == "present" and not _in_window(item.recorded, after, before):
        return Finding(slot.role, slot.required, "wrong date", item.number, after, before)
    return Finding(slot.role, slot.required, reason, item.number, after, before)


def _in_window(recorded: date | None, after: date | None, before: date | None) -> bool:
    """True when ``recorded`` is missing or falls in the inclusive bounds."""
    if recorded is None:
        return True
    if after is not None and recorded < after:
        return False
    if before is not None and recorded > before:
        return False
    return True


def _related_release(anchor: FiledInstrument, item: FiledInstrument) -> bool:
    """True when a same-day reconveyance names the builder or the buyer."""
    if not _same_day(anchor, item) or item.kind != "release":
        return False
    owners = (*anchor.grantors, *anchor.grantees)
    return any(name_keeps(owner, party) for owner in owners for party in (*item.grantors, *item.grantees))


def _same_day(anchor: FiledInstrument, item: FiledInstrument) -> bool:
    return item.number != anchor.number and item.number[:8] == anchor.number[:8]


def _by_number(around: tuple[FiledInstrument, ...]) -> dict[str, FiledInstrument]:
    return {item.number: item for item in around}
