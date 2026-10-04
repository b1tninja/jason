"""Owner-transfer and membership records: an escrow company's resale document order, the association's forms, and the
membership list.

The law shapes the escrow order. On a written request the association provides the CIV 4525 documents within 10 days of
the mailing or delivery of the request (4530(a)(1)); before it processes the request it gives an estimate of its fees on
the CIV 4528 form (4530(b)(2)); the fees are its actual cost, stated and billed apart from other fees (4530(b)(1), (4));
and beyond those and the cost of changing its records it charges no fee on a transfer (4575).

The membership list is a record the association keeps: each member's name, property address, mailing address, and email,
leaving out members who opted out of sharing (CIV 5200(a)(9), 5220). It is confidential here: the record counts rows and
names columns and never holds a member's name, address, or email.

The forms are the association's blanks (resident registration, home improvement application, special-meeting
petition, towing authorization) and a filled one, such as its own change of mailing address with the County Assessor.
An architectural application answers to CIV 4765: a decision in writing, and for a disapproval the reasons and how to
ask the board to reconsider (4765(a)(4), (5)).
"""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.invoices import parse_date
from jason.community.models.legal_shared import (
    apns_in,
    building_number,
    building_of,
    days_between,
    known_parcels,
    site_address,
    unit_count,
)
from jason.community.reviews import AS_OF
from jason.community.symbols import Building, DocumentKind

DOCUMENT_DAYS = 10      # CIV 4530(a)(1)


@dataclass
class EscrowRequest:
    association: str = ""
    property_address: str = ""
    building: Building | None = None
    requester: str = ""                  # the escrow or title company
    order_type: str = ""                 # "RESALE", "REFINANCE"
    escrow_number: str = ""
    ordered: date | None = None
    paid: date | None = None
    expected_completion: date | None = None
    completed: date | None = None
    estimated_closing: date | None = None
    sales_price: int | None = None       # cents
    names_seller: bool = False
    names_buyer: bool = False
    buyer_occupant: bool | None = None
    va_loan: bool | None = None
    documents: tuple[str, ...] = ()      # the 4525 documents the order lists, when it lists them
    fee: int | None = None               # cents, when the order prints one


def _field(label: str, text: str) -> str:
    """A form export prints each label then its value on the next line (or after a colon on the same line)."""
    m = re.search(r"(?:^|\n)" + label + r"\s*:?[ \t]*([^\n]*)\n?([^\n]*)", text, re.I)
    if not m:
        return ""
    value = m.group(1).strip() or m.group(2).strip()
    return value


def _yes(value: str) -> bool | None:
    v = value.strip().lower()
    return True if v.startswith("y") else False if v.startswith("n") else None


@AS_OF.check("resale-documents-overdue", EscrowRequest, fields=("ordered", "completed"))
def documents_overdue(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: an order that shows no completion, once the days to deliver the documents have run."""
    if days_between(r.ordered, r.completed) is None and r.ordered and as_of > r.ordered + timedelta(days=DOCUMENT_DAYS):
        return [Finding("documents-overdue", f"no completion is shown and {DOCUMENT_DAYS} days from the order passed on "
                        f"{r.ordered + timedelta(days=DOCUMENT_DAYS)}", Severity.CHECK, "CIV 4530(a)(1)")]
    return []


class EscrowRequestModel(DocumentModel):
    kind = DocumentKind.ESCROW_REQUEST
    name = "resale-document-order"
    required = ("property_address", "requester", "ordered")
    lens_checks = (documents_overdue,)

    def parse(self, text: str, context: ModelContext) -> EscrowRequest | None:
        if not re.search(r"Requestor Information|Escrow/File Number|CHARGES FOR DOCUMENTS PROVIDED AS REQUIRED BY SECTION 4525|"
                         r"resale (?:package|document|certificate) (?:order|request)", text or "", re.I):
            return None
        r = EscrowRequest()
        r.association = _field(r"Association Name", text).lstrip(": ")
        r.property_address = site_address(_field(r"Street Address", text)) or site_address(text)
        r.building = building_of(context, r.property_address)
        r.requester = _field(r"Company", text)
        r.order_type = _field(r"Order Type", text).upper()
        r.escrow_number = _field(r"Escrow/File Number", text) or _field(r"Escrow Number", text)
        r.ordered = parse_date(_field(r"Date Ordered", text) or "")
        r.paid = parse_date(_field(r"Date Paid", text) or "")
        r.expected_completion = parse_date(_field(r"Expected Completion", text) or "")
        r.completed = parse_date((_field(r"Actual Completion", text) or "").split(" ")[0])
        r.estimated_closing = parse_date(_field(r"Estimated Closing Date", text) or "")
        price = re.sub(r"[^\d.]", "", _field(r"Sales Price", text))
        r.sales_price = int(float(price) * 100) if price else None
        seller = text[text.find("Seller Information"):text.find("Buyer Information")] if "Seller Information" in text else ""
        buyer = text[text.find("Buyer Information"):text.find("Transaction Information")] if "Buyer Information" in text else ""
        r.names_seller = bool(re.search(r"Name\s*\n?\s*[A-Z][a-z]+", seller))
        r.names_buyer = bool(re.search(r"Name\s*\n?\s*[A-Z][a-z]+", buyer))
        r.buyer_occupant = _yes(_field(r"Is Buyer Occupant\?", text))
        r.va_loan = _yes(_field(r"Veterans Affairs Loan\?", text))
        r.documents = tuple(dict.fromkeys(re.findall(r"(CC&Rs|Bylaws|Articles of Incorporation|Operating Rules|Budget|Reserve Study|"
                                                     r"Insurance Summary|Minutes|Financial Statement|Collection Policy)", text)))
        fee = first(r"(?:Total Fees?|Fee for Document|Order Total)\s*:?\s*\$\s*([\d,]+\.\d\d)", text)
        r.fee = int(round(float(fee.replace(",", "")) * 100)) if fee else None
        return r

    def check(self, r: EscrowRequest, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        took = days_between(r.ordered, r.completed)
        if took is not None:
            severity = Severity.PROBLEM if took > DOCUMENT_DAYS else Severity.INFO
            found.append(Finding("documents-days", f"the order was completed {took} days after it was placed", severity, "CIV 4530(a)(1)"))
        found.append(documents_overdue)   # the as-of lens's place: no completion shown and the days to deliver have run
        if r.fee is None:
            found.append(Finding("fee-not-in-text", "the order shows no fee; the fee estimate goes on the CIV 4528 form before the "
                                 "request is processed", Severity.CHECK, "CIV 4530(b)(2)"))
        if not r.documents:
            found.append(Finding("documents-not-listed", "the order does not list the documents requested (CIV 4525(a) has eleven items)",
                                 Severity.INFO, "CIV 4525(a)"))
        found.append(Finding("transfer-fee-limit", "on a transfer the association may charge only its cost to change its records and the "
                             "4530 document fee", Severity.INFO, "CIV 4575"))
        found.append(Finding("record-change", f"a sale of {r.property_address or 'the unit'} is pending; the owner roll and mailing "
                             "address change at closing", Severity.INFO))
        return found


class FormType(Enum):
    RESIDENT_REGISTRATION = "resident registration"
    ARCHITECTURAL_APPLICATION = "home improvement (architectural) application"
    SPECIAL_MEETING_PETITION = "petition for a special meeting"
    TOWING_AUTHORIZATION = "towing authorization"
    ASSESSOR_ADDRESS_CHANGE = "county assessor change of mailing address"
    OTHER = "other"


_FORM_TYPES = ((FormType.RESIDENT_REGISTRATION, r"RESIDENT REGISTRATION FORM"),
               (FormType.ARCHITECTURAL_APPLICATION, r"HOME IMPROVEMENT REQUEST|ARCHITECTURAL (?:REVIEW|IMPROVEMENT) (?:APPLICATION|REQUEST)"),
               (FormType.SPECIAL_MEETING_PETITION, r"Petition requesting a special meeting"),
               (FormType.TOWING_AUTHORIZATION, r"Towing Authorization"),
               (FormType.ASSESSOR_ADDRESS_CHANGE, r"CHANGE OF MAILING ADDRESS"))


@dataclass
class Form:
    form_type: FormType = FormType.OTHER
    title: str = ""
    issuer: str = ""                     # the association, or the agency whose form it is
    filled: bool = False
    carries_personal_data: bool = False
    return_days: int | None = None       # "complete and return ... within thirty (30) days"
    ccr_sections: tuple[str, ...] = ()
    bylaw_sections: tuple[str, ...] = ()
    statutes: tuple[str, ...] = ()       # outside codes the form cites ("CVC 22658")
    signature_lines: int = 0
    # special-meeting petition
    purpose: str = ""
    threshold_percent: float | None = None
    signatures_required: int | None = None
    units_listed: int = 0
    building_mismatches: int = 0
    # architectural application
    lead_days: int | None = None         # "submitted at least thirty (30) days before"
    states_response_time: bool = False
    describes_reconsideration: bool = False
    # assessor change of address
    apns: tuple[str, ...] = ()
    property_address: str = ""
    new_mailing_address: str = ""
    effective: date | None = None
    signed: date | None = None


class FormModel(DocumentModel):
    kind = DocumentKind.FORM
    name = "association-form"
    required = ("title",)

    def parse(self, text: str, context: ModelContext) -> Form | None:
        form_type = next((t for t, pattern in _FORM_TYPES if re.search(pattern, text or "", re.I)), None)
        if form_type is None:
            # An unknown form still titles itself as one in its first lines.
            if not re.search(r"^[^\n]{0,60}\b(?:form|application|petition|authorization|request)\s*$", (text or "")[:400], re.I | re.M):
                return None
            form_type = FormType.OTHER
        flat = squash(text)
        r = Form(form_type=form_type)
        r.title = first(dict(_FORM_TYPES).get(form_type, r"^([^\n]{5,80})"), text, 0) if form_type is not FormType.OTHER else first(r"^\s*([^\n]{5,80})", text)
        r.title = r.title.title() if r.title.isupper() else r.title
        r.issuer = "Sacramento County Assessor" if re.search(r"COUNTY ASSESSOR", text) else "Mystique Community Association"
        underscores = len(re.findall(r"_{10,}", text))
        contact = bool(re.search(r"[\w.]+@[\w.]+\.\w{2,}|\(\d{3}\)\s*\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b", text))
        if form_type is FormType.ASSESSOR_ADDRESS_CHANGE:
            cleaned = text.replace("_", "")
            r.apns = apns_in(cleaned)
            r.filled = bool(r.apns)
            r.property_address = site_address(cleaned)
            mailing = re.search(r"New Mailing Address as of[^\n]*\n([^\n]+)\n(?:Address 1[^\n]*\n)?([^\n]+)", cleaned)
            if mailing:
                r.new_mailing_address = squash(f"{mailing.group(1)} {mailing.group(2) if not mailing.group(2).startswith('Address') else ''}")
            m = re.search(r"New Mailing Address as of\s*([^\n]*?)\s*\(Date\)", cleaned)
            r.effective = next(iter(dates_in(re.sub(r"\s*/\s*", "/", m.group(1)))), None) if m else None
            r.signed = next(iter(dates_in(re.sub(r"\s*/\s*", "/", flat[flat.find("Property Owner or Agent"):][:200]) if "Property Owner or Agent" in flat else "")), None)
            # The association's own filing carries its officer's contact, not a member's.
            r.carries_personal_data = contact and not re.search(r"Property Owner:[^\n]*\n(?:[^\n]*\n){0,2}\s*MYSTIQUE COMMUNITY ASSOCIATION", cleaned)
        elif form_type is FormType.RESIDENT_REGISTRATION:
            r.filled = underscores < 3
            r.carries_personal_data = r.filled
            if r.filled:
                # A handwritten address rarely survives OCR; the file is named for the unit it registers.
                r.property_address = site_address(text) or site_address(context.name)
        else:
            r.filled = contact
            r.carries_personal_data = contact
        days = first(r"within (?:\w+ )?\((\d+)\) days", flat) or first(r"within (\d+) days", flat)
        r.return_days = int(days) if days and form_type is FormType.RESIDENT_REGISTRATION else None
        r.ccr_sections = tuple(dict.fromkeys(re.findall(r"(?:CC&Rs?\s*)?§\s*(\d+\.\d+(?:\([a-z]\))?(?:\([ivx]+\))?)", flat)))
        r.bylaw_sections = tuple(dict.fromkeys(re.findall(r"\n(\d\.\d)\s*-\s*[A-Z]", text))) if re.search(r"BYLAWS", text) else ()
        r.statutes = tuple(dict.fromkeys(f"CVC {s}" for s in re.findall(r"(?:Vehicle Code|CVC)\s*§\s*(\d{5})", flat)))
        r.signature_lines = len(re.findall(r"\bSignature\b", text, re.I))
        if form_type is FormType.SPECIAL_MEETING_PETITION:
            r.purpose = first(r"Purpose of meeting\s*\n(?:[^\n]*\n)*?([A-Z][^\n]{3,80})\s*\n\s*Mystique Community Association", text) or \
                first(r"\n([A-Z][a-z]+(?: [a-z]+)* [A-Z]?[a-z]+ Change)\s*\n", text)
            pct = first(r"at least [\w ]+ percent \((\d+(?:\.\d+)?)%\)", flat) or first(r"(\d+(?:\.\d+)?)% of total voting power", flat)
            r.threshold_percent = float(pct) if pct else None
            req = first(r"\(\s*(\d+) member signatures required", flat)
            r.signatures_required = int(req) if req else None
            listed = 0
            parts = re.split(r"\nBuilding (\d)\n", text)
            for number, block in zip(parts[1::2], parts[2::2]):
                header = building_number(number)
                for line in re.findall(r"\n(\d{4} [A-Z]+ (?:DR|WALK|LN))(?: # \d+)?", block):
                    listed += 1
                    spec = building_of(context, site_address(line))
                    if spec and header and spec != header:
                        r.building_mismatches += 1
            r.units_listed = listed
        if form_type is FormType.ARCHITECTURAL_APPLICATION:
            lead = first(r"at least \w+ \((\d+)\) days before", flat)
            r.lead_days = int(lead) if lead else None
            r.states_response_time = bool(re.search(r"(?:respond|decision|decide|act)[^.]{0,60}within \w+ (?:\(\d+\) )?days", flat, re.I))
            r.describes_reconsideration = bool(re.search(r"reconsider", flat, re.I))
        return r

    def check(self, r: Form, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.carries_personal_data:
            found.append(Finding("personal-data", "a completed form carries a resident's contact details; keep the file confidential and "
                                 "out of shared folders", Severity.CHECK, "CIV 5215(a)(4)"))
        if r.form_type is FormType.SPECIAL_MEETING_PETITION:
            units = unit_count(context)
            if r.threshold_percent and units:
                needed = math.ceil(units * r.threshold_percent / 100)
                if r.signatures_required is not None and r.signatures_required != needed:
                    found.append(Finding("signature-count", f"the petition asks for {r.signatures_required} signatures; "
                                         f"{r.threshold_percent:g}% of {units} units is {needed}", Severity.CHECK))
            if units and r.units_listed and r.units_listed != units:
                found.append(Finding("units-listed", f"the signature pages list {r.units_listed} units; the specification has {units}",
                                     Severity.CHECK))
            if r.building_mismatches:
                found.append(Finding("building-pages", f"{r.building_mismatches} address(es) sit on a building page the specification does not "
                                     "place them in", Severity.CHECK))
        if r.form_type is FormType.ARCHITECTURAL_APPLICATION:
            if not r.states_response_time:
                found.append(Finding("no-response-time", "the application does not state the maximum time for the association's response; "
                                     "the procedure in the governing documents must", Severity.CHECK, "CIV 4765(a)(1)"))
            if not r.describes_reconsideration:
                found.append(Finding("no-reconsideration", "the decision block does not describe how to ask the board to reconsider a "
                                     "disapproval, which a written disapproval must", Severity.CHECK, "CIV 4765(a)(4), (5)"))
        if r.form_type is FormType.ASSESSOR_ADDRESS_CHANGE:
            parcels = known_parcels(context)
            if parcels and r.apns:
                outside = [a for a in r.apns if a not in parcels]
                if outside:
                    found.append(Finding("parcel-not-in-spec", f"APN {outside[0]} is not one of the association's parcels in the "
                                         "specification", Severity.CHECK))
            current = _current_mailing(context)
            if current and r.new_mailing_address:
                if all(word in r.new_mailing_address.upper() for word in current):
                    found.append(Finding("mailing-address-current", "the new mailing address is the association's current one",
                                         Severity.INFO))
                else:
                    found.append(Finding("mailing-address-not-current", f"the form gives {r.new_mailing_address!r}; the specification's "
                                         "current mailing address differs", Severity.CHECK))
        return found


def _current_mailing(context: ModelContext) -> tuple[str, ...]:
    """Words the association's current mailing address carries ('901 H ST', 'PMB 188'), from the specification."""
    addresses = getattr(context.community, "mail_addresses", None)
    if addresses is None:
        return ()
    for row in addresses():
        if getattr(getattr(row, "kind", None), "name", "") == "CURRENT":
            words = tuple(getattr(row, "words", ())[:1]) + tuple(getattr(row, "requires", ())[:1])
            return tuple(w.upper() for w in words)
    return ()


@dataclass
class MembershipList:
    as_of: date | None = None            # the file's period, or the latest date a row carries
    rows: int = 0
    columns: tuple[str, ...] = ()        # the header's field names (never a row's values)
    has_name: bool = False
    has_property_address: bool = False
    has_mailing_address: bool = False
    has_email: bool = False
    rows_with_email: int = 0
    rows_with_mailing_address: int = 0
    rows_rented: int | None = None
    opt_out_column: bool = False
    extra_columns: tuple[str, ...] = ()  # fields beyond the 5200(a)(9) four
    distinct_properties: int = 0


_NAME_COLS = re.compile(r"^(?:name|owner|owner name|grantee|member|first name|last name)$", re.I)
_PROPERTY_COLS = re.compile(r"^(?:property address|unit address|address|site address)$", re.I)
_MAILING_COLS = re.compile(r"^(?:mailing address|mail address|address_line_1)$", re.I)
_EMAIL_COLS = re.compile(r"^e-?mail(?: address)?$", re.I)
_OPT_OUT = re.compile(r"opt.?out|do not share|share", re.I)


class MembershipListModel(DocumentModel):
    kind = DocumentKind.MEMBERSHIP_LIST
    name = "membership-list"
    required = ("rows", "columns")

    def parse(self, text: str, context: ModelContext) -> MembershipList | None:
        if not text or "," not in text.split("\n", 1)[0]:
            return None
        try:
            table = list(csv.reader(io.StringIO(text)))
        except csv.Error:
            return None
        if len(table) < 2:
            return None
        header = [h.strip() for h in table[0]]
        if not any(_PROPERTY_COLS.match(h) or _EMAIL_COLS.match(h) for h in header):
            return None
        body = [row for row in table[1:] if any(cell.strip() for cell in row)]
        r = MembershipList(rows=len(body), columns=tuple(h for h in header if h))
        index = {h: i for i, h in enumerate(header)}

        def col(pattern: re.Pattern) -> int | None:
            return next((i for h, i in index.items() if pattern.match(h)), None)

        name_i, prop_i, mail_i, email_i = col(_NAME_COLS), col(_PROPERTY_COLS), col(_MAILING_COLS), col(_EMAIL_COLS)
        r.has_name, r.has_property_address = name_i is not None, prop_i is not None
        r.has_mailing_address, r.has_email = mail_i is not None, email_i is not None

        def filled(row: list[str], i: int | None) -> bool:
            return i is not None and i < len(row) and bool(row[i].strip())

        r.rows_with_email = sum(1 for row in body if filled(row, email_i))
        r.rows_with_mailing_address = sum(1 for row in body if filled(row, mail_i))
        rented = index.get("Rented")
        if rented is not None:
            r.rows_rented = sum(1 for row in body if rented < len(row) and row[rented].strip().upper() in ("TRUE", "YES", "Y", "1"))
        r.opt_out_column = any(_OPT_OUT.search(h) for h in header)
        known = {i for i in (name_i, prop_i, mail_i, email_i) if i is not None}
        r.extra_columns = tuple(h for i, h in enumerate(header) if h and i not in known)
        r.distinct_properties = len({row[prop_i].strip().upper() for row in body if filled(row, prop_i)}) if prop_i is not None else 0
        r.as_of = parse_date(context.period) if context.period and re.fullmatch(r"\d{4}-\d{2}-\d{2}", context.period) else None
        if r.as_of is None and "Date" in index:
            dated = [parse_date(row[index["Date"]]) for row in body if index["Date"] < len(row) and row[index["Date"]].strip()]
            dated = [d for d in dated if d]
            r.as_of = max(dated) if dated else None
        return r

    def check(self, r: MembershipList, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        units = unit_count(context)
        if units and r.distinct_properties and r.distinct_properties != units:
            found.append(Finding("property-count", f"the list covers {r.distinct_properties} properties; the specification has {units} units",
                                 Severity.CHECK))
        missing = [label for label, present in (("name", r.has_name), ("property address", r.has_property_address),
                                                ("mailing address", r.has_mailing_address), ("email", r.has_email)) if not present]
        if missing:
            found.append(Finding("list-fields-missing", f"the list has no {', '.join(missing)} column", Severity.CHECK, "CIV 5200(a)(9)"))
        if not r.opt_out_column:
            found.append(Finding("no-opt-out-marker", "the list does not mark members who opted out of sharing; a copy given to a member "
                                 "must leave them out", Severity.CHECK, "CIV 5200(a)(9), 5220"))
        if r.extra_columns:
            found.append(Finding("extra-columns", f"the list carries {len(r.extra_columns)} columns beyond the four the records statute names; "
                                 "strip them from any copy shared with a member", Severity.INFO, "CIV 5200(a)(9), 5215(a)(4)"))
        found.append(Finding("confidential", "the list holds members' personal data; the member who asks for it must state a purpose "
                             "reasonably related to membership", Severity.INFO, "CIV 5225"))
        return found


register(EscrowRequestModel())
register(FormModel())
register(MembershipListModel())

__all__ = ["EscrowRequest", "EscrowRequestModel", "FormType", "Form", "FormModel", "MembershipList", "MembershipListModel"]
