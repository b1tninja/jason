"""Consideration declared on a Sacramento grant deed.

The deed does not print the price. It prints the documentary transfer tax.
Revenue and Taxation Code section 11911 rates that tax at fifty-five cents
for each five hundred dollars of consideration, or any fraction of five
hundred dollars. Sacramento County imposes that rate. On these deeds the
City of Sacramento tax is two dollars and seventy-five cents per one
thousand dollars. When both are declared, they are the same dollar. That
dollar is the consideration the tax was computed on. It is not the value
the assessor later enrolled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Fifty-five cents for each five hundred dollars.
_COUNTY_STEP_CENTS = 55
_COUNTY_STEP_VALUE_CENTS = 50_000

# Two dollars and seventy-five cents per one thousand dollars.
_CITY_STEP_CENTS = 275
_CITY_STEP_VALUE_CENTS = 100_000

# A scan sometimes turns an underline into hyphens between the words, and
# splits a decimal with a space; both spellings are read.
_GAP = r"[\s\-]+"
_AMOUNT = r"([0-9][0-9,]*(?:\.\s?[0-9]{2})?)"
_COUNTY_AMOUNT = re.compile(
    rf"transfer{_GAP}tax(?:{_GAP}is)?[\s\-]*\$\s*{_AMOUNT}",
    re.IGNORECASE,
)
_CITY_AMOUNT = re.compile(
    rf"city(?:{_GAP}transfer)?{_GAP}tax(?:{_GAP}is|:)?[\s\-]*\$\s*{_AMOUNT}"
    rf"|city\s+\$\s*{_AMOUNT}",
    re.IGNORECASE,
)
_ZERO = re.compile(
    rf"transfer{_GAP}tax(?:{_GAP}is)?\s*\$\s*-+\s*0",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DeedPrice:
    """Transfer tax declared on one deed, and the consideration it computes.

    ``price_cents`` is set when the county tax is an exact count of the
    five-hundred-dollar step. A city tax that computes a different dollar
    leaves the price blank. ``exempt`` is a deed that declares no tax.
    """

    county_tax_cents: int | None
    city_tax_cents: int | None
    exempt: bool
    price_cents: int | None


def granting_clause(text: str) -> tuple[str, str]:
    """Grantor and grantee printed in the granting sentence.

    The recorder's index names are preferred when they are already known.
    This is the sentence on the deed itself. A missing clause is two empty
    strings.
    """
    flat = " ".join(text.split())
    match = re.search(r"hereby\s+GRANT(?:\(?S\)?)?\s+to\b", flat, re.IGNORECASE)  # "does hereby grant to" is the same clause
    if match is None:
        return "", ""
    before = flat[max(0, match.start() - 240):match.start()]
    acknowledged = re.split(r"(?:acknowledged|value received),?\s*", before, flags=re.IGNORECASE)[-1]
    grantor = re.sub(r"\s+(?:does|do)$", "", acknowledged.strip(" ,-"), flags=re.IGNORECASE)
    after = flat[match.end():match.end() + 180]
    grantee = re.split(
        r"\b(?:the land described|the following described|dated:|for a valuable)\b",
        after,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return _clean_party(grantor), _clean_party(grantee)


def _clean_party(text: str) -> str:
    words = " ".join(text.split())
    words = re.sub(r"\s+,", ",", words).strip(" ,.;")
    return words


def deed_price(text: str) -> DeedPrice | None:
    """Read the documentary transfer tax and the city tax from a deed.

    A deed that never mentions the transfer tax returns none. The statute
    number 11911 printed in a blank amount is not a tax.
    """
    flat = _repair_scan(" ".join(text.split()))
    if not re.search(rf"transfer{_GAP}tax", flat, re.IGNORECASE):
        return None
    county = _county_cents(flat)
    city = _city_cents(flat)
    declared_exempt = bool(
        re.search(r"not payable|consideration less than", flat, re.IGNORECASE) or _ZERO.search(flat)
    )
    exempt = county == 0 or (county is None and declared_exempt)
    price = None if exempt else _price(county, city)
    return DeedPrice(county, city, exempt, price)


# A title company rounds the city tax its own way; this many cents is still the same dollar.
_CITY_ROUNDING_CENTS = 100


def _price(county: int | None, city: int | None) -> int | None:
    if county is None or county <= 0 or county % _COUNTY_STEP_CENTS:
        return None
    price = (county // _COUNTY_STEP_CENTS) * _COUNTY_STEP_VALUE_CENTS
    if city is None or city <= 0:
        return price
    expected = (price * _CITY_STEP_CENTS + _CITY_STEP_VALUE_CENTS // 2) // _CITY_STEP_VALUE_CENTS
    if abs(expected - city) > _CITY_ROUNDING_CENTS:
        return None
    return price


def _repair_scan(flat: str) -> str:
    """Undo the two OCR slips that hide a tax amount: ``S`` for ``$`` and ``l`` for ``1``.

    Only a ``S`` directly before digits, and only an ``l`` or ``I`` inside a
    run of digits, are touched, so names and words stay as printed.
    """
    flat = re.sub(r"(?<![A-Za-z])S(?=[\dlI][\dlI,.]*\d)", "$", flat)
    return re.sub(r"(?<=[\d$.,])[lI](?=[\d.,])", "1", flat)


def _county_cents(flat: str) -> int | None:
    for match in _COUNTY_AMOUNT.finditer(flat):
        start = match.start()
        window = flat[max(0, start - 12):start].lower()
        if "city" in window:
            continue
        amount = _cents(match.group(1))
        if amount is None or amount == 1_191_100:
            continue
        return amount
    return None


def _city_cents(flat: str) -> int | None:
    found: int | None = None
    for match in _CITY_AMOUNT.finditer(flat):
        token = match.group(1) or match.group(2)
        amount = _cents(token)
        if amount is None:
            continue
        found = amount
    return found


def _cents(token: str) -> int | None:
    text = re.sub(r"\.\s+(?=\d{2})", ".", token.strip())
    if re.fullmatch(r"\d+,\d{2}", text):
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d{2})?", text):
        return None
    if "." not in text:
        return int(text) * 100
    dollars, cents = text.split(".")
    return int(dollars) * 100 + int(cents)
