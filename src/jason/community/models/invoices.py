"""Vendor invoices, receipts, and statements for services: what was billed, by whom, to whom, and for how much.

An invoice or receipt for a payment the association made is an "enhanced association record" (CIV 5200(b)), open to a
member's inspection for the current fiscal year and the two before it (CIV 5210(a)(1)); the board's written approval
of an invoice is a record too (CIV 5200(a)(5)). The law says nothing about an invoice's content, so the checks here are
the document's own consistency: the line items add to what it asks, the dates are in order, it has a number, and it is
billed to the association.

``InvoiceModel`` wraps ``jason.community.invoices.read_invoice`` with the vendor layouts in
``jason.community.invoice_formats`` (one ``InvoiceFormat`` row per vendor the general labels get wrong) and the vendor
names the specification knows (``Community.senders()``, the vendor portals, the format rows). A vendor layout whose
record says more than an invoice does gets its own model, registered first: Philadelphia Indemnity's NFIP flood
renewal notice (``FloodPremiumNoticeModel``), whose policy number and property location are checked against the
specification's flood policies.

``TaxReturnModel`` is a light reader for the preparer's filing letter and the returns behind it (Form 1120-H, CA Form
100 and 199, Form 7004 extensions): the tax year, each form's result, the deadlines, and the signature forms. State and
federal tax returns are association records (CIV 5200(a)(6)).

Amounts are integer cents. A field no pattern finds stays empty.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from functools import lru_cache
from typing import Any

from jason.community.base import alternation, street_words
from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    amount_after,
    cents,
    dates_in,
    register,
    squash,
)
from jason.community.invoice_formats import INVOICE_FORMATS
from jason.community.invoices import InvoiceFormat, parse_date, read_invoice, readable
from jason.community.reviews import AS_OF
from jason.community.symbols import Building, DocumentKind, Street

RECORD_AUTHORITY = "CIV 5200(b), 5210(a)(1)"
TAX_RECORD_AUTHORITY = "CIV 5200(a)(6), 5210(a)(1)"

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
_DATE = (r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}-\d{1,2}-\d{4}|" + _MONTH + r" \d{1,2},? \d{4}|\d{1,2}[ -]" + _MONTH
         + r",?[ -]\d{4})")
# Date labels the general reader does not know, in the order they are trusted.
_MORE_DATE_LABELS = (r"date of issue", r"order placed", r"statement date", r"posted date", r"receipt date", r"payment date",
                     r"invoice date", r"issued")
_NUMERIC = re.compile(r"^\(?-?\$?\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,4}))?\)?$")


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: float
    rate_cents: int
    amount_cents: int


@dataclass
class InvoiceRecord:
    vendor: str = ""
    number: str = ""
    invoice_date: date | None = None
    due_date: date | None = None
    total_cents: int | None = None        # what the document asks to be paid (or, on a receipt, what was paid)
    subtotal_cents: int | None = None
    amount_due_cents: int | None = None   # the balance the document says is still due, when it prints one
    paid: bool | None = None              # the document itself shows the amount paid (a receipt, "Amount due $0.00")
    bill_to: str = ""
    association_named: bool = False
    line_items: tuple[LineItem, ...] = ()
    line_items_partial: bool = False      # a row read as quantity, rate, amount did not multiply out (OCR); items may be short
    amounts: tuple[int, ...] = field(default=(), repr=False)
    method: str = "general"               # "format:<vendor>" when a vendor row read it
    service_address: str = ""             # the unit or common area the work was done at ("3007 ENCHANTED WALK")
    building: int | None = None           # the flood building that address falls in, by the specification
    reference: str = ""                   # the proposal, estimate, purchase order, work order, or contract it bills against
    license: str = ""                     # the contractor's license number, when the invoice prints one

    @property
    def items_cents(self) -> int:
        return sum(i.amount_cents for i in self.line_items)


# Reading


def loose_date(raw: str) -> date | None:
    """``parse_date`` plus the day-first forms vendors print: "23-MAR-2026", "08 May, 2024"."""
    raw = re.sub(r",(?=\d{4}$)", ", ", (raw or "").strip())
    found = parse_date(raw)
    if found:
        return found
    m = re.fullmatch(r"(\d{1,2})[- ]([A-Za-z]{3,9})\.?,?[- ](\d{4})", raw)
    return parse_date(f"{m[2]} {m[1]}, {m[3]}") if m else None


def _format_for(text: str, formats: tuple[InvoiceFormat, ...]) -> InvoiceFormat | None:
    text = re.sub(r"(\d) ,", r"\1,", text)
    return next((f for f in formats if f.matches(text)), None)


def _format_date(pattern: str, text: str) -> date | None:
    if not pattern:
        return None
    m = re.search(pattern, text, re.I)
    return loose_date(m.group(1)) if m and m.group(1) else None


def _labeled_date(text: str) -> date | None:
    for label in _MORE_DATE_LABELS:
        m = re.search(r"\b" + label + r"\b\s*:?\s*" + _DATE, text, re.I)
        if m:
            found = loose_date(m.group(1))
            if found:
                return found
    return None


def _value(token: str) -> float | None:
    token = token.strip()
    m = _NUMERIC.match(token)
    if not m:
        return None
    value = float(m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else ""))
    return -value if token.startswith("(") and token.endswith(")") or token.startswith("-") else value


def scan_items(text: str) -> tuple[tuple[LineItem, ...], int]:
    """(line items, rows that did not multiply out).

    Invoices print a row as quantity, rate, amount (a description may sit between), one value per line in the text
    layer. A triple whose quantity times rate is the amount, within a cent, is an item; a triple that reads as a row
    but does not multiply out (an OCR misread, a rate with more places than printed) is counted, so a caller knows the
    items it has may not be all of them.
    """
    lines = [ln.strip() for ln in (text or "").splitlines()]
    found: list[LineItem] = []
    odd = 0
    i = 0
    while i < len(lines):
        q = _value(lines[i]) if not lines[i].startswith("$") and "(" not in lines[i] else None
        hit = None
        if q and 0 < q <= 10000:
            j = next((n for n in range(i + 1, min(i + 4, len(lines))) if _value(lines[n]) is not None), None)
            k = j + 1 if j is not None and j + 1 < len(lines) else None
            if j is not None and k is not None and _value(lines[k]) is not None and "." in lines[k]:
                r, a = _value(lines[j]), _value(lines[k])
                if a and abs(q * r - a) < 0.011 and not (q == r == a):
                    hit = (j, k, r, a)
                elif a and "." in lines[j] and i + 1 == j and 1 <= q <= 100 and q == int(q):
                    odd += 1
        if hit:
            j, k, r, a = hit
            between = [ln for ln in lines[i + 1:j] if ln and _value(ln) is None]
            before = next((ln for ln in reversed(lines[max(0, i - 3):i]) if ln and _value(ln) is None), "")
            found.append(LineItem(squash(between[0] if between else before)[:80], q, round(r * 100), round(a * 100)))
            i = k + 1
            continue
        i += 1
    half = len(found) // 2
    if found and len(found) % 2 == 0 and found[:half] == found[half:]:
        found = found[:half]  # the text repeats the page
    # A "1 / $691.91 / $691.91" run after the rows is the page's total, not an item: it is the sum of the items before it.
    found = [item for n, item in enumerate(found) if not (n and item.amount_cents == sum(x.amount_cents for x in found[:n]))]
    return tuple(found), odd


def line_items(text: str) -> tuple[LineItem, ...]:
    return scan_items(text)[0]


_BILL_TO = re.compile(r"(?im)^[ \t]*(?:bill(?:ed)?\s*to|sold\s*to(?:\s*address)?|customer(?:\s+name)?|prepared\s+for|insured(?:\s+name)?(?:\(s\))?"
                      r"|payor\s+name)[ \t]*(?::[ \t]*(.*))?$")
_NOT_A_PARTY = re.compile(r"\b(?:number|date|details|information|payment|address|summary|due|phone|e-?mail|terms|project|account|service|"
                          r"statement|renewal|offer|photographs?|bill to|sold to|p\.?o\.?|attn|contact|page|invoice|propertyaddress)\b"
                          r"|:\s*$|^[\W\d_]*$|\d{4}|https?:", re.I)


def bill_to(text: str) -> str:
    """The first name under a bill-to label ("Bill To", "Sold To", "Customer", "Prepared For", "Insured").

    A label's value is on its line after a colon or on one of the next three lines; a line that reads as another label
    (a number, a date, an address heading) is not a party.
    """
    lines = (text or "").splitlines()
    for m in _BILL_TO.finditer(text or ""):
        rest = (m.group(1) or "").strip()
        if rest and re.search(r"[A-Za-z]{3}", rest) and not _NOT_A_PARTY.search(rest):
            return squash(rest)[:80]
        index = (text or "")[:m.end()].count("\n")
        for line in lines[index + 1:index + 4]:
            line = line.strip()
            if line and re.search(r"[A-Za-z]{3}", line) and not _NOT_A_PARTY.search(line) and len(line) <= 60:
                return squash(line)[:80]
    return ""


def association_word(context: ModelContext) -> str:
    """The association's distinctive name word ("OAKRIDGE"), from the specification."""
    community = context.community
    for attr in ("index_association", "name"):
        value = getattr(community, attr, None)
        value = value() if callable(value) else value
        for word in re.findall(r"[A-Za-z]{5,}", str(value or "")):
            if word.casefold() not in ("community", "association", "homeowners", "owners"):
                return word.upper()
    return ""


def _fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").casefold())


_NAMES_CACHE: dict[int, tuple[str, ...]] = {}


def vendor_names(context: ModelContext) -> tuple[str, ...]:
    """Vendor names the specification knows: its counterparties that bill, its vendor portals, and the format rows."""
    community = context.community
    key = hash((id(community), str(context.data_dir or "")))
    if key in _NAMES_CACHE:
        return _NAMES_CACHE[key]
    names: list[str] = [f.vendor for f in INVOICE_FORMATS]
    # PayHOA's vendor directory as ``jason invoices`` saved it, when the data directory has it (disk only).
    directory = Path(context.data_dir) / "payhoa" / "vendor-info.json" if context.data_dir else None
    if directory is not None and directory.is_file():
        try:
            names += [str(row.get("vendorName") or "") for row in json.loads(directory.read_text(encoding="utf-8")).get("rows", [])]
        except (ValueError, AttributeError):
            pass
    try:
        from jason.community.sources import SourceKind

        skip = {SourceKind.OWNER, SourceKind.OTHER_ASSOCIATION}
        for sender in (community.senders() if community is not None else ()):
            if sender.kind in skip:
                continue
            names += [sender.payhoa_vendor, re.sub(r"\s*\(.*\)$", "", sender.name)]
        names += [p.vendor for p in (community.vendor_portals() if community is not None else ())]
    except (AttributeError, TypeError):
        pass
    found = tuple(dict.fromkeys(n for n in names if n and len(_fold(n)) >= 4))
    _NAMES_CACHE[key] = found
    return found


def _sender_name(text: str, context: ModelContext) -> str:
    """The specification's counterparty whose words appear in the letterhead, when no vendor name is found."""
    community = context.community
    if community is None:
        return ""
    try:
        from jason.community.sources import resolve

        known, _kind, _level, _word = resolve("", text, tuple(community.senders()), own_name=association_word(context))
    except (AttributeError, TypeError):
        return ""
    return re.sub(r"\s*\(.*\)$", "", known.name) if known else ""


_CUE = re.compile(r"invoice|receipt|statement|order|bill\b|amount due|balance due|total|premium|estimate", re.I)
_PAID = re.compile(r"\bTotal Paid\b|\bAmount paid\b|Thank you for your (?:payment|order)|\bPAID IN FULL\b|Payment Receipt|"
                   r"retain this receipt|Order Total|Grand Total", re.I)


def read_record(text: str, context: ModelContext, formats: tuple[InvoiceFormat, ...] = INVOICE_FORMATS) -> InvoiceRecord | None:
    """An invoice's record, or None when the text is not a readable invoice, receipt, or bill."""
    if not text or len(text.strip()) < 40 or not readable(text):
        return None
    fmt = _format_for(text, formats)
    if fmt is None and not _CUE.search(text):
        return None
    inv = read_invoice(text, vendors=vendor_names(context), formats=formats)
    if not inv.number and inv.total_cents is None and not inv.amounts:
        return None
    r = InvoiceRecord(vendor=inv.vendor, number=inv.number, invoice_date=inv.invoice_date, due_date=inv.due_date,
                      total_cents=inv.total_cents, amounts=inv.amounts, method=inv.method)
    if fmt is not None:
        r.invoice_date = r.invoice_date or _format_date(fmt.invoice_date, text)
        r.due_date = r.due_date or _format_date(fmt.due_date, text)
    r.invoice_date = r.invoice_date or _labeled_date(text)
    r.vendor = r.vendor or _sender_name(text, context)
    r.subtotal_cents = amount_after(r"\bsub\s*-?\s*total\b", text)
    due = re.search(r"\b(?:amount due|balance due|invoice balance|total due)\b[^$\n]{0,20}\n?\s*\$?\s?(\d{1,3}(?:,\d{3})+|\d+)\.(\d\d)", text, re.I)
    r.amount_due_cents = int(due.group(1).replace(",", "")) * 100 + int(due.group(2)) if due else None
    r.paid = True if (r.amount_due_cents == 0 or _PAID.search(text)) else None
    r.bill_to = bill_to(text)
    word = association_word(context)
    r.association_named = bool(word) and word.casefold() in _fold(text)
    items, odd = scan_items(text)
    r.line_items, r.line_items_partial = items, odd > 0
    r.service_address, r.building = service_address(text, context)
    ref = _REFERENCE.search(text)
    r.reference = f"{ref.group(1).strip().title()} {ref.group(2)}" if ref else ""
    from jason.community.models.contracts_agreements import _LICENSE

    lic = _LICENSE.search(text)
    r.license = lic.group(1) if lic else ""
    return r


# "Proposal #6021-1", "Estimate 000999", "PO: 4471", "Work Order WO-2231", "per contract 2024-07": what the bill is against.
# The number must hold a digit, so "Estimate Date" is not a reference.
_REFERENCE = re.compile(r"\b(Proposal|Estimate|Quote|Purchase Order|P\.?O\.?|Work Order|W\.?O\.?|Contract|Job)\s*(?:#|No\.?|Number)?\s*:?\s*"
                        r"((?=[A-Z0-9-]*\d)[A-Z]{0,4}-?\d[\w-]{1,})\b", re.I)
@lru_cache(maxsize=16)
def _street_address(streets: tuple[Street, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(\d{4})\s+(" + alternation(street_words(streets)) + r")\s*(Dr(?:ive)?|Walk|L(?:a)?n(?:e)?)\b\.?", re.I)


def service_address(text: str, context: ModelContext) -> tuple[str, int | None]:
    """The first community address the invoice names, on one of the profile's streets, and the building it falls in by
    the specification's ranges."""
    community = context.community
    streets = tuple(getattr(community, "streets", tuple)())
    by_word = street_words(streets)
    for m in _street_address(streets).finditer(text or ""):
        address = f"{m.group(1)} {by_word[m.group(2).upper()].value}"
        building = None
        if community is not None and hasattr(community, "building_for_address"):
            row = community.building_for_address(address)
            building = int(row.number) if row is not None else None
        return address, building
    return "", None


@AS_OF.check("invoice-dated", InvoiceRecord, fields=("invoice_date",))
def invoice_dated(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: an invoice dated after it."""
    if r.invoice_date and r.invoice_date > as_of:
        return [Finding("dated-in-future", f"the invoice is dated {r.invoice_date}, after today", Severity.CHECK)]
    return []


@AS_OF.check("invoice-due", InvoiceRecord, fields=("due_date", "paid"))
def invoice_due(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: a due date that has passed on an invoice the text does not show paid."""
    if r.due_date and r.due_date < as_of and not r.paid:
        days = (as_of - r.due_date).days
        return [Finding("due-date-passed", f"it was due {r.due_date} ({days} days ago) and the text does not show it paid; "
                        "confirm the payment", Severity.INFO)]
    return []


def invoice_findings(r: InvoiceRecord, context: ModelContext) -> list[Finding]:
    found: list[Finding] = []
    if r.line_items and not r.line_items_partial and r.total_cents is not None:
        items = r.items_cents
        targets = {t for t in (r.subtotal_cents, r.total_cents) if t is not None}
        if items not in targets:
            against = r.subtotal_cents if r.subtotal_cents is not None else r.total_cents
            what = "subtotal" if r.subtotal_cents is not None else "total"
            # Without a subtotal, tax, shipping, or fees may explain a total above the items; only less is a finding.
            if r.subtotal_cents is not None or items > r.total_cents:
                found.append(Finding("line-items-differ", f"the {len(r.line_items)} line items add to ${items / 100:,.2f}; the {what} is "
                                     f"${against / 100:,.2f}", Severity.CHECK))
    found.append(invoice_dated)   # the as-of lens's place: dated in the future
    if r.invoice_date and r.due_date and r.due_date < r.invoice_date:
        found.append(Finding("due-before-issued", f"due {r.due_date}, before its own date {r.invoice_date}", Severity.CHECK))
    found.append(invoice_due)     # the as-of lens's place: the due date passed, unpaid in the text
    word = association_word(context)
    if word and r.bill_to and word.casefold() not in _fold(r.bill_to):
        found.append(Finding("billed-to-other", "the bill-to line does not name the association: a board member's or an owner's "
                             "invoice is a reimbursement, and the association's record should show why it paid", Severity.CHECK))
    elif word and not r.association_named:
        found.append(Finding("association-not-named", "the text never names the association as the customer", Severity.CHECK))
    found.append(Finding("enhanced-association-record", "an invoice or receipt for a payment the association made is an enhanced "
                         "association record, open to members for the current and two previous fiscal years; the board's "
                         "written approval of it is a record too", Severity.INFO, RECORD_AUTHORITY + ", 5200(a)(5)"))
    return found


class InvoiceModel(DocumentModel):
    """Any vendor's invoice, receipt, or statement for services: the format rows first, then the general labels."""

    kind = DocumentKind.INVOICE
    name = "invoice"
    required = ("vendor", "number", "invoice_date", "total_cents")
    lens_checks = (invoice_dated, invoice_due)

    def parse(self, text: str, context: ModelContext) -> InvoiceRecord | None:
        return read_record(text, context)

    def check(self, record: InvoiceRecord, context: ModelContext) -> list[Finding]:
        return invoice_findings(record, context)


# Philadelphia Indemnity's NFIP flood renewal notice and new-application invoice


@dataclass
class FloodPremiumNotice(InvoiceRecord):
    carrier: str = ""
    notice: str = ""                     # "renewal notice" or "new application invoice"
    policy_number: str = ""              # the policy (or, on a new application, the application) number
    expiration_date: date | None = None
    property_location: str = ""
    building: Building | None = None     # the specification's building for the location, when it matches one
    building_coverage_cents: int | None = None
    deductible_cents: int | None = None
    premium_cents: int | None = None


_FLOOD_TITLE = re.compile(r"RENEWAL NOTICE|New Application Invoice", re.I)
_LOCATION = re.compile(r"\n\s*(\d{4}(?:-\d{4})?\s+[A-Z][A-Z .]+(?:WALK|LANE|LN|DR|DRIVE|CR|CIRCLE|WAY|CT|ST)\b)[^\n]*", re.I)


@AS_OF.check("flood-renewal-due", FloodPremiumNotice, fields=("expiration_date",))
def flood_renewal_due(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: how long until the flood policy the notice renews expires."""
    if not r.expiration_date:
        return []
    left = (r.expiration_date - as_of).days
    if left < 0:
        return []
    return [Finding("flood-renewal-due", f"the policy expires {r.expiration_date} ({left} days); the notice renews it "
                    "without a lapse only if the premium arrives within 30 days after", Severity.CHECK if left < 45 else Severity.INFO)]


class FloodPremiumNoticeModel(DocumentModel):
    kind = DocumentKind.INVOICE
    name = "flood-premium-notice"
    required = ("policy_number", "invoice_date", "premium_cents", "property_location")
    lens_checks = (invoice_dated, flood_renewal_due)

    def parse(self, text: str, context: ModelContext) -> FloodPremiumNotice | None:
        if not text or not _FLOOD_TITLE.search(text) or not re.search(r"PHILADELPHIA", text, re.I) or not re.search(r"flood", text, re.I):
            return None
        base = read_record(text, context)
        if base is None:
            return None
        r = FloodPremiumNotice(**{f: getattr(base, f) for f in base.__dataclass_fields__})
        r.carrier = "Philadelphia Indemnity Insurance Company"
        r.vendor = r.vendor or r.carrier
        r.notice = "new application invoice" if re.search(r"New Application Invoice", text, re.I) else "renewal notice"
        numbers = re.findall(r"\b(50\d{8})\b", text)
        r.policy_number = max(set(numbers), key=numbers.count) if numbers else ""
        expiry = re.search(r"will expire\s+(\d{1,2}/\d{1,2}/\d{4})", text, re.I)
        r.expiration_date = parse_date(expiry.group(1)) if expiry else r.due_date
        if r.notice == "new application invoice":
            dated = [d for d in dates_in(text)]
            r.expiration_date = max(dated) if dated else None
        location = _LOCATION.search(text)
        r.property_location = squash(location.group(1)) if location else ""
        r.building = _building_of(r.property_location, context)
        row = re.search(r"\n\s*(\d{1,3}(?:,\d{3})+\.\d\d)\s*\n(?:\s*N/A\s*\n)+\s*([\d,]+\.\d\d)\s*\n(?:\s*N/A\s*\n)+\s*([\d,]+\.\d\d)", text)
        if row:
            r.building_coverage_cents, r.deductible_cents, r.premium_cents = (cents(row.group(i)) for i in (1, 2, 3))
        else:
            cover = re.search(r"\$\s?(\d{1,3}(?:,\d{3}){2,})\b", text)
            r.building_coverage_cents = cents(cover.group(1)) if cover else None
            r.premium_cents = r.total_cents
        r.total_cents = r.total_cents if r.total_cents is not None else r.premium_cents
        return r

    def check(self, r: FloodPremiumNotice, context: ModelContext) -> list[Finding]:
        found = [f for f in invoice_findings(r, context) if f is not invoice_due]   # a premium notice's due date is its expiry, below
        policy = _flood_policy(r.policy_number, context)
        policies = _flood_policies(context)
        if r.policy_number and policies and policy is None and r.notice == "renewal notice":
            found.append(Finding("unknown-flood-policy", f"policy {r.policy_number} is not one of the specification's flood policies",
                                 Severity.CHECK))
        if policy is not None and r.building is not None and policy.building is not None and policy.building != r.building:
            found.append(Finding("flood-building-mismatch", f"the notice's location is building {r.building.value}; the specification "
                                 f"has policy {r.policy_number} on building {policy.building.value}", Severity.CHECK))
        found.append(flood_renewal_due)   # the as-of lens's place: how long until the policy expires
        return found


def _flood_policies(context: ModelContext) -> tuple[Any, ...]:
    try:
        from jason.community.symbols import PolicyKind

        return tuple(p for p in context.community.insurance().policies if p.kind is PolicyKind.FLOOD)
    except AttributeError:
        return ()


def _flood_policy(number: str, context: ModelContext) -> Any | None:
    return next((p for p in _flood_policies(context) if number and number in p.numbers), None)


def _building_of(location: str, context: ModelContext) -> Building | None:
    """The specification's building for the notice's location ("3007-3039 ENCHANTED WALK" by its first number)."""
    if not location or context.community is None:
        return None
    try:
        from jason.community.base import assign_building

        first_number = re.sub(r"^(\d+)-\d+", r"\1", location)
        hit = assign_building(first_number, context.community.buildings())
    except (AttributeError, TypeError, ValueError):
        return None
    return hit.number if hit else None


# Tax returns


@dataclass(frozen=True)
class FormResult:
    form: str                  # "1120-H", "100", "199", "7004", "3539"
    result: str                # "overpayment", "balance due", "no balance due", "amount due"
    amount_cents: int | None = None


@dataclass
class TaxReturn:
    tax_year: int | None = None
    preparer: str = ""
    letter_date: date | None = None
    forms: tuple[str, ...] = ()
    results: tuple[FormResult, ...] = ()
    extension: bool = False
    deadlines: tuple[date, ...] = ()
    signature_forms: tuple[str, ...] = ()
    estimated_payments_cents: int | None = None


_FORMS = re.compile(r"\bForm\s+(1120-?H|100(?!\d)|199(?!\d)|7004|3539|8453-(?:C|EO))\b", re.I)


@AS_OF.check("tax-deadline", TaxReturn, fields=("deadlines",))
def tax_deadline(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: the next deadline the preparer's letter gives."""
    upcoming = [d for d in r.deadlines if d >= as_of]
    return [Finding("tax-deadline", f"the next deadline the letter gives is {upcoming[0]}", Severity.CHECK)] if upcoming else []


class TaxReturnModel(DocumentModel):
    kind = DocumentKind.TAX_RETURN
    name = "tax-return"
    required = ("tax_year", "forms", "preparer")
    lens_checks = (tax_deadline,)

    def parse(self, text: str, context: ModelContext) -> TaxReturn | None:
        if not text or not _FORMS.search(text) or not re.search(r"return|extension", text, re.I):
            return None
        r = TaxReturn()
        year = re.search(r"\b(20\d\d)\s+(?:return|extension|Form)", text) or re.search(r"year ended \w+ \d{1,2}, (20\d\d)", text)
        r.tax_year = int(year.group(1)) if year else None
        r.forms = tuple(dict.fromkeys(f.upper().replace("1120H", "1120-H") for f in _FORMS.findall(text)))
        signed = re.search(r"Sincerely,\s*\n\s*([^\n]+)\n\s*([^\n]+)", text)
        r.preparer = squash(signed.group(2)) if signed else ""
        head = dates_in(text[:200])
        r.letter_date = head[0] if head else None
        results = []
        for m in re.finditer(r"Form (\S+) shows (?:a total |an |a )?(overpayment|balance due|amount due|no balance due)(?: of \$([\d,]+))?", text, re.I):
            results.append(FormResult(m.group(1).upper(), m.group(2).lower(), int(m.group(3).replace(",", "")) * 100 if m.group(3) else None))
        r.results = tuple(results)
        r.extension = bool(re.search(r"\bextension", text, re.I))
        deadlines = [d for m in re.finditer(r"(?:mail by|by|valid until|before)\s+(" + _MONTH + r" \d{1,2}, \d{4})", text, re.I)
                     for d in [parse_date(m.group(1))] if d]
        r.deadlines = tuple(sorted(set(deadlines)))
        r.signature_forms = tuple(dict.fromkeys(f.upper() for f in re.findall(r"Form\s+(8453-(?:C|EO))", text, re.I)))
        est = re.search(r"total amount of Federal estimated tax payments is \$([\d,]+)", text, re.I)
        r.estimated_payments_cents = int(est.group(1).replace(",", "")) * 100 if est else None
        return r

    def check(self, r: TaxReturn, context: ModelContext) -> list[Finding]:
        found = [Finding("tax-return-record", "state and federal tax returns are association records, open to members for the current "
                         "and two previous fiscal years", Severity.INFO, TAX_RECORD_AUTHORITY)]
        if r.signature_forms or re.search("1120", " ".join(r.forms)):
            found.append(Finding("signature-not-in-text", "the return is filed only once an authorized board member signs it"
                                 + (f" (Form {', '.join(r.signature_forms)})" if r.signature_forms else "")
                                 + "; the copy's text cannot show the signature", Severity.CHECK))
        for result in r.results:
            if result.result in ("balance due", "amount due") and result.amount_cents:
                found.append(Finding("tax-due", f"Form {result.form} shows ${result.amount_cents / 100:,.2f} due", Severity.CHECK))
        found.append(tax_deadline)   # the as-of lens's place: the next deadline the letter gives
        return found


register(FloodPremiumNoticeModel())
register(InvoiceModel())
register(TaxReturnModel())

__all__ = ["InvoiceRecord", "LineItem", "InvoiceModel", "FloodPremiumNotice", "FloodPremiumNoticeModel", "TaxReturn", "FormResult",
           "TaxReturnModel", "read_record", "invoice_findings", "line_items", "bill_to", "loose_date", "vendor_names"]
