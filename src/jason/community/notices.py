"""The notices the law requires, as rules: who receives each and how, when, what it says, and what proves it was given.

Two kinds of record live here.

A ``NoticeRule`` is the association's delivery rule for a notice it sends: whether it goes by individual delivery
(Civil Code 4040: each owner's election, or first-class mail without one) or as a general notice (4045: posted where the
annual policy statement says, and individually to any member who asked for general notices that way), whether the
secondary addresses get a copy (4040(b): the annual budget report and policy statement, and the assessment collection
notices), and its reach: every owner, or the owners of the units carrying a unit tag (a building's flood policy).

A ``NoticeRequirement`` is what the statute requires of one kind of notice, read from the section's text: its
recipients, its methods, its clock (``Timing``: an offset before or after an anchoring event), its content, and the
evidence that proves it was given. The general rows are ``jason.community.notice_catalog.REQUIREMENTS``; each has a
stable key ("board-meeting", "discipline-hearing") that a ``NoticeRule``, a ledger key, or another session's duty
finding links to. A ``NoticeProvision`` is a governing document's own clause about a notice: it adds to the statute
(a longer period, another method, more content), matches it, departs from it (a lead for the conflict register), or is
a notice the statute does not require at all. A document can require more than the statute; it cannot require less
(Civil Code 4205), so ``combined`` applies the stricter clock of the two.

PayHOA's own filters select anyone carrying any of the chosen tags; they cannot say "owners with no election", who are
the ones the law sends first-class mail. So jason resolves a rule to the exact recipients (``tasks.notice_delivery``)
and the sending tools take the ids; and ``audit`` keeps the tags whole, so a person using PayHOA's filters alone selects
the same people: every owner carries a delivery tag, mail until they elect otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from enum import Enum
from typing import Iterable


class NoticeKind(Enum):
    INDIVIDUAL = "individual delivery (4040)"
    GENERAL = "general notice (4045)"


@dataclass(frozen=True)
class NoticeRule:
    key: str
    title: str
    authority: str
    kind: NoticeKind
    secondary_copies: bool = False        # 4040(b): a copy to each secondary address on file
    reach: str = "all owners"             # or "unit tag", narrowed to the units carrying a tag given at send time
    note: str = ""
    courtesy_email: bool = False          # also email every owner with a deliverable address, beside the law's delivery
    unconfirmed_copies: bool = False      # copies also reach secondary records tagged unconfirmed (an address not yet the owner's word)
    requirements: tuple[str, ...] = ()    # the catalog's requirement keys this rule delivers; empty: its own key


# What a notice requirement says, as symbols.


class Method(Enum):
    """How a notice may be delivered. A requirement lists the methods any one of which satisfies it."""

    INDIVIDUAL = "individual delivery (4040): the member's 4041 choice, else first-class mail to the address on the books"
    GENERAL = "general delivery (4045): any 4040 method, a billing statement or newsletter, or the designated posting"
    POSTING = "posted at the location the annual policy statement designates (4045(a)(3))"
    WEBSITE = "posted on the website the annual policy statement designates (4045(a)(5))"
    FIRST_CLASS_MAIL = "first-class mail"
    CERTIFIED_MAIL = "certified mail"
    REGISTERED_OR_CERTIFIED = "registered or certified mail"
    PERSONAL_DELIVERY = "personal delivery"
    PERSONAL_SERVICE = "personal service, in the manner of a summons (CCP 415.10)"
    ELECTRONIC = "electronic transmission to the address or system the member designated"
    WRITTEN = "in writing; the section names no method"
    MADE_AVAILABLE = "made available to members (copies on request)"
    RECORDED = "recorded with the county recorder"
    POSTED_AT_SITE = "posted in a conspicuous place where the work or event is"


class Recipients(Enum):
    ALL_MEMBERS = "every member"
    MEMBER = "the member concerned"
    OWNER_OF_RECORD = "the owner of record"
    RECORD_OWNERS = "every person shown as an owner in the association's records"
    OWNER_OR_REPRESENTATIVE = "the owner, or the legal representative the owner designated"
    OCCUPANTS_AND_OWNER = "the occupants, and the owner when not an occupant"
    OWNER_AND_TENANT = "the owner and any tenant of the unit (and of an adjacent unit the work could affect)"
    NOMINATOR_AND_NOMINEE = "the member who nominated, and the nominee"
    APPLICANT = "the applicant"
    REQUESTER = "the member or person who asked"
    BUILDING_OWNERS = "the owners of the units in the building"
    PARTIES = "every other party to the dispute"
    BOARD = "the board"
    MORTGAGEES = "the mortgagees who asked for notice"


class Anchor(Enum):
    """The event a notice's clock runs from."""

    MEETING = "the meeting"
    HEARING = "the hearing"
    ACTION = "the board's action or decision"
    RULE_CHANGE = "the board's decision on the rule change"
    FISCAL_YEAR_END = "the end of the fiscal year"
    DUE_DATE = "the day the assessment becomes due"
    LIEN_RECORDING = "the recording of the lien"
    NOMINATION_DEADLINE = "the deadline for submitting nominations"
    NOMINATION_RECEIVED = "the receipt of a nomination"
    BALLOTS_DISTRIBUTED = "the distribution of the ballots"
    VOTING_DEADLINE = "the deadline for voting"
    ELECTION = "the election"
    CLOSE_OF_VOTING = "the close of voting"
    OPT_OUT_DEADLINE = "the deadline to opt out of electronic voting"
    RECONVENED_MEETING = "the reconvened meeting"
    REQUEST_RECEIVED = "the association's receipt of the request"
    REQUEST_MAILED = "the mailing or delivery of the request (its postmark)"
    APPLICATION_RECEIVED = "the receipt of the application"
    SERVICE = "service of the claim or request"
    EVENT = "the event the notice reports"
    RELOCATION = "the temporary relocation"
    APPLICATION_OF_PESTICIDE = "the application of the pesticide"
    PUBLIC_SALE = "the public sale"
    PAYMENT = "the payment"
    FILING = "the filing of the civil action"
    RECORDING = "the recording of the instrument"
    SETTLEMENT = "the settlement or resolution"
    ANNUAL_REPORTS = "the distribution of the annual budget report and policy statement"
    DEFAULT_RECORDED = "the recording of the notice of default"
    CONTRACT = "entering into the management agreement"
    VOTE_TO_FORECLOSE = "the board's vote to foreclose"
    ACCEPTANCE = "the receipt of the acceptance"


class Unit(Enum):
    CALENDAR_DAYS = "days"
    BUSINESS_DAYS = "business days"
    HOURS = "hours"


class Evidence(Enum):
    """What proves a notice was given: each is a record a person can hand to the board, a court, or a member."""

    TEXT_AS_SENT = "the notice as sent: its text, attachments, and date"
    RECIPIENTS = "the recipient list as of the record date, with each member's delivery method and why"
    DELIVERY_LEDGER = "each delivery attempt and its outcome (jason notices KEY)"
    FOLLOW_UPS = "each follow-up the ledger owed (a bounce resent by mail, a letter that never mailed), sent and read back"
    MAILING_DECLARATION = "a declaration of mailing: who deposited what, with what postage, where, and when"
    POSTING = "the posting: where (the designated location or website), from when to when, and a dated photo or capture"
    CERTIFIED_RECEIPTS = "the certified or registered mail numbers, the mailing receipts, and any return receipt"
    PROOF_OF_SERVICE = "a proof of service by the person who served it"
    DELIVERY_DECLARATION = "a declaration of personal delivery: who handed it to whom, where, and when"
    RECORDING = "the recorder's document number and recording date"
    MINUTES = "the minutes that record the meeting, action, vote, or finding"
    AGENDA = "the agenda, as it went out with the notice"
    REQUEST_ON_FILE = "the written request or application that started the clock, with the day it was received"
    ANCHOR_DATE = "the date of the event the clock runs from (the meeting, the due date, the recording)"


class NoticeStrength(Enum):
    """How strongly the record shows a notice was given, strongest first (``jason.tasks.notice_evidence`` reads it).

    A clock (4360, 4920) is met by a delivery on time, or by a send on time with its outstanding follow-ups listed. A
    file never meets one: it shows the notice was written, not that it went out."""

    DELIVERED = "delivered"                        # every member the ledger holds reached; or a general notice posted
    FOLLOW_UPS = "sent, with follow-ups owed"      # a bounce owed a resend (4041(e)), a returned letter, no address
    SENT = "sent"                                  # it went out; its outcomes are not synced
    FILE = "file"                                  # jason has the notice's file; no record it went out

    @property
    def counts(self) -> bool:
        """Whether a record of this strength, on time, meets a notice clock."""
        return self is not NoticeStrength.FILE

    @property
    def rank(self) -> int:
        return list(NoticeStrength).index(self)


class Comparison(Enum):
    """How a governing document's notice clause compares with the statute's requirement."""

    MORE = "more"                # a longer period, another method, or more content: follow both
    SAME = "same"                # restates the statute
    LESS = "less"                # asks less than the statute: the statute governs (4205); a conflict lead
    DIFFERENT = "different"      # a method or step the statute does not name; whether it satisfies the statute is a question
    RENUMBERED = "renumbered"    # cites a former section by its old number; read as its successor
    OWN = "own"                  # a notice the statute does not require: the document's own


@dataclass(frozen=True)
class Timing:
    """One clock: at least ``least`` and at most ``most`` units before (or, with ``after``, after) the anchor.

    ``least`` and ``most`` are both optional. "At least four days before the meeting" is ``least=4``; "not less than 30
    nor more than 60 days prior to" is ``least=30, most=60``; "within 14 days following the action" is ``after=True,
    most=14``; "as soon as reasonably practicable" has neither, and ``words`` carries the standard.
    """

    anchor: Anchor
    after: bool = False
    least: int | None = None
    most: int | None = None
    unit: Unit = Unit.CALENDAR_DAYS
    words: str = ""
    delivery: bool = True        # the clock governs the delivery; False: another act (entering the answers, a meeting)

    def window(self, anchor_day: date) -> tuple[date | None, date | None]:
        """The first and last day the notice may go out (be deposited in the mail, or transmitted, or posted) for an
        anchor on ``anchor_day``. A None end is open. Days are counted by subtracting whole days from the anchor's
        date (the anchor's own day not counted), business days skip weekends but not holidays (jason knows no
        holiday calendar, so a business-day deadline here is the earliest it can fall), and hours round up to whole
        days. How a court counts a period ending on a weekend or holiday is for counsel (docs/notices.md)."""
        if self.after:
            first = _shift(anchor_day, self.least or 0, self.unit)
            last = _shift(anchor_day, self.most, self.unit) if self.most is not None else None
            return first, last
        first = _shift(anchor_day, -self.most, self.unit) if self.most is not None else None
        last = _shift(anchor_day, -(self.least or 0), self.unit)
        return first, last

    def describe(self) -> str:
        span = ""
        unit = self.unit.value
        if self.least is not None and self.most is not None:
            span = f"{self.least} to {self.most} {unit}"
        elif self.least is not None:
            span = f"at least {self.least} {unit}"
        elif self.most is not None:
            span = f"within {self.most} {unit}" if self.after else f"at most {self.most} {unit}"
        side = "after" if self.after else "before"
        if not span:
            return f"{self.words or 'no period stated'} ({side} {self.anchor.value})"
        return f"{span} {side} {self.anchor.value}"


def _shift(day: date, amount: int | None, unit: Unit) -> date:
    if not amount:
        return day
    if unit is Unit.HOURS:
        days = -(-abs(amount) // 24)
        return day + timedelta(days=days if amount > 0 else -days)
    if unit is Unit.CALENDAR_DAYS:
        return day + timedelta(days=amount)
    step = 1 if amount > 0 else -1
    left = abs(amount)
    while left:
        day += timedelta(days=step)
        if day.weekday() < 5:
            left -= 1
    return day


@dataclass(frozen=True)
class NoticeRequirement:
    """What the statute requires of one kind of notice. ``key`` is stable: other records link to it.

    ``statute`` is the section whose words hold the rule ("CIV 4920"); ``words`` is a phrase that section's text carries
    (a regex, checked against the exported statute by ``tests/test_notice_catalog.py``), so a change in the law fails
    the build rather than leaving the row stale. ``verified`` is False for a row whose section is not on disk: it says
    so instead of inventing the rule. ``delivers`` is False for a deadline that is not a delivery (records produced
    within 10 business days; a payment-plan meeting within 45 days)."""

    key: str
    title: str
    statute: str
    recipients: Recipients
    kind: NoticeKind | None
    methods: tuple[Method, ...]
    timing: tuple[Timing, ...] = ()
    content: tuple[str, ...] = ()
    words: str = ""
    verified: bool = True
    delivers: bool = True
    annual: bool = False
    secondary_copies: bool = False        # 4040(b): Article 7 (5300-5320) and Article 2 of Chapter 8 (5650-5690), and 5710
    individual_on_request: bool = False   # a member who asks gets it by individual delivery (4045(b), 5115(a), (b)(5))
    carried_by: str = ""                  # the requirement whose document carries this one (5730's notice, in the APS)
    term: str = ""                        # the statutory_terms.TERMS name that holds the period
    also: tuple[str, ...] = ()            # related sections
    evidence: tuple[Evidence, ...] = ()   # beyond what its methods call for
    note: str = ""
    caveat: str = ""                      # unclear in the text: for counsel

    def proof(self) -> tuple[Evidence, ...]:
        """The evidence that proves this notice was given: what its methods call for, then its own."""
        found: list[Evidence] = []

        def add(*items: Evidence) -> None:
            for item in items:
                if item not in found:
                    found.append(item)

        if self.delivers:
            add(Evidence.TEXT_AS_SENT)
        methods = set(self.methods)
        if self.kind is NoticeKind.INDIVIDUAL or Method.INDIVIDUAL in methods:
            add(Evidence.RECIPIENTS, Evidence.DELIVERY_LEDGER, Evidence.FOLLOW_UPS, Evidence.MAILING_DECLARATION)
        if self.kind is NoticeKind.GENERAL or Method.GENERAL in methods:
            add(Evidence.POSTING, Evidence.RECIPIENTS, Evidence.DELIVERY_LEDGER, Evidence.FOLLOW_UPS)
        if methods & {Method.POSTING, Method.WEBSITE, Method.POSTED_AT_SITE}:
            add(Evidence.POSTING)
        if Method.FIRST_CLASS_MAIL in methods:
            add(Evidence.MAILING_DECLARATION)
        if methods & {Method.CERTIFIED_MAIL, Method.REGISTERED_OR_CERTIFIED}:
            add(Evidence.CERTIFIED_RECEIPTS, Evidence.MAILING_DECLARATION)
        if Method.PERSONAL_SERVICE in methods:
            add(Evidence.PROOF_OF_SERVICE)
        if Method.PERSONAL_DELIVERY in methods:
            add(Evidence.DELIVERY_DECLARATION)
        if Method.RECORDED in methods:
            add(Evidence.RECORDING)
        if any(t.anchor in (Anchor.REQUEST_RECEIVED, Anchor.REQUEST_MAILED, Anchor.APPLICATION_RECEIVED,
                            Anchor.NOMINATION_RECEIVED)
               for t in self.timing):
            add(Evidence.REQUEST_ON_FILE)
        if self.timing:
            add(Evidence.ANCHOR_DATE)
        add(*self.evidence)
        return tuple(found)


@dataclass(frozen=True)
class NoticeProvision:
    """A governing document's clause about a notice. ``document`` is the outline key ("bylaws"), ``section`` the
    section as the document numbers it. ``requirement`` is the catalog key it adds to or departs from (empty for a
    notice the statute does not require; then ``title`` and ``recipients`` name it). ``says`` paraphrases; quote a
    provision only from its text. ``lead`` is the sentence for the conflict register when the clause asks less than
    the statute, or departs from it."""

    key: str
    document: str
    section: str
    says: str
    comparison: Comparison
    requirement: str = ""
    timing: tuple[Timing, ...] = ()
    methods: tuple[Method, ...] = ()
    content: tuple[str, ...] = ()
    title: str = ""
    recipients: Recipients | None = None
    lead: str = ""

    @property
    def citation(self) -> str:
        return f"{self.document} {self.section}"


def combined(statute: Iterable[Timing], provisions: Iterable[NoticeProvision] = ()) -> tuple[tuple[Timing, ...], list[str]]:
    """The statute's clocks made stricter by the provisions that ask more: for the same anchor, direction, and unit,
    the larger "at least" and the smaller "at most". A provision that asks less is not applied (the statute governs,
    Civil Code 4205); a clock that becomes impossible (its least exceeds its most) is reported, never silently kept.
    Returns the clocks and the notes on what changed."""
    out = list(statute)
    notes: list[str] = []
    for p in provisions:
        if p.comparison not in (Comparison.MORE, Comparison.SAME):
            continue
        for t in p.timing:
            at = next((i for i, s in enumerate(out) if (s.anchor, s.after, s.unit) == (t.anchor, t.after, t.unit)), None)
            if at is None:
                out.append(t)
                notes.append(f"{p.citation} adds a clock: {t.describe()}")
                continue
            s = out[at]
            least = max((x for x in (s.least, t.least) if x is not None), default=None)
            most = min((x for x in (s.most, t.most) if x is not None), default=None)
            if least is not None and most is not None and least > most:
                notes.append(f"{p.citation} cannot be met with the statute: {t.describe()} against {s.describe()}")
                continue
            if (least, most) != (s.least, s.most):
                out[at] = replace(s, least=least, most=most, words=s.words)
                notes.append(f"{p.citation} narrows {s.describe()} to {out[at].describe()}")
    return tuple(out), notes


__all__ = ["Anchor", "Comparison", "Evidence", "Method", "NoticeKind", "NoticeProvision", "NoticeRequirement",
           "NoticeRule", "NoticeStrength", "Recipients", "Timing", "Unit", "combined"]
