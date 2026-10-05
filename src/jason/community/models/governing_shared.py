"""Shared readers for the governing group's models: the recorder's stamp, the citations, the execution block, and the
specification lookups. Registers no model.

The recorded instruments (declaration, amendment, annexation, grant deed, condominium plan) are read with the mixins in
``jason.community.readings``; this module only repairs what OCR does to their input before handing it over: a stamp
whose digits came apart (``Doc # 201 91 2201433``), a ``Doc#·`` with a stray mark, an old ``in Book 20070920 at Page
0938`` citation that the citation reader only knows as ``as Document No. 200709200938``, and a unit range broken as
``Units 28 through 3 7``. The spec lookups tolerate a community that lacks a fact: a miss stays a miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Sequence

from jason.community.document_models import Finding, Severity, dates_in, squash
from jason.community.readings import AnnexedProperty, Citation, Reader, Stamp
from jason.community.reviews import RECORDS

READER = Reader()

_DOC_SPACED = re.compile(r"Doc\s*#\W{0,3}\s*((?:\d\s?){12})(?!\d)")
_BOOK_LOOSE = re.compile(r"\bBOO\S{0,3}\s*([^\n]{3,16}?)\s*PAGE\s*((?:\d\s?){4})(?!\s?\d)(?!\s*OF\b)")
_STAMP_DAY = re.compile(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+(\d{1,2}),\s*(\d{4})\b")
_BOX = re.compile(r"SPACE\s+ABOVE\s+THIS\s+LINE\s+FOR\s+RECORDER", re.I)
_CERTIFIED = re.compile(r"Certified\s+to\s+be\s+a\s+true\s+and\s+correct\s+copy", re.I)
_BOOK_PAGE = re.compile(r"\bin\s+Book\s+(?:Number\s+)?(\d{8}),?\s+(?:at\s+)?Page\s+(?:Number\s+)?(\d{1,4})\b", re.I)
_BOOK_PAGE_BARE = re.compile(r"\b(?:in\s+)?Book\s+(?:Number\s+)?(\d{8}),?\s+(?:at\s+)?Page\s+(?:Number\s+)?(\d{1,4})\b", re.I)
_MAP_BOOK = re.compile(r"Book\s+(\d{1,4})\s+of\s+(Parcel\s+Maps|Maps)\W{0,3}\s*(?:at\s+)?page\s+(\d{1,4})", re.I)
_NAME_NUMBER = re.compile(r"(?<!\d)((?:19|20)\d{10})(?!\d)")
# A former Davis-Stirling citation, with the subdivision when one is printed ("Civil Code Section 1363(g)", "Section
# 1365(e)(4) of the Civil Code"): the subdivision is what the recodification table places.
_SUB = r"((?:\s?\([a-z0-9]{1,4}\))*)"
_REPEALED = re.compile(r"Civil\s+Code\s+(?:Section|§)?\s*(13[5-7]\d(?:\.\d+)?)" + _SUB
                       + r"|Section\s+(13[5-7]\d(?:\.\d+)?)" + _SUB + r"\s+of\s+the\s+(?:California\s+)?Civil\s+Code", re.I)
_FOOTER_PAGE = re.compile(r"(?:^|\s)-\s(\d{1,3})\s-(?=\s|$)")
_TOC_PAGE = re.compile(r"(?:\.\s?){3,}[\s.]*(\d{1,3})\s*$", re.M)
_UNITS_SPLIT = re.compile(r"\bUnits?\s+(\d(?:\s?\d){0,2})\s+through\s+(\d(?:\s?\d){0,2})\b", re.I)
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
             "tenth": 10}


@dataclass(frozen=True)
class Recording:
    """The county's stamp as this copy shows it. ``source`` says how the number was read: ``stamp`` (the recorder's
    ``Doc#`` or ``BOOK/PAGE``), ``spaced`` (a ``Doc#`` whose digits OCR split), or empty when the copy has no number."""

    number: str = ""
    recorded: date | None = None
    pages: int | None = None
    fees_cents: int | None = None
    unrecorded_copy: bool = False     # the "space above this line" box with no stamp: a draft or an unrecorded copy
    certified_copy: bool = False      # a title company's "certified to be a true and correct copy" of the recorded original
    source: str = ""


@dataclass(frozen=True)
class Execution:
    """The signature and acknowledgment block, as far as text can show it. A signature is often only an image."""

    witness_clause: bool = False      # "IN WITNESS WHEREOF"
    date_blank: bool = False          # "DATED: ______" or "____ day of ______"
    signature_blank: bool = False     # "By: ______" or "By: President" with nothing between
    acknowledged: bool = False        # a notary's certificate: "Notary Public" and "personally appeared"
    dated: date | None = None         # the date the execution block gives, when it gives one


def number_date(number: str) -> date | None:
    """The recording date a modern instrument number carries in its first eight digits (``YYYYMMDD``)."""
    if len(number) < 8 or not number[:8].isdigit():
        return None
    try:
        return date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    except ValueError:
        return None


def _subsequence(small: str, big: str) -> bool:
    it = iter(big)
    return all(ch in it for ch in small)


def _old_stamp(text: str, name: str) -> tuple[str, str]:
    """A pre-2018 ``BOOK 20120302 PAGE 1601`` stamp that OCR mangled (``BOO!(' 2012t?302 PAGE 1601``). The book is the
    recording day: the stamp's printed date supplies it, or else the file name's number when its page is the stamp's
    page and the book's legible digits appear, in order, in the name's book."""
    hit = _BOOK_LOOSE.search(text[:4000])
    if not hit:
        return "", ""
    legible = re.sub(r"\D", "", hit.group(1))
    page = re.sub(r"\s", "", hit.group(2))
    when = _STAMP_DAY.search(text[hit.end(): hit.end() + 400])
    if when:
        found = dates_in(f"{when.group(1)[:3].title()} {when.group(2)}, {when.group(3)}")
        if found:
            book = found[0].strftime("%Y%m%d")
            if _subsequence(legible, book):
                return book + page, "stamp"
    named = name_number(name)
    if named and named[8:] == page and len(legible) >= 4 and _subsequence(legible, named[:8]):
        return named, "stamp and name"
    return "", ""


def recording(text: str, name: str = "") -> Recording:
    """``StampReader`` first; then a ``Doc#`` whose digits came apart; then an old ``BOOK/PAGE`` stamp OCR mangled. The
    date an instrument number carries wins over a time-stamped line elsewhere on the head (a title company's print
    header), since the county numbers by day."""
    stamp: Stamp = READER.read_stamp(text)
    number, source = stamp.number, "stamp" if stamp.number else ""
    if not number:
        hit = _DOC_SPACED.search(text[:4000])
        if hit:
            digits = re.sub(r"\s", "", hit.group(1))
            if number_date(digits):
                number, source = digits, "spaced"
    if not number:
        number, source = _old_stamp(text, name)
    recorded = stamp.recorded
    carried = number_date(number)
    if carried and recorded != carried:
        recorded = carried
    # StampReader takes the largest amount on the head as the fee; on a deed that is the transfer tax. A stamp that prints
    # "Fees $101.00" is read directly; on a head that declares a transfer tax the fee is left unread.
    found = re.search(r"Fees\s*\$\s?(\d{1,4})[.,]\s?(\d{2})", text[:4000])
    if found:
        fees = int(found.group(1)) * 100 + int(found.group(2))
    elif re.search(r"TRANSFER|City\s+Tax|Documentary|GRANT\s+DEED", text[:4000], re.I):
        fees = None
    else:
        fees = stamp.fees_cents
    box = stamp.unrecorded_copy or bool(_BOX.search(" ".join(text[:4000].split())))
    return Recording(number, recorded, stamp.pages, fees, box and not number, bool(_CERTIFIED.search(" ".join(text[:6000].split()))), source)


def as_document_numbers(text: str) -> str:
    """The text with each ``in Book 20070920 at Page 0938`` rewritten as ``as Document No. 200709200938``, the form
    the citation reader knows. Sacramento's book is the recording day, so book and page are the instrument number."""
    return _BOOK_PAGE.sub(lambda m: f"as Document No. {m.group(1)}{int(m.group(2)):04d}", text)


def citations(text: str, own: str = "") -> tuple[Citation, ...]:
    """Every earlier instrument the text cites, by document number or by book and page."""
    return READER.read_citations(as_document_numbers(" ".join(text.split())), own=own)


def book_page_numbers(text: str) -> tuple[str, ...]:
    """Every ``Book 20070912 ... Page 757`` the text names, as instrument numbers, in order."""
    return tuple(dict.fromkeys(f"{m.group(1)}{int(m.group(2)):04d}" for m in _BOOK_PAGE_BARE.finditer(" ".join(text.split()))))


def map_reference(text: str) -> str:
    """The parcel map or subdivision map a legal description rests on: ``Book 194 of Parcel Maps, page 18``."""
    hit = _MAP_BOOK.search(" ".join((text or "").split()))
    return f"Book {hit.group(1)} of {hit.group(2).title()}, page {hit.group(3)}" if hit else ""


def name_number(name: str) -> str:
    """The twelve-digit instrument number a file name repeats (``GD 202412130194.pdf``), or empty."""
    hit = _NAME_NUMBER.search(name or "")
    return hit.group(1) if hit and number_date(hit.group(1)) else ""


def execution(text: str) -> Execution:
    flat = squash(text)
    tail = flat[flat.upper().rfind("WITNESS WHEREOF"):] if "WITNESS WHEREOF" in flat.upper() else flat[-3000:]
    dated = None
    hit = re.search(r"(?:DATED|Dated|executed[^.]{0,60}?as of|Date)\s*:?\s*((?:January|February|March|April|May|June|July|August|"
                    r"September|October|November|December)\s+\d{1,2},?\s+\d{4})", tail)
    if hit:
        found = dates_in(hit.group(1))
        dated = found[0] if found else None
    return Execution(
        witness_clause=bool(re.search(r"WITNESS\s+WHEREOF", flat, re.I)),
        date_blank=bool(re.search(r"DATED:?\s*_{3,}|_{3,}\s*day\s+of\s*_{3,}|\badopted\s*_{3,}", flat, re.I)),
        signature_blank=bool(re.search(r"By:\s*_{3,}|By:\s+(?:President|Secretary)\b|_{8,}\s*(?:President|Secretary)\b", flat)),
        acknowledged=bool(re.search(r"Notary\s+Public", flat, re.I)
                          and re.search(r"personall?y?\s*:?\s+appeared|basis\s+of\s+satisfactory\s+evidence|acknowledged\s+to\s+me", flat, re.I)),
        dated=dated,
    )


def repealed_sections(text: str) -> tuple[str, ...]:
    """Former Davis-Stirling sections (Civil Code 1350 to 1378) the text still cites, each with its subdivision when the
    text prints one ("1363(g)"), in the order first cited."""
    found = (((m.group(1) or m.group(3)) + re.sub(r"\s", "", m.group(2) or m.group(4) or "")) for m in _REPEALED.finditer(text or ""))
    return tuple(dict.fromkeys(found))


def page_coverage(text: str) -> tuple[int | None, int | None]:
    """The last page the table of contents lists and the last page footer (``- 24 -``) the text reaches. A text that
    stops short of its own contents is a partial extract."""
    toc = [int(n) for n in _TOC_PAGE.findall(text[:30000])]
    seen = [int(n) for n in _FOOTER_PAGE.findall(text)]
    return (max(toc) if toc else None), (max(seen) if seen else None)


def annexed_property(text: str) -> AnnexedProperty:
    """``AnnexationReader``; a range OCR split (``28 through 3 7``) is joined when the joined range reads forward."""
    found = READER.read_annexed(text)
    if found.first_unit is not None and found.last_unit is not None:
        return found
    hit = _UNITS_SPLIT.search(text[:8000])
    if not hit:
        return found
    first, last = int(re.sub(r"\s", "", hit.group(1))), int(re.sub(r"\s", "", hit.group(2)))
    if last < first:
        return found
    return AnnexedProperty(first, last, found.association_common_areas, found.condominium_common_areas)


def ordinal(word: str) -> int | None:
    return _ORDINALS.get((word or "").strip().lower())


# Specification lookups. Each tolerates a community without the fact.

def spec_ccrs_number(community) -> str:
    return str(getattr(getattr(community, "ccrs", None), "recorder_number", "") or "")


def spec_amendment_numbers(community) -> tuple[str, ...]:
    ccrs = getattr(community, "ccrs", None)
    return tuple(a.recorder_number for a in getattr(ccrs, "amendments", ()) if getattr(a, "recorder_number", ""))


def spec_supersessions(community) -> tuple:
    fn = getattr(community, "supersessions", None)
    try:
        return tuple(fn()) if callable(fn) else ()
    except Exception:  # a spec without the fact
        return ()


def spec_reports(community) -> tuple:
    fn = getattr(community, "public_reports", None)
    try:
        return tuple(fn()) if callable(fn) else ()
    except Exception:
        return ()


def spec_parcels(community) -> frozenset[str]:
    found: set[str] = set()
    for attr in ("units", "common_areas"):
        fn = getattr(community, attr, None)
        try:
            found |= set(fn() if callable(fn) else ())
        except Exception:
            continue
    return frozenset(found)


def spec_unit_blocks(community) -> tuple:
    for attr in ("unit_blocks", "plan_blocks"):
        fn = getattr(community, attr, None)
        if callable(fn):
            try:
                return tuple(fn())
            except Exception:
                continue
    return ()


# Findings the recorded kinds share.

def recording_findings(r: Recording, name: str, *, authority: str = "") -> list[Finding]:
    found: list[Finding] = []
    named = name_number(name)
    if r.number and named and named != r.number:
        found.append(Finding("name-number-differs", f"the file name gives instrument {named}; the county stamp on the copy is {r.number}",
                             Severity.CHECK))
    if not r.number and r.unrecorded_copy:
        found.append(Finding("unrecorded-copy", "the copy shows the blank recorder's box and no county stamp: a draft or an unrecorded "
                             "copy; keep the recorded one", Severity.CHECK, authority))
    elif not r.number and r.certified_copy:
        found.append(Finding("certified-copy", "a title company's certified copy; the stamp's number did not survive OCR",
                             Severity.INFO))
    elif not r.number:
        found.append(Finding("no-stamp-in-text", "no county stamp in the text (a title company's copy, or a stamp OCR lost)",
                             Severity.CHECK, authority))
    return found


def repealed_finding(sections: tuple[str, ...], now: Sequence[str] = ()) -> list[Finding]:
    """Former Davis-Stirling sections a document cites; with ``now`` (``sections_now``), where each one is today."""
    if not sections:
        return []
    cited = ", ".join(sections)
    where = ("; " + "; ".join(now)) if now else ""
    return [Finding("cites-repealed-sections", f"cites former Civil Code {cited}, since repealed and continued in new provisions "
                    f"(4000-6150){where}; the board may correct the cross-references by resolution", Severity.INFO, "CIV 4235(a)")]


def sections_now(sections: Sequence[str], data_dir: Any) -> list[str]:
    """From the exported law history on disk: "1363(g) is now CIV 5855 (disposition table)" for each of ``sections`` the
    stored history places; none without the history."""
    if not sections or data_dir is None:
        return []
    from jason.community.succession import now_at

    return [f for f in (now_at(data_dir, s) for s in sections) if f]


def repealed_now(r, records) -> list[str]:
    """Where each former section the record cites is now, from the exported law history (``sections_now``)."""
    return sections_now(r.repealed_sections, records.data_dir) if r.repealed_sections else []


def cites_repealed(key: str, record: type) -> Any:
    """Register the records lens's check ``key`` on ``record``'s ``repealed_sections``: the former sections it cites,
    each with where the law history on disk places it now. A reader lists the check and puts it where the finding goes."""
    @RECORDS.check(key, record, fields=("repealed_sections",), facts=repealed_now, dated=False)
    def repealed(r, _as_of, now: list[str]) -> list[Finding]:
        return repealed_finding(r.repealed_sections, now)
    return repealed


def coverage_finding(toc_last: int | None, seen_last: int | None) -> list[Finding]:
    if toc_last and seen_last and seen_last + 1 < toc_last:
        return [Finding("partial-text", f"the text reaches page {seen_last} of the {toc_last} its contents list; later sections "
                        "are not in the extract", Severity.CHECK)]
    return []


# What a missing field's finding says. The framework writes "the text gives no adopted"; a model that knows what the text
# prints in the field's place (a blank line, "effective on the date of adoption", nothing at all) says that instead.

_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                 "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20, "twenty-one": 21,
                 "twenty-eight": 28, "thirty": 30, "forty-five": 45, "sixty": 60, "ninety": 90}


def number_word(text: str) -> int | None:
    """``10``, ``ten``, or ``ten (10)`` as 10; the digits in parentheses win over the word."""
    text = (text or "").strip().lower()
    hit = re.search(r"\((\d{1,3})\)", text) or re.fullmatch(r"(\d{1,3})", text)
    if hit:
        return int(hit.group(1))
    return _WORD_NUMBERS.get(re.sub(r"\s*\(.*$", "", text))


def explain_missing(reading, notes: dict[str, tuple[str, str]]):
    """The reading with each ``missing-<field>`` finding's message (and authority) replaced by ``notes[field]``."""
    if reading is None or not notes:
        return reading
    out = []
    for f in reading.findings:
        key = f.code[len("missing-"):].replace("-", "_") if f.code.startswith("missing-") else ""
        if key in notes:
            message, authority = notes[key]
            f = replace(f, message=message, authority=authority or f.authority)  # the same finding reworded; it keeps its basis
        out.append(f)
    reading.findings = tuple(out)
    return reading


class ExplainsMissing:
    """A ``DocumentModel`` mixin: ``missing_notes`` says, per required field, what the text prints in its place, so a
    missing field's finding reads "not printed in the text: the adoption line is blank" rather than the bare field name.
    List it before ``DocumentModel``."""

    def missing_notes(self, record, context) -> dict[str, tuple[str, str]]:
        return {}

    def read(self, text, context, kind=None):
        reading = super().read(text, context, kind)
        return explain_missing(reading, self.missing_notes(reading.record, context)) if reading is not None else None


__all__ = ["READER", "Recording", "Execution", "recording", "number_date", "as_document_numbers", "citations", "book_page_numbers",
           "map_reference", "name_number", "execution", "repealed_sections", "page_coverage", "annexed_property", "ordinal",
           "spec_ccrs_number", "spec_amendment_numbers", "spec_supersessions", "spec_reports", "spec_parcels", "spec_unit_blocks",
           "recording_findings", "repealed_finding", "sections_now", "cites_repealed", "coverage_finding", "number_word",
           "explain_missing", "ExplainsMissing"]
