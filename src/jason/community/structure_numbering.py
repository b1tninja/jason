"""The numbering grammar of printed headings, and the check that a number follows the one before it.

A heading prints its number in a few shapes: ``ARTICLE IV``, ``Section 3.2``, ``B-12.``, ``1.1``, ``A.``, ``(a)``,
``(ii)``. ``split_number`` reads the number off the front of a line and returns it as printed with the words after it.
``SequenceCheck`` walks the numbers of a document's headings in order and notes a gap, a repeat, or a number out of
order: findings for a person, never silently repaired (the number stays as printed).

Nothing here names an association: the grammar is how documents number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class NumberKind(Enum):
    WORD = "word"          # Article IV, Section 3.2, Rule 4.1
    DASH = "dash"          # B-12, R-3.1
    DOTTED = "dotted"      # 1, 1.1, 1.1.2
    CAPITAL = "capital"    # A.
    PAREN = "paren"        # (a), (ii), (1), (A)
    ROMAN = "roman"        # IV.


_ROMAN = re.compile(r"^(?=[IVXLCivxlc])(?:M{0,3})(?:CM|CD|D?C{0,3}|cm|cd|d?c{0,3})(?:XC|XL|L?X{0,3}|xc|xl|l?x{0,3})"
                    r"(?:IX|IV|V?I{0,3}|ix|iv|v?i{0,3})$")
_WORD = re.compile(r"^(?P<num>(?:article|section|rule|part|chapter|exhibit|appendix|schedule)\s+"
                   r"(?:[IVXLC]+|\d+(?:\.\d+)*(?:\([a-z0-9]+\))*|[A-Z]))(?P<sep>\s*[-–—.:)]?)(?:\s+|$)(?P<rest>.*)$", re.I)
_DASH = re.compile(r"^(?P<num>[A-Z]{1,2}-\d+(?:\.\d+)*)(?P<sep>[.):]?)\s+(?P<rest>\S.*)$")
_DOTTED = re.compile(r"^(?P<num>\d{1,3}(?:\.\d{1,3})*)(?P<sep>[.)]?)\s+(?P<rest>\S.*)$")
_CAPITAL = re.compile(r"^(?P<num>[A-Z])(?P<sep>[.)])\s+(?P<rest>\S.*)$")
_PAREN = re.compile(r"^(?P<num>\((?:[a-z]{1,4}|[A-Z]{1,4}|\d{1,3})\))\s*(?P<rest>\S.*)?$")
_ROMAN_LEAD = re.compile(r"^(?P<num>[IVXLC]{1,6}|[ivxlc]{1,6})(?P<sep>[.)])\s+(?P<rest>\S.*)$")


@dataclass(frozen=True)
class Number:
    kind: NumberKind
    printed: str            # as the line prints it ("ARTICLE IV", "B-12.", "(a)")
    tokens: tuple           # ("IV",), ("B", 12), (1, 1), ("a",)
    rest: str               # the words after the number

    @property
    def depth(self) -> int:
        """How deep the number sits by itself: ``ARTICLE`` and ``A.`` are 1, each dotted part adds one. A parenthesized
        number has no depth of its own (0): it hangs from the heading before it."""
        if self.kind is NumberKind.DOTTED:
            return len(self.tokens)
        if self.kind is NumberKind.DASH:
            return len(self.tokens) - 1
        return 0 if self.kind is NumberKind.PAREN else 1


def roman_value(token: str) -> int:
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    total, prev = 0, 0
    for ch in reversed(token.lower()):
        v = values.get(ch, 0)
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return total


def split_number(line: str) -> Number | None:
    """The number a heading line starts with, as printed, and the words after it; None when it starts with none."""
    s = line.strip()
    if not s:
        return None
    if m := _WORD.match(s):
        raw = m["num"]
        word, _, value = raw.partition(" ")
        value = value.strip()
        token = int(value) if value.isdigit() else value
        printed = raw + (m["sep"].strip() if m["sep"].strip() in (".", ":") else "")
        return Number(NumberKind.WORD, printed, (word.lower(), token), m["rest"].strip(" -–—:"))
    if m := _DASH.match(s):
        letter, _, digits = m["num"].partition("-")
        parts = tuple(int(x) for x in digits.split("."))
        return Number(NumberKind.DASH, m["num"] + m["sep"], (letter, *parts), m["rest"].strip())
    if m := _DOTTED.match(s):
        rest = m["rest"].strip()
        if re.match(r"^\d", rest) and not m["sep"]:
            return None                                   # "12 34 ..." is two numbers, not a heading
        return Number(NumberKind.DOTTED, m["num"] + m["sep"], tuple(int(x) for x in m["num"].split(".")), rest)
    if m := _ROMAN_LEAD.match(s):
        if _ROMAN.match(m["num"]) and (len(m["num"]) > 1 or m["num"] in "IVXivx" and m["sep"] == "."):
            return Number(NumberKind.ROMAN, m["num"] + m["sep"], (m["num"],), m["rest"].strip())
    if m := _CAPITAL.match(s):
        return Number(NumberKind.CAPITAL, m["num"] + m["sep"], (m["num"],), m["rest"].strip())
    if m := _PAREN.match(s):
        token = m["num"][1:-1]
        return Number(NumberKind.PAREN, m["num"], (token,), (m["rest"] or "").strip())
    return None


def fold_number(printed: str) -> str:
    """A printed number as compared: case folded, spaces and trailing punctuation taken off ("8.5." equals "8.5")."""
    s = re.sub(r"\s+", "", printed or "").casefold()
    return s if s.startswith("(") else s.rstrip(".:)")


def fold_text(text: str) -> str:
    """A heading's words as compared: case, accents, punctuation, and spacing folded."""
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _value(tokens: tuple, kind: NumberKind) -> tuple[tuple, int] | None:
    """(the family it counts in, its place in the family): ("B", 12) is in family ("B",) at 12."""
    if kind is NumberKind.DOTTED:
        return tokens[:-1], tokens[-1]
    if kind is NumberKind.DASH:
        return (tokens[0], *tokens[1:-1]), tokens[-1]
    if kind is NumberKind.WORD:
        word, v = tokens
        if isinstance(v, int):
            return (word,), v
        if re.fullmatch(r"[IVXLC]+", v):
            return (word,), roman_value(v)
        if re.fullmatch(r"[A-Z]", v):
            return (word,), ord(v) - 64
        return None
    if kind is NumberKind.CAPITAL:
        return ("capital",), ord(tokens[0]) - 64
    if kind is NumberKind.ROMAN:
        return ("roman",), roman_value(tokens[0])
    if kind is NumberKind.PAREN:
        t = tokens[0]
        if t.isdigit():
            return ("paren-digit",), int(t)
        if t.isupper():
            return ("paren-capital",), ord(t[0]) - 64 if len(t) == 1 else roman_value(t)
        return ("paren-lower",), ord(t[0]) - 96 if len(t) == 1 else roman_value(t)
    return None


@dataclass(frozen=True)
class SequenceFinding:
    kind: str               # "gap", "repeat", "out of order"
    printed: str
    after: str              # the number it was read after
    detail: str


class SequenceCheck:
    """Numbers in reading order, each checked against the one before it in its family. ``see`` returns how the number
    stands: ``"first"``, ``"next"`` (the successor), or the finding's kind. Nothing is corrected."""

    def __init__(self) -> None:
        self.last: dict[tuple, tuple[int, str]] = {}
        self.findings: list[SequenceFinding] = []
        self._scope: tuple = ()

    def see(self, number: Number) -> str:
        got = _value(number.tokens, number.kind)
        if got is None:
            return "unread"
        family, value = got
        if number.kind in (NumberKind.DOTTED, NumberKind.DASH, NumberKind.WORD, NumberKind.CAPITAL, NumberKind.ROMAN):
            self._scope = (number.kind, family, value)
            key = (number.kind, family)
        else:
            key = (number.kind, family, self._scope[:2])
        before = self.last.get(key)
        self.last[key] = (value, number.printed)
        # A shallower number starts a new run beneath it.
        for other in [k for k in self.last if len(k) > 1 and k != key and k[0] in (NumberKind.PAREN,) and number.kind is not NumberKind.PAREN]:
            del self.last[other]
        if number.kind is NumberKind.DOTTED:
            for other in [k for k in self.last if k[0] is NumberKind.DOTTED and len(k[1]) > len(family) and k[1][:len(family)] == family + (value,)]:
                del self.last[other]
        if before is None:
            return "first"
        prev, printed = before
        if value == prev + 1:
            return "next"
        if value == prev:
            self.findings.append(SequenceFinding("repeat", number.printed, printed, f"{number.printed} follows {printed}"))
            return "repeat"
        if value < prev:
            self.findings.append(SequenceFinding("out of order", number.printed, printed,
                                                 f"{number.printed} follows {printed}"))
            return "out of order"
        self.findings.append(SequenceFinding("gap", number.printed, printed, f"{number.printed} follows {printed}"))
        return "gap"


__all__ = ["Number", "NumberKind", "SequenceCheck", "SequenceFinding", "fold_number", "fold_text", "roman_value",
           "split_number"]


_LEADER = re.compile(r"^(?P<title>.*?\S)\s*(?:\.{2,}|\s{2,}|\s)\s*(?P<page>\d{1,4}|[ivxlc]{1,6})\s*$", re.I)
_LEADER_DOTS = re.compile(r"\.{3,}|(?:\. ){3,}")


def contents_entries(lines: list[str]) -> list[tuple[str, str]]:
    """(title, printed page) of each line of a contents page: "Title ..... 12". A line whose words end in a number
    without a leader counts only when the title has two words or more."""
    out = []
    for line in lines:
        s = line.strip()
        m = _LEADER.match(s)
        if not m:
            continue
        title = _LEADER_DOTS.sub(" ", m["title"]).strip(" .")
        if len(title) < 3 or not re.search(r"[A-Za-z]", title):
            continue
        if not _LEADER_DOTS.search(s) and len(title.split()) < 2:
            continue
        out.append((title, m["page"]))
    return out


def is_contents_page(lines: list[str]) -> bool:
    """A page most of whose lines are entries ("Title ..... 12"), five or more of them, or one that is headed "contents"
    and has three."""
    entries = contents_entries(lines)
    head = " ".join(lines[:4]).casefold()
    if "contents" in head and len(entries) >= 3:
        return True
    return len(entries) >= 5 and len(entries) >= 0.5 * max(1, len(lines))
