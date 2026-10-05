"""Assessment collection documents: the pre-lien notice, a reimbursement assessment notice, an owner's statement, and
the manager's owner ledgers.

The law shapes the pre-lien notice. At least 30 days before recording a lien the association notifies the owner of
record by certified mail of: its collection and lien enforcement procedures and how the amount is figured, the right to
inspect the records (5205), and the foreclosure warning in capitals (5660(a)); an itemized statement of the charges
(5660(b)); that the owner owes no charges if the assessment was paid on time (5660(c)); the right to meet the board
(5660(d), 5665, where the owner may ask for a payment plan); the right to dispute the debt through meet and confer
(5660(e)); and the right to ADR before foreclosure (5660(f)). An assessment is delinquent 15 days after it is due, the
late charge is at most 10 percent or $10, and interest at most 12 percent a year from 30 days after the due date
(5650(b)). The board alone decides to record a lien, by majority vote in an open meeting, recorded in the minutes (5673),
and alone decides to foreclose one, by majority vote in executive session, never delegated to an agent (5705(c)); a lien
is foreclosed only when the delinquent assessments alone reach $1,800 or are more than 12 months delinquent (5720(b)).

``PreLienNotice`` reads the association's "Notice of Default and Demand for Payment" letters (the 2022 letter with the
manager's ledger and the enclosed Assessment Collection Policy, and the 2024 letters that offer a payment plan).
``ReimbursementNotice`` reads the board's reimbursement assessment letter. ``OwnerStatement`` reads PayHOA's owner
statement. ``OwnerHistory`` reads The Helsing Group's owner ledgers, one account or the whole roll.

A record keeps the unit's street address and the amounts; it never keeps the owner's name (``names_owner`` says the
text names one).
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

from jason.community.base import name_regex
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
from jason.community.invoices import parse_date
from jason.community.sources import SourceKind, manager_name, sender_name
from jason.community.models.legal_shared import (
    DELINQUENT_AFTER_DAYS,
    FORECLOSURE_FLOOR,
    INTEREST_AFTER_DAYS,
    INTEREST_CAP_PERCENT,
    LATE_CHARGE_PERCENT,
    PRE_LIEN_DAYS,
    Charge,
    ChargeKind,
    building_of,
    charge_kind,
    former_sections,
    cites_former,
    ledger_counts,
    ledger_findings,
    monthly_assessment,
    site_address,
    total,
)
from jason.community.symbols import Building, DocumentKind


class PreLienElement(Enum):
    """What CIV 5660 has the pre-lien notice say, one member per item."""

    PROCEDURES = "collection and lien enforcement procedures and the method of calculation (5660(a))"
    RECORDS = "right to inspect the association records under 5205 (5660(a))"
    FORECLOSURE_WARNING = "the foreclosure warning in capitals (5660(a))"
    ITEMIZED = "itemized statement of the charges (5660(b))"
    PAID_ON_TIME = "no liability if the assessment was paid on time (5660(c))"
    BOARD_MEETING = "right to request a meeting with the board (5660(d), 5665)"
    MEET_AND_CONFER = "right to dispute through meet and confer (5660(e))"
    ADR = "right to alternative dispute resolution before foreclosure (5660(f))"


_ELEMENT_AUTHORITY = {
    PreLienElement.PROCEDURES: "CIV 5660(a)", PreLienElement.RECORDS: "CIV 5660(a)", PreLienElement.FORECLOSURE_WARNING: "CIV 5660(a)",
    PreLienElement.ITEMIZED: "CIV 5660(b)", PreLienElement.PAID_ON_TIME: "CIV 5660(c)", PreLienElement.BOARD_MEETING: "CIV 5660(d)",
    PreLienElement.MEET_AND_CONFER: "CIV 5660(e)", PreLienElement.ADR: "CIV 5660(f)",
}

_WARNING = "IF YOUR SEPARATE INTEREST IS PLACED IN FORECLOSURE BECAUSE YOU ARE BEHIND IN YOUR ASSESSMENTS, IT MAY BE SOLD WITHOUT COURT ACTION"
# The letters reprint 5660 and 5720 after the notice; the reprint must not count as the notice's own words.
_REPRINT = re.compile(r"§\s*5660\.?\s*\n?\s*At least 30 days prior", re.I)


def _statute_block(own: str) -> re.Pattern[str]:
    """The reprint of 5660 after the notice, up to the enclosed collection policy's heading, which the association's
    name leads (``own``, ``Community.name``); with no name, up to the end."""
    return re.compile(rf"(?:California Civil Code\s*)?§\s*5660\.?\s*At least 30 days prior.*?(?={name_regex(own)}\s+ASSESSMENT COLLECTION POLICY|\Z)",
                      re.I | re.S)


class SenderKind(Enum):
    ASSOCIATION = "association"
    ATTORNEY = "attorney"
    MANAGER = "manager"


@dataclass
class PreLienNotice:
    notice_date: date | None = None
    as_of: date | None = None
    title: str = ""                         # "Notice of Default and Demand for Payment", "Pre-Lien Notice"
    sender: str = ""                        # the association, or its attorney
    sender_kind: SenderKind | None = None
    manager: str = ""                       # the manager the letterhead names, if any
    ledger_by: str = ""                     # who printed the enclosed ledger: a listed law firm or manager, by its directory name
    property_address: str = ""
    building: Building | None = None
    unit: str = ""
    names_owner: bool = False
    days_delinquent_stated: int | None = None
    cure_days: int | None = None            # "if payment in full is not received within N days ... may be recorded"
    foreclosure_days_after_lien: int | None = None
    lien_threshold: int | None = None       # cents: "exceeds $1,800.00"
    collections_threshold: int | None = None
    payment_plan_offered: bool = False
    board_decides_lien: bool = False        # "a decision ... would be made at an Open Board Meeting"
    foreclosure_by_agent: bool = False      # "we will refer the account to collections. If they are unable ... they may begin foreclosure"
    certified_mail: bool = False
    elements: tuple[PreLienElement, ...] = ()
    charges: tuple[Charge, ...] = ()
    total_due: int | None = None
    assessments: int | None = None
    late_charges: int | None = None
    interest: int | None = None
    payments: int | None = None
    monthly_installment: int | None = None
    policy_enclosed: bool = False
    policy_in_text: bool = False
    policy_effective: date | None = None
    policy_late_charge_percent: float | None = None
    policy_interest_percent: float | None = None
    statute_reprinted: bool = False
    former_sections: tuple[str, ...] = ()

    @property
    def missing_elements(self) -> tuple[PreLienElement, ...]:
        return tuple(e for e in PreLienElement if e not in self.elements)


def _notice_body(text: str, context: ModelContext) -> str:
    """The letter without the reprinted statute."""
    return _statute_block(_own_name(context)).sub("\n", text)


def _elements(body: str, flat: str, itemized: bool) -> tuple[PreLienElement, ...]:
    found = []
    if re.search(r"general description of the collection and lien enforcement procedures", flat, re.I) or \
            re.search(r"collection policy[^.]{0,80}enclosed", flat, re.I):
        found.append(PreLienElement.PROCEDURES)
    if re.search(r"inspect the association(?:'|’)?s? records|§\s*5205|section 5205", flat, re.I):
        found.append(PreLienElement.RECORDS)
    if _WARNING in squash(body):
        found.append(PreLienElement.FORECLOSURE_WARNING)
    if itemized:
        found.append(PreLienElement.ITEMIZED)
    if re.search(r"not be liable to pay the charges", flat, re.I):
        found.append(PreLienElement.PAID_ON_TIME)
    if re.search(r"request a meeting with the board", flat, re.I):
        found.append(PreLienElement.BOARD_MEETING)
    if re.search(r"meet and confer", flat, re.I):
        found.append(PreLienElement.MEET_AND_CONFER)
    if re.search(r"alternative dispute resolution", flat, re.I):
        found.append(PreLienElement.ADR)
    return tuple(found)


# A collections firm's "Account Transaction Report": document number, description (one or two lines), amount, balance, date.
_TX_ROW = re.compile(r"\n([A-Z]{2,5}-[A-Z0-9-]+|\d{8,12})\n((?:[^\n]+\n){1,2}?)([\d,]+\.\d\d)\n([\d,]+\.\d\d)\n(\d\d/\d\d/\d\d)\b")


def _transaction_report(text: str) -> tuple[Charge, ...]:
    rows = []
    previous = 0
    for m in _TX_ROW.finditer(text):
        description = squash(m.group(2))
        amount, balance = cents(m.group(3)) or 0, cents(m.group(4)) or 0
        kind = charge_kind(description)
        if balance < previous or kind in (ChargeKind.PAYMENT, ChargeKind.CREDIT):
            amount = -amount
        rows.append(Charge(parse_date(m.group(5)), description, kind, amount, balance))
        previous = balance
    return tuple(rows)


def _percent(pattern: str, text: str) -> float | None:
    v = first(pattern, text)
    try:
        return float(v) if v else None
    except ValueError:
        return None


def _own_name(context: ModelContext) -> str:
    """The association's name as the specification gives it (``Community.name``); empty without one, and then no
    letter is read as the association's own."""
    return str(getattr(context.community, "name", "") or "")


notice_former_sections = cites_former("pre-lien-former-sections", PreLienNotice)


class PreLienNoticeModel(DocumentModel):
    kind = DocumentKind.DELINQUENCY_NOTICE
    name = "pre-lien-notice"
    lens_checks = (notice_former_sections,)
    # Not the total due: a letter without its itemized statement has none to give, and ``no-itemized-statement`` says so.
    required = ("notice_date", "property_address", "sender", "elements")

    def parse(self, text: str, context: ModelContext) -> PreLienNotice | None:
        if not re.search(r"notice of default and demand for payment|pre-lien notice|civ\.?\s*§+\s*5660|notice of intent to (?:record|lien)",
                         text or "", re.I):
            return None
        body = _notice_body(text, context)
        flat = squash(body)
        r = PreLienNotice()
        r.statute_reprinted = bool(_REPRINT.search(text))
        r.title = "Pre-Lien Notice" if re.search(r"pre-lien notice", text, re.I) else \
            "Notice of Default and Demand for Payment" if re.search(r"notice of default and demand", text, re.I) else "Notice of Intent to Lien"
        head = body[:1500]
        dated = dates_in(head)
        r.notice_date = dated[0] if dated else None
        r.as_of = date_after(r"records as of", flat, window=40) or date_after(r"records as of", body, window=80)
        # A law firm the sender directory lists, named in the letter's head, sent it, unless the head is the board's own
        # letterhead (a short letter's enclosed ledger can name the firm that printed it within the same span).
        firm = sender_name(head, context.community, SourceKind.LAW_FIRM)
        own = _own_name(context)
        if firm and not (own and re.search(rf"{name_regex(own)}\s*\n\s*Board of Directors", head, re.I)):
            r.sender, r.sender_kind = firm, SenderKind.ATTORNEY
        else:
            r.sender, r.sender_kind = own, SenderKind.ASSOCIATION
        r.manager = manager_name(head, context.community)
        # The line under the ledger's title names who printed it: the collections firm or the manager.
        r.ledger_by = sender_name(first(r"Account Transaction Report\s*\n\s*([^\n]+)", text), context.community,
                                  SourceKind.LAW_FIRM, SourceKind.MANAGER)
        r.property_address = site_address(first(r"Property Address\s*(?:\n[^\n]*){0,8}", text, 0) or "") or site_address(body[:1500])
        r.building = building_of(context, r.property_address)
        r.unit = first(r"Bldg\s*\d+\s*#\s*(\d+)", text) or first(r"Walk\s*#\s*(\d+)", text)
        r.names_owner = bool(re.search(r"\bDear\s+(?!(?:member|homeowner|owner|sir|madam)\b)[A-Z]", body, re.I))
        r.days_delinquent_stated = int(first(r"more than (\d+) days delinquent", flat) or 0) or None
        r.cure_days = int(first(r"not received within (\d+) days of receipt", flat) or 0) or None
        r.foreclosure_days_after_lien = int(first(r"not received within (\d+) days of the recording", flat) or 0) or None
        r.lien_threshold = cents(first(r"exceeds (\$[\d,]+\.\d\d), by recording", flat)) if re.search(r"exceeds \$[\d,]+\.\d\d, by recording", flat) else \
            (cents(first(r"delinquent assessments exceed (\$[\d,]+)", flat)) if re.search(r"delinquent assessments exceed \$", flat) else None)
        r.collections_threshold = cents(first(r"balance exceeds (\$[\d,]+)[^.]{0,60}collections", flat)) \
            if re.search(r"balance exceeds \$[\d,]+[^.]{0,60}collections", flat) else None
        r.payment_plan_offered = bool(re.search(r"offer to set up a payment plan", flat, re.I))
        r.board_decides_lien = bool(re.search(r"decision (?:about|regarding) the recording of the lien would be made at an open board meeting", flat, re.I))
        r.foreclosure_by_agent = bool(re.search(r"collections?(?: agency)?\.\s*If (?:they|the (?:collection )?agency)\b[^.]{0,200}?\b(?:they|it) "
                                                r"(?:may|will) (?:begin|initiate|start|commence) foreclosure", flat, re.I))
        r.certified_mail = bool(re.search(r"certified mail", flat, re.I))
        r.charges = _transaction_report(text)
        itemized = len(r.charges) >= 2
        if r.charges:
            r.total_due = cents(first(r"([\d,]+\.\d\d)\s*\n\s*Total Due:", text)) if re.search(r"[\d,]+\.\d\d\s*\n\s*Total Due:", text) else r.charges[-1].balance
            r.assessments = total(r.charges, ChargeKind.ASSESSMENT)
            r.late_charges = total(r.charges, ChargeKind.LATE_CHARGE)
            r.interest = total(r.charges, ChargeKind.INTEREST)
            r.payments = -total(r.charges, ChargeKind.PAYMENT, ChargeKind.CREDIT)
            r.monthly_installment = monthly_assessment(r.charges)
        r.elements = _elements(body, flat, itemized)
        r.policy_enclosed = bool(re.search(r"collection policy, a copy of which has been enclosed", flat, re.I))
        r.policy_in_text = bool(re.search(r"ASSESSMENT COLLECTION POLICY\s*\n?\s*EFFECTIVE", text))
        if r.policy_in_text:
            policy = text[re.search(r"ASSESSMENT COLLECTION POLICY\s*\n?\s*EFFECTIVE", text).start():]
            r.policy_effective = date_after(r"EFFECTIVE:?", policy, window=40)
            pflat = squash(policy)
            r.policy_late_charge_percent = _percent(r"late charge not exceeding (\d+(?:\.\d+)?)\s*%", pflat)
            r.policy_interest_percent = _percent(r"rate of (\d+(?:\.\d+)?)\s*% per annum", pflat)
            r.former_sections = former_sections(policy)
        return r

    def check(self, r: PreLienNotice, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        for element in r.missing_elements:
            if element is PreLienElement.ITEMIZED:
                found.append(Finding("no-itemized-statement", "the text carries no itemized statement of the charges; confirm one went with "
                                     "the letter", Severity.CHECK, "CIV 5660(b)"))
            else:
                found.append(Finding("pre-lien-element-missing", f"the letter does not state the {element.value}", Severity.PROBLEM,
                                     _ELEMENT_AUTHORITY[element]))
        if r.cure_days is not None and r.cure_days < PRE_LIEN_DAYS:
            found.append(Finding("lien-sooner-than-30-days", f"the letter says a lien may be recorded if payment is not received within "
                                 f"{r.cure_days} days of receipt; the notice must come at least {PRE_LIEN_DAYS} days before a lien is recorded",
                                 Severity.PROBLEM, "CIV 5660"))
        if not r.certified_mail:
            found.append(Finding("certified-mail-not-shown", "the text does not say the notice went by certified mail; keep the mailing "
                                 "receipt", Severity.CHECK, "CIV 5660"))
        if r.notice_date:
            found.append(Finding("earliest-lien", f"no lien may be recorded before {r.notice_date + timedelta(days=PRE_LIEN_DAYS)} "
                                 f"({PRE_LIEN_DAYS} days after the notice), and only on the board's majority vote in an open meeting, "
                                 "recorded in the minutes", Severity.INFO, "CIV 5660, 5673"))
        if r.charges:
            found += ledger_findings(r.charges)
            if r.total_due is not None and r.charges[-1].balance is not None and r.total_due != r.charges[-1].balance:
                found.append(Finding("total-disagrees", f"the total due ${r.total_due / 100:,.2f} differs from the ledger's last balance "
                                     f"${r.charges[-1].balance / 100:,.2f}", Severity.PROBLEM, "CIV 5660(b)"))
            if r.assessments is not None and r.total_due is not None:
                owed = r.total_due - (r.late_charges or 0) - (r.interest or 0)
                if owed < FORECLOSURE_FLOOR:
                    found.append(Finding("below-foreclosure-floor", f"about ${owed / 100:,.2f} of the balance is assessments; under $1,800 "
                                         "(and not over 12 months delinquent) a lien may be recorded but not foreclosed", Severity.INFO, "CIV 5720(b)"))
        if r.policy_late_charge_percent and r.policy_late_charge_percent > LATE_CHARGE_PERCENT:
            found.append(Finding("policy-late-charge-over-cap", f"the enclosed policy sets a late charge of {r.policy_late_charge_percent:g}%",
                                 Severity.PROBLEM, "CIV 5650(b)(2)"))
        if r.policy_interest_percent and r.policy_interest_percent > INTEREST_CAP_PERCENT:
            found.append(Finding("policy-interest-over-cap", f"the enclosed policy sets interest at {r.policy_interest_percent:g}% a year",
                                 Severity.PROBLEM, "CIV 5650(b)(3)"))
        found.append(notice_former_sections)   # the records lens's place: the former sections cited, and where the law history puts each
        if r.policy_enclosed and not r.policy_in_text:
            found.append(Finding("policy-not-in-text", "the letter says the Assessment Collection Policy is enclosed; this file does not "
                                 "carry it", Severity.INFO, "CIV 5660(a)"))
        if r.foreclosure_by_agent:
            found.append(Finding("foreclosure-by-agent", "the letter says the collection agency may begin foreclosure; only the board may "
                                 "decide to foreclose a recorded lien, by a majority vote in executive session recorded in the next open "
                                 "meeting's minutes, and it may not delegate that decision to an agent", Severity.CHECK, "CIV 5705(c)"))
            if r.lien_threshold is None:
                found.append(Finding("foreclosure-floor-not-stated", "the letter ties foreclosure to the balance; a lien may be foreclosed "
                                     "only when the delinquent assessments alone, without late charges, fees, costs, and interest, reach "
                                     "$1,800 or are more than 12 months delinquent", Severity.CHECK, "CIV 5720(b)"))
        if r.collections_threshold is not None:
            found.append(Finding("collections-referral", f"the letter says a balance over ${r.collections_threshold / 100:,.0f} goes to "
                                 "collections; jason hands off a sheet only and never submits an account", Severity.INFO))
        return found


@dataclass
class ReimbursementNotice:
    notice_date: date | None = None
    sender: str = ""
    property_address: str = ""
    building: Building | None = None
    names_owner: bool = False
    subject: str = ""
    cause: str = ""                         # what the letter says happened
    amount: int | None = None               # cents
    contractor: str = ""
    invoices: tuple[str, ...] = ()          # the attached invoice file names
    ccr_sections: tuple[str, ...] = ()
    hearing_offered: bool = False           # a meeting date, time, and place for the owner to be heard
    common_area_damage: bool = False        # the text says the damage was to common area


class ReimbursementNoticeModel(DocumentModel):
    kind = DocumentKind.DELINQUENCY_NOTICE
    name = "reimbursement-assessment-notice"
    required = ("notice_date", "property_address", "amount")

    def parse(self, text: str, context: ModelContext) -> ReimbursementNotice | None:
        head = (text or "")[:2500]
        if not re.search(r"reimbursement assessment", head, re.I) or not re.search(r"\blevy(?:ing)?\b|\blevied\b|\bcharg(?:e|ing)\b", head, re.I) \
                or re.search(r"notice of default and demand", text or "", re.I):
            return None
        flat = squash(text)
        r = ReimbursementNotice()
        dated = dates_in(first(r"Reimbursement Assessment\s*-\s*(\w+ \d{1,2}, \d{4})", text)) or dates_in(text[:3000])
        r.notice_date = dated[0] if dated else None
        own = _own_name(context)
        r.sender = f"{own} Board of Directors".strip() if re.search(r"Board of Directors", text) else own
        r.property_address = site_address(text[:800])
        r.building = building_of(context, r.property_address)
        r.names_owner = bool(re.search(r"\bDear\s+(?!(?:member|homeowner|owner)\b)[A-Z]", text))
        r.subject = first(r"RE:\s*([^\n]+)", text)
        r.cause = first(r"(leak[^.]{0,160}\.)", flat)
        r.amount = cents(first(r"(?:totall?ing|total of|in the amount of)\s*(\$[\d,]+(?:\.\d\d)?)", flat)) \
            if re.search(r"(?:totall?ing|total of|in the amount of)\s*\$", flat) else None
        r.contractor = first(r"hired ([A-Z][\w&.,' ]+?(?:Construction|Plumbing|Restoration|Inc\.?|LLC))", flat)
        r.invoices = tuple(dict.fromkeys(re.findall(r"(Inv_[\w.-]+\.pdf)", text)))
        r.ccr_sections = tuple(dict.fromkeys(re.findall(r"CC&R\s*§\s*([\d.]+(?:\([a-z]\))?)", text)))
        r.hearing_offered = bool(re.search(r"(?:hearing|meeting)[^.]{0,80}(?:at|on) \w+ \d{1,2}, \d{4}[^.]{0,40}\d{1,2}:\d\d", flat, re.I))
        r.common_area_damage = bool(re.search(r"damage to (?:the )?common area", flat, re.I))
        return r

    def check(self, r: ReimbursementNotice, context: ModelContext) -> list[Finding]:
        found = []
        if not r.hearing_offered:
            found.append(Finding("no-hearing-notice", "the letter levies the charge without a notice of a board hearing; a charge for damage "
                                 "to common area needs 10 days' written notice of a hearing, and a written decision within 14 days, "
                                 "before it takes effect", Severity.CHECK, "CIV 5855(a), (f), (g)"))
        found.append(Finding("lien-only-if-authorized", "a charge that reimburses repair of common-area damage may become a lien only if the "
                             "governing documents authorize it; other reimbursements are collected as a debt", Severity.INFO, "CIV 5725(a)"))
        if r.amount and not r.invoices:
            found.append(Finding("no-invoices-listed", "the letter names no invoice for the amount charged", Severity.CHECK))
        return found


@dataclass
class OwnerStatement:
    statement_date: date | None = None
    issuer: str = ""                        # "PayHOA"
    association_address: str = ""
    remit_to: str = ""
    property_address: str = ""
    building: Building | None = None
    names_owner: bool = False
    charges: tuple[Charge, ...] = ()
    duplicated_lines: int = 0               # lines the text repeats (same kind, date, amount, and charge); kept once in charges
    amount_due: int | None = None
    lines_total: int | None = None          # every line the text prints, repeats included
    unique_total: int | None = None         # each line once
    late_fee_percent: float | None = None
    interest_percent_monthly: float | None = None
    late_fee_after_days: tuple[int, ...] = ()    # due date to the late fee's date, per late fee
    interest_after_days: tuple[int, ...] = ()


_STMT_ROW = re.compile(r"\n(\d{2}/\d{2}/\d{4})\n\$([\d,]+\.\d\d)(?=\n)")


class OwnerStatementModel(DocumentModel):
    kind = DocumentKind.OWNER_STATEMENT
    name = "payhoa-owner-statement"
    required = ("statement_date", "property_address", "amount_due", "charges")

    def parse(self, text: str, context: ModelContext) -> OwnerStatement | None:
        if not re.search(r"ALL CURRENT CHARGES", text or "") or not re.search(r"AMOUNT DUE", text or ""):
            return None
        r = OwnerStatement(issuer="PayHOA" if re.search(r"PayHOA", text) else "")
        r.statement_date = date_after(r"Generated on:?", text, window=30)
        r.amount_due = cents(first(r"AMOUNT DUE:\s*(\$[\d,]+\.\d\d)", text))
        r.property_address = site_address(first(r"Unit:\s*([^\n]+)", text)) or site_address(text[:600])
        r.building = building_of(context, r.property_address)
        r.names_owner = bool(re.search(r"\n[A-Z][A-Za-z.'-]+(?: [A-Z][A-Za-z.'-]+)+\n\d{4} [A-Z]", text[:600]))
        r.remit_to = first(r"return with remittance slip[^\n]*\n(?:[^\n]*\n){0,8}?(PO Box [^\n]+\n[^\n]+)", text)
        own = _own_name(context)
        r.association_address = first(rf"^{name_regex(own)}\n([^\n]+\n(?:PMB [^\n]+\n)?[^\n]+)", text, flags=re.M | re.I) if own else ""
        charges: list[Charge] = []
        keys: list[tuple] = []
        start = 0
        late_after: list[int] = []
        interest_after: list[int] = []
        for m in _STMT_ROW.finditer(text):
            block = text[start:m.start()]
            start = m.end()
            block = re.sub(r"ALL CURRENT CHARGES\s*DUE DATE\s*AMOUNT", "", block)
            lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
            if not lines:
                continue
            head = lines[-1] if len(lines) == 1 else next((ln for ln in lines if re.match(r"(Regular|Special|Late Fee|Interest|Assessment|Fine|Reimburse)", ln, re.I)), lines[0])
            detail = squash(" ".join(lines))
            posted, amount = parse_date(m.group(1)), cents(m.group(2)) or 0
            pct = first(r"(\d+(?:\.\d+)?)% \(\$[\d.,]+\) late fee", detail)
            kind = charge_kind(head)
            if kind is ChargeKind.LATE_CHARGE and pct and float(pct) < 5:
                kind = ChargeKind.INTEREST
            for_due = parse_date(first(r"due on (\d{2}/\d{2}/\d{4})", detail) or "") if "due on" in detail else None
            key = (kind, posted, amount, for_due)
            if key in keys:
                r.duplicated_lines += 1
                r.lines_total = (r.lines_total or 0) + amount
                continue
            keys.append(key)
            if for_due and posted:
                (late_after if kind is ChargeKind.LATE_CHARGE else interest_after if kind is ChargeKind.INTEREST else []).append((posted - for_due).days)
            charges.append(Charge(posted, head, kind, amount))
        r.charges = tuple(charges)
        r.unique_total = sum(c.amount for c in charges) if charges else None
        r.lines_total = (r.lines_total or 0) + (r.unique_total or 0) if charges else None
        r.late_fee_percent = float(first(r"late fee of (\d+(?:\.\d+)?)% of the remaining balance\.\s*Pay before", squash(text)) or 0) or None
        monthly = [float(v) for v in re.findall(r"late fee of (\d+(?:\.\d+)?)% of the remaining balance, repeating every month", squash(text))]
        r.interest_percent_monthly = monthly[0] if monthly else None
        r.late_fee_after_days = tuple(late_after)
        r.interest_after_days = tuple(interest_after)
        return r

    def check(self, r: OwnerStatement, context: ModelContext) -> list[Finding]:
        found = ledger_findings(r.charges)
        due = r.amount_due
        if r.duplicated_lines and due is not None and due == r.lines_total:
            found.append(Finding("duplicate-charges-billed", f"{r.duplicated_lines} charge line(s) repeat an earlier line and the amount due "
                                 "counts both; a second late fee on one installment exceeds the 10 percent cap", Severity.PROBLEM, "CIV 5650(b)(2)"))
        elif r.duplicated_lines and due is not None and due == r.unique_total:
            found.append(Finding("repeated-lines-in-text", f"the text repeats {r.duplicated_lines} line(s); the amount due counts each once "
                                 "(the PDF's text layer is doubled)", Severity.INFO))
        elif r.duplicated_lines:
            found.append(Finding("duplicate-charges", f"{r.duplicated_lines} charge line(s) repeat an earlier line; confirm each was billed "
                                 "once", Severity.CHECK, "CIV 5650(b)(2)"))
        if due is not None and r.unique_total is not None and due not in (r.unique_total, r.lines_total):
            found.append(Finding("lines-disagree-with-amount-due", f"the charges listed add to ${r.unique_total / 100:,.2f}; the statement asks "
                                 f"${due / 100:,.2f} (earlier balances or payments may not be listed)", Severity.CHECK))
        if r.late_fee_percent and r.late_fee_percent > LATE_CHARGE_PERCENT:
            found.append(Finding("late-fee-rate-over-cap", f"the statement sets a {r.late_fee_percent:g}% late fee", Severity.PROBLEM, "CIV 5650(b)(2)"))
        if r.interest_percent_monthly and r.interest_percent_monthly * 12 > INTEREST_CAP_PERCENT + 0.05:
            found.append(Finding("interest-rate-over-cap", f"{r.interest_percent_monthly:g}% a month is over 12 percent a year", Severity.PROBLEM,
                                 "CIV 5650(b)(3)"))
        early = [d for d in r.late_fee_after_days if d < DELINQUENT_AFTER_DAYS]
        if early:
            found.append(Finding("late-fee-before-delinquent", f"{len(early)} late fee(s) dated fewer than {DELINQUENT_AFTER_DAYS} days after the "
                                 "installment was due", Severity.PROBLEM, "CIV 5650(b)"))
        early_interest = [d for d in r.interest_after_days if d < INTEREST_AFTER_DAYS]
        if early_interest:
            found.append(Finding("interest-before-30-days", f"{len(early_interest)} interest charge(s) dated fewer than {INTEREST_AFTER_DAYS} days "
                                 "after the installment was due", Severity.PROBLEM, "CIV 5650(b)(3)"))
        return found


@dataclass(frozen=True)
class AccountHistory:
    """One unit's ledger on the manager's report. No owner name and no account number."""

    property_address: str
    building: Building | None
    unit: str
    first_posted: date | None
    last_posted: date | None
    entries: int
    monthly_installment: int | None
    assessments: int
    payments: int
    late_fees: int
    late_fee_count: int
    interest: int
    credits: int
    balance: int | None
    aging: tuple[int, ...] = ()             # current, 30-59, 60-89, over 90 days (cents)
    balance_breaks: int = 0                 # lines whose running balance does not follow from the one before
    early_late_fees: int = 0                # late fees posted fewer than 15 days after the installment's due date
    over_cap_late_fees: int = 0
    several_installment_late_fees: int = 0
    high_interest: int = 0


_SUMMED = ("entries", "assessments", "payments", "late_fees", "late_fee_count", "interest", "credits", "balance_breaks", "early_late_fees",
           "over_cap_late_fees", "several_installment_late_fees", "high_interest")


def _continue(prev: AccountHistory, more: AccountHistory) -> AccountHistory:
    """An account whose ledger runs onto another page: the sums add, the later page's balance and aging stand."""
    return dataclasses.replace(more, first_posted=prev.first_posted or more.first_posted, unit=more.unit or prev.unit,
                               monthly_installment=prev.monthly_installment or more.monthly_installment,
                               **{f: getattr(prev, f) + getattr(more, f) for f in _SUMMED})


@dataclass
class OwnerHistory:
    manager: str = ""
    report_date: date | None = None
    names_owner: bool = False
    accounts: tuple[AccountHistory, ...] = field(default_factory=tuple)
    account_count: int = 0
    total_balance: int | None = None
    accounts_with_balance: int = 0
    accounts_over_90_days: int = 0


_HIST_ROW = re.compile(r"\n(ASSOC ASSESSMENT|SPECIAL ASSESSMENT|PAYMENT|LATE FEE|LateFee Credit|Interest - Delinquent Accts|[A-Z][A-Za-z/ -]{2,40})\n"
                       r"(\d{1,2}/\d{1,2}/\d{4})\n(-?[\d,]+\.\d\d)\n(-?[\d,]+\.\d\d)")
_AGING = re.compile(r"Balance:\s*\n(-?[\d,]+\.\d\d)\n(-?[\d,]+\.\d\d)\n(-?[\d,]+\.\d\d)\n(-?[\d,]+\.\d\d)\n(-?[\d,]+\.\d\d)\n(\d{1,2}/\d{1,2}/\d{4})")


def _signed(v: str) -> int:
    c = cents(v.replace("-", "")) or 0
    return -c if v.strip().startswith("-") else c


def _account(block: str, context: ModelContext) -> AccountHistory | None:
    address = site_address(first(r"Property Address:\s*\n?([^\n]+)", block))
    rows = list(_HIST_ROW.finditer(block))
    if not address and not rows:
        return None
    charges = []
    breaks = early = 0
    previous: int | None = None
    due_dates: list[date] = []
    for m in rows:
        code, posted, amount, balance = m.group(1).strip(), parse_date(m.group(2)), _signed(m.group(3)), _signed(m.group(4))
        kind = charge_kind(code)
        if code.upper() == "LATE FEE":
            kind = ChargeKind.LATE_CHARGE
        if previous is not None and previous + amount != balance:
            breaks += 1
        previous = balance
        if kind is ChargeKind.ASSESSMENT and posted:
            due_dates.append(posted)
        if kind is ChargeKind.LATE_CHARGE and posted:
            due = max((d for d in due_dates if d <= posted), default=None)
            if due and (posted - due).days < DELINQUENT_AFTER_DAYS:
                early += 1
        charges.append(Charge(posted, code, kind, amount, balance))
    aging_m = _AGING.search(block)
    aging = tuple(_signed(aging_m.group(i)) for i in range(2, 6)) if aging_m else ()
    balance = _signed(aging_m.group(1)) if aging_m else (charges[-1].balance if charges else None)
    monthly = monthly_assessment(charges)
    over, several, high = ledger_counts(charges)
    dates = [c.posted for c in charges if c.posted]
    return AccountHistory(
        property_address=address, building=building_of(context, address), unit=first(r"Property Address:\s*\n?[^\n]*?\s(\d{1,2})\s*$", block, flags=re.M | re.I),
        first_posted=min(dates) if dates else None, last_posted=max(dates) if dates else None, entries=len(charges),
        monthly_installment=monthly, assessments=total(charges, ChargeKind.ASSESSMENT), payments=-total(charges, ChargeKind.PAYMENT),
        late_fees=total(charges, ChargeKind.LATE_CHARGE), late_fee_count=sum(1 for c in charges if c.kind is ChargeKind.LATE_CHARGE),
        interest=total(charges, ChargeKind.INTEREST), credits=-total(charges, ChargeKind.CREDIT), balance=balance, aging=aging,
        balance_breaks=breaks, early_late_fees=early, over_cap_late_fees=over, several_installment_late_fees=several, high_interest=high)


class OwnerHistoryModel(DocumentModel):
    kind = DocumentKind.OWNER_HISTORY
    name = "helsing-owner-history"
    required = ("report_date", "accounts")

    def parse(self, text: str, context: ModelContext) -> OwnerHistory | None:
        if not re.search(r"Property Address:", text or "") or not re.search(r"ASSOC ASSESSMENT|Balance Forward", text or ""):
            return None
        r = OwnerHistory(manager=manager_name(text, context.community))
        starts = [m.start() for m in re.finditer(r"Property Address:", text)]
        accounts = []
        for i, s in enumerate(starts):
            # Each account's block runs from a little before its address label to the next account's label.
            block = text[max(0, s - 120): starts[i + 1] if i + 1 < len(starts) else len(text)]
            block = block[block.find("Property Address:"):]
            account = _account(block, context)
            if account:
                accounts.append(account)
        # A multi-page account repeats its header; the same address twice is one account continued.
        merged: dict[str, AccountHistory] = {}
        for a in accounts:
            key = a.property_address or f"#{len(merged)}"
            if key in merged and not merged[key].aging:
                merged[key] = _continue(merged[key], a)
            else:
                merged[key] = a
        r.accounts = tuple(merged.values())
        r.account_count = len(r.accounts)
        tail = dates_in(text[-60:])
        r.report_date = tail[-1] if tail else None
        balances = [a.balance for a in r.accounts if a.balance is not None]
        r.total_balance = sum(balances) if balances else None
        r.accounts_with_balance = sum(1 for b in balances if b > 0)
        r.accounts_over_90_days = sum(1 for a in r.accounts if len(a.aging) == 4 and a.aging[3] > 0)
        # The manager's letterhead ends with its city line; the owner's name is the next line (the owner's own city
        # line is followed by "Property Address:").
        r.names_owner = bool(re.search(r"[A-Za-z .]+, [A-Z]{2} \d{5}(?:-\d{4})?\n\s*(?!Property Address|Account)[A-Z][a-z]+", text))
        return r

    def check(self, r: OwnerHistory, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        early = sum(a.early_late_fees for a in r.accounts)
        if early:
            found.append(Finding("late-fee-before-delinquent", f"{early} late fee(s) posted fewer than {DELINQUENT_AFTER_DAYS} days after the "
                                 "installment's due date (the ledger posts on the 15th an installment due the 1st)", Severity.CHECK, "CIV 5650(b)"))
        over = sum(a.over_cap_late_fees for a in r.accounts)
        if over:
            found.append(Finding("late-charge-over-cap", f"{over} late fee(s) exceed the greater of 10 percent of the balance before "
                                 "them or $10; a lump may gather several months' charges", Severity.CHECK, "CIV 5650(b)(2)"))
        several = sum(a.several_installment_late_fees for a in r.accounts)
        if several:
            found.append(Finding("late-charge-several-installments", f"{several} late fee(s) exceed 10 percent of one installment; each "
                                 "should cover more than one delinquent installment", Severity.CHECK, "CIV 5650(b)(2)"))
        high = sum(a.high_interest for a in r.accounts)
        if high:
            found.append(Finding("interest-over-cap", f"{high} account(s) carry an interest line over one month at 12 percent a year on the "
                                 "balance before it", Severity.CHECK, "CIV 5650(b)(3)"))
        aging_off = [a for a in r.accounts if len(a.aging) == 4 and a.balance is not None and sum(a.aging) != a.balance]
        if aging_off:
            found.append(Finding("aging-disagrees", f"{len(aging_off)} account(s) whose aging buckets do not add to the balance", Severity.CHECK))
        breaks = sum(a.balance_breaks for a in r.accounts)
        if breaks:
            found.append(Finding("running-balance-breaks", f"{breaks} ledger line(s) whose running balance does not follow from the line "
                                 "before (a page break or the text layer may cause it)", Severity.CHECK))
        if r.accounts_over_90_days:
            found.append(Finding("over-90-days", f"{r.accounts_over_90_days} account(s) carry a balance over 90 days old; a lien needs the "
                                 "pre-lien notice at least 30 days before and the board's vote", Severity.INFO, "CIV 5660, 5673"))
        units = context.community.units() if context.community is not None and hasattr(context.community, "units") else ()
        if r.account_count > 1 and units and r.account_count > len(units):
            found.append(Finding("more-accounts-than-units", f"{r.account_count} accounts for {len(units)} units (prior owners' accounts may "
                                 "be listed)", Severity.INFO))
        return found


register(PreLienNoticeModel())
register(ReimbursementNoticeModel())
register(OwnerStatementModel())
register(OwnerHistoryModel())

__all__ = ["PreLienElement", "SenderKind", "PreLienNotice", "PreLienNoticeModel", "ReimbursementNotice", "ReimbursementNoticeModel",
           "OwnerStatement", "OwnerStatementModel", "AccountHistory", "OwnerHistory", "OwnerHistoryModel"]
