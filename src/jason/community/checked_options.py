"""Checked options: which of a proposal's offered options were chosen, read from the text alone.

A proposal or service agreement often offers a short list of options and asks the customer to mark the ones wanted: a
row of boxes in the header ("☐ Certificate of Insurance ☒ Inspection Program"), bracketed choices ("[X] Monthly
service"), or blank lines to initial or mark ("______ Annual Inspection"). What was chosen is part of the agreement, so
the reader needs it, and it must never be guessed.

``find_options(text)`` reads each option with the ``MARKERS`` rows. A row names how a marker looks, whether it is read
anywhere on a line or only at the line's start, and what it says about the mark. The label is the words after the
marker, up to the next marker on the same line or the line's end, trimmed and capped at 120 characters.

``checked`` is True or False only when the option's own line says so: a filled box, an X in the brackets, an X or check
on the blank. An empty blank line is ``None``: the text cannot say. A signed PDF often draws the X in a separate text
layer, so it lands elsewhere in the extracted text (a lone "X" lines after the list) and belongs to an option only by
its place on the page. That is for a layout reader, which knows each mark's position, to settle later; this reader
leaves those options ``None`` and never moves a mark from another line onto an option.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

LABEL_CAP = 120

_CHECKS = "Xx✓✔☒☑"
_BLANK = re.compile(r"_{3,}")


class Placement(Enum):
    ANYWHERE = "anywhere"  # an unambiguous glyph: a box is an option wherever it sits
    LINE_START = "line start"  # brackets and blanks also occur in prose and signature lines


class Reading(Enum):
    CHECKED = "checked"
    UNCHECKED = "unchecked"
    INNER = "inner"  # checked when the marker holds an X or a check, else unchecked
    BLANK = "blank"  # checked when the blank carries a mark, else the text cannot say


@dataclass(frozen=True)
class Option:
    label: str
    checked: bool | None
    marker: str
    start: int
    end: int


@dataclass(frozen=True)
class MarkerRow:
    name: str
    pattern: re.Pattern[str]
    placement: Placement
    reading: Reading


MARKERS: tuple[MarkerRow, ...] = (
    # Order matters: a blank or brackets may hold a check glyph, so they claim their span before the bare glyphs do.
    # "X ____", "____", "__X__": a blank with an optional mark before it or inside it.
    MarkerRow(
        "blank",
        re.compile(rf"(?:[{_CHECKS}][ \t]*)?_+(?:[{_CHECKS}]_*)?"),
        Placement.LINE_START,
        Reading.BLANK,
    ),
    MarkerRow("brackets", re.compile(r"\[[ \t]*[Xx✓✔]?[ \t]*\]"), Placement.LINE_START, Reading.INNER),
    MarkerRow("parentheses", re.compile(r"\([ \t]*[Xx✓✔]?[ \t]*\)"), Placement.LINE_START, Reading.INNER),
    MarkerRow("checked box", re.compile(r"[☒☑✓✔]"), Placement.ANYWHERE, Reading.CHECKED),
    MarkerRow("empty box", re.compile(r"[☐□]"), Placement.ANYWHERE, Reading.UNCHECKED),
)

_LEAD = re.compile(r"[ \t]*(?:[-*•o][ \t]+)?")


def _checked(row: MarkerRow, marker: str) -> bool | None:
    if row.reading is Reading.CHECKED:
        return True
    if row.reading is Reading.UNCHECKED:
        return False
    marked = any(ch in _CHECKS for ch in marker)
    if row.reading is Reading.INNER:
        return marked
    return True if marked else None


def _markers(line: str) -> list[tuple[int, int, MarkerRow]]:
    """Every marker on one line, left to right; the first row to claim a span wins."""
    found: list[tuple[int, int, MarkerRow]] = []
    taken: list[tuple[int, int]] = []
    lead = _LEAD.match(line).end()
    for row in MARKERS:
        for m in row.pattern.finditer(line):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            # One or two underscores are punctuation; a blank to mark is at least three.
            if row.reading is Reading.BLANK and m.group().count("_") < 3:
                continue
            found.append((m.start(), m.end(), row))
            taken.append((m.start(), m.end()))
    found.sort(key=lambda f: f[0])
    kept: list[tuple[int, int, MarkerRow]] = []
    for start, end, row in found:
        if row.placement is Placement.LINE_START:
            # At the line's start, or right after another option on a line that opens with one.
            if not (start == lead or (kept and kept[0][0] == lead)):
                continue
        kept.append((start, end, row))
    return kept


# The words under or beside a signature block's blank line: what goes on the line, not an option.
_FORM_FIELD = re.compile(
    r"^\(?\s*(?:\w+\s+){0,2}(?:signature|sign(?:ed)?|initials?|print(?:ed)?\s+name|name|title|date|by|its)"
    r"(?:\s+here)?\s*\)?\s*$", re.IGNORECASE)


def find_options(text: str) -> list[Option]:
    """Each offered option in ``text``, in order, with whether its own line marks it chosen.

    Note: blank-line options whose marks sit elsewhere in the text layer (a lone "X" after the list) come back with
    ``checked=None``; a later layout reader fills them from the marks' positions on the page.
    """
    options: list[Option] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        marks = _markers(body)
        for i, (start, end, row) in enumerate(marks):
            stop = marks[i + 1][0] if i + 1 < len(marks) else len(body)
            raw = body[end:stop]
            label = raw.strip()
            # A label needs words, and a blank inside it means a fill-in line ("____ Date ____"), not an option.
            if not re.search(r"[A-Za-z]", label) or _BLANK.search(label):
                continue
            # A signature block's blank names what is written on it ("(print name)", "(Client initials here)"): a
            # field to fill, not an option to choose.
            if row.reading is Reading.BLANK and _FORM_FIELD.match(label):
                continue
            if row.reading is Reading.BLANK and not raw[:1].isspace():
                continue
            label = label[:LABEL_CAP].rstrip()
            label_end = end + (len(raw) - len(raw.lstrip())) + len(label)
            options.append(
                Option(
                    label=label,
                    checked=_checked(row, body[start:end]),
                    marker=body[start:end].strip(),
                    start=offset + start,
                    end=offset + label_end,
                )
            )
        offset += len(line)
    return options


__all__ = ["LABEL_CAP", "MARKERS", "MarkerRow", "Option", "Placement", "Reading", "find_options"]
