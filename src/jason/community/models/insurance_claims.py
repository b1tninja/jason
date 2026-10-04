"""Insurance claim papers: the carrier's loss run, its letters on one claim, what it paid, the claim's repair paperwork,
its estimate, and the police report a loss rests on.

No Davis-Stirling section shapes these papers; the policy does. The master policy covers the buildings; an owner's
HO-6 policy covers the unit's contents, improvements, and the deductible the declaration may shift (a "primacy" letter
is the owner's carrier deferring to the master). What a model reads is evidence for the incident history
(`jason incidents`); whether a peril was covered is the carrier's answer.

- ``LossRunModel`` reads a carrier's Claim Summary and Claim Detail reports: the policy, the valuation date, and each
  claim's number, date of loss, status, type, cause, location, and amounts.
- ``ClaimLetterModel`` reads a carrier's letter on one claim (Farmers' National Document Center layout and the usual
  labels): the claim and policy numbers, the insured, the loss date and location, what the letter is (acknowledgment,
  status, settlement, denial or disclaimer, closed for no contact, primacy, reservation of rights), and the settlement
  table when it prints one.
- ``ClaimPaymentModel`` reads a statement of loss and a claim check: the net loss, deductible, depreciation, the net
  claim, and the check's number, date, and amount.
- ``ClaimAuthorizationModel`` reads a program contractor's work authorization, certificate of satisfaction, or project
  tracker: the claim, the date of loss, the carrier, the address, and the signing date.
- ``ClaimEstimateModel`` reads a carrier's or its vendor's estimate (the Xactimate layout): the claim, the type of loss,
  and the replacement cost, depreciation, actual cash value, deductible, and net claim.
- ``PoliceReportModel`` reads only the report number, the date, and the location; the people in a report are not read.

A claim paper names owners, policyholders, and drivers; the library holds these kinds as confidential, and a record
keeps no person's name except the carrier's and the program contractor's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import Path

from jason.community.base import alternation, street_words
from jason.community.document_models import DocumentModel, Finding, ModelContext, Severity, cents, date_after, first, register, squash
from jason.community.incidents import LOSS_RUN, LossRunClaim, claim_key, read_loss_run
from jason.community.reviews import AS_OF
from jason.community.symbols import DocumentKind

_CARRIERS = (("Farmers", r"farmersinsurance|Farmers Insurance|Truck Insurance Exchange|Fire Insurance Exchange"),
             ("USAA (Garrison Property and Casualty)", r"USAA|Garrison Property"),
             ("Accelerant National Insurance Company", r"Accelerant"),
             ("AAA Insurance", r"AAA Insurance|\bCSAA\b"),
             ("Athens Program Insurance Services", r"Athens"),
             ("MG Skinner & Associates", r"MG ?Skinner"),
             ("McGowan Program Administrators", r"McGowan"),
             ("Philadelphia Insurance", r"Philadelphia Indemnity|Philadelphia Insurance"))


def carrier_of(text: str) -> str:
    for name, pattern in _CARRIERS:
        if re.search(pattern, text or "", re.I):
            return name
    return ""


def _us_day(text: str) -> date | None:
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text or "")
    if not m:
        long = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})",
                         text or "")
        if long:
            months = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
                      "december")
            return date(int(long.group(3)), months.index(long.group(1).lower()) + 1, int(long.group(2)))
        return None
    year = int(m.group(3))
    year += 2000 if year < 100 else 0
    try:
        return date(year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def _after(label: str, text: str, width: int = 80) -> str:
    """The value on the label's line, or on the next line when the label stands alone."""
    m = re.search(label + r"[ \t]*:?[ \t]*([^\n]*)\n?[ \t]*([^\n]*)", text or "", re.I)
    if not m:
        return ""
    value = m.group(1).strip() or m.group(2).strip()
    return value[:width]


def _money(label: str, text: str) -> int | None:
    m = re.search(label + r"\s*:?\s*\n?\s*\(?\$?\s*\(?([\d,]+\.\d\d)", text or "", re.I)
    return cents("$" + m.group(1)) if m else None


def _deposited(context: ModelContext, amount: int, after: date | None, days: int = 60) -> str | None:
    """The ledger's deposit of ``amount`` within ``days`` of ``after``, as its day; None when there is none or no ledger."""
    if not context.data_dir or not after:
        return None
    path = Path(context.data_dir) / "payhoa" / "ledger.db"
    if not path.is_file():
        return None
    import sqlite3

    with sqlite3.connect(path) as db:
        row = db.execute("select day from entries where credit = ? and day >= ? and day <= ? order by day limit 1",
                         (amount, after.isoformat(), (after + timedelta(days=days)).isoformat())).fetchone()
        if row is None:
            row = db.execute("select day from entries where debit = ? and account like '%Operating%' and day >= ? and day <= ? "
                             "order by day limit 1", (amount, after.isoformat(), (after + timedelta(days=days)).isoformat())).fetchone()
    return row[0] if row else None


# -- the loss run ----------------------------------------------------------------------------------------------------


@dataclass
class LossRun:
    carrier: str = ""
    policy: str = ""
    valued: date | None = None
    period: str = ""                 # "01/01/2019 - 08/19/2024"
    claims: tuple[LossRunClaim, ...] = ()
    claim_count: int | None = None   # the summary's total, which a run with no detail pages still prints
    paid_cents: int = 0


@AS_OF.check("loss-run-age", LossRun, fields=("valued",))
def loss_run_age(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: whether the loss run was valued more than a year before."""
    if r.valued and (as_of - r.valued).days > 365:
        return [Finding("stale-loss-run", f"the loss run is valued {r.valued}; lenders and renewals ask for one valued "
                        "within the year: ask the carrier or agent for a current one", Severity.CHECK)]
    return []


class LossRunModel(DocumentModel):
    kind = DocumentKind.LOSS_RUN
    name = "loss-run"
    required = ("carrier", "policy", "valued")
    lens_checks = (loss_run_age,)

    def parse(self, text: str, context: ModelContext) -> LossRun | None:
        if not LOSS_RUN.search((text or "")[:600]):
            return None
        r = LossRun()
        r.claims = read_loss_run(text)
        r.carrier = (r.claims[0].carrier if r.claims else "") or _after(r"Company:", text) or carrier_of(text)
        r.policy = (r.claims[0].policy if r.claims else "") or _after(r"Policy #:", text)
        r.valued = (r.claims[0].valued if r.claims else None) or _us_day(_after(r"Valuation Date:", text))
        r.period = first(r"Date Range(?: Selection)?:?\s*\n?\s*([\d/]+\s*-\s*[\d/]+)", text)
        total = re.search(r"Totals\s*\n\s*(\d+)\s*\n", text)
        r.claim_count = int(total.group(1)) if total else len(r.claims)
        r.paid_cents = sum(c.paid_cents or 0 for c in r.claims)
        return r

    def check(self, r: LossRun, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.claim_count == 0:
            found.append(Finding("no-claims", f"the carrier records no claim on policy {r.policy} for {r.period or 'the period'}",
                                 Severity.INFO))
        for c in r.claims:
            paid = f", paid ${(c.paid_cents or 0) / 100:,.2f}" if c.paid_cents else ""
            found.append(Finding("claim", f"claim {c.number}: loss {c.date_of_loss} at {c.location}, {c.cause}, {c.status}{paid}",
                                 Severity.INFO))
        found.append(loss_run_age)   # the as-of lens's place: valued more than a year ago
        return found


# -- the carrier's letter on a claim ---------------------------------------------------------------------------------


class LetterType(Enum):
    ACKNOWLEDGMENT = "acknowledgment"
    STATUS = "status"
    SETTLEMENT = "settlement"
    DENIAL = "denial or disclaimer"
    CLOSED_NO_CONTACT = "closed: no contact"
    PRIMACY = "primacy (the owner's carrier defers to the master policy)"
    RESERVATION_OF_RIGHTS = "reservation of rights"
    OTHER = "other"


_LETTER_TYPES = ((LetterType.PRIMACY, r"primary insurer|master carrier|COVERAGE FOR YOUR\s+CONDOMINIUM CLAIM"),
                 (LetterType.RESERVATION_OF_RIGHTS, r"reservation of rights|reserves? (?:its|all) rights"),
                 (LetterType.SETTLEMENT, r"Settlement Notice|settlement of your claim|payment has been (?:made|issued)"),
                 (LetterType.DENIAL, r"disclaim coverage|deny (?:coverage|your claim)|not covered under|policy (?:was )?not active"),
                 (LetterType.CLOSED_NO_CONTACT, r"(?:unable|haven.t been able) to (?:reach|contact) you|closed your file"),
                 (LetterType.ACKNOWLEDGMENT, r"acknowledge (?:receipt|your claim)|Acknowledg(?:e)?ment"),
                 (LetterType.STATUS, r"status (?:letter|of your claim|update)|Subject:\s*\n?\s*Status"))
# The letter's own subject line names it before any quoted policy language does.
_SUBJECTS = ((LetterType.SETTLEMENT, r"settlement"), (LetterType.DENIAL, r"denial|disclaim"), (LetterType.STATUS, r"status"),
             (LetterType.ACKNOWLEDGMENT, r"acknowledg"), (LetterType.RESERVATION_OF_RIGHTS, r"reservation"))
_CLAIM_NO = re.compile(r"Claim (?:Number|No\.?|#)\s*:?\s*\n?\s*([A-Z]{0,3}\d[\dA-Z]*(?:\s*[-–]\s*\d+)*)", re.I)


@dataclass
class ClaimLetter:
    carrier: str = ""
    letter_date: date | None = None
    letter_type: LetterType = LetterType.OTHER
    claim_number: str = ""
    policy_number: str = ""
    association_is_insured: bool = False    # the association's own policy, not an owner's
    loss_date: date | None = None
    loss_location: str = ""
    replacement_cost_cents: int | None = None
    depreciation_cents: int | None = None
    actual_cash_value_cents: int | None = None
    deductible_cents: int | None = None
    paid_cents: int | None = None
    program_contractor: str = ""            # "Lionsbridge Contractor Group"
    canceled_effective: date | None = None  # a disclaimer's policy cancellation date


class ClaimLetterModel(DocumentModel):
    kind = DocumentKind.CLAIM_LETTER
    name = "claim-letter"
    required = ("carrier", "claim_number", "loss_date")

    def parse(self, text: str, context: ModelContext) -> ClaimLetter | None:
        if not re.search(r"claim", text or "", re.I) or LOSS_RUN.search((text or "")[:600]):
            return None
        r = ClaimLetter(carrier=carrier_of(text))
        head = (text or "")[:3000]
        r.letter_date = _us_day(first(r"\n((?:January|February|March|April|May|June|July|August|September|October|November|December)"
                                      r"\s+\d{1,2},\s*\d{4})\s*\n", head)) or date_after(r"\bDate:", head, window=30)
        subject = first(r"Subject:\s*\n?\s*([^\n]+)", head)
        r.letter_type = next((kind for kind, pattern in _SUBJECTS if subject and re.search(pattern, subject, re.I)), LetterType.OTHER)
        if r.letter_type is LetterType.OTHER:
            r.letter_type = next((kind for kind, pattern in _LETTER_TYPES if re.search(pattern, text or "", re.I)), LetterType.OTHER)
        number = _CLAIM_NO.search(head)
        r.claim_number = re.sub(r"\s+", "", number.group(1)).replace("–", "-") if number else ""
        r.policy_number = _after(r"Policy (?:Number|No\.?|#)", head, 30)
        insured = _after(r"Insured", head, 60) or _after(r"Policyholder", head, 60)
        own = getattr(context.community, "name_pattern", str)()
        r.association_is_insured = bool(re.search("|".join(filter(None, (own, "association", "community"))), insured or head[:800], re.I)) and \
            r.letter_type is not LetterType.PRIMACY
        r.loss_date = _us_day(_after(r"(?:Loss Date|Date of Loss)", head, 30))
        r.loss_location = squash(_after(r"(?:Location of Loss|Loss Location)", head, 80))
        r.replacement_cost_cents = _money(r"Replacement Cost", text)
        r.depreciation_cents = _money(r"Depreciation", text)
        r.actual_cash_value_cents = _money(r"Actual Cash Value", text)
        r.deductible_cents = _money(r"Deductible", text)
        r.paid_cents = _money(r"(?:Amount Paid|Payment Amount|Net Claim|Total Paid)", text)
        r.program_contractor = first(r"(Lionsbridge Contract(?:or|ing) Group|CCA Global Partners)", text)
        canceled = re.search(r"canceled per your request\s+effective\s+(\w+ \d{1,2}, \d{4})", text or "", re.I)
        r.canceled_effective = _us_day(canceled.group(1)) if canceled else None
        if not r.claim_number:
            return None
        return r

    def check(self, r: ClaimLetter, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.letter_type is LetterType.DENIAL and r.canceled_effective and r.loss_date and r.canceled_effective <= r.loss_date:
            master = _master(context)
            where = f"; the specification's master policy is {master}" if master else ""
            found.append(Finding("filed-with-a-prior-carrier", f"{r.carrier} disclaimed claim {r.claim_number}: its policy was canceled "
                                 f"effective {r.canceled_effective}, before the loss of {r.loss_date}. The loss belongs with the master "
                                 f"carrier in force on that day{where}; the record shows no claim there", Severity.PROBLEM))
        elif r.letter_type is LetterType.DENIAL:
            found.append(Finding("denied", f"{r.carrier} denied or disclaimed claim {r.claim_number}; read its reasons against the policy",
                                 Severity.CHECK))
        if r.letter_type is LetterType.CLOSED_NO_CONTACT:
            found.append(Finding("closed-no-contact", f"{r.carrier} closed claim {r.claim_number} because it could not reach the "
                                 "insured; the policy's conditions set how long it may be reopened", Severity.CHECK))
        if r.letter_type is LetterType.RESERVATION_OF_RIGHTS:
            found.append(Finding("reservation-of-rights", f"{r.carrier} reserves its rights on claim {r.claim_number}: coverage is "
                                 "not yet accepted; counsel should read the letter", Severity.CHECK))
        if r.letter_type is LetterType.PRIMACY:
            found.append(Finding("owner-carrier-defers", f"an owner's carrier ({r.carrier}) defers to the association's master "
                                 "policy for the building; it asks for the master carrier's settlement or denial", Severity.INFO))
        if r.letter_type is LetterType.SETTLEMENT and r.program_contractor:
            found.append(Finding("paid-to-program-contractor", f"{r.carrier} paid {r.program_contractor}, which releases the funds as "
                                 "the repairs are done: a certificate of satisfaction closes it", Severity.INFO))
        return found


def _master(context: ModelContext) -> str:
    community = context.community
    try:
        catalog = community.insurance() if community is not None else None
    except Exception:
        return ""
    for policy in getattr(catalog, "policies", ()) or ():
        if getattr(getattr(policy, "kind", None), "name", "") == "MASTER":
            return f"{policy.carrier} ({policy.number})"
    return ""


# -- what the carrier paid -------------------------------------------------------------------------------------------


@dataclass
class ClaimPayment:
    carrier: str = ""
    claim_number: str = ""
    date_of_loss: date | None = None
    statement: bool = False              # a statement of loss (else a check)
    net_loss_cents: int | None = None
    deductible_cents: int | None = None
    depreciation_cents: int | None = None
    net_claim_cents: int | None = None   # at actual cash value when both print
    check_number: str = ""
    issued: date | None = None
    amount_cents: int | None = None


class ClaimPaymentModel(DocumentModel):
    kind = DocumentKind.CLAIM_PAYMENT
    name = "claim-payment"
    required = ("amount_cents",)

    def parse(self, text: str, context: ModelContext) -> ClaimPayment | None:
        statement = bool(re.search(r"net claim at|less deductible|statement of loss", text or "", re.I))
        check = bool(re.search(r"remittance advice|check number|payable to", text or "", re.I))
        if not (statement or check):
            return None
        r = ClaimPayment(carrier=carrier_of(text), statement=statement and not check)
        r.claim_number = first(r"\b([A-Z]{2}\d{6})\b", text) or _after(r"CLAIM #", text, 30)
        r.date_of_loss = _us_day(_after(r"DATE OF LOSS", text, 30))
        if statement:
            r.net_loss_cents = _money(r"Net Loss", text)
            r.deductible_cents = _money(r"Less Deductible", text)
            r.depreciation_cents = _money(r"Less Depreciation", text)
            r.net_claim_cents = _money(r"Net Claim at ACV", text) or _money(r"Net Claim at RCV", text)
            r.amount_cents = r.net_claim_cents
        if check:
            block = re.search(r"Amount\s*\n\s*Check Number\s*\n\s*Issued Date\s*\n\s*([\d,.]+)\s*\n\s*(\d+)\s*\n\s*([\d-]+)", text or "")
            if block:
                r.amount_cents = cents("$" + block.group(1))
                r.check_number = block.group(2)
                r.issued = _us_day(block.group(3))
        return r

    def check(self, r: ClaimPayment, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.depreciation_cents:
            found.append(Finding("depreciation-held-back", f"${r.depreciation_cents / 100:,.2f} of depreciation was held back; recoverable "
                                 "depreciation is paid when the repairs are done and invoiced to the carrier", Severity.CHECK))
        if r.check_number and r.amount_cents:
            day = _deposited(context, r.amount_cents, r.issued)
            if day:
                found.append(Finding("deposited", f"check {r.check_number} (${r.amount_cents / 100:,.2f}) is in the ledger on {day}",
                                     Severity.INFO))
            elif context.data_dir:
                found.append(Finding("not-deposited", f"check {r.check_number} for ${r.amount_cents / 100:,.2f}, issued {r.issued}, is not "
                                     "in the stored ledger within 60 days: confirm it was deposited", Severity.CHECK))
        return found


# -- the claim's repair paperwork ------------------------------------------------------------------------------------


class AuthorizationType(Enum):
    WORK_AUTHORIZATION = "work authorization"
    CERTIFICATE_OF_SATISFACTION = "certificate of satisfaction"
    PROJECT_TRACKER = "project tracker"


@dataclass
class ClaimAuthorization:
    form: AuthorizationType = AuthorizationType.WORK_AUTHORIZATION
    claim_number: str = ""
    date_of_loss: date | None = None
    carrier: str = ""
    address: str = ""
    program_contractor: str = ""
    signed: date | None = None


class ClaimAuthorizationModel(DocumentModel):
    kind = DocumentKind.CLAIM_AUTHORIZATION
    name = "claim-authorization"
    required = ("claim_number", "form")

    def parse(self, text: str, context: ModelContext) -> ClaimAuthorization | None:
        if re.search(r"certificate of satisfaction|\bCOS\b", (context.name or "") + "\n" + (text or "")[:1500], re.I) and \
                not re.search(r"WORK AUTHORIZATION", (text or "")[:300]):
            form = AuthorizationType.CERTIFICATE_OF_SATISFACTION
        elif re.search(r"project tracker", (context.name or "") + (text or "")[:800], re.I):
            form = AuthorizationType.PROJECT_TRACKER
        elif re.search(r"work authorization", text or "", re.I):
            form = AuthorizationType.WORK_AUTHORIZATION
        else:
            return None
        blank = re.search(r"Your Insurance Carrier\s*(.*?)\s*submitt", text or "", re.I | re.S)
        # The carrier is typed into a blank, and OCR spaces its letters ("_F_a_r_m_e_rs___").
        typed = re.sub(r"[_\s]+", "", blank.group(1)) if blank else ""
        r = ClaimAuthorization(form=form, carrier=carrier_of(text) or (typed if 2 < len(typed) < 40 else ""))
        typed = re.sub(r"\s+", "", _after(r"CLAIM\s*#", text, 30))
        # A blank form's empty field reads the next label ("DATE OF LOSS:"); a claim number has digits.
        r.claim_number = typed if re.search(r"\d{5}", typed) else first(r"\b(\d{9,10}(?:-\d{1,3})+)\b", (context.name or "") + " " + text)
        r.date_of_loss = _us_day(_after(r"DATE OF LOSS", text, 30))
        r.address = squash(_after(r"ADDRESS", text, 80)) if re.search(r"\d{4} ", _after(r"ADDRESS", text, 80)) else ""
        r.program_contractor = first(r"(Lionsbridge Contract(?:or|ing) Group|CCA Global Partners)", text)
        signed = re.findall(r"\n\s*(\d{1,2}/\d{1,2}/\d{4})\s*\n", text or "")
        r.signed = _us_day(signed[-1]) if signed else None
        return r

    def check(self, r: ClaimAuthorization, context: ModelContext) -> list[Finding]:
        if r.form is AuthorizationType.WORK_AUTHORIZATION:
            return [Finding("authorized", f"the insured authorized the carrier to pay {r.program_contractor or 'the program contractor'} "
                            f"for claim {r.claim_number}; the deductible and depreciation stay the insured's", Severity.INFO)]
        if r.form is AuthorizationType.CERTIFICATE_OF_SATISFACTION:
            return [Finding("repairs-accepted", f"a certificate of satisfaction for claim {r.claim_number}: the repairs were accepted"
                            + (f" on {r.signed}" if r.signed else ""), Severity.INFO)]
        return []


# -- the carrier's estimate ------------------------------------------------------------------------------------------


@dataclass
class ClaimEstimate:
    carrier: str = ""
    claim_number: str = ""
    type_of_loss: str = ""
    date_of_loss: date | None = None
    replacement_cost_cents: int | None = None
    depreciation_cents: int | None = None
    actual_cash_value_cents: int | None = None
    deductible_cents: int | None = None
    net_claim_cents: int | None = None
    mitigation: bool = False            # a water mitigation (dry-out) estimate, not the repairs


class ClaimEstimateModel(DocumentModel):
    kind = DocumentKind.CLAIM_ESTIMATE
    name = "claim-estimate"
    required = ("claim_number", "type_of_loss")

    def parse(self, text: str, context: ModelContext) -> ClaimEstimate | None:
        # The estimate's own header (Xactimate prints "Type of Loss"); a settlement letter that encloses one does not.
        if not re.search(r"Type of Loss", text or "", re.I) or not re.search(r"estimate", text or "", re.I):
            return None
        r = ClaimEstimate(carrier=carrier_of(text))
        r.claim_number = re.sub(r"\s+", "", _after(r"Claim Number", text, 30))
        r.type_of_loss = _after(r"Type of Loss", text, 40)
        r.date_of_loss = _us_day(_after(r"Date of Loss", text, 30))
        r.replacement_cost_cents = _money(r"(?:Replacement Cost Value|RCV)", text)
        r.depreciation_cents = _money(r"(?:Less )?(?:Recoverable )?Depreciation", text)
        r.actual_cash_value_cents = _money(r"(?:Actual Cash Value|ACV)", text)
        r.deductible_cents = _money(r"(?:Less )?Deductible", text)
        r.net_claim_cents = _money(r"Net Claim", text)
        r.mitigation = bool(re.search(r"mitigation|dry(?:ing)?[- ]?out|dehumidif|air mover", (context.name or "") + text[:4000], re.I))
        return r

    def check(self, r: ClaimEstimate, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.deductible_cents and r.replacement_cost_cents and r.replacement_cost_cents <= r.deductible_cents:
            found.append(Finding("under-deductible", f"the estimate (${r.replacement_cost_cents / 100:,.2f}) is within the deductible "
                                 f"(${r.deductible_cents / 100:,.2f}): the carrier pays nothing", Severity.INFO))
        master = _master_deductible(context)
        if master and r.replacement_cost_cents and r.replacement_cost_cents < master:
            found.append(Finding("under-master-deductible", f"the estimate (${r.replacement_cost_cents / 100:,.2f}) is under the master "
                                 f"policy's ${master / 100:,.0f} deductible: a claim on the master policy would pay nothing", Severity.INFO))
        return found


def _master_deductible(context: ModelContext) -> int | None:
    try:
        master = context.community.insurance().master() if context.community is not None else None
    except Exception:
        return None
    return getattr(master, "deductible_cents", None) if master else None


# -- the police report -----------------------------------------------------------------------------------------------


@dataclass
class PoliceReport:
    report_number: str = ""
    agency: str = ""
    occurred: date | None = None
    location: str = ""


class PoliceReportModel(DocumentModel):
    kind = DocumentKind.POLICE_REPORT
    name = "police-report"
    required = ("report_number",)

    def parse(self, text: str, context: ModelContext) -> PoliceReport | None:
        number = first(r"Report No\.?\s*([\d-]{6,})", text) or first(r"(?:REPORT NUMBER|Case (?:No\.?|Number))\s*:?\s*\n?\s*([\d-]{6,})", text)
        if not number and not re.search(r"police", (context.name or "") + (text or "")[:500], re.I):
            return None
        r = PoliceReport(report_number=number)
        r.agency = first(r"(Sacramento Police Department|Sacramento County Sheriff|California Highway Patrol)", text)
        r.occurred = date_after(r"(?:Date|OCCURRED ON)", text, window=40)
        streets = alternation(street_words(getattr(context.community, "streets", tuple)()))
        street = re.search(rf"\b(\d{{4}}\s+(?:{streets})\s+\w+)", text or "", re.I)
        r.location = street.group(1) if street else ""
        return r


for _model in (LossRunModel(), ClaimLetterModel(), ClaimPaymentModel(), ClaimAuthorizationModel(), ClaimEstimateModel(), PoliceReportModel()):
    register(_model)


__all__ = ["LossRun", "LossRunModel", "LetterType", "ClaimLetter", "ClaimLetterModel", "ClaimPayment", "ClaimPaymentModel",
           "AuthorizationType", "ClaimAuthorization", "ClaimAuthorizationModel", "ClaimEstimate", "ClaimEstimateModel", "PoliceReport",
           "PoliceReportModel", "carrier_of", "claim_key"]
