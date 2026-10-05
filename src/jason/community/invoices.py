"""A vendor's invoice as a document: who billed, what number, what date, and what amount.

Vendor invoices come in every layout. ``read_invoice`` reads the fields most invoices label
the same way ("Invoice #", "Invoice Date", "Amount Due", "Balance Due", "Total"). A vendor
whose layout the general reader gets wrong gets an ``InvoiceFormat`` row: the phrases that
identify its invoices and its own patterns for the fields. Formats are tried first, in
order; the general reader fills whatever a format leaves out. A field no pattern finds
stays empty.

Every amount the document prints is kept too (``amounts``), because the check that matters
most is plain: does the payment's amount appear on the document attached to it?

Amounts are integer cents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_MONEY = re.compile(r"(?<![\d.])\$?\s?(\d{1,3}(?:,\d{3})+|\d+)\.(\d\d)(?!\d)")
# "2,750." with no cents, as some hand-typed invoices print it: whole dollars, thousands separator required.
_WHOLE = re.compile(r"(?<![\d.])\$?\s?(\d{1,3}(?:,\d{3})+)\.(?!\d)")
_DATE = r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}-\d{1,2}-\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4}|\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4})"


def parse_date(text: str) -> date | None:
    """"07/10/26", "08-31-2026", "2026-07-10", "July 10, 2026", "Jul 10 2026", "Jul 16,2024", "10 July 2026",
    "08 May, 2024", or "23-MAR-2026"."""
    t = text.strip().replace(".", "")
    # "23-MAR-2026" is "23 MAR 2026"; "08 May, 2024" and "Jul 16,2024" lose the comma's oddities.
    t = re.sub(r"^(\d{1,2})-([A-Za-z]{3,9})-(\d{4})$", r"\1 \2 \3", t)
    t = re.sub(r"^(\d{1,2}) ([A-Za-z]+), (\d{4})$", r"\1 \2 \3", t)
    t = re.sub(r"^([A-Za-z]+) (\d{1,2}),(\d{4})$", r"\1 \2, \3", t)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", t)
    if m:
        year = int(m.group(3))
        try:
            return date(year + 2000 if year < 100 else year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.fullmatch(r"([A-Za-z]+) (\d{1,2}),? (\d{4})", t) or None
    if m:
        month, day, year = m.group(1), m.group(2), m.group(3)
    else:
        m = re.fullmatch(r"(\d{1,2}) ([A-Za-z]+) (\d{4})", t)
        if not m:
            return None
        day, month, year = m.group(1), m.group(2), m.group(3)
    index = next((i for i, name in enumerate(MONTHS) if name.startswith(month.lower()[:3])), None)
    if index is None:
        return None
    try:
        return date(int(year), index + 1, int(day))
    except ValueError:
        return None


def money_values(text: str) -> tuple[int, ...]:
    """Every dollar amount the text prints, as cents, in order ("2,750." counts as $2,750.00)."""
    found = [(m.start(), int(m.group(1).replace(",", "")) * 100 + int(m.group(2))) for m in _MONEY.finditer(text)]
    found += [(m.start(), int(m.group(1).replace(",", "")) * 100) for m in _WHOLE.finditer(text)]
    return tuple(v for _pos, v in sorted(found))


def readable(text: str) -> bool:
    """The text layer reads as characters, not glyph codes.

    A PDF whose font carries no character map extracts as control characters ("\\x00\\x01\\x02"); a real text
    layer has almost none. Two percent is the line.
    """
    body = text.strip()
    if not body:
        return False
    control = sum(1 for c in body if ord(c) < 32 and c not in "\n\r\t")
    return control / len(body) < 0.02


@dataclass(frozen=True)
class InvoiceFormat:
    """One vendor's layout: phrases that identify it (all must appear) and patterns for its fields.

    Each pattern has one group. ``total`` is the amount the vendor asks to be paid. A layout that prints the
    association's name as the vendor writes it ("<the association> Condos") sets ``names_association`` to the words
    that follow the name ("Condos"): it then also needs the association's name word (``Community.name_pattern()``,
    given to `matches`) right before them. The name is the profile's fact and not the row's. With no name pattern such
    a row matches nothing.
    """

    vendor: str
    phrases: tuple[str, ...]
    number: str = ""
    invoice_date: str = ""
    due_date: str = ""
    total: str = ""
    names_association: str = ""

    def matches(self, text: str, name_pattern: str = "") -> bool:
        folded = text.casefold()
        if not all(p.casefold() in folded for p in self.phrases):
            return False
        if not self.names_association:
            return True
        return bool(name_pattern and re.search(rf"(?:{name_pattern})\s+{re.escape(self.names_association)}", text, re.I))


@dataclass(frozen=True)
class Invoice:
    vendor: str = ""
    number: str = ""
    invoice_date: date | None = None
    due_date: date | None = None
    total_cents: int | None = None
    amounts: tuple[int, ...] = field(default=(), repr=False)
    method: str = "general"

    def shows(self, cents: int) -> bool:
        """The document prints this amount somewhere."""
        return cents in self.amounts


# Labels in the order an invoice's payable amount is most likely named.
_TOTAL_LABELS = (
    r"amount\s+due", r"balance\s+due", r"total\s+due", r"total\s+amount\s+due", r"please\s+pay", r"amount\s+enclosed",
    r"invoice\s+total", r"total\s+for\s+this\s+invoice", r"total\s+amount", r"grand\s+total", r"amount\s+paid",
    r"payment\s+amount", r"renewal\s+premium", r"total\s+premium", r"total",
)


def _first(pattern: str, text: str, flags: int = re.I) -> str:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


def _labeled_amount(text: str) -> int | None:
    """The amount after the most telling label. A zero (a paid invoice's "Amount Due $0.00") gives way to the next label.

    A short phrase may sit between the label and the amount ("TOTAL AMOUNT DUE ON April 3, 2024 $1.50").
    """
    flat = re.sub(r"[ \t]+", " ", text)
    for label in _TOTAL_LABELS:
        for m in re.finditer(r"\b" + label + r"\b[^$\n]{0,34}\n?\s*(?:USD\s*)?\$?\s?(\d{1,3}(?:,\d{3})+|\d+)\.(\d\d)(?!\d)", flat, re.I):
            value = int(m.group(1).replace(",", "")) * 100 + int(m.group(2))
            if value:
                return value
    return None


def read_invoice(text: str, *, vendors: tuple[str, ...] = (), formats: tuple[InvoiceFormat, ...] = (),
                 name_pattern: str = "") -> Invoice:
    """An invoice's fields from its text: a vendor format when one matches, the general labels for the rest.

    ``vendors`` are names to look for in the text (the association's vendor directory); the first one found,
    longest names first, is the vendor. ``name_pattern`` is the association's name word (``Community.name_pattern()``),
    for a format that prints it (``InvoiceFormat.names_association``).
    """
    text = re.sub(r"(\d) ,", r"\1,", text)
    amounts = money_values(text)
    fmt = next((f for f in formats if f.matches(text, name_pattern)), None)
    number = invoice_date = due = ""
    total = None
    vendor = ""
    method = "general"
    if fmt is not None:
        vendor, method = fmt.vendor, f"format:{fmt.vendor}"
        number = _first(fmt.number, text) if fmt.number else ""
        invoice_date = _first(fmt.invoice_date, text) if fmt.invoice_date else ""
        due = _first(fmt.due_date, text) if fmt.due_date else ""
        if fmt.total:
            found = money_values(_first(fmt.total, text))
            total = found[0] if found else None
    if not number:
        # A number has a digit: "INVOICE NO." above "ACCOUNT NUMBER" is a layout, not the number.
        number = _first(r"invoice\s*(?:#|no\.?|number|num\.?)\s*[:.]?\s*#?\s*((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]{2,})\b", text)
    if not invoice_date:
        invoice_date = _first(r"(?:invoice date|date of invoice|bill date|statement date|date issued|invoice\s+date)\s*[:.]?\s*" + _DATE, text) \
            or _first(r"\bdate\s*[:.]?\s*" + _DATE, text)
    if not due:
        due = _first(r"(?:due date|payment due|due by|due on)\s*[:.]?\s*" + _DATE, text)
    if total is None:
        total = _labeled_amount(text)
    if not vendor and vendors:
        folded = _fold(text)
        vendor = next((v for v in sorted(vendors, key=len, reverse=True) if len(_fold(v)) >= 4 and _fold(v) in folded), "")
    return Invoice(vendor, number, parse_date(invoice_date) if invoice_date else None, parse_date(due) if due else None,
                   total, amounts, method)


def _fold(text: str) -> str:
    """Letters and digits only, lowercased: "E&R Landscaping, Inc." and "E & R LANDSCAPING INC" meet."""
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def names_vendor(text: str, name: str) -> bool:
    """The text names the vendor: its whole name, or its first distinctive word of five letters or more."""
    folded = _fold(text)
    if len(_fold(name)) >= 4 and _fold(name) in folded:
        return True
    words = [w for w in re.findall(r"[A-Za-z]{5,}", name) if w.casefold() not in _GENERIC_WORDS]
    return bool(words) and _fold(words[0]) in folded


_GENERIC_WORDS = {"company", "services", "service", "insurance", "construction", "landscaping", "roofing", "control",
                  "systems", "system", "group", "association", "sacramento", "california", "county", "management", "property"}


__all__ = ["Invoice", "InvoiceFormat", "read_invoice", "money_values", "parse_date", "names_vendor", "readable"]
