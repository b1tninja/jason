"""A chronology of what a set of documents says: every dated statement in a slice of the passage index.

This is the "Chronology" lens of docs/ingestion-and-review.md: what happened, in what order, *according to which
document*. It takes a ``passage_index.Scope`` and a title, reads the passages the scope allows, and gives each dated
statement as an ``Event``:

- **the date**, read by the existing date readers (``document_models.dates_in``, ``invoices.parse_date``), with the
  words it was written in. A range ("from ... through ...") is one event with its end; "on or about" is marked; a
  month with no day ("March 2099") is the first of the month, marked as a month.
- **the words**, verbatim: the sentence, or the smallest group of clauses, that carries the date. A statement too
  long to quote whole is cut around the date and the cut is marked.
- **the place**: the file, its context line, the section, the passage, and the word and character position, with the
  document's standing, kind, and whether it is held back unless asked.
- **what kind of date it is** (``DateRole``): the document's own date (a date line, or a "Date:", "Sent:", "Hearing
  Date:" line at its head); a date in a short line at its head, which is often the document's own and is not taken
  for it; a message header's date further in (a quoted message); a date the text speaks about; or a date only the
  file's name prints (a recording's stamp), which is never taken for the document's words. ``rule`` names the rule
  that said so (``_role``).

An event states only what a document says and whose document it is. It never finds that the thing happened: that is a
finding of fact, and it rests on the record a person weighs (docs/ingestion-and-review.md, "Three questions"). Near
copies of a statement fold under one event (``retrieval.near_copies``), and the other places are listed with it.

Where the specification already holds a chronology (a ``LegalCase``'s events), it is passed as ``recorded`` and kept
as its own source, "the specification's record": never merged into the documents' statements.

Rule-based: no model and no network. A date the readers cannot read is not an event, and a miss stays a miss.
``write_page`` saves the generated page under ``data/collections/<slug>/``; nothing is written without it.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.passage_index import Row, Scope, Standing
from jason.community.passages import Passage

COLLECTIONS_DIR = "collections"
CHRONOLOGY_PAGE = "chronology.md"
MAX_QUOTE = 420                 # a statement longer than this is cut around its date
QUOTE_BEFORE, QUOTE_AFTER = 160, 220
HEAD_CHARS = 700                # how far into a file's first passage a header's date can sit
SHORT_LINE = 45                 # a line shorter than this ends its statement (a wrapped line of prose is longer)
HEAD_LINE_CHARS, HEAD_LINE_WORDS = 90, 14
LABEL_LINE_CHARS = 40           # a label line above a bare date is no longer than this
CELL_WORDS = 3                  # a line with its date and no more words than this, further in, is a form's or table's cell
CELL_LINE_CHARS = 80            # ... and carries the line above and the line below, when each is this short
FOLD_WORDS = 8                  # a statement shorter than this folds only when the passages around it are the same
SHORT_FOLD_SIMILARITY = 0.97    # ... which is this share of their letters: two reports from one form are not copies
PIVOT_YEARS = 20                # a two-digit year read more than this far ahead of today is read a century back

# Sorted after the date: the law, the association's record, a matter's evidence, a reference work, a page jason wrote.
STANDING_ORDER: tuple[Standing, ...] = (Standing.AUTHORITY, Standing.RECORD, Standing.EVIDENCE, Standing.REFERENCE,
                                        Standing.PAGE)

CAVEATS: tuple[str, ...] = (
    "Each event is what a document says, quoted, with whose document it is. It is not a finding that the event "
    "happened: read the document, and weigh it against the others.",
    "A date the readers cannot read (a date with no year, a date spelled out in words) is not here, and OCR can "
    "misread a date: check the quote against the file.",
    "The document's own date is read from its head by rule (a date line, or a labeled line such as Date, Sent, or "
    "Hearing Date). A date in a file's name is listed as the name's, never as the document's: a person or a system "
    "named the file, and a recording's stamp can be a day off (another time zone).",
    "The specification's record is kept apart from the documents' statements: it is the specification's entry, "
    "not a quote from a file.",
)


class DateRole(Enum):
    """What kind of date a statement carries."""

    DOCUMENT = "document"        # the document's own date: a date line or a labeled header at its head
    HEADING = "heading"          # a date in a short line at its head: often the document's own, not always
    NAME = "name"                # a date the file's name prints: not the document's words (a recording's stamp)
    EMBEDDED = "embedded"        # a message header's date further in: a quoted message, an attachment
    ABOUT = "about"              # a date the text speaks about


ROLE_WORDS = {DateRole.DOCUMENT: "the document's own date",
              DateRole.HEADING: "a date in a line at the document's head (often its own date; a scheduled time reads the same)",
              DateRole.NAME: "a date in the file's name, not in its words",
              DateRole.EMBEDDED: "a message header's date inside the document",
              DateRole.ABOUT: "a date the text speaks about"}
_ROLE_ORDER = (DateRole.DOCUMENT, DateRole.HEADING, DateRole.NAME, DateRole.EMBEDDED, DateRole.ABOUT)


class Precision(Enum):
    DAY = "day"
    MONTH = "month"              # the text gives a month and a year; the event's day is the first of the month


# A labeled line that gives the date of the document itself, by its label's words (lower case), when it sits at the
# file's head. Further in, the same label gives a date the text speaks about ("Date Filed: ..." in a list), except a
# message header's (``MESSAGE_LABELS``).
MESSAGE_LABELS: frozenset[str] = frozenset({"date", "sent", "date sent", "sent on"})
DOCUMENT_LABELS: frozenset[str] = frozenset({
    "date", "dated", "sent", "date sent", "sent on", "letter date", "date of letter", "notice date", "date of notice",
    "invoice date", "statement date", "report date", "date of report", "inspection date", "date of inspection",
    "meeting date", "date of meeting", "hearing date", "date of hearing", "hearing", "date issued", "issue date",
    "issued", "date prepared", "prepared", "printed", "print date", "recorded", "recording date", "date recorded",
    "filed", "date filed", "filing date", "date signed", "signed",
})
# Labels that give a date the document speaks about. They are recognized mid-line too, as the labels above are.
ABOUT_LABELS: frozenset[str] = frozenset({
    "due", "due date", "date due", "effective", "effective date", "expires", "expiration", "expiration date",
    "received", "date received", "date of loss", "loss date", "date of service", "service date", "deadline",
    "term", "period", "as of", "start date", "end date", "paid", "date paid", "payment date", "next meeting",
})
# In a short line at a file's head, a word that says the date is about something, not the document's own.
_ABOUT_CUE = re.compile(r"\b(?:due|effective|expir\w*|through|thru|until|period|ending|ended|deadline|before|after|since|"
                        r"birth|loss|term|renew\w*|as of|next|prior|previous|last|between)\b", re.I)

_MONTH_NAMES = "January|February|March|April|May|June|July|August|September|October|November|December"
_MONTH_ABBR = "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec"
_MONTH = rf"(?:{_MONTH_NAMES}|(?:{_MONTH_ABBR})\.?)"
_ORDINAL = r"(?:st|nd|rd|th)?"
_YEAR_SEP = r"(?:\s*,\s*|\s+)"
# Where a date is written. This only finds the words; ``read_date`` hands them to the existing readers. A numeric
# date inside a longer run of digits and dashes (an account or a parcel number) is dropped by ``date_spans``.
DATE_SPAN = re.compile(
    r"(?<![\w/])(?:"
    r"(?P<numeric>\d{1,2}/\d{1,2}/(?:\d{4}|\d{2})|\d{4}-\d{2}-\d{2}|\d{1,2}-\d{1,2}-\d{4})"
    rf"|(?P<long>{_MONTH}\s+\d{{1,2}}{_ORDINAL}{_YEAR_SEP}\d{{4}})"
    rf"|(?P<daymonth>\d{{1,2}}{_ORDINAL}\s+(?:day\s+of\s+)?{_MONTH}{_YEAR_SEP}\d{{4}})"
    rf"|(?P<dashed>\d{{1,2}}-(?:{_MONTH_ABBR}|May)-\d{{4}})"
    rf"|(?P<month>(?:{_MONTH_NAMES})(?:\s+of)?{_YEAR_SEP}\d{{4}})"
    r")(?!\d|/\d)", re.I)
_APPROXIMATE = re.compile(r"(?:\bon or about|\bon or around|\bin or about|\bin or around|\bapproximately|\babout|\baround|"
                          r"\bcirca|\bc\.)\s*$", re.I)
# Between a range's two dates: the joining word, after the first date's time of day when it gives one.
_RANGE_JOIN = re.compile(r"\s*(?:\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AP]\.?M\.?)?\s*)?(?P<join>-|\u2013|\u2014|to|through|thru|until|and)\s*",
                         re.I)
_BETWEEN = re.compile(r"\bbetween\s*$", re.I)
_WEEKDAY = r"(?:[A-Za-z]{3,6}day|Mon|Tues?|Wed|Thu(?:rs?)?|Fri|Sat|Sun)\.?"
_LABEL_BEFORE = re.compile(rf"([A-Za-z][A-Za-z ./]{{0,40}}?)\s*:\s*(?:{_WEEKDAY},?\s*)?$")
_LINE_LEAD = " \t-*|>#"
_DATE_LINE_REST = re.compile(rf"^[\s,.*_|>#-]*(?:{_WEEKDAY})?[\s,.*_|-]*$")
_BULLET_LINE = re.compile(r"^\s*(?:[-*\u2022>|#]|\(?[0-9A-Za-z]{1,3}[.)]\s)")
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*\s+")
_ABBREVIATIONS = frozenset(
    "mr mrs ms dr st no nos inc co corp ltd jr sr vs v esq dept ave blvd rd ste apt etc art sec p pp cal civ "
    "jan feb mar apr jun jul aug sep sept oct nov dec".split())


# --- reading the text -------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DateSpan:
    """One date as the text writes it: where, the words, and the existing readers' reading of them."""

    start: int
    end: int
    written: str
    day: date
    precision: Precision = Precision.DAY


def read_date(written: str, *, today: date | None = None) -> tuple[date | None, Precision]:
    """The date the words give, by the existing readers (``document_models.dates_in``, then ``invoices.parse_date``
    for the forms it does not list). The words are only tidied first: an ordinal's suffix and "day of" are dropped. A
    month with no day is read as its first day and marked. A two-digit year the readers place more than
    ``PIVOT_YEARS`` years after today is read a century earlier."""
    from jason.community.document_models import dates_in
    from jason.community.invoices import parse_date

    today = today or date.today()
    tidy = " ".join(written.replace(",", ", ").split()).replace(" ,", ",")
    tidy = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", tidy, flags=re.I)
    tidy = " ".join(re.sub(r"\b(?:day\s+of|of)\b", " ", tidy, flags=re.I).split())
    precision = Precision.DAY
    month_only = re.fullmatch(rf"({_MONTH_NAMES}),?\s+(\d{{4}})", tidy, re.I)
    if month_only:
        tidy, precision = f"{month_only.group(1)} 1, {month_only.group(2)}", Precision.MONTH
    found = dates_in(tidy)
    day = found[0] if found else parse_date(tidy)
    if day is None:
        return None, precision
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}", tidy) and day.year > today.year + PIVOT_YEARS:
        try:
            day = day.replace(year=day.year - 100)
        except ValueError:
            return None, precision
    if not 1850 <= day.year <= today.year + 100:
        return None, precision
    return day, precision


def date_spans(text: str, *, today: date | None = None) -> list[DateSpan]:
    """Every date the text writes that the readers can read, in order."""
    text = text or ""
    out: list[DateSpan] = []
    found = list(DATE_SPAN.finditer(text))
    for i, m in enumerate(found):
        written = m.group(0)
        if m.group("month") and not written[0].isupper():      # "may 2099" in a sentence is not a month
            continue
        if m.group("numeric"):
            # "-" and a digit on either side is a longer number, unless the neighbour is itself a date (a range).
            before = text[m.start() - 2: m.start()] if m.start() >= 2 else ""
            if re.fullmatch(r"\d-", before) and not (i and found[i - 1].end() == m.start() - 1):
                continue
            if re.match(r"-\d", text[m.end(): m.end() + 2]) and not (
                    i + 1 < len(found) and found[i + 1].start() == m.end() + 1):
                continue
        day, precision = read_date(written, today=today)
        if day is not None:
            out.append(DateSpan(m.start(), m.end(), written, day, precision))
    return out


_NAME_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})([-._]?)(\d{2})\2(\d{2})(?!\d)")
_PARTIAL_DATE = re.compile(rf"\b{_MONTH}\s+\d{{1,2}}{_ORDINAL}\b(?!{_YEAR_SEP}\d{{4}})(?!\d)", re.I)


def name_spans(name: str, *, today: date | None = None) -> list[DateSpan]:
    """The dates a file's name prints year first: "2099-11-20", "2099.11.20", or a recording's stamp "20991120". Each
    is read by the existing reader as a year, a month, and a day. A six-digit run is not read: it has two readings.
    A system's stamp can be in another time zone than the event, so the name's date can be a day off."""
    out: list[DateSpan] = []
    for m in _NAME_DATE.finditer(name or ""):
        day, _ = read_date(f"{m.group(1)}-{m.group(3)}-{m.group(4)}", today=today)
        if day is not None:
            out.append(DateSpan(m.start(), m.end(), m.group(0), day))
    return out


def partial_dates(text: str) -> int:
    """How many times the text names a month and a day with no year ("March 5th"): a date that cannot be placed."""
    return len(_PARTIAL_DATE.findall(text or ""))


def squash(text: str) -> str:
    """The words on one line with single spaces: the quote's form. No word is changed."""
    return " ".join((text or "").split())


def _blocks(text: str) -> list[tuple[int, int]]:
    """The runs of lines that read together: a blank line, a list or table mark, a heading, a line ending in a colon,
    or a short line whose next line does not run on in lower case ends a run. A passage with no line breaks is one
    run."""
    lines: list[tuple[int, str]] = []
    at = 0
    for raw in text.splitlines(keepends=True):
        lines.append((at, raw))
        at += len(raw)
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for i, (offset, raw) in enumerate(lines):
        line = raw.strip()
        if not line:
            if start is not None:
                blocks.append((start, offset))
                start = None
            continue
        if start is None:
            start = offset
        following = lines[i + 1][1] if i + 1 < len(lines) else ""
        continues = following.lstrip()[:1].islower()          # a narrow column's prose runs on in lower case
        ends = (not following.strip() or bool(_BULLET_LINE.match(following)) or line.startswith(("|", "#"))
                or line.endswith(":") or (len(line) < SHORT_LINE and not continues))
        if ends:
            blocks.append((start, offset + len(raw)))
            start = None
    if start is not None:
        blocks.append((start, len(text)))
    return blocks


def clauses(text: str) -> list[tuple[int, int]]:
    """The text as statements: (start, end) of each sentence, table row, or short line, in order, trimmed of the space
    around it. A period after an abbreviation or an initial does not end a sentence."""
    out: list[tuple[int, int]] = []
    for block_start, block_end in _blocks(text):
        block = text[block_start:block_end]
        cut = 0
        for m in _SENTENCE_END.finditer(block):
            if m.end() >= len(block):
                break
            following = block[m.end()]
            if not (following.isupper() or following.isdigit() or following in "\"'(["):
                continue
            before = block[cut:m.start()].split()
            word = re.sub(r"[^A-Za-z.]", "", before[-1]).lower() if before else ""
            if block[m.start()] == "." and (word in _ABBREVIATIONS or (len(word) == 1 and word.isalpha())):
                continue
            out.append((block_start + cut, block_start + m.end()))
            cut = m.end()
        out.append((block_start + cut, block_end))
    trimmed: list[tuple[int, int]] = []
    for start, end in out:
        piece = text[start:end]
        lead = len(piece) - len(piece.lstrip())
        tail = len(piece.rstrip())
        if tail > lead:
            trimmed.append((start + lead, start + tail))
    return trimmed


def clause_at(spans: Sequence[tuple[int, int]], start: int, end: int) -> tuple[int, int]:
    """The statement that holds text[start:end]: one clause, or the clauses from the one that holds its start to the
    one that holds its end."""
    if not spans:
        return start, end
    starts = [s for s, _ in spans]
    first = max(0, bisect.bisect_right(starts, start) - 1)
    last = max(first, bisect.bisect_right(starts, max(start, end - 1)) - 1)
    return min(spans[first][0], start), max(spans[last][1], end)


def quote_of(text: str, clause: tuple[int, int], start: int, end: int) -> tuple[str, bool, bool, int]:
    """The statement's words for text[start:end], whole when it fits in ``MAX_QUOTE`` characters, else cut around the
    span at word breaks: (the words, cut before, cut after, where the quote starts)."""
    cs, ce = clause
    if ce - cs <= MAX_QUOTE:
        return squash(text[cs:ce]), False, False, cs
    qs, qe = max(cs, start - QUOTE_BEFORE), min(ce, end + QUOTE_AFTER)
    if qs > cs:
        space = text.find(" ", qs, start)
        qs = space + 1 if space != -1 else qs
    if qe < ce:
        space = text.rfind(" ", end, qe)
        qe = space if space != -1 else qe
    return squash(text[qs:qe]), qs > cs, qe < ce, qs


class FileLines:
    """A passage with its file's own line breaks. A file with no headings is cut into windows of words
    (``passages.passages_of``), which joins its lines; a date line or a "Date:" line is then lost in a run of words.
    Called with a passage, this reads the file once and gives the passage back with the same words as the file
    prints them. A passage that already has line breaks, a file that cannot be read, or one whose words no longer
    match the index is given back as it is."""

    def __init__(self) -> None:
        self._files: dict[Path, tuple[str, list[tuple[int, int]]] | None] = {}

    def _words(self, path: Path) -> tuple[str, list[tuple[int, int]]] | None:
        if path not in self._files:
            try:
                body = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
            except OSError:
                self._files[path] = None
            else:
                self._files[path] = (body, [(m.start(), m.end()) for m in re.finditer(r"\S+", body)])
        return self._files[path]

    def __call__(self, passage: Passage) -> Passage:
        if "\n" in passage.text:
            return passage
        held = self._words(passage.path)
        own = passage.text.split()
        if held is None or not own:
            return passage
        body, words = held
        chunk = words[passage.start_word: passage.start_word + len(own)]
        if len(chunk) != len(own):
            return passage
        original = body[chunk[0][0]: chunk[-1][1]]
        return replace(passage, text=original) if original.split() == own else passage


# --- the records ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Place:
    """Where a statement sits, and what its document is."""

    file: str
    path: str
    context: str                 # the index's context line for the file (a library file's name, kind, and period)
    section: str
    passage: int
    word: int                    # the statement's first word, counted from the start of the file
    char: int                    # the statement's first character, counted from the start of the passage as the file prints it
    catalog: str
    standing: Standing
    kind: str
    confidential: bool
    generated: bool

    @property
    def document(self) -> str:
        """The file with its context line: a library file is named by its id, and the context carries its name."""
        return f"{self.file} ({self.context})" if self.context else self.file

    @property
    def where(self) -> str:
        section = f", section {self.section}" if self.section else ""
        return f"passage {self.passage}, word {self.word}{section}"

    def as_dict(self) -> dict[str, Any]:
        return {"file": self.file, "path": self.path, "context": self.context, "section": self.section,
                "passage": self.passage, "word": self.word, "char": self.char, "catalog": self.catalog,
                "standing": self.standing.value, "kind": self.kind, "confidential": self.confidential,
                "generated": self.generated}


def place_of(passage: Passage, row: Row, char: int = 0) -> Place:
    return Place(passage.title, str(passage.path), passage.context, passage.heading, passage.index,
                 passage.start_word + len(passage.text[:char].split()), char, row.catalog, row.standing, row.kind,
                 row.confidential, row.generated)


@dataclass(frozen=True)
class Event:
    """One dated statement of one document. ``quote`` is the document's words; nothing here says the event happened."""

    day: date
    quote: str
    place: Place
    role: DateRole
    rule: str                              # the rule that gave the role and the statement's bounds (``_role``)
    written: str                           # the date as the document writes it
    label: str = ""                        # the label of a labeled line ("Sent", "Hearing Date"), as written
    end: date | None = None                # a range's last day
    approximate: bool = False              # "on or about"
    precision: Precision = Precision.DAY
    cut_before: bool = False               # the quote starts after the statement's start
    cut_after: bool = False
    document_day: date | None = None       # the document's own date, when its head gives one
    also: tuple[Place, ...] = ()           # the other places that carry a near copy of the statement

    @property
    def quoted(self) -> str:
        """The quote with any cut marked by an ellipsis."""
        return f"{'... ' if self.cut_before else ''}{self.quote}{' ...' if self.cut_after else ''}"

    @property
    def when(self) -> str:
        text = self.day.isoformat()[:7] if self.precision is Precision.MONTH else self.day.isoformat()
        if self.end is not None:
            text += f" to {self.end.isoformat()}"
        return f"{text} (on or about)" if self.approximate else text

    @property
    def confidential(self) -> bool:
        return self.place.confidential or any(p.confidential for p in self.also)

    def says(self) -> str:
        """The statement as a sentence that names its document and asserts nothing more."""
        doc = self.place.document
        if self.role is DateRole.DOCUMENT:
            how = f'its "{self.label}" line' if self.label else "its date line"
            return f'{doc} gives its own date as {self.written} ({how}): "{self.quoted}"'
        if self.role is DateRole.EMBEDDED:
            return f'{doc} carries a header dated {self.written} ("{self.label}"): "{self.quoted}"'
        if self.role is DateRole.NAME:
            return f'The name of the file "{self.quote}" prints {self.written}; this is the name, not the document\'s words'
        if self.role is DateRole.HEADING:
            return f'{doc} carries {self.written} in a line at its head: "{self.quoted}"'
        own = f", dated {self.document_day.isoformat()} at its head," if self.document_day else ""
        return f'{doc}{own} says: "{self.quoted}"'

    def as_dict(self) -> dict[str, Any]:
        return {"date": self.day.isoformat(), "end": self.end.isoformat() if self.end else None,
                "written": self.written, "precision": self.precision.value, "approximate": self.approximate,
                "role": self.role.value, "rule": self.rule, "label": self.label, "quote": self.quote,
                "cutBefore": self.cut_before, "cutAfter": self.cut_after,
                "documentDate": self.document_day.isoformat() if self.document_day else None,
                **self.place.as_dict(), "alsoIn": [p.as_dict() for p in self.also]}


@dataclass(frozen=True)
class RecordedEvent:
    """An entry of the specification's own chronology (a ``LegalCase`` event): its day, its step in the
    specification's words, and where the specification says it is recorded. Not a quote from a file."""

    day: date
    step: str
    where: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"date": self.day.isoformat(), "step": self.step, "recordedIn": self.where,
                "source": "the specification's record"}


# --- reading a passage ------------------------------------------------------------------------------------------------


def _norm_label(label: str) -> str:
    return " ".join(re.sub(r"[^a-z ]", " ", label.lower()).split())


def _label_before(text: str, line_start: int, at: int) -> str:
    """The label of a "Label: date" line, as written, or "". A label of up to four words at the line's start is taken
    as it stands; mid-line (a passage with no line breaks) only a known label is."""
    m = _LABEL_BEFORE.search(text[line_start:at])
    if not m:
        return ""
    label = " ".join(m.group(1).split())
    words = label.split()
    at_line_start = not text[line_start: line_start + m.start(1)].strip(_LINE_LEAD)
    if at_line_start and 1 <= len(words) <= 4:
        return label
    for n in (3, 2, 1):
        tail = " ".join(words[-n:])
        if len(words) >= n and _norm_label(tail) in DOCUMENT_LABELS | ABOUT_LABELS:
            return tail
    return ""


def _line_before(text: str, at: int) -> tuple[int, int] | None:
    """(start, end) of the last line with words before offset ``at`` (a line's start), or None."""
    end = at
    while end > 0:
        start = text.rfind("\n", 0, end - 1) + 1
        if text[start:end].strip():
            return start, end
        end = start
    return None


def _line_after(text: str, at: int) -> tuple[int, int] | None:
    """(start, end) of the first line with words from offset ``at`` (a line's end) on, or None."""
    start = at
    while start < len(text):
        end = text.find("\n", start + 1)
        end = len(text) if end == -1 else end
        if text[start:end].strip():
            return start, end
        start = end
    return None


def _cell_bounds(text: str, clause: tuple[int, int]) -> tuple[int, int]:
    """A cell's statement: its own line with the line above and the line below, each when it is short."""
    line_start = text.rfind("\n", 0, clause[0]) + 1
    line_end = text.find("\n", clause[1])
    line_end = len(text) if line_end == -1 else line_end
    above, below = _line_before(text, line_start), _line_after(text, line_end)
    start = above[0] if above is not None and above[1] - above[0] <= CELL_LINE_CHARS else clause[0]
    end = below[1] if below is not None and below[1] - below[0] <= CELL_LINE_CHARS else clause[1]
    return start, end


def statement_at(text: str, statements: Sequence[tuple[int, int]], start: int, end: int) -> tuple[tuple[int, int], bool]:
    """The statement that carries text[start:end], and whether it is a cell: a value with at most ``CELL_WORDS``
    other words on its line and no label before it there (a form's field, a table's cell), which gets the short lines
    above and below it, since the value alone says nothing."""
    clause = clause_at(statements, start, end)
    labeled = ":" in text[text.rfind("\n", 0, start) + 1: start]
    if "\n" in text and not labeled and len(text[clause[0]: clause[1]].split()) - len(text[start:end].split()) <= CELL_WORDS:
        return _cell_bounds(text, clause), True
    return clause, False


def _is_label_line(line: str) -> bool:
    """Whether a line above a bare date is that date's label, as a form prints it: short, and ending in a colon, or
    a known label, or a label that says "date" ("Battery Date")."""
    line = line.strip()
    if not line or len(line) > LABEL_LINE_CHARS or len(line.split()) > 5 or not re.search(r"[A-Za-z]", line):
        return False
    return (line.endswith(":") or _norm_label(line) in DOCUMENT_LABELS | ABOUT_LABELS
            or bool(re.search(r"\bdated?\b", line, re.I)))


def _role(text: str, span: DateSpan, *, head: bool) -> tuple[DateRole, str, str, tuple[int, int] | None]:
    """(role, rule, label, the statement's bounds when the rule sets them) for one date in a passage; ``head`` says
    the date sits at the head of its file.

    - ``label-line``: "Label: date" on one line. A document label (``DOCUMENT_LABELS``) at the head is the document's
      own date; a message label (``MESSAGE_LABELS``) further in is a header inside the document; any other is a date
      spoken about, with its label kept.
    - ``label-above``: a line that is only the date, under a short label line, as a form prints a field. The
      statement is the two lines, and the role is the label's, as above.
    - ``date-line``: a line that is only the date, at the head, with no label above: a letter's date line.
    - ``date-cell`` (given by ``events_of``): a line further in that is the date and at most ``CELL_WORDS`` other
      words, with no label: a form's or a table's cell. The statement carries the short lines above and below it,
      since the date alone says nothing.
    - ``head-line``: a short line at the head that carries the date and no word saying the date is about something
      else ("Minutes of the meeting of March 5, 2099"). Its role is ``HEADING``, not the document's own date: a
      notice's scheduled time reads the same.
    - ``sentence``: any other date."""
    def labeled(label: str) -> DateRole:
        norm = _norm_label(label)
        if head and norm in DOCUMENT_LABELS:
            return DateRole.DOCUMENT
        return DateRole.EMBEDDED if not head and norm in MESSAGE_LABELS else DateRole.ABOUT

    line_start = text.rfind("\n", 0, span.start) + 1
    line_end = text.find("\n", span.end)
    line_end = len(text) if line_end == -1 else line_end
    label = _label_before(text, line_start, span.start)
    if label:
        return labeled(label), "label-line", label, None
    if "\n" not in text:
        return DateRole.ABOUT, "sentence", "", None
    before, after = text[line_start:span.start], text[span.end:line_end]
    if _DATE_LINE_REST.match(before) and _DATE_LINE_REST.match(after):
        above = _line_before(text, line_start)
        if above is not None and _is_label_line(text[above[0]: above[1]]):
            label = text[above[0]: above[1]].strip().rstrip(":").strip()
            return labeled(label), "label-above", label, (above[0], line_end)
        if head:
            return DateRole.DOCUMENT, "date-line", "", None
        return DateRole.ABOUT, "sentence", "", None          # a cell: ``events_of`` gives it the lines around it
    if not head:
        return DateRole.ABOUT, "sentence", "", None
    line = text[line_start:line_end].strip()
    if (len(line) <= HEAD_LINE_CHARS and len(line.split()) <= HEAD_LINE_WORDS and not line.endswith(".")
            and not _ABOUT_CUE.search(before + " " + after)):
        return DateRole.HEADING, "head-line", "", None
    return DateRole.ABOUT, "sentence", "", None


def events_of(passage: Passage, row: Row, *, today: date | None = None) -> list[Event]:
    """The dated statements of one passage, in the order the text gives them."""
    text = passage.text
    spans = date_spans(text, today=today)
    if not spans:
        return []
    statements = clauses(text)
    out: list[Event] = []
    i = 0
    while i < len(spans):
        span, last, end = spans[i], spans[i], None
        if i + 1 < len(spans):
            joined = _RANGE_JOIN.fullmatch(text[span.end: spans[i + 1].start])
            if joined and spans[i + 1].day >= span.day and (
                    joined.group("join").lower() != "and" or _BETWEEN.search(text[max(0, span.start - 12): span.start])):
                last, end = spans[i + 1], spans[i + 1].day
                i += 1
        i += 1
        head = passage.index == 0 and span.start < HEAD_CHARS
        role, rule, label, bounds = _role(text, span, head=head)
        if end is not None and role is not DateRole.ABOUT:
            role = DateRole.ABOUT                     # a period is spoken about, whatever line it sits on
        if bounds is not None and end is None:
            clause = bounds
        elif rule == "sentence" and role is DateRole.ABOUT:
            clause, cell = statement_at(text, statements, span.start, last.end)
            rule = "date-cell" if cell else rule
        else:
            clause = clause_at(statements, span.start, last.end)
        quote, cut_before, cut_after, at = quote_of(text, clause, span.start, last.end)
        out.append(Event(
            span.day, quote, place_of(passage, row, at), role, rule,
            written=squash(text[span.start: last.end]), label=label, end=end,
            approximate=bool(_APPROXIMATE.search(text[max(0, span.start - 24): span.start])), precision=span.precision,
            cut_before=cut_before, cut_after=cut_after))
    return out


# --- folding and sorting ----------------------------------------------------------------------------------------------


def _standing_rank(standing: Standing) -> int:
    return STANDING_ORDER.index(standing) if standing in STANDING_ORDER else len(STANDING_ORDER)


def _sort_key(event: Event) -> tuple:
    return (event.day, _standing_rank(event.place.standing), _ROLE_ORDER.index(event.role), event.place.path,
            event.place.passage, event.place.char)


def fold(events: Iterable[Event], passages: dict[tuple[str, int], Passage] | None = None) -> list[Event]:
    """Near copies of a statement on the same day as one event, the others listed under it (``Event.also``). Two
    statements are copies when their words are (``retrieval.near_copies``). A short statement (a date line, a form's
    field) folds only when the two passages it sits in are the same nearly letter for letter, so two letters dated
    the same day, or two reports filled in on one form, stay two."""
    passages = passages or {}
    groups: list[list[Event]] = []
    by_day: dict[tuple, list[list[Event]]] = {}
    cache: dict[int, frozenset[str]] = {}
    as_passage: dict[int, Passage] = {}

    def quote_passage(event: Event) -> Passage:
        if id(event) not in as_passage:
            as_passage[id(event)] = Passage(Path(event.place.path), event.place.passage, event.place.word, event.quote)
        return as_passage[id(event)]

    def copies(a: Event, b: Event) -> bool:
        if a.role is not b.role or not retrieval.near_copies(quote_passage(a), quote_passage(b), cache=cache):
            return False
        if (a.place.path, a.quote) == (b.place.path, b.quote):          # the same words where two passages overlap
            return True
        if min(len(a.quote.split()), len(b.quote.split())) >= FOLD_WORDS:
            return True
        pa = passages.get((a.place.path, a.place.passage))
        pb = passages.get((b.place.path, b.place.passage))
        return pa is not None and pb is not None and retrieval.near_copies(pa, pb, threshold=SHORT_FOLD_SIMILARITY,
                                                                          cache=cache)

    for event in sorted(events, key=_sort_key):
        day_groups = by_day.setdefault((event.day, event.end), [])
        for group in day_groups:
            if copies(group[0], event):
                group.append(event)
                break
        else:
            group = [event]
            day_groups.append(group)
            groups.append(group)
    out: list[Event] = []
    for group in groups:
        lead = group[0]
        seen = {(lead.place.path, lead.quote)}
        also: list[Place] = []
        for other in group[1:]:
            if (other.place.path, other.quote) in seen:
                continue
            seen.add((other.place.path, other.quote))
            also.append(other.place)
        out.append(replace(lead, also=tuple(also)) if also else lead)
    return out


# --- the chronology ---------------------------------------------------------------------------------------------------


def describe_scope(scope: Scope) -> str:
    """A scope in a line, for a page's header."""
    parts = []
    if scope.catalogs:
        parts.append("catalogs " + ", ".join(scope.catalogs))
    if scope.standings:
        parts.append("standings " + ", ".join(s.value for s in scope.standings))
    if scope.kinds:
        parts.append("kinds " + ", ".join(scope.kinds))
    if scope.folders:
        parts.append("folders " + ", ".join(scope.folders))
    held = ("with the files held back unless asked" if scope.confidential else
            f"with the held files of {', '.join(scope.confidential_in)}" if scope.confidential_in else
            "without the files held back unless asked")
    return "; ".join([*parts, held]) if parts else f"every catalog; {held}"


def slug_of(title: str) -> str:
    """A title as a folder name under ``data/collections``."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "collection"


@dataclass(frozen=True)
class SourceFile:
    """One file the lens read, with how many of its statements are in the result."""

    file: str
    path: str
    context: str
    catalog: str
    standing: Standing
    kind: str
    confidential: bool
    generated: bool
    statements: int = 0

    @property
    def document(self) -> str:
        return f"{self.file} ({self.context})" if self.context else self.file

    def as_dict(self) -> dict[str, Any]:
        return {"file": self.file, "path": self.path, "context": self.context, "catalog": self.catalog,
                "standing": self.standing.value, "kind": self.kind, "confidential": self.confidential,
                "generated": self.generated, "statements": self.statements}


def source_files(loaded: pi.Loaded, counts: dict[str, int]) -> tuple[SourceFile, ...]:
    """The files a scope gave, each once, with ``counts`` (by path) of what the lens found in it."""
    out: dict[str, SourceFile] = {}
    for passage in loaded.passages:
        path = str(passage.path)
        if path in out:
            continue
        row = loaded.rows[(path, passage.index)]
        out[path] = SourceFile(passage.title, path, passage.context, row.catalog, row.standing, row.kind,
                               row.confidential, row.generated, counts.get(path, 0))
    return tuple(out.values())


def page_header(heading: str, *, today: date, scope: Scope, files: Sequence[SourceFile], what: str,
                extra: Sequence[str] = (), confidential: bool | None = None) -> list[str]:
    """The lines every generated collection page opens with: that jason generated it and from what, that it is a
    summary and not the record, and whether it is confidential (when any source is)."""
    held = [f for f in files if f.confidential]
    is_confidential = bool(held) if confidential is None else confidential or bool(held)
    return [f"# {heading}", "",
            f"- Generated: by jason on {today.isoformat()}, by rule (no model), from the {len(files)} documents listed "
            f"under Sources. No person wrote or checked it.",
            f"- Standing: a summary, not the record. {what}",
            ("- Confidential: yes. " + (f"{len(held)} of its sources are held back unless asked; " if held else "")
             + "for directors and counsel only." if is_confidential else
             "- Confidential: no. No source is held back unless asked."),
            f"- Scope: {describe_scope(scope)}", *[f"- {line}" for line in extra], ""]


def sources_section(files: Sequence[SourceFile], noun: str) -> list[str]:
    out = ["## Sources", ""]
    for f in files:
        flags = ", ".join(part for part in (f.catalog, f.standing.value, f.kind.replace("_", " "),
                                            "confidential" if f.confidential else "",
                                            "generated by jason" if f.generated else "") if part)
        out.append(f"- {f.document} [{flags}]: {f.statements} {noun}")
    return [*out, ""]


@dataclass
class Chronology:
    """The dated statements of a scope, in date order, with the specification's record kept apart."""

    title: str
    scope: Scope
    events: tuple[Event, ...] = ()
    recorded: tuple[RecordedEvent, ...] = ()
    files: tuple[SourceFile, ...] = ()
    recorded_confidential: bool = False
    since: date | None = None
    until: date | None = None
    partial: int = 0                     # mentions of a month and a day with no year: not placed
    caveats: tuple[str, ...] = CAVEATS

    @property
    def confidential(self) -> bool:
        """Whether the page is held back: any file it read is (its name is listed even when it gave no statement),
        or it carries the specification's record of a confidential matter."""
        return any(f.confidential for f in self.files) or bool(self.recorded and self.recorded_confidential)

    @property
    def span(self) -> tuple[date, date] | None:
        days = [e.day for e in self.events] + [e.end for e in self.events if e.end]
        return (min(days), max(days)) if days else None

    def counts(self) -> dict[str, Any]:
        span = self.span
        return {"events": len(self.events), "files": len(self.files),
                "filesWithEvents": sum(1 for f in self.files if f.statements),
                "from": span[0].isoformat() if span else None, "to": span[1].isoformat() if span else None,
                "byRole": {role.value: sum(1 for e in self.events if e.role is role) for role in DateRole},
                "folded": sum(len(e.also) for e in self.events), "recorded": len(self.recorded),
                "datesWithNoYear": self.partial}

    def _summary(self, noun: str) -> str:
        c = self.counts()
        text = (f"{c['events']} dated statements from {c['filesWithEvents']} of {c['files']} {noun}"
                + (f", {c['from']} to {c['to']}" if c["from"] else "") + f"; {c['folded']} near copies folded")
        if self.partial:
            text += (f"; about {self.partial} mentions of a month and a day with no year were not placed (a spoken or "
                     f"a short date)")
        return text

    def as_dict(self) -> dict[str, Any]:
        return {"title": self.title, "generatedBy": "jason (rule-based; no model)", "confidential": self.confidential,
                "scope": describe_scope(self.scope), "counts": self.counts(),
                "events": [e.as_dict() for e in self.events], "recorded": [e.as_dict() for e in self.recorded],
                "files": [f.as_dict() for f in self.files], "caveats": list(self.caveats)}

    def lines(self) -> list[str]:
        """The chronology for a terminal: a line an event, then the specification's record, then the caveats."""
        out = []
        for e in self.events:
            flags = ", ".join(part for part in (e.place.standing.value, e.place.kind,
                                                "confidential" if e.place.confidential else "") if part)
            label = f' "{e.label}"' if e.label else ""
            out.append(f"{e.when}  [{e.role.value}{label}; {e.rule}]  {e.place.document} [{flags}] {e.place.where}")
            out.append(f'    "{e.quoted}"')
            if e.also:
                out.append("    also in: " + "; ".join(f"{p.document} {p.where}" for p in e.also))
        if self.recorded:
            out += ["", "The specification's record (not a quote from a file):"]
            out += [f"{e.day.isoformat()}  {e.step}" + (f"  [recorded in: {e.where}]" if e.where else "") for e in self.recorded]
        out += ["", self._summary("files")]
        out += [f"Note: {caveat}" for caveat in self.caveats]
        return out

    def markdown(self, today: date | None = None) -> str:
        """The generated page: its header, the documents' statements by day, the specification's record, the sources."""
        today = today or date.today()
        extra = [f"Found: {self._summary('documents')}."]
        if self.since or self.until:
            extra.append(f"Dates kept: {self.since.isoformat() if self.since else 'the first'} to "
                         f"{self.until.isoformat() if self.until else 'the last'}.")
        out = page_header(f"Chronology: {self.title}", today=today, scope=self.scope, files=self.files,
                          what="Each line quotes what a document says and names the document. It does not find that "
                               "the event happened.", extra=extra,
                          confidential=bool(self.recorded and self.recorded_confidential))
        out += ["## What the documents say", ""]
        if not self.events:
            out += ["No dated statement was read in the scope.", ""]
        day: str | None = None
        for e in self.events:
            if e.when != day:
                day = e.when
                out += [f"### {day}", ""]
            label = f', "{e.label}" line' if e.label else ""
            own = f"; the document's own date at its head: {e.document_day.isoformat()}" if (
                e.document_day and e.role is DateRole.ABOUT) else ""
            flags = ", ".join(part for part in (e.place.standing.value, e.place.kind.replace("_", " "),
                                                "confidential" if e.place.confidential else "") if part)
            if e.role is DateRole.NAME:
                out += [f"- {ROLE_WORDS[e.role]} (written \"{e.written}\"; rule {e.rule}). {e.place.document} [{flags}]. "
                        f"The name is:", f"  > {e.quote}", ""]
                continue
            out.append(f"- {ROLE_WORDS[e.role]}{label} (written \"{e.written}\"; rule {e.rule}). "
                       f"{e.place.document} [{flags}], {e.place.where}{own}. It says:")
            out.append(f"  > {e.quoted}")
            if e.also:
                out.append("  - The same words are also in: " + "; ".join(f"{p.document}, {p.where}" for p in e.also))
            out.append("")
        if self.recorded:
            out += ["## The specification's record", "",
                    "These entries are the specification's own chronology, confirmed by a person. They are kept apart "
                    "from the statements above: none is a quote from a file, and none is merged with one.", ""]
            out += [f"- {e.day.isoformat()}: {e.step}" + (f" (recorded in: {e.where})" if e.where else "")
                    for e in self.recorded]
            out.append("")
        out += sources_section(self.files, "dated statements")
        out += ["## Caveats", "", *[f"- {caveat}" for caveat in self.caveats], ""]
        return "\n".join(out)


def chronology(data_dir: Path | str, scope: Scope, title: str, *, since: date | None = None, until: date | None = None,
               recorded: Sequence[Any] = (), recorded_confidential: bool = True, today: date | None = None) -> Chronology:
    """The chronology of the passages ``scope`` allows (``passage_index.load``).

    ``since`` and ``until`` keep the events whose day (or range) falls within them. ``recorded`` is the
    specification's own chronology for the collection, when it holds one: records with ``day``, ``step``, and
    ``source`` (a ``LegalCase``'s ``events``); they are returned apart, as ``Chronology.recorded``, held to the same
    dates. ``recorded_confidential`` says whether those entries are held back (a legal case's are). Raises
    ``FileNotFoundError`` when there is no index."""
    loaded = pi.load(data_dir, scope, vectors=False)
    by_place = {(str(p.path), p.index): p for p in loaded.passages}
    lines = FileLines()
    found: list[Event] = []
    named: set[str] = set()
    partial = 0
    for passage in loaded.passages:
        row = loaded.rows[(str(passage.path), passage.index)]
        found += events_of(lines(passage), row, today=today)
        partial += partial_dates(passage.text)
        if str(passage.path) not in named:               # the file's name, once a file: a date its words may not give
            named.add(str(passage.path))
            found += [Event(span.day, passage.title, place_of(passage, row), DateRole.NAME, "file-name", span.written)
                      for span in name_spans(passage.title, today=today)]
    # The document's own date: the first one its head gives.
    own: dict[str, date] = {}
    for e in sorted((e for e in found if e.role is DateRole.DOCUMENT), key=lambda e: (e.place.path, e.place.passage, e.place.char)):
        own.setdefault(e.place.path, e.day)
    found = [replace(e, document_day=own[e.place.path]) if e.place.path in own else e for e in found]

    def kept(day: date, end: date | None = None) -> bool:
        return (since is None or (end or day) >= since) and (until is None or day <= until)

    events = tuple(fold((e for e in found if kept(e.day, e.end)), by_place))
    counts: dict[str, int] = {}
    for e in events:
        counts[e.place.path] = counts.get(e.place.path, 0) + 1
    entries = tuple(sorted((RecordedEvent(r.day, str(r.step), str(getattr(r, "source", "") or "")) for r in recorded
                            if kept(r.day)), key=lambda r: r.day))
    return Chronology(title, scope, events, entries, source_files(loaded, counts), recorded_confidential, since, until,
                      partial)


def page_path(data_dir: Path | str, slug: str, name: str) -> Path:
    return Path(data_dir) / COLLECTIONS_DIR / slug / name


def write_page(data_dir: Path | str, slug: str, name: str, text: str) -> Path:
    """Save a generated collection page (``data/collections/<slug>/<name>``) under the store lock."""
    from jason.locks import Resource, hold

    path = page_path(data_dir, slug, name)
    with hold(Resource.STORE, "collections", purpose=f"write the collection page {slug}/{name}"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return path


__all__ = ["ABOUT_LABELS", "CAVEATS", "CHRONOLOGY_PAGE", "COLLECTIONS_DIR", "Chronology", "DATE_SPAN", "DOCUMENT_LABELS",
           "MESSAGE_LABELS", "DateRole", "DateSpan", "Event", "FileLines", "Place", "Precision", "ROLE_WORDS", "RecordedEvent", "STANDING_ORDER",
           "SourceFile", "chronology", "clause_at", "clauses", "date_spans", "describe_scope", "events_of", "fold",
           "name_spans", "page_header", "page_path", "partial_dates", "place_of", "quote_of", "read_date", "statement_at", "slug_of", "source_files", "sources_section",
           "squash", "write_page"]
