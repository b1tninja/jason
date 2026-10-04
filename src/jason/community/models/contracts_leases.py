"""Leases of a unit and settlement agreements: kept light.

A lease is an owner's, filed with the association so it knows who lives in the unit. The law lets the governing
documents bar a rental of 30 days or less, and nothing shorter-reaching (CIV 4741(a)-(c)). The reader keeps no tenant's
name: it counts the residents.

A settlement the association signs is an executed contract and an association record unless privileged (CIV
5200(a)(4)). When it settles construction defect claims with the builder, the association must tell its members, as
soon as reasonably practicable, that the matter is resolved, which defects it expects to correct and when, and where the
other defect claims stand (CIV 6100(a)).

Layouts: ``lease`` reads Belong, Inc.'s residential lease (Belong signs as the owner's agent; each signer's e-signature
leaves a "Signed on" line) and other residential leases that print the same clauses ("The term begins on", "agrees to
pay $... per month"); ``settlement`` reads a settlement agreement and release (the association's 2022-23 builder
settlement layout: Claimant, Respondents, a defined Dispute, a Settlement Payment).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    cents,
    date_after,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.models.contracts_insurance import building_at
from jason.community.models.contracts_signing import Execution, Signature, read_signing
from jason.community.reviews import AS_OF
from jason.community.symbols import Building, DocumentKind

SOON_DAYS = 60
SHORT_TERM_DAYS = 30


@dataclass
class Lease:
    agent: str = ""                       # the owner's leasing agent, when one signs for the owner
    premises: str = ""
    building: Building | None = None
    dated: date | None = None
    term_start: date | None = None
    term_end: date | None = None
    month_to_month: bool = False
    rent: int | None = None               # cents a month
    adjusted_rent: int | None = None      # an addendum's rent
    deposit: int | None = None
    deposit_waived: bool = False
    residents: int | None = None          # how many residents sign; their names are not kept
    execution: Execution | None = None
    signers: int = 0
    signed_on: date | None = None


def _count_names(names: str) -> int:
    return len([n for n in re.split(r",\s*|\s+and\s+", names) if n.strip()])


@AS_OF.check("lease-term", Lease, fields=("term_end",))
def lease_term(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: whether the lease's term has ended or ends soon."""
    if not r.term_end:
        return []
    left = (r.term_end - as_of).days
    if left < 0:
        return [Finding("lease-ended", f"the lease term ended {r.term_end}; unless renewed it runs month to month or the "
                        "unit changed hands", Severity.INFO)]
    if left <= SOON_DAYS:
        return [Finding("lease-ending", f"the lease term ends {r.term_end} ({left} days)", Severity.INFO)]
    return []


class LeaseModel(DocumentModel):
    kind = DocumentKind.LEASE
    name = "lease"
    required = ("premises", "term_start", "term_end", "rent")
    lens_checks = (lease_term,)

    def parse(self, text: str, context: ModelContext) -> Lease | None:
        if not re.search(r"\bLEASE\b|RENTAL AGREEMENT", text or "", re.I) or not re.search(r"\brent\b", text, re.I):
            return None
        flat = squash(text)
        r = Lease()
        r.agent = first(r"([A-Z][\w.,&' ]{2,40}?),? \([“\"][A-Za-z]+[”\"]\),? as agent for Owner", flat)
        r.premises = first(r"described as:\s*([^(]{5,120}?)\s*\(", flat) or first(r"(?:Premises|Property Address)\s*:\s*([^\n]{5,120})", text)
        r.building, _address = building_at(r.premises or flat[:3000], context)
        r.dated = date_after(r"^\s*On", flat, window=14) or (dates_in(first(r"(On \d{1,2}/\d{1,2}/\d{4})", flat)) or [None])[0]
        r.term_start = date_after(r"term (?:begins|commences) on", flat, window=20)
        r.term_end = date_after(r"(?:shall )?terminate on", flat, window=20)
        r.month_to_month = bool(re.search(r"month[- ]to[- ]month", flat, re.I)) and r.term_end is None
        rent = first(r"agrees to pay (\$[\d,]+(?:\.\d\d)?) per month", flat)
        r.rent = cents(rent) if rent else None
        adjusted = first(r"monthly rent is adjusted to (\$[\d,]+(?:\.\d\d)?)", flat)
        r.adjusted_rent = cents(adjusted) if adjusted else None
        deposit = first(r"agrees to pay (\$[\d,]+(?:\.\d\d)?) as a security deposit", flat)
        r.deposit = cents(deposit) if deposit else None
        r.deposit_waived = bool(re.search(r"Security Deposit.{0,120}is waived", flat, re.I))
        names = first(r"as agent for Owner, and (.{3,200}?) \([“\"]Resident", flat)
        r.residents = _count_names(names) if names else None
        signing = read_signing(text)
        r.signers = signing.signers()
        r.signed_on = signing.signed_on
        r.execution = Execution.EXECUTED if r.signers >= 2 else signing.execution(one_side=False)
        return r

    def check(self, r: Lease, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.term_start and r.term_end and (r.term_end - r.term_start).days <= SHORT_TERM_DAYS:
            found.append(Finding("short-term-rental", f"a term of {(r.term_end - r.term_start).days} days: the governing documents may bar "
                                 "rentals of 30 days or less", Severity.CHECK, "CIV 4741(c)"))
        found.append(lease_term)   # the as-of lens's place: the term ended or ends soon
        if r.premises and r.building is None and context.community is not None:
            found.append(Finding("premises-not-placed", f"the leased address {r.premises!r} does not fall in a building of the "
                                 "specification", Severity.CHECK))
        if r.execution is Execution.NOT_IN_TEXT:
            found.append(Finding("unsigned-in-text", "no signature shows in the text; confirm the signed lease is the copy on file",
                                 Severity.CHECK))
        if r.adjusted_rent and r.rent and r.adjusted_rent != r.rent:
            found.append(Finding("rent-adjusted", f"an addendum sets the rent at ${r.adjusted_rent / 100:,.2f} a month instead of "
                                 f"${r.rent / 100:,.2f}", Severity.INFO))
        return found


@dataclass(frozen=True)
class Party:
    role: str      # "claimant", "respondent"
    name: str


@dataclass
class Settlement:
    title: str = ""
    parties: tuple[Party, ...] = ()
    dispute: str = ""                     # what was settled, as the agreement defines it
    dispute_began: date | None = None
    payment: int | None = None            # cents the association receives or pays
    payment_due_days: int | None = None   # after execution
    payee: str = ""
    builder_claim: bool = False           # construction defect claims against the builder or developer
    waives_1542: bool = False             # Civil Code 1542 waiver
    exhibits: tuple[str, ...] = ()
    execution: Execution | None = None
    signatures: tuple[Signature, ...] = ()
    signed_on: date | None = None
    blank_signature_lines: int = 0


class SettlementModel(DocumentModel):
    kind = DocumentKind.SETTLEMENT
    name = "settlement"
    required = ("parties", "dispute", "payment")

    def parse(self, text: str, context: ModelContext) -> Settlement | None:
        if not re.search(r"SETTLEMENT AGREEMENT|RELEASE", text or "", re.I):
            return None
        flat = squash(text)
        r = Settlement()
        r.title = first(r"^\s*((?:[A-Z]+ ){0,4}SETTLEMENT AGREEMENT(?: AND [A-Z ]+RELEASE)?)\s*$", text, flags=re.M)
        parties = []
        claimant = first(r"between Claimant\s+(.{3,80}?)\s*\([“\"]Claimant", flat)
        if claimant:
            parties.append(Party("claimant", claimant.rstrip(", ")))
        respondents = first(r"Respondents\s+(.{3,200}?)\s*\([“\"](?:Watt|Respondents)", flat) or first(r"and Respondents?\s+(.{3,200}?)\s*\(", flat)
        for name in re.split(r";\s*and\s+|;\s*|\s+and\s+(?=[A-Z])", respondents or ""):
            if name.strip():
                parties.append(Party("respondent", name.strip(" ,")))
        r.parties = tuple(parties)
        r.dispute = first(r"[“\"]Dispute[”\"] shall mean (.{10,300}?\.)", flat)
        r.dispute_began = (dates_in(r.dispute) or [None])[0]
        payment = first(r"agree to pay (?:Claimant )?the sum of (\$[\d,]+(?:\.\d\d)?)", flat) or first(r"Settlement Payment[^$]{0,60}(\$[\d,]+(?:\.\d\d)?)", flat)
        r.payment = cents(payment) if payment else None
        due = first(r"shall be made within ([a-z]+ \(\d+\)|\d+) days", flat)
        m = re.search(r"\d+", due or "")
        r.payment_due_days = int(m.group(0)) if m else None
        r.payee = first(r"payable to (?:the )?[“\"]([^”\"]{3,80})[”\"]", flat)
        r.builder_claim = bool(re.search(r"Notice to Builder|SB ?800|construction defect|Civil Code section 895|developer", flat, re.I))
        r.waives_1542 = bool(re.search(r"(?:Civil Code )?section 1542", flat, re.I))
        r.exhibits = tuple(dict.fromkeys(re.findall(r"EXHIBIT [“\"]([A-Z])[”\"]", text)))
        signing = read_signing(text)
        r.signatures = signing.signatures
        r.signed_on = signing.signed_on
        r.execution = signing.execution(one_side=False)
        r.blank_signature_lines = signing.blank_lines + len(re.findall(r"(?m)^\s*(?:Date|Name|Title):\s*$", text))
        return r

    def check(self, r: Settlement, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.execution is not Execution.EXECUTED:
            found.append(Finding("unsigned-in-text", "the signature page's names, titles, and dates are blank in the text; confirm the "
                                 "fully executed copy is on file", Severity.CHECK, "CIV 5200(a)(4)"))
        if r.builder_claim:
            found.append(Finding("member-disclosure", "a settlement of defect claims with the builder: members must be told, as soon as "
                                 "reasonably practicable, that the matter is resolved, which defects the association expects to correct and "
                                 "when, and where the other defect claims stand", Severity.CHECK, "CIV 6100(a)"))
        if r.waives_1542:
            found.append(Finding("waives-1542", "the association waives Civil Code section 1542 for the released claims (unknown claims "
                                 "within them are released too)", Severity.INFO))
        if r.payment and r.payment_due_days:
            when = f" (by {r.signed_on + timedelta(days=r.payment_due_days)})" if r.signed_on else ""
            found.append(Finding("settlement-payment", f"a payment of ${r.payment / 100:,.2f} due within {r.payment_due_days} days of "
                                 f"execution{when}" + (f", payable to {r.payee}" if r.payee else ""), Severity.INFO))
        return found


register(LeaseModel())
register(SettlementModel())

__all__ = ["Lease", "Settlement", "Party", "LeaseModel", "SettlementModel"]
