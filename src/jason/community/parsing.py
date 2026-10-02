"""Read a recorded instrument and name the fields that instrument prints.

A parser turns a file into pages of text. A document mixin decides which
instrument those pages are and pulls the fields that form is known to print.
``identify`` tries each parser until one sees text, then the first mixin that
recognizes the instrument. Each field names the template that matched, so a
later pass can tell a clean assessor number from one recovered through noise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from jason.community.consideration import granting_clause
from jason.community.tax import parcel_number

# A labeled assessor number, dashed as book-page-block-subparcel.
_APN = re.compile(
    r"\bA\.?\s*P\.?\s*N\.?(?!\w)"
    r"(?:\s*/\s*Parcel\s+I[DO]\(?s?\)?)?"
    r"\s*[:.]?\s*"
    r"(\d{3})\s*[-–]\s*(\d{4})\s*[-–]\s*(\d{3})\s*[-–]\s*(\d{4})",
    re.IGNORECASE,
)
# The same label when OCR leaves junk between the four groups.
_APN_LOOSE = re.compile(
    r"\bA\.?\s*P\.?\s*N\.?(?!\w)"
    r"(?:\s*/\s*Parcel\s+I[DO]\(?s?\)?)?"
    r"\s*[:.]?\s*"
    r"(\d{3})\D{0,8}(\d{4})\D{0,8}(\d{3})\D{0,8}(\d{4})",
    re.IGNORECASE,
)
# The sample grant deed labels this blank "Parcel No". A title company
# often prints the same blank as APN. The letter o in "No" survives as a zero.
_PARCEL_NO = re.compile(
    r"\bParcel\s+N[o0]\.?(?!\w)\s*[:.]?\s*"
    r"(\d{3})\s*[-–]\s*(\d{4})\s*[-–]\s*(\d{3})\s*[-–]\s*(\d{4})",
    re.IGNORECASE,
)
_PARCEL_NO_LOOSE = re.compile(
    r"\bParcel\s+N[o0]\.?(?!\w)\s*[:.]?\s*"
    r"(\d{3})\D{0,8}(\d{4})\D{0,8}(\d{3})\D{0,8}(\d{4})",
    re.IGNORECASE,
)
# A bare subparcel continuing the assessor number just read: "& 0008".
_SUFFIX = re.compile(r"\s*(?:,|&|and)\s*(\d{4})\b", re.IGNORECASE)
# "GRANT DEED" on the sample. A scan may read the two e's as 3.
_GRANT_DEED = re.compile(r"\bGRANT\s+D[E3][E3]D\b", re.IGNORECASE)
# The sample's granting line, with or without the title words above it.
_GRANTS_TO = re.compile(r"hereby\s+GRANT\(?S\)?\s+to\b", re.IGNORECASE)
_PARCEL_LABEL = re.compile(r"\bParcel\s+N[o0]\b|\bA\.?\s*P\.?\s*N\.?(?!\w)", re.IGNORECASE)
# "Unit 35 inclusive in Building 5" fills the sample's unit blank.
# A few words may sit between the number and "in Building". "Units 21" does not match.
_UNIT = re.compile(
    r"\bUnit\s+(?:No\.?\s*)?(\d{1,3})\b"
    r"(?:(?:[\s,]+(?!in\b)\w+){0,4}[\s,]+in\s+Build\w*\s+(\d+)\b)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Page:
    """One page of text and the parser that produced it."""

    number: int
    text: str
    source: str


@dataclass(frozen=True)
class Reading:
    """The pages a parser could see."""

    name: str
    pages: tuple[Page, ...]
    parser: str

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)


@dataclass(frozen=True)
class Field:
    """One value taken from the page, and the template that recognized it."""

    name: str
    value: str
    template: str


@dataclass(frozen=True)
class Identification:
    """Which parser saw the file, which instrument it is, and the fields."""

    parser: str
    kind: str
    fields: tuple[Field, ...]

    def values(self, name: str) -> tuple[str, ...]:
        return tuple(field.value for field in self.fields if field.name == name)


class TextLayer:
    """PDF text layer. A scan with no embedded text returns nothing.

    ``pages`` replaces the PDF reader in tests. It returns one string per page.
    """

    name = "text"

    def __init__(self, pages=None) -> None:
        self._pages = pages

    def read(self, path: str | Path) -> Reading | None:
        source = Path(path)
        if self._pages is not None:
            texts = self._pages(source)
        else:
            texts = _pdf_pages(source)
        if not texts:
            return None
        pages = tuple(
            Page(index, text, self.name)
            for index, text in enumerate(texts, start=1)
            if text and text.strip()
        )
        if not pages:
            return None
        return Reading(source.name, pages, self.name)


class MarkdownExtract:
    """A markdown extract saved beside a PDF, or the markdown file itself.

    The extract for ``GD 202412130194.pdf`` is ``GD 202412130194.pdf.md``.
    """

    name = "extract"

    def read(self, path: str | Path) -> Reading | None:
        source = Path(path)
        extract = source if source.suffix.lower() == ".md" else Path(str(source) + ".md")
        if not extract.is_file():
            return None
        text = extract.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return None
        return Reading(extract.name, (Page(1, text, self.name),), self.name)


class ApnMixin:
    """Assessor numbers printed on an instrument.

    The sample grant deed labels the blank ``Parcel No``. A recorded deed
    fills that blank, sometimes under the title company's ``APN`` label.
    A clean dashed number uses ``parcel_no`` or ``apn``. A labeled number
    with junk between the groups uses the loose template of that label. A
    four-digit subparcel that continues the number just read, as in
    ``0001 & 0008``, uses ``apn_suffix``.
    """

    def apn_fields(self, reading: Reading) -> tuple[Field, ...]:
        return apn_fields(reading.text)


class GrantDeedMixin(ApnMixin):
    """The subdivider's sample grant deed, and a recorded deed that fills it.

    The sample prints GRANT DEED, a Parcel No blank, and ``hereby GRANTS to``.
    A scan still counts when those two blanks are readable and the title is not.
    ``unit`` fills the sample's unit blank. ``building`` is set when the same
    phrase names the building.
    """

    kind = "grant_deed"

    def detect(self, reading: Reading) -> bool:
        text = reading.text
        if _GRANT_DEED.search(text):
            return True
        return _GRANTS_TO.search(text) is not None and _PARCEL_LABEL.search(text) is not None

    def fields(self, reading: Reading) -> tuple[Field, ...]:
        found = list(self.apn_fields(reading))
        grantor, grantee = granting_clause(reading.text)
        if grantor:
            found.append(Field("grantor", grantor, "granting_clause"))
        if grantee:
            found.append(Field("grantee", grantee, "granting_clause"))
        found.extend(unit_fields(reading.text))
        return tuple(found)


def identify(
    path: str | Path,
    parsers: tuple[TextLayer | MarkdownExtract, ...] = (),
    mixins: tuple[GrantDeedMixin, ...] = (),
) -> Identification | None:
    """The first parser that sees text, and the first mixin that knows the form.

    An empty text layer falls through to the next parser. A file no parser
    can read returns none. Text that no mixin recognizes comes back with an
    empty kind.
    """
    chosen = parsers or (TextLayer(), MarkdownExtract())
    forms = mixins or (GrantDeedMixin(),)
    reading: Reading | None = None
    for parser in chosen:
        found = parser.read(path)
        if found is not None and found.text.strip():
            reading = found
            break
    if reading is None:
        return None
    for mixin in forms:
        if mixin.detect(reading):
            return Identification(reading.parser, mixin.kind, mixin.fields(reading))
    return Identification(reading.parser, "", ())


def apn_fields(text: str) -> tuple[Field, ...]:
    """Every distinct assessor number a labeled line prints, in page order."""
    found: list[Field] = []
    seen: set[str] = set()
    covered: list[tuple[int, int]] = []
    labeled = (
        ("parcel_no", _PARCEL_NO),
        ("apn", _APN),
        ("parcel_no_loose", _PARCEL_NO_LOOSE),
        ("apn_loose", _APN_LOOSE),
    )
    for template, pattern in labeled:
        for match in pattern.finditer(text):
            if _overlaps(match.span(), covered):
                continue
            number = _dashed(match.groups())
            _add(found, seen, number, template)
            cursor = match.end()
            covered.append(match.span())
            while True:
                suffix = _SUFFIX.match(text, cursor)
                if suffix is None:
                    break
                _add(found, seen, _dashed((*match.groups()[:3], suffix.group(1))), "apn_suffix")
                cursor = suffix.end()
                covered.append(suffix.span())
    return tuple(found)


def unit_fields(text: str) -> tuple[Field, ...]:
    """The unit blank on the sample, when a recorded deed filled it in."""
    found: list[Field] = []
    seen: set[tuple[str, str]] = set()
    for match in _UNIT.finditer(text):
        unit = match.group(1)
        building = match.group(2) or ""
        key = (unit, building)
        if key in seen:
            continue
        seen.add(key)
        found.append(Field("unit", unit, "unit"))
        if building:
            found.append(Field("building", building, "unit"))
    return tuple(found)


def _add(found: list[Field], seen: set[str], number: str, template: str) -> None:
    if not number or number in seen:
        return
    seen.add(number)
    found.append(Field("apn", number, template))


def _dashed(groups: tuple[str, ...]) -> str:
    digits = "".join(groups)
    if len(digits) != 14 or not digits.isdigit():
        return ""
    return parcel_number(digits)


def _overlaps(span: tuple[int, int], covered: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < right and end > left for left, right in covered)


def _pdf_pages(path: Path) -> tuple[str, ...] | None:
    if path.suffix.lower() != ".pdf" or not path.is_file():
        return None
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return tuple((page.extract_text() or "") for page in reader.pages)
